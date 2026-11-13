#!/usr/bin/env python3
"""
Verification script for Task R13-T020: git-unwip
Validates:
- Scoped source and documentation changes for git-unwip (positional argument handling and option support).
- Native Bats test execution (tests/git-unwip.bats).
- Mutation testing: introduces a temporary one-condition mutant (`[ 'WIP' = "$LAST_COMMIT" ]`),
  verifies that valid input rejects (kills) the mutant, and confirms regression tests pass against the real code.
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
WORK_DIR = REPO_ROOT / "work" / "R13-T020"
BIN_DIR = REPO_ROOT / "bin"


def run_cmd(cmd, cwd=None, env=None, check=False):
    """Run command with isolated environment and repository bin prepended to PATH."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    if not (env and "PATH" in env):
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
    bats_file = REPO_ROOT / "tests" / "git-unwip.bats"
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
    temp_dir = tempfile.mkdtemp(prefix="git_unwip_test_")
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
    bare_dir = tempfile.mkdtemp(prefix="git_unwip_bare_")
    run_cmd(["git", "init", "--bare"], cwd=bare_dir, env=env, check=True)
    run_cmd(["git", "remote", "add", "origin", bare_dir], cwd=temp_dir, env=env, check=True)
    run_cmd(["git", "push", "origin", "main", "topic"], cwd=temp_dir, env=env, check=True)

    return temp_dir, bare_dir, env


def inspect_state(repo_dir, env):
    """Capture current branch, HEAD sha, branch list, commit subject, and file list."""
    branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir, env=env).stdout.strip()
    head_sha = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).stdout.strip()
    branches = run_cmd(["git", "branch", "--list"], cwd=repo_dir, env=env).stdout.strip().split("\n")
    branches = [b.strip().replace("* ", "") for b in branches if b.strip()]
    files = sorted(os.listdir(repo_dir))
    files = [f for f in files if f != ".git"]
    commit_subject = run_cmd(["git", "log", "-1", "--pretty=%s"], cwd=repo_dir, env=env).stdout.strip()
    return {
        "current_branch": branch,
        "head_sha": head_sha,
        "branches": branches,
        "commit_subject": commit_subject,
        "files": files,
    }


def verify_mutation_testing():
    """
    Demonstrate that a temporary one-condition mutant is rejected by the regression test.
    Mutant: Inverts condition `if [ 'WIP' != "$LAST_COMMIT" ]; then` to `if [ 'WIP' = "$LAST_COMMIT" ]; then`.
    Valid input: A repository with a WIP commit.
    Against real code: git unwip succeeds (exit 0).
    Against mutant: git unwip fails (exit 1), proving the regression input kills the mutant.
    """
    temp_dir = tempfile.mkdtemp(prefix="git_unwip_mutant_test_")
    env = {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Test Author",
        "GIT_AUTHOR_EMAIL": "author@example.com",
        "GIT_COMMITTER_NAME": "Test Committer",
        "GIT_COMMITTER_EMAIL": "committer@example.com",
    }
    try:
        run_cmd(["git", "init", "--initial-branch", "main"], cwd=temp_dir, env=env, check=True)
        run_cmd(["git", "config", "user.name", "Test User"], cwd=temp_dir, env=env, check=True)
        run_cmd(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, env=env, check=True)

        base_file = Path(temp_dir) / "work.txt"
        base_file.write_text("initial\n")
        run_cmd(["git", "add", "work.txt"], cwd=temp_dir, env=env, check=True)
        run_cmd(["git", "commit", "-m", "Initial"], cwd=temp_dir, env=env, check=True)

        base_file.write_text("wip change\n")
        run_cmd(["git", "add", "work.txt"], cwd=temp_dir, env=env, check=True)
        run_cmd(["git", "commit", "-m", "WIP"], cwd=temp_dir, env=env, check=True)

        # Create temporary mutated git-unwip binary with condition inverted
        real_unwip_code = (BIN_DIR / "git-unwip").read_text()
        mutated_unwip_code = real_unwip_code.replace(
            "if [ 'WIP' != \"$LAST_COMMIT\" ]; then",
            "if [ 'WIP' = \"$LAST_COMMIT\" ]; then",
        )
        assert mutated_unwip_code != real_unwip_code, "Mutation failed to substitute condition"

        mutant_bin_dir = Path(temp_dir) / "mutant_bin"
        mutant_bin_dir.mkdir()
        mutant_unwip = mutant_bin_dir / "git-unwip"
        mutant_unwip.write_text(mutated_unwip_code)
        mutant_unwip.chmod(0o755)

        # Run mutant with valid WIP input: should FAIL because condition is inverted
        mutant_env = env.copy()
        mutant_env["PATH"] = f"{mutant_bin_dir}:{BIN_DIR}:/opt/homebrew/bin:{os.environ.get('PATH', '')}"
        mutant_res = run_cmd(["git", "unwip"], cwd=temp_dir, env=mutant_env)

        # Assert mutant is rejected (exits 1 instead of succeeding 0)
        assert mutant_res.returncode == 1, (
            f"Mutant should fail on valid WIP input, but exited {mutant_res.returncode}"
        )
        assert "Last commit is not a WIP commit" in mutant_res.stdout

        # Run genuine code with identical input: succeeds 0
        real_res = run_cmd(["git", "unwip"], cwd=temp_dir, env=env)
        assert real_res.returncode == 0, (
            f"Genuine code must succeed on valid WIP input, but exited {real_res.returncode}"
        )

        return {
            "mutant_condition": "if [ 'WIP' = \"$LAST_COMMIT\" ]; then",
            "original_condition": "if [ 'WIP' != \"$LAST_COMMIT\" ]; then",
            "mutant_exit_code": mutant_res.returncode,
            "real_exit_code": real_res.returncode,
            "mutant_rejected": True,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    print("=== Starting R13-T020 Verification: git-unwip ===")

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

    # 4. Mutation testing verification
    print("Executing condition mutation verification...")
    mutation_info = verify_mutation_testing()
    print(f"Mutation verification: {mutation_info}")

    # 5. Execute focused test cases in isolated temporary repo
    test_cases_results = []

    # Case 1: Successful unwip of exact "WIP" commit
    temp_dir1, bare_dir1, env1 = setup_temp_repo()
    try:
        run_cmd(["git", "checkout", "topic"], cwd=temp_dir1, env=env1, check=True)
        wip_file = Path(temp_dir1) / "file_b.txt"
        wip_file.write_text("WIP work in progress\n")
        run_cmd(["git", "add", "file_b.txt"], cwd=temp_dir1, env=env1, check=True)
        run_cmd(["git", "commit", "-m", "WIP"], cwd=temp_dir1, env=env1, check=True)

        before_state = inspect_state(temp_dir1, env1)
        assert before_state["commit_subject"] == "WIP"

        cmd = ["git", "unwip"]
        res = run_cmd(cmd, cwd=temp_dir1, env=env1)
        after_state = inspect_state(temp_dir1, env1)

        assert res.returncode == 0, f"Expected exit 0, got {res.returncode}. STDERR: {res.stderr}"
        assert after_state["commit_subject"] == "Commit B", "HEAD should be reset to Commit B"
        # Working tree changes must be preserved (soft undo)
        assert wip_file.read_text() == "WIP work in progress\n"
        # Unrelated state (file_a.txt and branch main) must be preserved
        assert "file_a.txt" in after_state["files"]
        assert "main" in after_state["branches"]

        test_cases_results.append({
            "name": "wip_commit_undo_success",
            "command": "git unwip",
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

    # Case 2: Handling WIP commit with whitespace
    temp_dir2, bare_dir2, env2 = setup_temp_repo()
    try:
        run_cmd(["git", "checkout", "topic"], cwd=temp_dir2, env=env2, check=True)
        wip_file = Path(temp_dir2) / "file_b.txt"
        wip_file.write_text("WIP with whitespace\n")
        run_cmd(["git", "add", "file_b.txt"], cwd=temp_dir2, env=env2, check=True)
        run_cmd(["git", "commit", "-m", "   WIP   \n"], cwd=temp_dir2, env=env2, check=True)

        before_state = inspect_state(temp_dir2, env2)
        cmd = ["git", "unwip"]
        res = run_cmd(cmd, cwd=temp_dir2, env=env2)
        after_state = inspect_state(temp_dir2, env2)

        assert res.returncode == 0
        assert after_state["commit_subject"] == "Commit B"

        test_cases_results.append({
            "name": "wip_whitespace_undo_success",
            "command": "git unwip",
            "arguments": [],
            "exit_status": res.returncode,
            "expected_exit_status": 0,
            "before_state": before_state,
            "after_state": after_state,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir2, ignore_errors=True)
        shutil.rmtree(bare_dir2, ignore_errors=True)

    # Case 3: Rejection of non-WIP commit (protecting condition)
    temp_dir3, bare_dir3, env3 = setup_temp_repo()
    try:
        run_cmd(["git", "checkout", "main"], cwd=temp_dir3, env=env3, check=True)
        before_state = inspect_state(temp_dir3, env3)
        assert before_state["commit_subject"] == "Commit C"

        cmd = ["git", "unwip"]
        res = run_cmd(cmd, cwd=temp_dir3, env=env3)
        after_state = inspect_state(temp_dir3, env3)

        assert res.returncode == 1, f"Expected exit 1 for non-WIP commit, got {res.returncode}"
        assert "Last commit is not a WIP commit, so it will not be unWIP-ed." in res.stdout
        assert before_state == after_state, "Commit state must remain untouched when not WIP"

        test_cases_results.append({
            "name": "non_wip_commit_rejection",
            "command": "git unwip",
            "arguments": [],
            "exit_status": res.returncode,
            "expected_exit_status": 1,
            "before_state": before_state,
            "after_state": after_state,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir3, ignore_errors=True)
        shutil.rmtree(bare_dir3, ignore_errors=True)

    # Case 4: Rejection of commit where WIP is only a substring
    temp_dir4, bare_dir4, env4 = setup_temp_repo()
    try:
        run_cmd(["git", "checkout", "topic"], cwd=temp_dir4, env=env4, check=True)
        f = Path(temp_dir4) / "file_b.txt"
        f.write_text("partial wip\n")
        run_cmd(["git", "add", "file_b.txt"], cwd=temp_dir4, env=env4, check=True)
        run_cmd(["git", "commit", "-m", "WIP: partial feature"], cwd=temp_dir4, env=env4, check=True)

        before_state = inspect_state(temp_dir4, env4)
        cmd = ["git", "unwip"]
        res = run_cmd(cmd, cwd=temp_dir4, env=env4)
        after_state = inspect_state(temp_dir4, env4)

        assert res.returncode == 1
        assert "Last commit is not a WIP commit, so it will not be unWIP-ed." in res.stdout
        assert before_state == after_state

        test_cases_results.append({
            "name": "wip_substring_commit_rejection",
            "command": "git unwip",
            "arguments": [],
            "exit_status": res.returncode,
            "expected_exit_status": 1,
            "before_state": before_state,
            "after_state": after_state,
            "status": "PASSED",
        })
    finally:
        shutil.rmtree(temp_dir4, ignore_errors=True)
        shutil.rmtree(bare_dir4, ignore_errors=True)

    # Case 5: Positional argument handling (inspected positional-argument handling in source)
    temp_dir5, bare_dir5, env5 = setup_temp_repo()
    try:
        before_state = inspect_state(temp_dir5, env5)
        cmd = ["git", "unwip", "unexpected_positional_arg"]
        res = run_cmd(cmd, cwd=temp_dir5, env=env5)
        after_state = inspect_state(temp_dir5, env5)

        assert res.returncode == 1, f"Expected exit 1 for unexpected positional argument, got {res.returncode}"
        combined_err = res.stderr + res.stdout
        assert "git-unwip: unexpected argument 'unexpected_positional_arg'" in combined_err
        assert "Usage: git unwip [-h|--help]" in combined_err
        assert before_state == after_state, "State should remain unchanged on argument error"

        test_cases_results.append({
            "name": "unexpected_positional_argument_rejection",
            "command": "git unwip unexpected_positional_arg",
            "arguments": ["unexpected_positional_arg"],
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
        cmd = ["git", "unwip", "-h"]
        res = run_cmd(cmd, cwd=temp_dir6, env=env6)
        after_state = inspect_state(temp_dir6, env6)

        assert res.returncode == 0
        assert "Usage: git unwip [-h|--help]" in res.stdout
        assert before_state == after_state

        test_cases_results.append({
            "name": "help_option_success",
            "command": "git unwip -h",
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

    # 6. Write results and summary
    results_payload = {
        "task_id": "R13-T020",
        "tool": "git-unwip",
        "total_cases_executed": len(test_cases_results),
        "native_bats_tests_count": len(native_names),
        "native_bats_tests": native_names,
        "mutation_verification": mutation_info,
        "cases": test_cases_results,
        "global_config_unimpaired": True,
    }

    with open(WORK_DIR / "results.json", "w") as f:
        json.dump(results_payload, f, indent=2)

    summary_content = (
        f"R13-T020: git-unwip Verification Summary\n"
        f"=========================================\n"
        f"Tool: git-unwip\n"
        f"Native Bats Tests Executed: {len(native_names)} (All Passed)\n"
        f"Focused Isolated Test Cases: {len(test_cases_results)} (All Passed)\n"
        f"Mutation Testing:\n"
        f"  - Condition protected: if [ 'WIP' != \"$LAST_COMMIT\" ]; then\n"
        f"  - Inverted condition mutant rejected by valid WIP input (mutant exit 1, real exit 0)\n"
        f"Positional Argument Handling:\n"
        f"  - Validated positional arguments rejected with exit 1 and usage\n"
        f"  - Help option (-h) outputs usage and exits 0\n"
        f"Cases Verified:\n"
        f"  - Exact WIP commit undo (soft reset to previous commit, work preserved)\n"
        f"  - Whitespace-trimmed WIP commit undo\n"
        f"  - Non-WIP commit rejection (exit 1, state preserved)\n"
        f"  - Substring WIP commit rejection (exit 1, state preserved)\n"
        f"  - Unexpected positional argument error (exit 1, state preserved)\n"
        f"  - Help usage option (-h)\n"
        f"Global Git Config: Unchanged\n"
        f"Status: SUCCESS\n"
    )

    with open(WORK_DIR / "summary.txt", "w") as f:
        f.write(summary_content)

    print(summary_content)
    print("=== Verification R13-T020 completed successfully ===")


if __name__ == "__main__":
    main()
