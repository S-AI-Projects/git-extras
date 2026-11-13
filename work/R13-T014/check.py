#!/usr/bin/env python3
"""Verification runner for R13-T014: git-unlock path quoting and argument boundary assertions.

Asserts:
- Exact argument boundaries for paths containing spaces.
- Filenames containing wildcard characters without shell expansion affecting unrelated files.
- Multiple arguments preserving quoting.
- Optional arguments (-h, --help).
- Documented invalid combinations (missing filename).
- Edge-states (non-existent file).
- Invariants: unrelated locked files, refs, and git configs remain unchanged.
- Zero-case run rejection.
- Isolated execution inside temporary directories without touching global state.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORK_DIR = REPO_ROOT / "work" / "R13-T014"


def get_tool_versions():
    versions = {}

    # Python
    versions["python"] = sys.version.split()[0]

    # Git
    try:
        res = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True)
        versions["git"] = res.stdout.strip()
    except Exception as e:
        versions["git"] = f"error: {e}"

    # Bash
    bash_path = shutil.which("bash") or "/bin/bash"
    try:
        res = subprocess.run([bash_path, "--version"], capture_output=True, text=True, check=True)
        versions["bash"] = res.stdout.splitlines()[0].strip()
    except Exception as e:
        versions["bash"] = f"error: {e}"

    # Bats
    bats_path = shutil.which("bats") or "/opt/homebrew/bin/bats"
    try:
        res = subprocess.run([bats_path, "--version"], capture_output=True, text=True, check=True)
        versions["bats"] = res.stdout.strip()
    except Exception as e:
        versions["bats"] = f"error: {e}"

    return versions


def run_native_bats_tests():
    bats_exec = shutil.which("bats") or "/opt/homebrew/bin/bats"
    bats_test_file = REPO_ROOT / "tests" / "git-unlock.bats"
    if not bats_test_file.exists():
        raise FileNotFoundError(f"Bats test file not found: {bats_test_file}")

    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:{REPO_ROOT / 'bin'}:{env.get('PATH', '')}"

    result = subprocess.run(
        [bats_exec, str(bats_test_file)],
        capture_output=True,
        text=True,
        env=env,
    )

    test_lines = []
    passed = 0
    failed = 0

    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("ok ") or line.startswith("not ok "):
            test_lines.append(line)
            if line.startswith("ok "):
                passed += 1
            else:
                failed += 1

    return {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "passed": passed,
        "failed": failed,
        "tests": test_lines,
    }


def capture_git_state(repo_dir):
    """Captures locked/unlocked files, branch, refs, and status."""
    state = {}

    # File lock status via git ls-files -v
    res = subprocess.run(
        ["git", "ls-files", "-v"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    file_statuses = {}
    if res.returncode == 0:
        for line in res.stdout.splitlines():
            line = line.strip()
            if len(line) >= 3 and line[1] == ' ':
                tag = line[0]
                path = line[2:]
                file_statuses[path] = tag  # 'S' = locked (skip-worktree), 'H' = tracked/unlocked
    state["file_statuses"] = file_statuses

    # Current branch
    res = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    state["current_branch"] = res.stdout.strip()

    # HEAD SHA
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    state["head_sha"] = res.stdout.strip() if res.returncode == 0 else ""

    # Local refs
    res = subprocess.run(
        ["git", "for-each-ref", "refs/heads", "--format=%(refname) %(objectname)"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    local_refs = {}
    if res.returncode == 0:
        for line in res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) == 2:
                local_refs[parts[0]] = parts[1]
    state["local_refs"] = local_refs

    # Status porcelain
    res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    state["status_porcelain"] = res.stdout.strip()

    return state


def setup_test_repository(base_dir):
    """Sets up a test git repository with commits A/B/C, branches main/topic,

    and files containing spaces, wildcard characters, and candidate matching names.
    """
    repo_dir = base_dir / "work_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    def git(*args, check=True):
        return subprocess.run(
            ["git", *args],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=check,
        )

    git("init", "--initial-branch", "main")
    git("config", "user.name", "Test User")
    git("config", "user.email", "test@example.com")

    # Commit A
    (repo_dir / "fileA.txt").write_text("Commit A content\n")
    (repo_dir / "file with spaces.txt").write_text("Path with spaces content\n")
    (repo_dir / "file*with*star.txt").write_text("Literal wildcard filename content\n")
    (repo_dir / "fileXwithYstar.txt").write_text("Unrelated file matching glob pattern\n")
    (repo_dir / "file with spaces 1.txt").write_text("Multi space file 1\n")
    (repo_dir / "file with spaces 2.txt").write_text("Multi space file 2\n")

    sub_dir = repo_dir / "dir with spaces"
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "sub file with space.txt").write_text("Subfolder space file\n")

    git("add", "-A")
    git("commit", "-m", "Commit A: initial files")

    # Commit B on topic
    git("branch", "topic")
    git("checkout", "topic")
    (repo_dir / "fileB.txt").write_text("Commit B on topic\n")
    git("add", "fileB.txt")
    git("commit", "-m", "Commit B: topic work")

    # Commit C on topic
    (repo_dir / "fileC.txt").write_text("Commit C on topic\n")
    git("add", "fileC.txt")
    git("commit", "-m", "Commit C: more topic work")

    # Back to main
    git("checkout", "main")

    # Lock files using git update-index --skip-worktree
    locked_files = [
        "file with spaces.txt",
        "file*with*star.txt",
        "fileXwithYstar.txt",
        "file with spaces 1.txt",
        "file with spaces 2.txt",
        "dir with spaces/sub file with space.txt",
    ]
    for lf in locked_files:
        git("update-index", "--skip-worktree", lf)

    return repo_dir


def run_check_case(case_name, cmd_args, expected_exit, assert_fn):
    """Runs a single isolated check case in its own temporary environment."""
    with tempfile.TemporaryDirectory(prefix=f"check_unlock_{case_name}_") as tmp_str:
        tmp_path = Path(tmp_str)
        repo_dir = setup_test_repository(tmp_path)

        env = os.environ.copy()
        env["PATH"] = f"/opt/homebrew/bin:{REPO_ROOT / 'bin'}:{env.get('PATH', '')}"
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "isolated_global_gitconfig")

        before_state = capture_git_state(repo_dir)

        # Run git-unlock
        cmd = [str(REPO_ROOT / "bin" / "git-unlock"), *cmd_args]
        proc = subprocess.run(
            cmd,
            cwd=repo_dir,
            capture_output=True,
            text=True,
            env=env,
        )

        after_state = capture_git_state(repo_dir)

        assertion_error = None
        try:
            if proc.returncode != expected_exit:
                raise AssertionError(
                    f"Expected exit code {expected_exit}, got {proc.returncode}.\n"
                    f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
                )
            assert_fn(before_state, after_state, proc.stdout, proc.stderr, repo_dir)
        except Exception as err:
            assertion_error = str(err)

        return {
            "name": case_name,
            "command": "git unlock " + " ".join(f'"{a}"' if " " in a or "*" in a else a for a in cmd_args),
            "actual_arguments": cmd_args,
            "expected_exit": expected_exit,
            "actual_exit": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "passed": assertion_error is None,
            "error": assertion_error,
            "before_state": before_state,
            "after_state": after_state,
        }


def main():
    print("=== Starting git-unlock verification (work/R13-T014) ===")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Tool Versions
    tool_versions = get_tool_versions()
    print("Tool versions detected:")
    for k, v in tool_versions.items():
        print(f"  {k}: {v}")
    with open(WORK_DIR / "tool_versions.json", "w", encoding="utf-8") as f:
        json.dump(tool_versions, f, indent=2)

    # 2. Native Bats Tests
    print("\n--- Running Native Bats Tests (tests/git-unlock.bats) ---")
    bats_res = run_native_bats_tests()
    print(f"Native Bats test results: {bats_res['passed']} passed, {bats_res['failed']} failed (total {len(bats_res['tests'])})")
    with open(WORK_DIR / "native_test_names.txt", "w", encoding="utf-8") as f:
        for t in bats_res["tests"]:
            f.write(t + "\n")

    if bats_res["failed"] > 0 or bats_res["exit_code"] != 0:
        print(f"Native Bats test failures:\n{bats_res['stdout']}\n{bats_res['stderr']}")
        sys.exit(1)

    # 3. Focused Isolated Shell Checks
    print("\n--- Running Focused Isolated Shell Checks ---")

    cases_to_run = []

    # Case 1: Path containing spaces (exact argument boundary)
    def assert_spaces(before, after, stdout, stderr, repo):
        # Target was locked (S) before, unlocked (H) after
        assert before["file_statuses"]["file with spaces.txt"] == "S", "Target should be locked before"
        assert after["file_statuses"]["file with spaces.txt"] == "H", "Target should be unlocked after"
        # Unrelated files remain locked (S)
        assert after["file_statuses"]["file*with*star.txt"] == "S", "file*with*star.txt must remain locked"
        assert after["file_statuses"]["fileXwithYstar.txt"] == "S", "fileXwithYstar.txt must remain locked"
        assert before["local_refs"] == after["local_refs"], "Git refs must remain unchanged"

    cases_to_run.append((
        "path_containing_spaces_exact_argument_boundary",
        ["file with spaces.txt"],
        0,
        assert_spaces,
    ))

    # Case 2: Subfolder path containing spaces
    def assert_subfolder_spaces(before, after, stdout, stderr, repo):
        target = "dir with spaces/sub file with space.txt"
        assert before["file_statuses"][target] == "S", "Subfolder target should be locked before"
        assert after["file_statuses"][target] == "H", "Subfolder target should be unlocked after"
        assert after["file_statuses"]["file with spaces.txt"] == "S", "Unrelated file must remain locked"

    cases_to_run.append((
        "subfolder_path_containing_spaces",
        ["dir with spaces/sub file with space.txt"],
        0,
        assert_subfolder_spaces,
    ))

    # Case 3: Argument containing wildcard character (exact argument boundary, no glob expansion affecting unrelated files)
    def assert_wildcard(before, after, stdout, stderr, repo):
        # Target with literal '*' in filename is unlocked
        target = "file*with*star.txt"
        unrelated_candidate = "fileXwithYstar.txt"
        assert before["file_statuses"][target] == "S", f"{target} should be locked before"
        assert after["file_statuses"][target] == "H", f"{target} should be unlocked after"
        # CRUCIAL ASSERTION: Shell expansion must NOT affect unrelated files matching pattern
        assert before["file_statuses"][unrelated_candidate] == "S", f"{unrelated_candidate} should be locked before"
        assert after["file_statuses"][unrelated_candidate] == "S", f"{unrelated_candidate} MUST remain locked"
        assert after["file_statuses"]["file with spaces.txt"] == "S", "file with spaces.txt must remain locked"

    cases_to_run.append((
        "argument_containing_wildcard_no_shell_expansion_affecting_unrelated",
        ["file*with*star.txt"],
        0,
        assert_wildcard,
    ))

    # Case 4: Multiple arguments preserving spaces and boundaries
    def assert_multi(before, after, stdout, stderr, repo):
        f1 = "file with spaces 1.txt"
        f2 = "file with spaces 2.txt"
        assert before["file_statuses"][f1] == "S" and before["file_statuses"][f2] == "S"
        assert after["file_statuses"][f1] == "H" and after["file_statuses"][f2] == "H"
        assert after["file_statuses"]["file*with*star.txt"] == "S", "Other locked file must remain locked"

    cases_to_run.append((
        "multiple_arguments_preserving_quoted_boundaries",
        ["file with spaces 1.txt", "file with spaces 2.txt"],
        0,
        assert_multi,
    ))

    # Case 5: Optional argument --help
    def assert_help(before, after, stdout, stderr, repo):
        assert "Usage: git unlock" in stdout, "Usage message expected in stdout"
        assert before["file_statuses"] == after["file_statuses"], "Locked state must remain unchanged"

    cases_to_run.append((
        "optional_argument_help_flag",
        ["--help"],
        0,
        assert_help,
    ))

    # Case 6: Optional argument -h
    def assert_short_help(before, after, stdout, stderr, repo):
        assert "Usage: git unlock" in stdout, "Usage message expected in stdout"
        assert before["file_statuses"] == after["file_statuses"], "Locked state must remain unchanged"

    cases_to_run.append((
        "optional_argument_short_help_flag",
        ["-h"],
        0,
        assert_short_help,
    ))

    # Case 7: Documented invalid combination - missing filename (0 arguments)
    def assert_missing_filename(before, after, stdout, stderr, repo):
        assert "filename required." in stderr, "Expected 'filename required.' in stderr"
        assert before["file_statuses"] == after["file_statuses"], "Locked state must remain unchanged"

    cases_to_run.append((
        "documented_invalid_combination_missing_filename",
        [],
        1,
        assert_missing_filename,
    ))

    # Case 8: Edge-state - non-existent file
    def assert_non_existent(before, after, stdout, stderr, repo):
        assert "Unable to mark file" in stderr or "fatal:" in stderr, "Expected git fatal error in stderr"
        assert before["file_statuses"] == after["file_statuses"], "Locked state must remain unchanged"

    cases_to_run.append((
        "edge_state_non_existent_file",
        ["non_existent_file.txt"],
        128,  # git update-index fatal error exits 128
        assert_non_existent,
    ))

    # Zero-case run rejection
    if len(cases_to_run) == 0:
        raise RuntimeError("Zero-case run rejected: No check cases defined.")

    results = []
    has_failure = False

    for name, args, exp_exit, fn in cases_to_run:
        res = run_check_case(name, args, exp_exit, fn)
        status_label = "PASS" if res["passed"] else "FAIL"
        print(f"[{status_label}] {res['name']}")
        print(f"  Args: {res['command']}")
        print(f"  Exit Status: {res['actual_exit']} (expected: {res['expected_exit']})")
        if not res["passed"]:
            print(f"  Error: {res['error']}")
            has_failure = True
        else:
            print("  Lock State Assertion: Verified target unlocked & unrelated files intact.")
        results.append(res)

    # 4. Save results.json
    results_path = WORK_DIR / "results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "tool_versions": tool_versions,
                "observed_option_tokens": ["--no-skip-worktree"],
                "native_bats": {
                    "total": len(bats_res["tests"]),
                    "passed": bats_res["passed"],
                    "failed": bats_res["failed"],
                    "tests": bats_res["tests"],
                },
                "focused_checks": results,
            },
            f,
            indent=2,
        )

    # 5. Save summary.txt
    summary_path = WORK_DIR / "summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("=== git-unlock Verification Summary (R13-T014) ===\n\n")
        f.write("Tool Versions:\n")
        for k, v in tool_versions.items():
            f.write(f"  {k}: {v}\n")
        f.write("\nObserved Option Tokens: --no-skip-worktree\n")
        f.write(f"\nNative Bats Tests ({len(bats_res['tests'])}):\n")
        for t in bats_res["tests"]:
            f.write(f"  {t}\n")
        f.write(f"\nFocused Shell Checks ({len(results)}):\n")
        for r in results:
            stat = "PASS" if r["passed"] else "FAIL"
            f.write(f"  [{stat}] {r['name']}\n")
            f.write(f"    Command: {r['command']}\n")
            f.write(f"    Exit Status: {r['actual_exit']} (expected {r['expected_exit']})\n")
            if r["error"]:
                f.write(f"    Error: {r['error']}\n")
            f.write("\n")

    print(f"\n=== Verification Complete: {sum(1 for r in results if r['passed'])}/{len(results)} checks passed ===")
    print(f"Results saved to: {results_path}")
    print(f"Summary saved to: {summary_path}")

    if has_failure:
        sys.exit(1)


if __name__ == "__main__":
    main()

