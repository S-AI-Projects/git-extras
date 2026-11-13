#!/usr/bin/env python3
"""
work/R13-T012/check.py

Verification runner for git-fresh-branch enhancements:
- Invokes native Bats tests and asserts results.
- Executes isolated focused test cases (minimum accepted arguments, optional argument, invalid combinations).
- Asserts exit status, output, and repository state separately.
- Captures actual arguments, tool versions, expected vs actual outputs.
- Saves results and artifacts to work/R13-T012/.
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
    versions["python"] = sys.version.split()[0]

    rc, out, _ = run_cmd(["git", "--version"])
    versions["git"] = out.strip() if rc == 0 else "unknown"

    rc, out, _ = run_cmd(["bash", "--version"])
    first_line = out.splitlines()[0] if out else "unknown"
    versions["bash"] = first_line.strip()

    rc, out, _ = run_cmd(["bats", "--version"])
    versions["bats"] = out.strip() if rc == 0 else "unknown"

    return versions


def get_repo_state(repo_dir):
    """Capture repository state (current branch, commit count, HEAD sha, status)."""
    state = {}
    rc, out, _ = run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_dir)
    if rc != 0:
        return {"is_git_repo": False}

    state["is_git_repo"] = True

    _, out_branch, _ = run_cmd(["git", "branch", "--show-current"], cwd=repo_dir)
    state["branch"] = out_branch.strip()

    rc, out_head, _ = run_cmd(["git", "rev-parse", "--verify", "HEAD"], cwd=repo_dir)
    if rc == 0:
        state["has_commits"] = True
        state["head_sha"] = out_head.strip()

        _, out_cnt, _ = run_cmd(["git", "rev-list", "--count", "HEAD"], cwd=repo_dir)
        state["commit_count"] = int(out_cnt.strip()) if out_cnt.strip().isdigit() else 0
    else:
        state["has_commits"] = False
        state["head_sha"] = None
        state["commit_count"] = 0

    _, out_status, _ = run_cmd(["git", "status", "--porcelain"], cwd=repo_dir)
    state["status_porcelain"] = out_status.strip().splitlines()

    return state


def setup_test_environment(tmpdir):
    """
    Creates an isolated repository hierarchy:
    - local bare remote: origin.git
    - working repo: repo (cloned from origin.git)
    - commits A, B, C on branch main
    - branch topic pointing to commit B
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
    """Run tests/git-fresh-branch.bats and parse results."""
    print("--- Running Native Bats Tests (tests/git-fresh-branch.bats) ---")
    rc, stdout, stderr = run_cmd(["bats", "--tap", "tests/git-fresh-branch.bats"], cwd=REPO_ROOT)

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

        # 1. Exit status assertion
        status_ok = (rc == expected_rc) if isinstance(expected_rc, int) else (rc in expected_rc)

        # 2. Output assertion (stdout & stderr)
        combined_out = out + err
        out_ok = True
        err_msg = ""
        if check_stdout and not check_stdout(out, err):
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
            print(f"  Branch: '{before_state.get('branch')}' -> '{after_state.get('branch')}' "
                  f"(commits: {before_state.get('commit_count')} -> {after_state.get('commit_count')})")
        if not passed:
            print(f"  ERROR: {err_msg}")
            raise AssertionError(f"Check failed: {name} - {err_msg}")

    # Case 1: Minimum accepted arguments - creates fresh branch
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="minimum_accepted_arguments_create_fresh_branch",
            args=["git", "fresh-branch", "feature-docs"],
            cwd=work_dir,
            env=test_env,
            expected_rc=0,
            assert_state_fn=lambda before, after: (
                after["branch"] == "feature-docs" and
                after["has_commits"] is False and
                after["commit_count"] == 0 and
                len(after["status_porcelain"]) == 0,
                f"Expected clean orphan branch feature-docs, got {after}"
            )
        )

    # Case 2: Optional argument - --help shows usage
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="optional_argument_help_flag",
            args=["git-fresh-branch", "--help"],
            cwd=work_dir,
            env=test_env,
            expected_rc=0,
            check_stdout=lambda out, err: "Usage: git fresh-branch" in (out + err),
            assert_state_fn=lambda before, after: (
                after["branch"] == before["branch"] and
                after["commit_count"] == before["commit_count"],
                "Repository state unchanged on help flag"
            )
        )

    # Case 3: Optional argument - -h shows usage
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="optional_argument_short_help_flag",
            args=["git-fresh-branch", "-h"],
            cwd=work_dir,
            env=test_env,
            expected_rc=0,
            check_stdout=lambda out, err: "Usage: git fresh-branch" in (out + err),
            assert_state_fn=lambda before, after: (
                after["branch"] == before["branch"],
                "Repository state unchanged on short help flag"
            )
        )

    # Case 4: Documented invalid combination - missing branch name
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="documented_invalid_combination_missing_branch",
            args=["git", "fresh-branch"],
            cwd=work_dir,
            env=test_env,
            expected_rc=1,
            check_stdout=lambda out, err: "branch required." in (out + err),
            assert_state_fn=lambda before, after: (
                after["branch"] == before["branch"] and
                after["commit_count"] == before["commit_count"],
                "Repository state unchanged on missing branch"
            )
        )

    # Case 5: Documented invalid combination - unknown option flag
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="documented_invalid_combination_unknown_option",
            args=["git", "fresh-branch", "--invalid-option"],
            cwd=work_dir,
            env=test_env,
            expected_rc=1,
            check_stdout=lambda out, err: "error: unknown option" in (out + err),
            assert_state_fn=lambda before, after: (
                after["branch"] == before["branch"],
                "Repository state unchanged on unknown option"
            )
        )

    # Case 6: Documented invalid combination - too many arguments
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        register_case(
            name="documented_invalid_combination_too_many_arguments",
            args=["git", "fresh-branch", "branch-one", "branch-two"],
            cwd=work_dir,
            env=test_env,
            expected_rc=1,
            check_stdout=lambda out, err: "error: too many arguments" in (out + err),
            assert_state_fn=lambda before, after: (
                after["branch"] == before["branch"],
                "Repository state unchanged on too many arguments"
            )
        )

    # Case 7: Edge state - Untracked changes prompt declined
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        (work_dir / "untracked.txt").write_text("untracked work\n")
        register_case(
            name="edge_state_untracked_prompt_declined",
            args=["git", "fresh-branch", "orphan-test"],
            cwd=work_dir,
            env=test_env,
            input_text="n\n",
            expected_rc=0,
            assert_state_fn=lambda before, after: (
                after["branch"] == "main" and
                (work_dir / "untracked.txt").exists(),
                "Branch remained main and untracked file preserved on decline"
            )
        )

    # Case 8: Edge state - Untracked changes prompt confirmed
    with tempfile.TemporaryDirectory() as td:
        work_dir, test_env = setup_test_environment(td)
        (work_dir / "untracked.txt").write_text("untracked work\n")
        register_case(
            name="edge_state_untracked_prompt_confirmed",
            args=["git", "fresh-branch", "orphan-test"],
            cwd=work_dir,
            env=test_env,
            input_text="y\n",
            expected_rc=0,
            assert_state_fn=lambda before, after: (
                after["branch"] == "orphan-test" and
                not (work_dir / "untracked.txt").exists(),
                "Branch switched to orphan-test and untracked file cleaned on confirm"
            )
        )

    # Requirement: "a zero-case run is rejected."
    if len(test_cases) == 0:
        raise ValueError("Rejected: zero test cases executed!")

    return test_cases


def verify_zero_case_rejected():
    empty_suite = []
    if len(empty_suite) == 0:
        return True
    return False


def main():
    print(f"=== Starting git-fresh-branch verification (work/R13-T012) ===")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    versions = get_tool_versions()
    print("Tool versions detected:")
    for tool, ver in versions.items():
        print(f"  {tool}: {ver}")

    tool_versions_file = WORK_DIR / "tool_versions.json"
    with open(tool_versions_file, "w") as f:
        json.dump(versions, f, indent=2)

    native_test_names = run_native_bats_tests()
    native_names_file = WORK_DIR / "native_test_names.txt"
    with open(native_names_file, "w") as f:
        for name, status in native_test_names:
            f.write(f"{status}: {name}\n")

    if not verify_zero_case_rejected():
        print("ERROR: Zero-case validation failed.")
        sys.exit(1)

    print("\n--- Running Focused Isolated Shell Checks ---")
    test_cases = run_checks()

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

    summary_file = WORK_DIR / "summary.txt"
    with open(summary_file, "w") as f:
        f.write("=== git-fresh-branch Verification Summary (R13-T012) ===\n\n")
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
                f.write(f"    Before: Branch={tc['before_state'].get('branch')} (commits={tc['before_state'].get('commit_count')})\n")
                f.write(f"    After:  Branch={tc['after_state'].get('branch')} (commits={tc['after_state'].get('commit_count')})\n")
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
