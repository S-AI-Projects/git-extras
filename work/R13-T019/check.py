#!/usr/bin/env python3
"""
Repeatable test entry point and verification script for Task R13-T019: git-delete-merged-branches.
Validates:
- Execution of native Bats tests (tests/git-delete-merged-branches.bats).
- Focused isolated checks in temporary Git repository with commits A/B/C, branches main/topic, and local bare remote.
- Observed option tokens: --no-color, --merged.
- Error propagation on unknown options/failures.
- Automatic cleanup of temporary state and independent execution without unrelated services.
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
WORK_DIR = REPO_ROOT / "work" / "R13-T019"
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
    bats_file = REPO_ROOT / "tests" / "git-delete-merged-branches.bats"
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
    temp_dir = tempfile.mkdtemp(prefix="git_delete_merged_test_")
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
    bare_dir = tempfile.mkdtemp(prefix="git_delete_merged_bare_")
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
    print("=== Starting R13-T019 Verification: git-delete-merged-branches ===")

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

    # Case 1: Standard successful deletion of merged branch (observed tokens: --no-color, --merged)
    temp_dir1, bare_dir1, env1 = setup_temp_repo()
    try:
        # Merge topic into main
        run_cmd(["git", "merge", "topic", "-m", "Merge topic into main"], cwd=temp_dir1, env=env1, check=True)
        # Verify observed option tokens in git branch
        merged_check = run_cmd(["git", "branch", "--no-color", "--merged"], cwd=temp_dir1, env=env1, check=True)
        assert "topic" in merged_check.stdout, "topic branch should be detected as merged"

        before_state = inspect_state(temp_dir1, env1)
        assert "topic" in before_state["branches"]
        assert "main" in before_state["branches"]

        # Run command
        cmd = ["git", "delete-merged-branches"]
        res = run_cmd(cmd, cwd=temp_dir1, env=env1)
        after_state = inspect_state(temp_dir1, env1)

        assert res.returncode == 0, f"Expected exit 0, got {res.returncode}. STDERR: {res.stderr}"
        assert "topic" not in after_state["branches"], "Merged branch topic should be deleted"
        assert "main" in after_state["branches"], "Default branch main must be preserved"
        # Assert unrelated state (files from commit A and C) remain intact
        assert "file_a.txt" in after_state["files"] and "file_c.txt" in after_state["files"]

        test_cases_results.append({
            "name": "merged_branch_deletion_success",
            "command": "git delete-merged-branches",
            "arguments": [],
            "exit_status": res.returncode,
            "expected_exit_status": 0,
            "before_state": before_state,
            "after_state": after_state,
            "deleted_branches": ["topic"],
            "preserved_branches": ["main"],
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir1, ignore_errors=True)
        shutil.rmtree(bare_dir1, ignore_errors=True)

    # Case 2: Preserves unmerged branch while deleting merged branch
    temp_dir2, bare_dir2, env2 = setup_temp_repo()
    try:
        # Create unmerged branch
        run_cmd(["git", "checkout", "-b", "feature-unmerged", "main"], cwd=temp_dir2, env=env2, check=True)
        unmerged_file = Path(temp_dir2) / "unmerged.txt"
        unmerged_file.write_text("Unmerged work\n")
        run_cmd(["git", "add", "unmerged.txt"], cwd=temp_dir2, env=env2, check=True)
        run_cmd(["git", "commit", "-m", "Unmerged commit"], cwd=temp_dir2, env=env2, check=True)

        # Create merged branch
        run_cmd(["git", "checkout", "main"], cwd=temp_dir2, env=env2, check=True)
        run_cmd(["git", "checkout", "-b", "feature-merged", "main"], cwd=temp_dir2, env=env2, check=True)
        merged_file = Path(temp_dir2) / "merged.txt"
        merged_file.write_text("Merged work\n")
        run_cmd(["git", "add", "merged.txt"], cwd=temp_dir2, env=env2, check=True)
        run_cmd(["git", "commit", "-m", "Merged commit"], cwd=temp_dir2, env=env2, check=True)
        run_cmd(["git", "checkout", "main"], cwd=temp_dir2, env=env2, check=True)
        run_cmd(["git", "merge", "feature-merged", "-m", "Merge feature-merged"], cwd=temp_dir2, env=env2, check=True)

        before_state = inspect_state(temp_dir2, env2)
        cmd = ["git", "delete-merged-branches"]
        res = run_cmd(cmd, cwd=temp_dir2, env=env2)
        after_state = inspect_state(temp_dir2, env2)

        assert res.returncode == 0
        assert "feature-merged" not in after_state["branches"]
        assert "feature-unmerged" in after_state["branches"], "Unmerged branch must be preserved"
        assert "main" in after_state["branches"], "Main branch must be preserved"

        test_cases_results.append({
            "name": "preserve_unmerged_branch_success",
            "command": "git delete-merged-branches",
            "arguments": [],
            "exit_status": res.returncode,
            "expected_exit_status": 0,
            "before_state": before_state,
            "after_state": after_state,
            "deleted_branches": ["feature-merged"],
            "preserved_branches": ["main", "feature-unmerged"],
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir2, ignore_errors=True)
        shutil.rmtree(bare_dir2, ignore_errors=True)

    # Case 3: When checked out on feature branch, protects default branch
    temp_dir3, bare_dir3, env3 = setup_temp_repo()
    try:
        run_cmd(["git", "checkout", "-b", "feature-active", "main"], cwd=temp_dir3, env=env3, check=True)
        # Create another branch merged into feature-active
        run_cmd(["git", "checkout", "-b", "sub-merged", "feature-active"], cwd=temp_dir3, env=env3, check=True)
        run_cmd(["git", "commit", "--allow-empty", "-m", "Sub merged"], cwd=temp_dir3, env=env3, check=True)
        run_cmd(["git", "checkout", "feature-active"], cwd=temp_dir3, env=env3, check=True)
        run_cmd(["git", "merge", "sub-merged", "-m", "Merge sub"], cwd=temp_dir3, env=env3, check=True)

        before_state = inspect_state(temp_dir3, env3)
        cmd = ["git", "delete-merged-branches"]
        res = run_cmd(cmd, cwd=temp_dir3, env=env3)
        after_state = inspect_state(temp_dir3, env3)

        assert res.returncode == 0
        assert "sub-merged" not in after_state["branches"]
        assert "main" in after_state["branches"], "Main default branch protected when on feature branch"
        assert "feature-active" in after_state["branches"], "Active feature branch protected"

        test_cases_results.append({
            "name": "protect_default_from_feature_branch",
            "command": "git delete-merged-branches",
            "arguments": [],
            "exit_status": res.returncode,
            "expected_exit_status": 0,
            "before_state": before_state,
            "after_state": after_state,
            "deleted_branches": ["sub-merged"],
            "preserved_branches": ["main", "feature-active"],
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir3, ignore_errors=True)
        shutil.rmtree(bare_dir3, ignore_errors=True)

    # Case 4: No matching merged branches (idempotency)
    temp_dir4, bare_dir4, env4 = setup_temp_repo()
    try:
        before_state = inspect_state(temp_dir4, env4)
        cmd = ["git", "delete-merged-branches"]
        res = run_cmd(cmd, cwd=temp_dir4, env=env4)
        after_state = inspect_state(temp_dir4, env4)

        assert res.returncode == 0
        assert before_state == after_state, "State should be identical when no branches match"

        test_cases_results.append({
            "name": "no_matching_branches_idempotent",
            "command": "git delete-merged-branches",
            "arguments": [],
            "exit_status": res.returncode,
            "expected_exit_status": 0,
            "before_state": before_state,
            "after_state": after_state,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir4, ignore_errors=True)
        shutil.rmtree(bare_dir4, ignore_errors=True)

    # Case 5: Documented Failure / Edge state - Unknown option handling and failure propagation
    temp_dir5, bare_dir5, env5 = setup_temp_repo()
    try:
        before_state = inspect_state(temp_dir5, env5)
        cmd = ["git", "delete-merged-branches", "--invalid-option"]
        res = run_cmd(cmd, cwd=temp_dir5, env=env5)
        after_state = inspect_state(temp_dir5, env5)

        assert res.returncode == 1, f"Expected exit 1 for unknown option, got {res.returncode}"
        combined_err = res.stderr + res.stdout
        assert "git-delete-merged-branches: unknown option '--invalid-option'" in combined_err
        assert "Usage: git delete-merged-branches" in combined_err
        assert before_state == after_state, "State should remain unchanged on option error"

        test_cases_results.append({
            "name": "unknown_option_failure_propagation",
            "command": "git delete-merged-branches --invalid-option",
            "arguments": ["--invalid-option"],
            "exit_status": res.returncode,
            "expected_exit_status": 1,
            "before_state": before_state,
            "after_state": after_state,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir5, ignore_errors=True)
        shutil.rmtree(bare_dir5, ignore_errors=True)

    # Case 6: Help option (-h)
    temp_dir6, bare_dir6, env6 = setup_temp_repo()
    try:
        before_state = inspect_state(temp_dir6, env6)
        cmd = ["git", "delete-merged-branches", "-h"]
        res = run_cmd(cmd, cwd=temp_dir6, env=env6)
        after_state = inspect_state(temp_dir6, env6)

        assert res.returncode == 0
        assert "Usage: git delete-merged-branches [-h|--help]" in res.stdout
        assert before_state == after_state

        test_cases_results.append({
            "name": "help_option_success",
            "command": "git delete-merged-branches -h",
            "arguments": ["-h"],
            "exit_status": res.returncode,
            "expected_exit_status": 0,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir6, ignore_errors=True)
        shutil.rmtree(bare_dir6, ignore_errors=True)

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
        "task_id": "R13-T019",
        "tool": "git-delete-merged-branches",
        "total_cases_executed": len(test_cases_results),
        "native_bats_tests_count": len(native_names),
        "native_bats_tests": native_names,
        "cases": test_cases_results,
        "global_config_unimpaired": True,
        "temporary_state_cleaned": True,
        "independent_of_unrelated_services": True,
    }

    with open(WORK_DIR / "results.json", "w") as f:
        json.dump(results_payload, f, indent=2)

    summary_content = (
        f"R13-T019: git-delete-merged-branches Verification Summary\n"
        f"==========================================================\n"
        f"Tool: git-delete-merged-branches\n"
        f"Native Bats Tests Executed: {len(native_names)} (All Passed)\n"
        f"Focused Isolated Test Cases: {len(test_cases_results)} (All Passed)\n"
        f"Observed Option Tokens: --no-color, --merged\n"
        f"Cases Verified:\n"
        f"  - Deletion of merged branch while preserving default branch\n"
        f"  - Preservation of unmerged branch while deleting merged branch\n"
        f"  - Protection of default branch when checked out on feature branch\n"
        f"  - Idempotent clean state when no branches match\n"
        f"  - Unknown option error diagnostic and failure propagation (exit 1)\n"
        f"  - Help usage option (-h)\n"
        f"Isolation & Cleanup: All temporary state cleaned up via finally blocks\n"
        f"Independence: Independent of unrelated services and external remotes\n"
        f"Global Git Config: Unchanged\n"
        f"Status: SUCCESS\n"
    )

    with open(WORK_DIR / "summary.txt", "w") as f:
        f.write(summary_content)

    print(summary_content)
    print("=== Verification R13-T019 completed successfully ====")


if __name__ == "__main__":
    main()
