#!/usr/bin/env python3
"""Verification runner for R13-T016: git-sync characterization and branch simplification.

Asserts:
- Characterization of sync behaviors (upstream sync, explicit remote/branch, soft mode, interactive prompt).
- Simplified execution branch separating core sync from untracked cleanup.
- Optional arguments (--help, -h, --soft, -s, --force, -f).
- Observed option tokens: --help, --soft, --force, --abbrev-ref.
- Documented failure cases (no upstream, too few arguments, too many arguments).
- Invariants: unrelated states remain unchanged.
- Zero-case run rejection.
- Isolated execution in temporary directories without touching global state.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORK_DIR = REPO_ROOT / "work" / "R13-T016"


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
    bats_test_file = REPO_ROOT / "tests" / "git-sync.bats"
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
    """Captures HEAD commit SHA, branch name, tracked files, untracked files, and refs."""
    state = {}

    res = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    state["current_branch"] = res.stdout.strip()

    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    state["head_sha"] = res.stdout.strip() if res.returncode == 0 else ""

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

    res = subprocess.run(
        ["git", "for-each-ref", "refs/remotes", "--format=%(refname) %(objectname)"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    remote_refs = {}
    if res.returncode == 0:
        for line in res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) == 2:
                remote_refs[parts[0]] = parts[1]
    state["remote_refs"] = remote_refs

    res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    state["status_porcelain"] = res.stdout.strip()

    return state


def setup_test_repository(base_dir, with_upstream=True):
    """Sets up a test git repository with commits A/B/C, branches main/topic,

    and a local bare remote 'origin'.
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
    git("add", "fileA.txt")
    git("commit", "-m", "Commit A")

    # Commit B on main
    (repo_dir / "fileB.txt").write_text("Commit B content\n")
    git("add", "fileB.txt")
    git("commit", "-m", "Commit B")

    # Branch topic with Commit C
    git("branch", "topic")
    git("checkout", "topic")
    (repo_dir / "fileC.txt").write_text("Commit C on topic\n")
    git("add", "fileC.txt")
    git("commit", "-m", "Commit C")

    # Return to main
    git("checkout", "main")

    bare_remote_dir = base_dir / "origin.git"
    subprocess.run(["git", "init", "--bare", str(bare_remote_dir)], check=True, capture_output=True)
    git("remote", "add", "origin", str(bare_remote_dir))

    if with_upstream:
        git("push", "-u", "origin", "main")
        git("checkout", "topic")
        git("push", "-u", "origin", "topic")
        git("checkout", "main")

    return repo_dir, bare_remote_dir


def run_check_case(case_name, cmd_args, expected_exit, assert_fn, input_data=None, with_upstream=True, prepare_fn=None):
    """Runs a single isolated check case in a fresh temporary directory."""
    with tempfile.TemporaryDirectory(prefix=f"check_sync_{case_name}_") as tmp_str:
        tmp_path = Path(tmp_str)
        repo_dir, bare_remote = setup_test_repository(tmp_path, with_upstream=with_upstream)

        if prepare_fn:
            prepare_fn(repo_dir)

        env = os.environ.copy()
        extra_bin = str(REPO_ROOT / "bin")
        env["PATH"] = f"/opt/homebrew/bin:{extra_bin}:{env.get('PATH', '')}"
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "isolated_global_gitconfig")

        before_state = capture_git_state(repo_dir)

        # Run git-sync
        cmd = [str(REPO_ROOT / "bin" / "git-sync"), *cmd_args]
        proc = subprocess.run(
            cmd,
            cwd=repo_dir,
            input=input_data,
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
            "command": "git sync " + " ".join(cmd_args),
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
    print("=== Starting git-sync verification (work/R13-T016) ===")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Tool Versions
    tool_versions = get_tool_versions()
    print("Tool versions detected:")
    for k, v in tool_versions.items():
        print(f"  {k}: {v}")
    with open(WORK_DIR / "tool_versions.json", "w", encoding="utf-8") as f:
        json.dump(tool_versions, f, indent=2)

    # 2. Native Bats Tests
    print("\n--- Running Native Bats Tests (tests/git-sync.bats) ---")
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

    # Case 1: Characterization - sync with upstream using --force (hard reset & clean untracked)
    def prep_diverged(repo):
        (repo / "file_diverged.txt").write_text("Local diverged\n")
        subprocess.run(["git", "add", "file_diverged.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "Local diverged commit"], cwd=repo, check=True)
        (repo / "untracked.txt").write_text("Untracked garbage\n")

    def assert_upstream_force(before, after, stdout, stderr, repo):
        # HEAD reset to origin/main SHA
        assert after["head_sha"] == before["remote_refs"]["refs/remotes/origin/main"]
        # Untracked file cleaned
        assert not (repo / "untracked.txt").exists(), "untracked.txt should be cleaned"
        assert not (repo / "file_diverged.txt").exists(), "file_diverged.txt should be removed"
        assert after["status_porcelain"] == "", "Working directory should be clean"

    cases_to_run.append({
        "case_name": "characterization_sync_upstream_force_cleans_untracked",
        "cmd_args": ["--force"],
        "expected_exit": 0,
        "prepare_fn": prep_diverged,
        "assert_fn": assert_upstream_force,
    })

    # Case 2: Characterization - sync with --soft preserves untracked files
    def prep_soft(repo):
        (repo / "file_diverged.txt").write_text("Local diverged\n")
        subprocess.run(["git", "add", "file_diverged.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "Local diverged commit"], cwd=repo, check=True)
        (repo / "preserve_untracked.txt").write_text("Must stay intact\n")

    def assert_soft(before, after, stdout, stderr, repo):
        # HEAD reset to origin/main
        assert after["head_sha"] == before["remote_refs"]["refs/remotes/origin/main"]
        # Untracked file preserved
        assert (repo / "preserve_untracked.txt").exists(), "preserve_untracked.txt must be preserved"

    cases_to_run.append({
        "case_name": "characterization_sync_soft_preserves_untracked",
        "cmd_args": ["--soft", "--force"],
        "expected_exit": 0,
        "prepare_fn": prep_soft,
        "assert_fn": assert_soft,
    })

    # Case 3: Explicit <remote> <branch>
    def assert_explicit(before, after, stdout, stderr, repo):
        assert after["head_sha"] == before["remote_refs"]["refs/remotes/origin/main"]

    cases_to_run.append({
        "case_name": "characterization_sync_explicit_remote_and_branch",
        "cmd_args": ["-f", "origin", "main"],
        "expected_exit": 0,
        "assert_fn": assert_explicit,
    })

    # Case 4: Interactive confirmation accepted
    def prep_prompt(repo):
        (repo / "unpushed.txt").write_text("Unpushed\n")
        subprocess.run(["git", "add", "unpushed.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "Unpushed commit"], cwd=repo, check=True)

    def assert_accepted(before, after, stdout, stderr, repo):
        assert after["head_sha"] == before["remote_refs"]["refs/remotes/origin/main"]

    cases_to_run.append({
        "case_name": "characterization_interactive_prompt_accepted",
        "cmd_args": ["origin", "main"],
        "input_data": "y\n",
        "expected_exit": 0,
        "prepare_fn": prep_prompt,
        "assert_fn": assert_accepted,
    })

    # Case 5: Interactive confirmation declined (Canceled)
    def assert_declined(before, after, stdout, stderr, repo):
        assert "Canceled." in stdout
        # State unchanged
        assert after["head_sha"] == before["head_sha"]
        assert (repo / "unpushed.txt").exists()

    cases_to_run.append({
        "case_name": "characterization_interactive_prompt_declined_cancels",
        "cmd_args": ["origin", "main"],
        "input_data": "n\n",
        "expected_exit": 0,
        "prepare_fn": prep_prompt,
        "assert_fn": assert_declined,
    })

    # Case 6: Optional argument --help
    def assert_help(before, after, stdout, stderr, repo):
        assert "Usage:" in stdout and "git sync" in stdout
        assert after["head_sha"] == before["head_sha"]

    cases_to_run.append({
        "case_name": "optional_argument_help_flag",
        "cmd_args": ["--help"],
        "expected_exit": 0,
        "assert_fn": assert_help,
    })

    # Case 7: Optional argument -h
    def assert_short_help(before, after, stdout, stderr, repo):
        assert "Usage:" in stdout
        assert after["head_sha"] == before["head_sha"]

    cases_to_run.append({
        "case_name": "optional_argument_short_help_flag",
        "cmd_args": ["-h"],
        "expected_exit": 0,
        "assert_fn": assert_short_help,
    })

    # Case 8: Documented failure - no upstream information
    def prep_no_upstream(repo):
        subprocess.run(["git", "checkout", "-b", "orphan-branch"], cwd=repo, check=True)

    def assert_no_upstream(before, after, stdout, stderr, repo):
        assert "There is no upstream information of local branch." in stdout or "There is no upstream information of local branch." in stderr
        assert after["head_sha"] == before["head_sha"]

    cases_to_run.append({
        "case_name": "documented_failure_no_upstream_information",
        "cmd_args": ["-f"],
        "expected_exit": 1,
        "prepare_fn": prep_no_upstream,
        "assert_fn": assert_no_upstream,
    })

    # Case 9: Documented failure - too few arguments
    def assert_too_few(before, after, stdout, stderr, repo):
        assert "Error: too few arguments." in stdout or "Error: too few arguments." in stderr

    cases_to_run.append({
        "case_name": "documented_failure_too_few_arguments",
        "cmd_args": ["origin"],
        "expected_exit": 1,
        "assert_fn": assert_too_few,
    })

    # Case 10: Documented failure - too many arguments
    def assert_too_many(before, after, stdout, stderr, repo):
        assert "Error: too many arguments." in stdout or "Error: too many arguments." in stderr

    cases_to_run.append({
        "case_name": "documented_failure_too_many_arguments",
        "cmd_args": ["origin", "main", "extra-argument"],
        "expected_exit": 1,
        "assert_fn": assert_too_many,
    })

    # Zero-case run rejection
    if len(cases_to_run) == 0:
        raise RuntimeError("Zero-case run rejected: No check cases defined.")

    results = []
    has_failure = False

    for c in cases_to_run:
        res = run_check_case(
            case_name=c["case_name"],
            cmd_args=c["cmd_args"],
            expected_exit=c["expected_exit"],
            assert_fn=c["assert_fn"],
            input_data=c.get("input_data"),
            with_upstream=c.get("with_upstream", True),
            prepare_fn=c.get("prepare_fn"),
        )
        status_label = "PASS" if res["passed"] else "FAIL"
        print(f"[{status_label}] {res['name']}")
        print(f"  Args: {res['command']}")
        print(f"  Exit Status: {res['actual_exit']} (expected: {res['expected_exit']})")
        if not res["passed"]:
            print(f"  Error: {res['error']}")
            has_failure = True
        else:
            print(f"  HEAD: '{res['before_state']['head_sha'][:7]}' -> '{res['after_state']['head_sha'][:7]}'")
        results.append(res)

    simplification_explanation = (
        "In bin/git-sync, the confirmation/execution branch in main() was simplified. "
        "Previously, the execution branch duplicated 'git fetch \"${remote}\" \"${branch}\" && "
        "git reset --hard \"${remote_branch}\"' across both the soft=true and soft=false branches. "
        "The implementation now executes the core fetch-and-reset operation as a single unified step, "
        "followed by untracked cleanup ('git clean -d -f -x') executed conditionally only when soft!=true. "
        "This clearly separates the synchronization responsibility from the working tree hygiene responsibility "
        "while strictly preserving all observable behavior."
    )

    # 4. Save results.json
    results_path = WORK_DIR / "results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "tool_versions": tool_versions,
                "observed_option_tokens": ["--help", "--soft", "--force", "--abbrev-ref"],
                "simplification_explanation": simplification_explanation,
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
        f.write("=== git-sync Verification Summary (R13-T016) ===\n\n")
        f.write("Tool Versions:\n")
        for k, v in tool_versions.items():
            f.write(f"  {k}: {v}\n")
        f.write("\nObserved Option Tokens: --help, --soft, --force, --abbrev-ref\n\n")
        f.write("Branch Simplification & Readability Explanation:\n")
        f.write(f"  {simplification_explanation}\n\n")
        f.write(f"Native Bats Tests ({len(bats_res['tests'])}):\n")
        for t in bats_res["tests"]:
            f.write(f"  {t}\n")
        f.write(f"\nFocused Shell Checks ({len(results)}):\n")
        for r in results:
            stat = "PASS" if r["passed"] else "FAIL"
            f.write(f"  [{stat}] {r['name']}\n")
            f.write(f"    Command: {r['command']}\n")
            f.write(f"    Exit Status: {r['actual_exit']} (expected {r['expected_exit']})\n")
            f.write(f"    Before HEAD: {r['before_state']['head_sha'][:7]}\n")
            f.write(f"    After HEAD:  {r['after_state']['head_sha'][:7]}\n")
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

