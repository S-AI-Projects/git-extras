#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time


def get_tool_versions(repo_root):
    versions = {}
    for cmd in ["git", "bats", "bash", "python3"]:
        try:
            res = subprocess.run([cmd, "--version"], capture_output=True, text=True, check=True)
            versions[cmd] = res.stdout.strip().split("\n")[0]
        except Exception as e:
            versions[cmd] = f"unknown ({e})"
    return versions


def run_cmd(args, cwd, env=None):
    res = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def get_repo_state(repo_dir, env):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_dir, text=True, env=env).strip()
    branches = subprocess.check_output(["git", "branch", "--list"], cwd=repo_dir, text=True, env=env).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_dir, text=True, env=env).strip()
    return {
        "head_commit": head,
        "branches": branches,
        "working_tree_clean": status == "",
    }


def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    work_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(work_dir, exist_ok=True)

    print("[*] Running check for R13-T028 (git-standup)...")
    tool_versions = get_tool_versions(repo_root)
    print(f"[*] Tool versions: {tool_versions}")

    cases_executed = []
    total_assertions = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["HOME"] = tmpdir
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = os.path.join(tmpdir, ".gitconfig")
        env["PATH"] = f"{os.path.join(repo_root, 'bin')}:{env.get('PATH', '')}"
        env["GIT_AUTHOR_NAME"] = "Test Author"
        env["GIT_AUTHOR_EMAIL"] = "author@example.com"
        env["GIT_COMMITTER_NAME"] = "Test Author"
        env["GIT_COMMITTER_EMAIL"] = "author@example.com"

        local_repo = os.path.join(tmpdir, "local_repo")
        os.makedirs(local_repo, exist_ok=True)

        subprocess.run(["git", "init", "--initial-branch", "main"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test Author"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "author@example.com"], cwd=local_repo, env=env, check=True, capture_output=True)

        test_file = os.path.join(local_repo, "sample.txt")
        with open(test_file, "w") as f:
            f.write("sample content\n")
        subprocess.run(["git", "add", "."], cwd=local_repo, env=env, check=True, capture_output=True)

        commit_ts = str(int(time.time()) - 86400)
        commit_env = env.copy()
        commit_env["GIT_AUTHOR_DATE"] = f"@{commit_ts}"
        commit_env["GIT_COMMITTER_DATE"] = f"@{commit_ts}"
        subprocess.run(["git", "commit", "-m", "Sample commit for standup"], cwd=local_repo, env=commit_env, check=True, capture_output=True)

        # Case 1: Failure/Edge-state: invalid invocation -d 0 fails with diagnostic message
        state_before = get_repo_state(local_repo, env)
        code, stdout, stderr = run_cmd(["git", "standup", "-d", "0"], cwd=local_repo, env=env)
        state_after = get_repo_state(local_repo, env)

        assert code == 1, f"Expected exit code 1, got {code}"
        assert "Specify days less than one is invalid" in stderr, f"Expected diagnostic message in stderr: {stderr}"
        assert "-d requires a positive integer" in stderr, f"Expected positive integer explanation in stderr: {stderr}"
        assert state_before == state_after, f"Repository state changed on invalid invocation: before='{state_before}', after='{state_after}'"
        total_assertions += 4

        cases_executed.append({
            "name": "invalid_invocation_fails_with_diagnostic",
            "type": "failure_edge_state",
            "command": "git standup -d 0",
            "actual_args": ["-d", "0"],
            "expected_exit_code": 1,
            "actual_exit_code": code,
            "expected_output_contains": "Specify days less than one is invalid: -d requires a positive integer",
            "actual_stderr": stderr.strip(),
            "actual_stdout": stdout.strip(),
            "state_before": state_before,
            "state_after": state_after,
            "passed": True,
        })
        print("[+] Case 1 passed: invalid -d 0 fails with diagnostic message and preserves repository state.")

        # Case 2: Success: corrected invocation -d 2 succeeds with commit output
        state_before = get_repo_state(local_repo, env)
        code, stdout, stderr = run_cmd(["git", "standup", "-d", "2"], cwd=local_repo, env=env)
        state_after = get_repo_state(local_repo, env)

        assert code == 0, f"Expected exit code 0, got {code}, stderr: {stderr}"
        assert "Sample commit for standup" in stdout, f"Expected commit summary in stdout: {stdout}"
        assert state_before == state_after, f"Repository state changed during read-only standup: before='{state_before}', after='{state_after}'"
        total_assertions += 3

        cases_executed.append({
            "name": "corrected_invocation_succeeds",
            "type": "ordinary_success",
            "command": "git standup -d 2",
            "actual_args": ["-d", "2"],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "expected_output_contains": "Sample commit for standup",
            "actual_stderr": stderr.strip(),
            "actual_stdout": stdout.strip(),
            "state_before": state_before,
            "state_after": state_after,
            "passed": True,
        })
        print("[+] Case 2 passed: corrected invocation -d 2 succeeds with commit output.")

        # Case 3: Success: standup with -a all succeeds
        state_before = get_repo_state(local_repo, env)
        code, stdout, stderr = run_cmd(["git", "standup", "-a", "all", "-d", "2"], cwd=local_repo, env=env)
        state_after = get_repo_state(local_repo, env)

        assert code == 0, f"Expected exit code 0, got {code}, stderr: {stderr}"
        assert "Sample commit for standup" in stdout, f"Expected commit summary in stdout: {stdout}"
        assert state_before == state_after, f"Repository state changed: before='{state_before}', after='{state_after}'"
        total_assertions += 3

        cases_executed.append({
            "name": "standup_all_authors_succeeds",
            "type": "ordinary_success",
            "command": "git standup -a all -d 2",
            "actual_args": ["-a", "all", "-d", "2"],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "expected_output_contains": "Sample commit for standup",
            "actual_stderr": stderr.strip(),
            "actual_stdout": stdout.strip(),
            "state_before": state_before,
            "state_after": state_after,
            "passed": True,
        })
        print("[+] Case 3 passed: standup with -a all succeeds.")

        # Case 4: Success: help invocation -h
        state_before = get_repo_state(local_repo, env)
        code, stdout, stderr = run_cmd(["git", "standup", "-h"], cwd=local_repo, env=env)
        state_after = get_repo_state(local_repo, env)

        assert code == 0, f"Expected exit code 0, got {code}, stderr: {stderr}"
        assert "Usage:" in stdout, f"Expected 'Usage:' in stdout: {stdout}"
        assert state_before == state_after, f"Repository state changed: before='{state_before}', after='{state_after}'"
        total_assertions += 3

        cases_executed.append({
            "name": "standup_help_succeeds",
            "type": "ordinary_success",
            "command": "git standup -h",
            "actual_args": ["-h"],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "expected_output_contains": "Usage:",
            "actual_stderr": stderr.strip(),
            "actual_stdout": stdout.strip(),
            "state_before": state_before,
            "state_after": state_after,
            "passed": True,
        })
        print("[+] Case 4 passed: standup help screen succeeds.")

    # Rejection of zero-case run
    if len(cases_executed) == 0 or total_assertions == 0:
        print("[!] ERROR: Zero-case run rejected!", file=sys.stderr)
        sys.exit(1)

    # Invoke native Bats test suite
    bats_bin = shutil.which("bats")
    bats_test_file = os.path.join(repo_root, "tests/git-standup.bats")
    bats_result = subprocess.run([bats_bin, bats_test_file], cwd=repo_root, capture_output=True, text=True)
    print(f"[*] Native Bats execution:\n{bats_result.stdout}")
    if bats_result.returncode != 0:
        print(f"[!] Bats test suite failed:\n{bats_result.stderr}", file=sys.stderr)
        sys.exit(bats_result.returncode)

    report = {
        "task": "R13-T028",
        "target": "bin/git-standup",
        "tool_versions": tool_versions,
        "total_cases": len(cases_executed),
        "total_assertions": total_assertions,
        "cases": cases_executed,
        "bats_suite": {
            "file": "tests/git-standup.bats",
            "exit_code": bats_result.returncode,
            "stdout": bats_result.stdout.strip(),
        },
        "all_passed": True,
    }

    report_path = os.path.join(work_dir, "results.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"[*] Report saved to {report_path}")
    print(f"[SUCCESS] All {len(cases_executed)} cases and {total_assertions} assertions passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
