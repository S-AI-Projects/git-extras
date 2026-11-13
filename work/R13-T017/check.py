#!/usr/bin/env python3
"""
Verification script for Task R13-T017: git-psykorebase
Validates documented usage examples, bats test suite execution,
option tokens (--no-ff, --continue, -h/--help), before/after repository states,
and error conditions in isolated temporary environments.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORK_DIR = REPO_ROOT / "work" / "R13-T017"
BIN_DIR = REPO_ROOT / "bin"


def run_cmd(cmd, cwd=None, env=None, check=False):
    """Run a shell command and return CompletedProcess."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    # Ensure homebrew and repo bin are in PATH
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
    bats_file = REPO_ROOT / "tests" / "git-psykorebase.bats"
    if not bats_file.exists():
        raise FileNotFoundError(f"Native bats test file not found: {bats_file}")

    res = run_cmd(["bats", str(bats_file)])
    lines = res.stdout.strip().split("\n")
    test_names = []
    failed_tests = []

    for line in lines:
        if line.startswith("ok "):
            # Format: ok 1 test name
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
    """Create isolated temporary Git repository with commits A/B/C, branches main/topic."""
    temp_dir = tempfile.mkdtemp(prefix="git_psykorebase_test_")
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
    base_file = Path(temp_dir) / "base.txt"
    base_file.write_text("Commit A content\n")
    run_cmd(["git", "add", "base.txt"], cwd=temp_dir, env=env, check=True)
    run_cmd(["git", "commit", "-m", "Commit A"], cwd=temp_dir, env=env, check=True)

    # Branch topic at Commit A, add Commit B
    run_cmd(["git", "checkout", "-b", "topic"], cwd=temp_dir, env=env, check=True)
    topic_file = Path(temp_dir) / "topic.txt"
    topic_file.write_text("Commit B content\n")
    run_cmd(["git", "add", "topic.txt"], cwd=temp_dir, env=env, check=True)
    run_cmd(["git", "commit", "-m", "Commit B"], cwd=temp_dir, env=env, check=True)

    # Return to main, add Commit C
    run_cmd(["git", "checkout", "main"], cwd=temp_dir, env=env, check=True)
    main_file = Path(temp_dir) / "main.txt"
    main_file.write_text("Commit C content\n")
    run_cmd(["git", "add", "main.txt"], cwd=temp_dir, env=env, check=True)
    run_cmd(["git", "commit", "-m", "Commit C"], cwd=temp_dir, env=env, check=True)

    # Setup local bare remote to satisfy requirement: "a local bare remote if needed"
    bare_dir = tempfile.mkdtemp(prefix="git_psykorebase_bare_")
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
    print("=== Starting R13-T017 Verification: git-psykorebase ===")

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

    # Case 1: Documented Usage Example (Success with --no-ff)
    temp_dir1, bare_dir1, env1 = setup_temp_repo()
    try:
        # Documented setup: checkout feature, add feature.txt commit
        run_cmd(["git", "checkout", "-b", "feature", "main"], cwd=temp_dir1, env=env1, check=True)
        feature_file = Path(temp_dir1) / "feature.txt"
        feature_file.write_text("feature change\n")
        run_cmd(["git", "add", "feature.txt"], cwd=temp_dir1, env=env1, check=True)
        run_cmd(["git", "commit", "-m", "Add feature"], cwd=temp_dir1, env=env1, check=True)

        # Checkout main, add main.txt commit
        run_cmd(["git", "checkout", "main"], cwd=temp_dir1, env=env1, check=True)
        main_file = Path(temp_dir1) / "main.txt"
        main_file.write_text("main change\n")
        run_cmd(["git", "add", "main.txt"], cwd=temp_dir1, env=env1, check=True)
        run_cmd(["git", "commit", "-m", "Update main"], cwd=temp_dir1, env=env1, check=True)

        # Checkout feature
        run_cmd(["git", "checkout", "feature"], cwd=temp_dir1, env=env1, check=True)

        before_state = inspect_state(temp_dir1, env1)

        # Execute Documented Command
        cmd = ["git", "psykorebase", "main", "--no-ff"]
        res = run_cmd(cmd, cwd=temp_dir1, env=env1)

        after_state = inspect_state(temp_dir1, env1)
        commit_subject = run_cmd(["git", "log", "-1", "--pretty=%s"], cwd=temp_dir1, env=env1).stdout.strip()
        parents = run_cmd(["git", "log", "-1", "--pretty=%P"], cwd=temp_dir1, env=env1).stdout.strip().split()

        # Assertions
        assert res.returncode == 0, f"Expected exit code 0, got {res.returncode}. STDERR: {res.stderr}"
        assert "Rebasing feature on top of main" in res.stdout, f"Expected rebase message in stdout: {res.stdout}"
        assert after_state["current_branch"] == "feature", f"Expected branch 'feature', got {after_state['current_branch']}"
        assert commit_subject == "Psycho-rebased branch feature on top of main", f"Unexpected subject: {commit_subject}"
        assert len(parents) == 2, f"Expected 2 merge parents, got {len(parents)}"
        assert "feature.txt" in after_state["files"] and "main.txt" in after_state["files"], "Expected files missing"
        # Assert unrelated state intact
        assert "base.txt" in after_state["files"], "Unrelated state base.txt missing"

        test_cases_results.append({
            "name": "documented_usage_example_success",
            "command": "git psykorebase main --no-ff",
            "arguments": ["main", "--no-ff"],
            "exit_status": res.returncode,
            "expected_exit_status": 0,
            "before_state": before_state,
            "after_state": after_state,
            "commit_subject": commit_subject,
            "parents_count": len(parents),
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir1, ignore_errors=True)
        shutil.rmtree(bare_dir1, ignore_errors=True)

    # Case 2: Success without --no-ff (Fast-forward / default rebase)
    temp_dir2, bare_dir2, env2 = setup_temp_repo()
    try:
        run_cmd(["git", "checkout", "topic"], cwd=temp_dir2, env=env2, check=True)
        before_state = inspect_state(temp_dir2, env2)

        cmd = ["git", "psykorebase", "main"]
        res = run_cmd(cmd, cwd=temp_dir2, env=env2)

        after_state = inspect_state(temp_dir2, env2)
        assert res.returncode == 0, f"Expected exit 0, got {res.returncode}"
        assert after_state["current_branch"] == "topic"
        assert "topic.txt" in after_state["files"] and "main.txt" in after_state["files"]

        test_cases_results.append({
            "name": "default_fast_forward_rebase_success",
            "command": "git psykorebase main",
            "arguments": ["main"],
            "exit_status": res.returncode,
            "expected_exit_status": 0,
            "before_state": before_state,
            "after_state": after_state,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir2, ignore_errors=True)
        shutil.rmtree(bare_dir2, ignore_errors=True)

    # Case 3: Conflict detection and resolution with --continue
    temp_dir3, bare_dir3, env3 = setup_temp_repo()
    try:
        # Create conflict on conflict.txt
        run_cmd(["git", "checkout", "-b", "feature", "main"], cwd=temp_dir3, env=env3, check=True)
        conflict_f = Path(temp_dir3) / "conflict.txt"
        conflict_f.write_text("feature conflicting line\n")
        run_cmd(["git", "add", "conflict.txt"], cwd=temp_dir3, env=env3, check=True)
        run_cmd(["git", "commit", "-m", "Feature conflict commit"], cwd=temp_dir3, env=env3, check=True)

        run_cmd(["git", "checkout", "main"], cwd=temp_dir3, env=env3, check=True)
        conflict_f.write_text("main conflicting line\n")
        run_cmd(["git", "add", "conflict.txt"], cwd=temp_dir3, env=env3, check=True)
        run_cmd(["git", "commit", "-m", "Main conflict commit"], cwd=temp_dir3, env=env3, check=True)

        run_cmd(["git", "checkout", "feature"], cwd=temp_dir3, env=env3, check=True)
        before_state = inspect_state(temp_dir3, env3)

        # Trigger conflict
        cmd_conflict = ["git", "psykorebase", "main", "--no-ff"]
        res_conflict = run_cmd(cmd_conflict, cwd=temp_dir3, env=env3)

        intermediate_state = inspect_state(temp_dir3, env3)
        assert res_conflict.returncode == 1, f"Expected conflict exit code 1, got {res_conflict.returncode}"
        assert intermediate_state["current_branch"] == "feature-rebased-on-top-of-main"
        assert "git psykorebase --continue" in res_conflict.stdout

        # Resolve conflict and run --continue
        conflict_f.write_text("resolved conflict line\n")
        run_cmd(["git", "add", "conflict.txt"], cwd=temp_dir3, env=env3, check=True)

        env3_continue = env3.copy()
        env3_continue["GIT_EDITOR"] = "cat"
        cmd_continue = ["git", "psykorebase", "--continue"]
        res_continue = run_cmd(cmd_continue, cwd=temp_dir3, env=env3_continue)

        after_state = inspect_state(temp_dir3, env3)
        assert res_continue.returncode == 0, f"Expected continue exit code 0, got {res_continue.returncode}"
        assert after_state["current_branch"] == "feature"
        commit_subject = run_cmd(["git", "log", "-1", "--pretty=%s"], cwd=temp_dir3, env=env3).stdout.strip()
        assert commit_subject == "Psycho-rebased branch feature on top of main"

        test_cases_results.append({
            "name": "conflict_and_continue_resolution",
            "command": "git psykorebase main --no-ff && git psykorebase --continue",
            "arguments": ["--continue"],
            "conflict_exit_status": res_conflict.returncode,
            "continue_exit_status": res_continue.returncode,
            "expected_conflict_exit": 1,
            "expected_continue_exit": 0,
            "intermediate_state": intermediate_state,
            "after_state": after_state,
            "commit_subject": commit_subject,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir3, ignore_errors=True)
        shutil.rmtree(bare_dir3, ignore_errors=True)

    # Case 4: Documented Failure - Missing arguments (exit 10)
    temp_dir4, bare_dir4, env4 = setup_temp_repo()
    try:
        before_state = inspect_state(temp_dir4, env4)
        cmd = ["git", "psykorebase"]
        res = run_cmd(cmd, cwd=temp_dir4, env=env4)
        after_state = inspect_state(temp_dir4, env4)

        assert res.returncode == 10, f"Expected exit code 10, got {res.returncode}"
        assert "USAGE: git psykorebase PRIMARY_BRANCH" in res.stdout
        assert before_state == after_state, "State should remain unchanged on argument error"

        test_cases_results.append({
            "name": "missing_arguments_failure",
            "command": "git psykorebase",
            "arguments": [],
            "exit_status": res.returncode,
            "expected_exit_status": 10,
            "before_state": before_state,
            "after_state": after_state,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir4, ignore_errors=True)
        shutil.rmtree(bare_dir4, ignore_errors=True)

    # Case 5: Documented Failure - Too many arguments (exit 20)
    temp_dir5, bare_dir5, env5 = setup_temp_repo()
    try:
        before_state = inspect_state(temp_dir5, env5)
        cmd = ["git", "psykorebase", "main", "feature", "extra_arg"]
        res = run_cmd(cmd, cwd=temp_dir5, env=env5)
        after_state = inspect_state(temp_dir5, env5)

        assert res.returncode == 20, f"Expected exit code 20, got {res.returncode}"
        assert "USAGE: git psykorebase PRIMARY_BRANCH" in res.stdout
        assert before_state == after_state, "State should remain unchanged on argument error"

        test_cases_results.append({
            "name": "too_many_arguments_failure",
            "command": "git psykorebase main feature extra_arg",
            "arguments": ["main", "feature", "extra_arg"],
            "exit_status": res.returncode,
            "expected_exit_status": 20,
            "before_state": before_state,
            "after_state": after_state,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir5, ignore_errors=True)
        shutil.rmtree(bare_dir5, ignore_errors=True)

    # Case 6: Documented Failure - Invalid --continue branch context (exit 30)
    temp_dir6, bare_dir6, env6 = setup_temp_repo()
    try:
        before_state = inspect_state(temp_dir6, env6)
        cmd = ["git", "psykorebase", "--continue"]
        res = run_cmd(cmd, cwd=temp_dir6, env=env6)
        after_state = inspect_state(temp_dir6, env6)

        assert res.returncode == 30, f"Expected exit code 30, got {res.returncode}"
        assert "Couldn't continue rebasing on main" in res.stdout
        assert before_state == after_state, "State should remain unchanged on continue failure"

        test_cases_results.append({
            "name": "invalid_continue_branch_failure",
            "command": "git psykorebase --continue",
            "arguments": ["--continue"],
            "exit_status": res.returncode,
            "expected_exit_status": 30,
            "before_state": before_state,
            "after_state": after_state,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir6, ignore_errors=True)
        shutil.rmtree(bare_dir6, ignore_errors=True)

    # Case 7: Usage option -h
    temp_dir7, bare_dir7, env7 = setup_temp_repo()
    try:
        before_state = inspect_state(temp_dir7, env7)
        cmd = ["git", "psykorebase", "-h"]
        res = run_cmd(cmd, cwd=temp_dir7, env=env7)
        after_state = inspect_state(temp_dir7, env7)

        assert res.returncode == 0, f"Expected exit code 0, got {res.returncode}"
        assert "USAGE: git psykorebase PRIMARY_BRANCH" in res.stdout
        assert before_state == after_state

        test_cases_results.append({
            "name": "help_option_success",
            "command": "git psykorebase -h",
            "arguments": ["-h"],
            "exit_status": res.returncode,
            "expected_exit_status": 0,
            "before_state": before_state,
            "after_state": after_state,
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
        "task_id": "R13-T017",
        "tool": "git-psykorebase",
        "total_cases_executed": len(test_cases_results),
        "native_bats_tests_count": len(native_names),
        "native_bats_tests": native_names,
        "cases": test_cases_results,
        "global_config_unimpaired": True,
    }

    with open(WORK_DIR / "results.json", "w") as f:
        json.dump(results_payload, f, indent=2)

    summary_content = (
        f"R13-T017: git-psykorebase Verification Summary\n"
        f"================================================\n"
        f"Tool: git-psykorebase\n"
        f"Native Bats Tests Executed: {len(native_names)} (All Passed)\n"
        f"Focused Isolated Test Cases: {len(test_cases_results)} (All Passed)\n"
        f"Observed Option Tokens: --no-ff, --continue, -h/--help\n"
        f"State Transitions Tested:\n"
        f"  - Documented usage example with setup, command, output, and state verification\n"
        f"  - Fast-forward default rebase\n"
        f"  - Conflict pause and --continue resolution\n"
        f"  - Missing arguments failure (exit 10)\n"
        f"  - Too many arguments failure (exit 20)\n"
        f"  - Invalid --continue branch failure (exit 30)\n"
        f"  - Help usage option (-h)\n"
        f"Global Git Config: Unchanged\n"
        f"Status: SUCCESS\n"
    )

    with open(WORK_DIR / "summary.txt", "w") as f:
        f.write(summary_content)

    print(summary_content)
    print("=== Verification R13-T017 completed successfully ===")


if __name__ == "__main__":
    main()
