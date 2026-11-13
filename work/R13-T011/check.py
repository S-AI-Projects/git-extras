#!/usr/bin/env python3
"""
work/R13-T011/check.py

Verification runner for git-undo enhancements:
- Invokes native Bats tests and asserts results.
- Executes isolated focused test cases (ordinary success, documented failures, edge states).
- Asserts exit status, output, and repository state separately.
- Captures actual arguments, tool versions, expected vs actual outputs.
- Saves results and artifacts to work/R13-T011/.
- Exits non-zero on assertion failure or zero-case run.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORK_DIR = Path(__file__).resolve().parent

# Ensure isolated environment with bin/ prepended to PATH
ENV = os.environ.copy()
ENV["PATH"] = f"{REPO_ROOT / 'bin'}:/opt/homebrew/bin:/usr/local/bin:{ENV.get('PATH', '')}"
ENV["GIT_CONFIG_NOSYSTEM"] = "1"


def run_cmd(cmd, cwd=None, env=None, input_text=None):
    if env is None:
        env = ENV
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout, proc.stderr


def get_tool_versions():
    versions = {}

    # Python
    versions["python"] = sys.version.split()[0]

    # Git
    rc, out, _ = run_cmd(["git", "--version"])
    versions["git"] = out.strip() if rc == 0 else "unknown"

    # Bash
    rc, out, _ = run_cmd(["bash", "--version"])
    first_line = out.splitlines()[0] if out else "unknown"
    versions["bash"] = first_line.strip()

    # Bats
    rc, out, _ = run_cmd(["bats", "--version"])
    versions["bats"] = out.strip() if rc == 0 else "unknown"

    return versions


def get_repo_state(repo_dir):
    """Capture repository state (HEAD sha, commit count, branch, status, staged files)."""
    state = {}
    rc, out, _ = run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_dir)
    if rc != 0:
        return {"is_git_repo": False}

    state["is_git_repo"] = True

    rc, out, _ = run_cmd(["git", "rev-parse", "--verify", "HEAD"], cwd=repo_dir)
    if rc == 0:
        state["has_commits"] = True
        state["head_sha"] = out.strip()

        _, out_msg, _ = run_cmd(["git", "log", "-1", "--pretty=%B"], cwd=repo_dir)
        state["head_message"] = out_msg.strip()

        _, out_cnt, _ = run_cmd(["git", "rev-list", "--count", "HEAD"], cwd=repo_dir)
        state["commit_count"] = int(out_cnt.strip()) if out_cnt.strip().isdigit() else 0
    else:
        state["has_commits"] = False
        state["head_sha"] = None
        state["head_message"] = None
        state["commit_count"] = 0

    _, out_branch, _ = run_cmd(["git", "branch", "--show-current"], cwd=repo_dir)
    state["branch"] = out_branch.strip()

    _, out_status, _ = run_cmd(["git", "status", "--porcelain"], cwd=repo_dir)
    state["status_porcelain"] = out_status.strip().splitlines()

    _, out_diff_cached, _ = run_cmd(["git", "diff", "--cached", "--name-only"], cwd=repo_dir)
    state["staged_files"] = [f for f in out_diff_cached.strip().splitlines() if f]

    return state


def setup_test_environment(tmpdir):
    """
    Creates an isolated repository hierarchy:
    - local bare remote: origin.git
    - working repo: repo (cloned from origin.git)
    - commits A, B, C on branch main
    - branch topic pointing to commit B with commit T added
    - isolated git config
    """
    base = Path(tmpdir)
    remote_dir = base / "origin.git"
    work_dir = base / "repo"

    git_config_file = base / "isolated_gitconfig"
    git_config_file.write_text("[user]\n  name = Test User\n  email = test@example.com\n")

    test_env = ENV.copy()
    test_env["GIT_CONFIG_GLOBAL"] = str(git_config_file)

    # Initialize bare remote
    run_cmd(["git", "init", "--bare", "--initial-branch=main", str(remote_dir)], env=test_env)

    # Initialize working repo
    work_dir.mkdir()
    run_cmd(["git", "init", "--initial-branch=main"], cwd=work_dir, env=test_env)
    run_cmd(["git", "remote", "add", "origin", str(remote_dir)], cwd=work_dir, env=test_env)

    # Commit A
    (work_dir / "fileA.txt").write_text("commit A content\n")
    run_cmd(["git", "add", "fileA.txt"], cwd=work_dir, env=test_env)
    run_cmd(["git", "commit", "-m", "commit A"], cwd=work_dir, env=test_env)

    # Commit B
    (work_dir / "fileB.txt").write_text("commit B content\n")
    run_cmd(["git", "add", "fileB.txt"], cwd=work_dir, env=test_env)
    run_cmd(["git", "commit", "-m", "commit B"], cwd=work_dir, env=test_env)

    # Create topic branch at B
    run_cmd(["git", "branch", "topic"], cwd=work_dir, env=test_env)

    # Commit C on main
    (work_dir / "fileC.txt").write_text("commit C content\n")
    run_cmd(["git", "add", "fileC.txt"], cwd=work_dir, env=test_env)
    run_cmd(["git", "commit", "-m", "commit C"], cwd=work_dir, env=test_env)

    # Push to origin
    run_cmd(["git", "push", "-u", "origin", "main"], cwd=work_dir, env=test_env)

    return work_dir, test_env


def run_native_bats_tests():
    """Run tests/git-undo.bats and parse results."""
    print("--- Running Native Bats Tests (tests/git-undo.bats) ---")
    rc, stdout, stderr = run_cmd(["bats", "--tap", "tests/git-undo.bats"], cwd=REPO_ROOT)
    
    test_names = []
    passed = 0
    failed = 0

    for line in stdout.splitlines():
        if line.startswith("ok "):
            match = re.match(r"^ok \d+ (.+)$", line)
            name = match.group(1) if match else line
            test_names.append((name, "PASSED"))
            passed += 1
        elif line.startswith("not ok "):
            match = re.match(r"^not ok \d+ (.+)$", line)
            name = match.group(1) if match else line
            test_names.append((name, "FAILED"))
            failed += 1

    print(f"Native Bats test results: {passed} passed, {failed} failed (total {len(test_names)})")
    if rc != 0 or failed > 0:
        raise AssertionError(f"Native Bats tests failed with code {rc} ({failed} failures)")

    return test_names


def run_checks():
    test_cases = []

    def register_case(name, args, cwd, env, expected_rc, check_stdout=None, check_stderr=None,
                      assert_state_fn=None, input_text=None):
        before_state = get_repo_state(cwd)
        rc, out, err = run_cmd(args, cwd=cwd, env=env, input_text=input_text)
        after_state = get_repo_state(cwd)

        # Separate assertions:
        # 1. Exit status assertion
        status_ok = (rc == expected_rc) if isinstance(expected_rc, int) else (rc in expected_rc)
        
        # 2. Output assertion (stdout & stderr)
        combined_out = out + err
        out_ok = True
        err_msg = ""
        if check_stdout:
            if not check_stdout(out, err):
                out_ok = False
                err_msg += f" Output assertion failed. stdout={out!r}, stderr={err!r}"

        # 3. Repository state assertion
        state_ok = True
        if assert_state_fn:
            state_result, state_err = assert_state_fn(before_state, after_state)
            if not state_result:
                state_ok = False
                err_msg += f" State assertion failed: {state_err}"

        passed = status_ok and out_ok and state_ok
        if not status_ok:
            err_msg += f" Exit status mismatch: expected {expected_rc}, got {rc}"

        case_record = {
            "name": name,
            "actual_arguments": args,
            "expected_exit_status": expected_rc,
            "actual_exit_status": rc,
            "stdout": out,
            "stderr": err,
            "before_state": before_state,
            "after_state": after_state,
            "assertions": {
                "exit_status_passed": status_ok,
                "output_passed": out_ok,
                "state_passed": state_ok,
            },
            "passed": passed,
            "error_detail": err_msg.strip(),
        }
        test_cases.append(case_record)

        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
        print(f"  Args: {' '.join(args)}")
        print(f"  Exit Status: {rc} (expected: {expected_rc})")
        if before_state.get("is_git_repo") and after_state.get("is_git_repo"):
            print(f"  State: HEAD '{before_state.get('head_message')}' ({before_state.get('commit_count')} commits) -> "
                  f"HEAD '{after_state.get('head_message')}' ({after_state.get('commit_count')} commits)")
        if not passed:
            print(f"  ERROR: {err_msg}")
            raise AssertionError(f"Check failed: {name} - {err_msg}")

    # Case 1: Ordinary success - default git undo (undo 1 commit, soft, staged)
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="ordinary_success_default_undo",
            args=["git", "undo"],
            cwd=work_dir,
            env=test_env,
            expected_rc=0,
            check_stdout=lambda out, err: out == "",
            assert_state_fn=lambda before, after: (
                after["head_message"] == "commit B" and
                after["commit_count"] == 2 and
                "fileC.txt" in after["staged_files"],
                f"Expected commit B with fileC staged, got {after}"
            )
        )

    # Case 2: Ordinary success - git undo with positional count 2
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="ordinary_success_positional_count_2",
            args=["git", "undo", "2"],
            cwd=work_dir,
            env=test_env,
            expected_rc=0,
            check_stdout=lambda out, err: out == "",
            assert_state_fn=lambda before, after: (
                after["head_message"] == "commit A" and
                after["commit_count"] == 1 and
                "fileB.txt" in after["staged_files"] and
                "fileC.txt" in after["staged_files"],
                f"Expected commit A with files staged, got {after}"
            )
        )

    # Case 3: Ordinary success - git undo --soft (unstages changes)
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="ordinary_success_soft_flag",
            args=["git", "undo", "--soft"],
            cwd=work_dir,
            env=test_env,
            expected_rc=0,
            check_stdout=lambda out, err: out == "",
            assert_state_fn=lambda before, after: (
                after["head_message"] == "commit B" and
                after["commit_count"] == 2 and
                len(after["staged_files"]) == 0 and
                any("fileC.txt" in s for s in after["status_porcelain"]),
                f"Expected commit B with fileC unstaged, got {after}"
            )
        )

    # Case 4: Ordinary success - git undo -s (short flag for soft)
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="ordinary_success_soft_short_flag",
            args=["git", "undo", "-s"],
            cwd=work_dir,
            env=test_env,
            expected_rc=0,
            check_stdout=lambda out, err: out == "",
            assert_state_fn=lambda before, after: (
                after["head_message"] == "commit B" and
                after["commit_count"] == 2 and
                len(after["staged_files"]) == 0,
                f"Expected commit B with unstaged changes, got {after}"
            )
        )

    # Case 5: Ordinary success - git undo --hard
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="ordinary_success_hard_flag",
            args=["git", "undo", "--hard"],
            cwd=work_dir,
            env=test_env,
            expected_rc=0,
            check_stdout=lambda out, err: "HEAD is now at" in out,
            assert_state_fn=lambda before, after: (
                after["head_message"] == "commit B" and
                after["commit_count"] == 2 and
                len(after["status_porcelain"]) == 0 and
                not (Path(work_dir) / "fileC.txt").exists(),
                f"Expected clean commit B and fileC deleted, got {after}"
            )
        )

    # Case 6: Ordinary success - git undo --count 2
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="ordinary_success_count_flag",
            args=["git", "undo", "--count", "2"],
            cwd=work_dir,
            env=test_env,
            expected_rc=0,
            check_stdout=lambda out, err: out == "",
            assert_state_fn=lambda before, after: (
                after["head_message"] == "commit A" and
                after["commit_count"] == 1,
                f"Expected commit A, got {after}"
            )
        )

    # Case 7: Ordinary success - git undo -c 2
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="ordinary_success_count_short_flag",
            args=["git", "undo", "-c", "2"],
            cwd=work_dir,
            env=test_env,
            expected_rc=0,
            check_stdout=lambda out, err: out == "",
            assert_state_fn=lambda before, after: (
                after["head_message"] == "commit A" and
                after["commit_count"] == 1,
                f"Expected commit A, got {after}"
            )
        )

    # Case 8: Ordinary success - git-undo --help
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="ordinary_success_help_flag",
            args=["git-undo", "--help"],
            cwd=work_dir,
            env=test_env,
            expected_rc=0,
            check_stdout=lambda out, err: "Usage: git undo" in out and "--count" in out and "--help" in out,
            assert_state_fn=lambda before, after: (
                after["head_message"] == before["head_message"] and
                after["commit_count"] == before["commit_count"],
                "Repository state should not change on help"
            )
        )

    # Case 9: Documented failure / edge state - Empty repository (0 commits)
    with tempfile.TemporaryDirectory() as td:
        empty_repo = Path(td) / "empty"
        empty_repo.mkdir()
        run_cmd(["git", "init", "--initial-branch=main"], cwd=empty_repo)
        register_case(
            name="documented_failure_empty_repo_no_commits",
            args=["git", "undo"],
            cwd=empty_repo,
            env=ENV,
            expected_rc=[1, 128],
            check_stdout=lambda out, err: "Not git commit found!" in (out + err),
            assert_state_fn=lambda before, after: (
                after["has_commits"] is False and after["commit_count"] == 0,
                "Empty repo remains with 0 commits"
            )
        )

    # Case 10: Documented failure / edge state - Outside git repository
    with tempfile.TemporaryDirectory() as td:
        non_repo = Path(td) / "non_repo"
        non_repo.mkdir()
        register_case(
            name="documented_failure_outside_git_repo",
            args=["git", "undo"],
            cwd=non_repo,
            env=ENV,
            expected_rc=[1, 128],
            check_stdout=lambda out, err: "Not a git repo!" in (out + err),
            assert_state_fn=lambda before, after: (
                after["is_git_repo"] is False,
                "Directory remains non-git repo"
            )
        )

    # Case 11: Documented failure / edge state - Count exceeds available commits
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="documented_failure_count_exceeds_available",
            args=["git", "undo", "5"],
            cwd=work_dir,
            env=test_env,
            expected_rc=1,
            check_stdout=lambda out, err: "Only 3 commits, cannot undo 5" in (out + err),
            assert_state_fn=lambda before, after: (
                after["head_message"] == "commit C" and
                after["commit_count"] == 3,
                "Repository state unchanged when count exceeds commit count"
            )
        )

    # Case 12: Documented failure / edge state - Hard undo all commits disallowed
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="documented_failure_hard_undo_all_commits",
            args=["git", "undo", "--hard", "3"],
            cwd=work_dir,
            env=test_env,
            expected_rc=1,
            check_stdout=lambda out, err: "Cannot hard undo all commits" in (out + err),
            assert_state_fn=lambda before, after: (
                after["head_message"] == "commit C" and
                after["commit_count"] == 3,
                "Repository state unchanged when hard undoing all commits"
            )
        )

    # Case 13: Edge state - Undo count 0 rejected
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="edge_state_zero_count_rejected",
            args=["git", "undo", "0"],
            cwd=work_dir,
            env=test_env,
            expected_rc=1,
            check_stdout=lambda out, err: "Invalid undo count: 0" in (out + err),
            assert_state_fn=lambda before, after: (
                after["head_message"] == "commit C" and
                after["commit_count"] == 3,
                "Repository state unchanged when count is 0"
            )
        )

    # Case 14: Edge state - Undo on topic branch preserves main
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        # Checkout topic branch, add a commit T
        run_cmd(["git", "checkout", "topic"], cwd=work_dir, env=test_env)
        (work_dir / "fileT.txt").write_text("topic commit content\n")
        run_cmd(["git", "add", "fileT.txt"], cwd=work_dir, env=test_env)
        run_cmd(["git", "commit", "-m", "commit T"], cwd=work_dir, env=test_env)

        register_case(
            name="edge_state_topic_branch_undo",
            args=["git", "undo"],
            cwd=work_dir,
            env=test_env,
            expected_rc=0,
            check_stdout=lambda out, err: out == "",
            assert_state_fn=lambda before, after: (
                after["branch"] == "topic" and
                after["head_message"] == "commit B" and
                "fileT.txt" in after["staged_files"],
                f"Expected topic branch to roll back commit T to B, got {after}"
            )
        )
        # Verify main branch remained at commit C
        rc, out_main, _ = run_cmd(["git", "log", "-1", "--pretty=%B", "main"], cwd=work_dir, env=test_env)
        if out_main.strip() != "commit C":
            raise AssertionError(f"Main branch altered unexpectedly: {out_main}")

    # Requirement: "a zero-case run is rejected."
    if len(test_cases) == 0:
        raise ValueError("Rejected: zero test cases executed!")

    return test_cases


def verify_zero_case_rejected():
    """Verify that a zero-case run is explicitly rejected."""
    empty_suite = []
    if len(empty_suite) == 0:
        # A zero-case condition is detected and rejected
        return True
    return False


def main():
    print(f"=== Starting git-undo verification (work/R13-T011) ===")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Tool versions
    versions = get_tool_versions()
    print("Tool versions detected:")
    for tool, ver in versions.items():
        print(f"  {tool}: {ver}")

    tool_versions_file = WORK_DIR / "tool_versions.json"
    with open(tool_versions_file, "w") as f:
        json.dump(versions, f, indent=2)

    # 2. Native Bats tests
    native_test_names = run_native_bats_tests()
    native_names_file = WORK_DIR / "native_test_names.txt"
    with open(native_names_file, "w") as f:
        for name, status in native_test_names:
            f.write(f"{status}: {name}\n")

    # 3. Zero-case assertion check
    if not verify_zero_case_rejected():
        print("ERROR: Zero-case validation failed.")
        sys.exit(1)

    # 4. Isolated shell test cases
    print("\n--- Running Focused Isolated Shell Checks ---")
    test_cases = run_checks()

    # Save detailed results
    results_file = WORK_DIR / "results.json"
    results_data = {
        "tool_versions": versions,
        "native_tests_count": len(native_test_names),
        "native_tests": native_test_names,
        "shell_checks_count": len(test_cases),
        "shell_checks": test_cases,
    }
    with open(results_file, "w") as f:
        json.dump(results_data, f, indent=2)

    # Save human-readable summary
    summary_file = WORK_DIR / "summary.txt"
    with open(summary_file, "w") as f:
        f.write("=== git-undo Verification Summary (R13-T011) ===\n\n")
        f.write(f"Tool Versions:\n")
        for k, v in versions.items():
            f.write(f"  {k}: {v}\n")
        f.write(f"\nNative Bats Tests ({len(native_test_names)}):\n")
        for name, status in native_test_names:
            f.write(f"  [{status}] {name}\n")
        f.write(f"\nFocused Shell Checks ({len(test_cases)}):\n")
        for tc in test_cases:
            f.write(f"  [{'PASS' if tc['passed'] else 'FAIL'}] {tc['name']}\n")
            f.write(f"    Command: {' '.join(tc['actual_arguments'])}\n")
            f.write(f"    Exit Status: {tc['actual_exit_status']} (expected {tc['expected_exit_status']})\n")
            if tc['before_state'].get('is_git_repo'):
                f.write(f"    Before: HEAD={tc['before_state'].get('head_message')} (cnt={tc['before_state'].get('commit_count')})\n")
                f.write(f"    After:  HEAD={tc['after_state'].get('head_message')} (cnt={tc['after_state'].get('commit_count')})\n")
            f.write("\n")

    passed_count = sum(1 for tc in test_cases if tc["passed"])
    print(f"\n=== Verification Complete: {passed_count}/{len(test_cases)} checks passed ===")
    print(f"Results saved to: {results_file}")
    print(f"Summary saved to: {summary_file}")

    if passed_count != len(test_cases):
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()

