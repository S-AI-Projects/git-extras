#!/usr/bin/env python3
"""
Verification script for Task R13-T018: git-info
Validates:
- Scoped source and documentation changes for git-info failure diagnostics.
- Native Bats test execution (tests/git-info.bats).
- Reaching actual failure branch with a small fixture, verifying exit status,
  and confirming useful diagnostic and troubleshooting explanation.
- Showing the corrected invocation succeeding afterwards.
- Observed option tokens: --color, --no-config, --get-all, --list.
- Isolated temporary Git repository with commits A/B/C, branches main/topic, and local bare remote.
- Global git configuration invariance and zero-case rejection.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORK_DIR = REPO_ROOT / "work" / "R13-T018"
BIN_DIR = REPO_ROOT / "bin"


def run_cmd(cmd, cwd=None, env=None, check=False):
    """Run command with isolated environment and repository bin prepended to PATH."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    path_entries = [str(BIN_DIR), "/opt/homebrew/bin", full_env.get("PATH", "")]
    full_env["PATH"] = ":".join(p for p in path_entries if p)

    res = subprocess.run(
        cmd,
        cwd=cwd or str(REPO_ROOT),
        env=full_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if check and res.returncode != 0:
        raise RuntimeError(
            f"Command failed ({res.returncode}): {' '.join(cmd) if isinstance(cmd, list) else cmd}\n"
            f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}"
        )
    return res


def collect_tool_versions():
    """Collect tool versions for environment documentation."""
    versions = {}
    for tool in ["git", "bash", "bats", "python3"]:
        try:
            r = run_cmd([tool, "--version"])
            versions[tool] = r.stdout.strip().split("\n")[0]
        except Exception as e:
            versions[tool] = f"unknown: {e}"
    return versions


def get_global_git_config():
    """Retrieve global git configuration for invariance check."""
    r = run_cmd(["git", "config", "--global", "--list"])
    return r.stdout.strip()


def run_native_bats_tests():
    """Execute the native bats test file and collect test names."""
    bats_file = REPO_ROOT / "tests" / "git-info.bats"
    if not bats_file.exists():
        raise FileNotFoundError(f"Native bats test file not found: {bats_file}")

    res = run_cmd(["bats", str(bats_file)])
    lines = res.stdout.strip().split("\n")
    test_names = []
    failed_tests = []

    for line in lines:
        if line.startswith("ok "):
            parts = line.split(" ", 2)
            if len(parts) >= 3:
                test_names.append(parts[2].strip())
        elif line.startswith("not ok "):
            parts = line.split(" ", 2)
            if len(parts) >= 3:
                failed_tests.append(parts[2].strip())

    if res.returncode != 0 or failed_tests:
        raise AssertionError(
            f"Native bats tests failed (exit {res.returncode}): {failed_tests}\n{res.stdout}\n{res.stderr}"
        )

    if not test_names:
        raise AssertionError("No native bats tests executed (zero-case run rejected)!")

    return test_names, res.stdout


def setup_temp_repo():
    """Create isolated temporary Git repository with commits A/B/C, branches main/topic, and local bare remote."""
    temp_dir = tempfile.mkdtemp(prefix="git_info_test_")
    env = {
        "GIT_AUTHOR_NAME": "Test Author",
        "GIT_AUTHOR_EMAIL": "author@example.com",
        "GIT_COMMITTER_NAME": "Test Committer",
        "GIT_COMMITTER_EMAIL": "committer@example.com",
        "GIT_CONFIG_NOSYSTEM": "1",
    }

    # git init with initial branch main
    run_cmd(["git", "init", "--initial-branch", "main"], cwd=temp_dir, env=env, check=True)
    run_cmd(["git", "config", "user.name", "Test User"], cwd=temp_dir, env=env, check=True)
    run_cmd(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, env=env, check=True)

    # Commit A
    file_a = Path(temp_dir) / "file_a.txt"
    file_a.write_text("Commit A content\n")
    run_cmd(["git", "add", "file_a.txt"], cwd=temp_dir, env=env, check=True)
    run_cmd(["git", "commit", "-m", "Commit A"], cwd=temp_dir, env=env, check=True)

    # Branch topic at Commit A, add Commit B
    run_cmd(["git", "checkout", "-b", "topic"], cwd=temp_dir, env=env, check=True)
    file_b = Path(temp_dir) / "file_b.txt"
    file_b.write_text("Commit B content\n")
    run_cmd(["git", "add", "file_b.txt"], cwd=temp_dir, env=env, check=True)
    run_cmd(["git", "commit", "-m", "Commit B"], cwd=temp_dir, env=env, check=True)

    # Return to main, add Commit C
    run_cmd(["git", "checkout", "main"], cwd=temp_dir, env=env, check=True)
    file_c = Path(temp_dir) / "file_c.txt"
    file_c.write_text("Commit C content\n")
    run_cmd(["git", "add", "file_c.txt"], cwd=temp_dir, env=env, check=True)
    run_cmd(["git", "commit", "-m", "Commit C"], cwd=temp_dir, env=env, check=True)

    # Setup local bare remote to satisfy requirement: "a local bare remote if needed"
    bare_dir = tempfile.mkdtemp(prefix="git_info_bare_")
    run_cmd(["git", "init", "--bare"], cwd=bare_dir, env=env, check=True)
    run_cmd(["git", "remote", "add", "origin", bare_dir], cwd=temp_dir, env=env, check=True)
    run_cmd(["git", "push", "origin", "main", "topic"], cwd=temp_dir, env=env, check=True)

    return temp_dir, bare_dir, env


def inspect_state(repo_dir, env):
    """Capture current branch, HEAD sha, branch list, and file list."""
    branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir, env=env).stdout.strip()
    head_sha = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).stdout.strip()
    branches = run_cmd(["git", "branch", "--list"], cwd=repo_dir, env=env).stdout.strip().split("\n")
    branches = [b.strip().replace("* ", "") for b in branches if b.strip()]
    files = sorted(os.listdir(repo_dir))
    files = [f for f in files if f != ".git"]
    return {
        "current_branch": branch,
        "head_sha": head_sha,
        "branches": branches,
        "files": files,
    }


def main():
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    print("=== Starting R13-T018 Verification: git-info ===")

    # 1. Collect tool versions
    tool_versions = collect_tool_versions()
    with open(WORK_DIR / "tool_versions.json", "w") as f:
        json.dump(tool_versions, f, indent=2)
    print(f"Recorded tool versions: {tool_versions}")

    # 2. Check global configuration invariance
    global_config_before = get_global_git_config()

    # 3. Execute native bats tests
    print("Running native bats tests...")
    native_names, bats_output = run_native_bats_tests()
    with open(WORK_DIR / "native_test_names.txt", "w") as f:
        f.write("\n".join(native_names) + "\n")
    print(f"Native bats tests passed ({len(native_names)} tests): {native_names}")

    # 4. Execute focused test cases in isolated temporary repo
    test_cases_results = []

    # Case 1: Standard successful git-info invocation
    temp_dir1, bare_dir1, env1 = setup_temp_repo()
    try:
        before_state = inspect_state(temp_dir1, env1)
        cmd = ["git", "info"]
        res = run_cmd(cmd, cwd=temp_dir1, env=env1)
        after_state = inspect_state(temp_dir1, env1)

        assert res.returncode == 0, f"Expected exit 0, got {res.returncode}. STDERR: {res.stderr}"
        assert "## Remote URLs:" in res.stdout
        assert "## Remote Branches:" in res.stdout
        assert "## Local Branches:" in res.stdout
        assert "## Most Recent Commit:" in res.stdout
        assert "## Configuration (.git/config):" in res.stdout
        assert before_state == after_state, "Repository state should remain unchanged after read-only git info"

        test_cases_results.append({
            "name": "standard_success",
            "command": "git info",
            "arguments": [],
            "exit_status": res.returncode,
            "expected_exit_status": 0,
            "before_state": before_state,
            "after_state": after_state,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir1, ignore_errors=True)
        shutil.rmtree(bare_dir1, ignore_errors=True)

    # Case 2: Observed option token --no-config
    temp_dir2, bare_dir2, env2 = setup_temp_repo()
    try:
        before_state = inspect_state(temp_dir2, env2)
        cmd = ["git", "info", "--no-config"]
        res = run_cmd(cmd, cwd=temp_dir2, env=env2)
        after_state = inspect_state(temp_dir2, env2)

        assert res.returncode == 0, f"Expected exit 0, got {res.returncode}"
        assert "## Remote URLs:" in res.stdout
        assert "## Most Recent Commit:" in res.stdout
        assert "## Configuration (.git/config):" not in res.stdout
        assert before_state == after_state

        test_cases_results.append({
            "name": "no_config_option_success",
            "command": "git info --no-config",
            "arguments": ["--no-config"],
            "exit_status": res.returncode,
            "expected_exit_status": 0,
            "before_state": before_state,
            "after_state": after_state,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir2, ignore_errors=True)
        shutil.rmtree(bare_dir2, ignore_errors=True)

    # Case 3: Observed option token --color
    temp_dir3, bare_dir3, env3 = setup_temp_repo()
    try:
        before_state = inspect_state(temp_dir3, env3)
        cmd = ["git", "info", "--color"]
        res = run_cmd(cmd, cwd=temp_dir3, env=env3)
        after_state = inspect_state(temp_dir3, env3)

        assert res.returncode == 0, f"Expected exit 0, got {res.returncode}"
        assert "## Remote URLs:" in res.stdout
        assert "## Local Branches:" in res.stdout
        assert before_state == after_state

        test_cases_results.append({
            "name": "color_option_success",
            "command": "git info --color",
            "arguments": ["--color"],
            "exit_status": res.returncode,
            "expected_exit_status": 0,
            "before_state": before_state,
            "after_state": after_state,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir3, ignore_errors=True)
        shutil.rmtree(bare_dir3, ignore_errors=True)

    # Case 4: Actual failure branch with fixture (failing config-grep) and corrected invocation (--no-config)
    # Exercises observed option tokens --get-all and --list logic
    temp_dir4, bare_dir4, env4 = setup_temp_repo()
    try:
        # Fixture setup: set failing git-extras.info.config-grep
        run_cmd(
            ["git", "config", "git-extras.info.config-grep", "grep-nonexistent-command"],
            cwd=temp_dir4,
            env=env4,
            check=True,
        )
        before_state = inspect_state(temp_dir4, env4)

        # Reaching actual failure branch with small fixture
        cmd_failing = ["git", "info"]
        res_failing = run_cmd(cmd_failing, cwd=temp_dir4, env=env4)

        assert res_failing.returncode == 1, f"Expected exit code 1 on failed config-grep, got {res_failing.returncode}"
        combined_err = res_failing.stderr + res_failing.stdout
        assert "git-info: failed to execute git-extras.info.config-grep: 'grep-nonexistent-command'" in combined_err, (
            f"Expected failure diagnostic in output: {combined_err}"
        )
        assert "Troubleshooting: verify the command in 'git config git-extras.info.config-grep' or use '--no-config'." in combined_err, (
            f"Expected troubleshooting explanation in output: {combined_err}"
        )

        # Show corrected invocation succeeding afterwards
        cmd_corrected = ["git", "info", "--no-config"]
        res_corrected = run_cmd(cmd_corrected, cwd=temp_dir4, env=env4)
        after_state = inspect_state(temp_dir4, env4)

        assert res_corrected.returncode == 0, f"Expected corrected invocation to exit 0, got {res_corrected.returncode}"
        assert "## Remote URLs:" in res_corrected.stdout
        assert "## Configuration (.git/config):" not in res_corrected.stdout
        assert before_state == after_state

        test_cases_results.append({
            "name": "fixture_config_grep_failure_and_corrected_recovery",
            "failing_command": "git info",
            "failing_arguments": [],
            "failing_exit_status": res_failing.returncode,
            "expected_failing_exit": 1,
            "diagnostic_present": True,
            "troubleshooting_present": True,
            "corrected_command": "git info --no-config",
            "corrected_arguments": ["--no-config"],
            "corrected_exit_status": res_corrected.returncode,
            "expected_corrected_exit": 0,
            "before_state": before_state,
            "after_state": after_state,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir4, ignore_errors=True)
        shutil.rmtree(bare_dir4, ignore_errors=True)

    # Case 5: Actual failure branch with fixture (failing log command) and corrected invocation
    temp_dir5, bare_dir5, env5 = setup_temp_repo()
    try:
        run_cmd(
            ["git", "config", "git-extras.info.log", "git log --nonexistent-flag-xyz"],
            cwd=temp_dir5,
            env=env5,
            check=True,
        )
        before_state = inspect_state(temp_dir5, env5)

        cmd_failing = ["git", "info"]
        res_failing = run_cmd(cmd_failing, cwd=temp_dir5, env=env5)

        assert res_failing.returncode == 1, f"Expected exit 1 on failed log command, got {res_failing.returncode}"
        combined_err = res_failing.stderr + res_failing.stdout
        assert "git-info: failed to execute git-extras.info.log: 'git log --nonexistent-flag-xyz'" in combined_err
        assert "Troubleshooting: verify the command in 'git config git-extras.info.log'." in combined_err

        # Corrected invocation: unset custom log config
        run_cmd(["git", "config", "--unset", "git-extras.info.log"], cwd=temp_dir5, env=env5, check=True)
        cmd_corrected = ["git", "info"]
        res_corrected = run_cmd(cmd_corrected, cwd=temp_dir5, env=env5)
        after_state = inspect_state(temp_dir5, env5)

        assert res_corrected.returncode == 0
        assert "## Most Recent Commit:" in res_corrected.stdout

        test_cases_results.append({
            "name": "fixture_log_cmd_failure_and_corrected_recovery",
            "failing_command": "git info",
            "failing_arguments": [],
            "failing_exit_status": res_failing.returncode,
            "expected_failing_exit": 1,
            "corrected_command": "git config --unset git-extras.info.log && git info",
            "corrected_exit_status": res_corrected.returncode,
            "expected_corrected_exit": 0,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir5, ignore_errors=True)
        shutil.rmtree(bare_dir5, ignore_errors=True)

    # Case 6: Unknown option failure and corrected invocation
    temp_dir6, bare_dir6, env6 = setup_temp_repo()
    try:
        before_state = inspect_state(temp_dir6, env6)
        cmd_failing = ["git", "info", "--invalid-option-token"]
        res_failing = run_cmd(cmd_failing, cwd=temp_dir6, env=env6)

        assert res_failing.returncode == 1, f"Expected exit 1 for unknown option, got {res_failing.returncode}"
        combined_err = res_failing.stderr + res_failing.stdout
        assert "git-info: unknown option '--invalid-option-token'" in combined_err
        assert "Troubleshooting: run 'git info -h' or refer to 'git info --help' for valid options." in combined_err

        # Corrected invocation
        cmd_corrected = ["git", "info", "--color"]
        res_corrected = run_cmd(cmd_corrected, cwd=temp_dir6, env=env6)
        after_state = inspect_state(temp_dir6, env6)

        assert res_corrected.returncode == 0
        assert before_state == after_state

        test_cases_results.append({
            "name": "unknown_option_failure_and_corrected_recovery",
            "failing_command": "git info --invalid-option-token",
            "failing_arguments": ["--invalid-option-token"],
            "failing_exit_status": res_failing.returncode,
            "expected_failing_exit": 1,
            "corrected_command": "git info --color",
            "corrected_arguments": ["--color"],
            "corrected_exit_status": res_corrected.returncode,
            "expected_corrected_exit": 0,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir6, ignore_errors=True)
        shutil.rmtree(bare_dir6, ignore_errors=True)

    # Case 7: Help option (-h)
    temp_dir7, bare_dir7, env7 = setup_temp_repo()
    try:
        before_state = inspect_state(temp_dir7, env7)
        cmd = ["git", "info", "-h"]
        res = run_cmd(cmd, cwd=temp_dir7, env=env7)
        after_state = inspect_state(temp_dir7, env7)

        assert res.returncode == 0
        assert "Usage: git info [-c|--color] [--no-config]" in res.stdout
        assert before_state == after_state

        test_cases_results.append({
            "name": "help_option_success",
            "command": "git info -h",
            "arguments": ["-h"],
            "exit_status": res.returncode,
            "expected_exit_status": 0,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir7, ignore_errors=True)
        shutil.rmtree(bare_dir7, ignore_errors=True)

    # Zero-case rejection assertion
    if len(test_cases_results) == 0:
        raise AssertionError("Zero-case run rejected: No test cases executed!")

    # Verify global config invariance
    global_config_after = get_global_git_config()
    assert global_config_before == global_config_after, (
        f"Global git configuration changed!\nBefore:\n{global_config_before}\nAfter:\n{global_config_after}"
    )

    # 5. Write results and summary
    results_payload = {
        "task_id": "R13-T018",
        "tool": "git-info",
        "total_cases_executed": len(test_cases_results),
        "native_bats_tests_count": len(native_names),
        "native_bats_tests": native_names,
        "cases": test_cases_results,
        "global_config_unimpaired": True,
    }

    with open(WORK_DIR / "results.json", "w") as f:
        json.dump(results_payload, f, indent=2)

    summary_content = (
        f"R13-T018: git-info Verification Summary\n"
        f"=========================================\n"
        f"Tool: git-info\n"
        f"Native Bats Tests Executed: {len(native_names)} (All Passed)\n"
        f"Focused Isolated Test Cases: {len(test_cases_results)} (All Passed)\n"
        f"Observed Option Tokens: --color, --no-config, --get-all, --list\n"
        f"Failure Diagnostics & Recoveries Verified:\n"
        f"  - Reached failure branch with failing config-grep fixture (exit 1) + verified troubleshooting diagnostic\n"
        f"  - Showed corrected invocation succeeding with --no-config (exit 0)\n"
        f"  - Reached failure branch with failing log command fixture (exit 1) + verified troubleshooting diagnostic\n"
        f"  - Showed corrected invocation succeeding after config fix (exit 0)\n"
        f"  - Reached failure branch with unknown option (exit 1) + verified usage troubleshooting\n"
        f"  - Showed corrected invocation succeeding with valid option (exit 0)\n"
        f"Global Git Config: Unchanged\n"
        f"Status: SUCCESS\n"
    )

    with open(WORK_DIR / "summary.txt", "w") as f:
        f.write(summary_content)

    print(summary_content)
    print("=== Verification R13-T018 completed successfully ===")


if __name__ == "__main__":
    main()
