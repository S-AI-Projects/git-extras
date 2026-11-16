#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile

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

def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    work_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(work_dir, exist_ok=True)

    print(f"[*] Running check for R13-T021 (git-delete-branch)...")
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

        # Setup bare remote repo
        bare_remote = os.path.join(tmpdir, "remote.git")
        subprocess.run(["git", "init", "--bare", bare_remote], cwd=tmpdir, env=env, check=True, capture_output=True)

        # Setup local test repo
        local_repo = os.path.join(tmpdir, "local_repo")
        os.makedirs(local_repo, exist_ok=True)
        subprocess.run(["git", "init", "--initial-branch", "main"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", bare_remote], cwd=local_repo, env=env, check=True, capture_output=True)

        # Initial commit on main and push to remote
        test_file = os.path.join(local_repo, "file.txt")
        with open(test_file, "w") as f:
            f.write("hello\n")
        subprocess.run(["git", "add", "."], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=local_repo, env=env, check=True, capture_output=True)

        # Case 1: Failure/Edge-state: missing argument
        before_branches = subprocess.check_output(["git", "branch", "--list"], cwd=local_repo, text=True, env=env).strip()
        code, stdout, stderr = run_cmd(["git", "delete-branch"], cwd=local_repo, env=env)
        after_branches = subprocess.check_output(["git", "branch", "--list"], cwd=local_repo, text=True, env=env).strip()

        assert code == 1, f"Expected exit code 1, got {code}"
        assert "branch required." in stderr or "branch required." in stdout, f"Expected 'branch required.' in output, got stderr: {stderr}, stdout: {stdout}"
        assert before_branches == after_branches, f"Branches changed on failure: before='{before_branches}', after='{after_branches}'"
        total_assertions += 3

        cases_executed.append({
            "name": "missing_branch_argument_failure",
            "type": "failure_edge_state",
            "command": "git delete-branch",
            "actual_args": [],
            "expected_exit_code": 1,
            "actual_exit_code": code,
            "expected_output_contains": "branch required.",
            "actual_stderr": stderr.strip(),
            "actual_stdout": stdout.strip(),
            "state_before": {"branches": before_branches},
            "state_after": {"branches": after_branches},
            "passed": True
        })
        print(f"[+] Case 1 passed: missing argument correctly rejected with exit code 1.")

        # Case 2: Failure/Edge-state: empty string argument
        before_branches = subprocess.check_output(["git", "branch", "--list"], cwd=local_repo, text=True, env=env).strip()
        code, stdout, stderr = run_cmd(["git", "delete-branch", ""], cwd=local_repo, env=env)
        after_branches = subprocess.check_output(["git", "branch", "--list"], cwd=local_repo, text=True, env=env).strip()

        assert code == 1, f"Expected exit code 1, got {code}"
        assert "branch required." in stderr or "branch required." in stdout, f"Expected 'branch required.', got stderr: {stderr}, stdout: {stdout}"
        assert before_branches == after_branches, f"Branches changed on failure"
        total_assertions += 3

        cases_executed.append({
            "name": "empty_string_branch_argument_failure",
            "type": "failure_edge_state",
            "command": "git delete-branch ''",
            "actual_args": [""],
            "expected_exit_code": 1,
            "actual_exit_code": code,
            "expected_output_contains": "branch required.",
            "actual_stderr": stderr.strip(),
            "actual_stdout": stdout.strip(),
            "state_before": {"branches": before_branches},
            "state_after": {"branches": after_branches},
            "passed": True
        })
        print(f"[+] Case 2 passed: empty argument correctly rejected with exit code 1.")

        # Case 3: Success: delete single local branch
        subprocess.run(["git", "branch", "feature-local"], cwd=local_repo, env=env, check=True, capture_output=True)
        before_branches = subprocess.check_output(["git", "branch", "--list"], cwd=local_repo, text=True, env=env).strip()
        assert "feature-local" in before_branches, "feature-local was not created"

        code, stdout, stderr = run_cmd(["git", "delete-branch", "feature-local"], cwd=local_repo, env=env)
        after_branches = subprocess.check_output(["git", "branch", "--list"], cwd=local_repo, text=True, env=env).strip()

        assert code == 0, f"Expected exit code 0, got {code}, stderr: {stderr}"
        assert "feature-local" not in after_branches, f"feature-local was not deleted: {after_branches}"
        assert "main" in after_branches, f"main branch was accidentally deleted: {after_branches}"
        total_assertions += 4

        cases_executed.append({
            "name": "delete_single_local_branch_success",
            "type": "ordinary_success",
            "command": "git delete-branch feature-local",
            "actual_args": ["feature-local"],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "state_before": {"branches": before_branches},
            "state_after": {"branches": after_branches},
            "passed": True
        })
        print(f"[+] Case 3 passed: single local branch deleted successfully.")

        # Case 4: Success: delete local branch and remote tracking branch
        subprocess.run(["git", "checkout", "-b", "feature-remote"], cwd=local_repo, env=env, check=True, capture_output=True)
        with open(os.path.join(local_repo, "feature.txt"), "w") as f:
            f.write("feature commit\n")
        subprocess.run(["git", "add", "."], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Commit on feature-remote"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "push", "-u", "origin", "feature-remote"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=local_repo, env=env, check=True, capture_output=True)

        before_local = subprocess.check_output(["git", "branch", "--list"], cwd=local_repo, text=True, env=env).strip()
        before_remote = subprocess.check_output(["git", "branch", "-r"], cwd=local_repo, text=True, env=env).strip()
        assert "feature-remote" in before_local, "feature-remote not found in local"
        assert "origin/feature-remote" in before_remote, "origin/feature-remote not found in remote"

        code, stdout, stderr = run_cmd(["git", "delete-branch", "feature-remote"], cwd=local_repo, env=env)
        after_local = subprocess.check_output(["git", "branch", "--list"], cwd=local_repo, text=True, env=env).strip()
        after_remote = subprocess.check_output(["git", "branch", "-r"], cwd=local_repo, text=True, env=env).strip()
        remote_ls = subprocess.check_output(["git", "ls-remote", "--heads", "origin", "feature-remote"], cwd=local_repo, text=True, env=env).strip()

        assert code == 0, f"Expected exit code 0, got {code}, stderr: {stderr}"
        assert "feature-remote" not in after_local, f"feature-remote still present locally: {after_local}"
        assert "origin/feature-remote" not in after_remote, f"origin/feature-remote still present in remote tracking: {after_remote}"
        assert remote_ls == "", f"Remote branch still exists on bare origin: {remote_ls}"
        total_assertions += 5

        cases_executed.append({
            "name": "delete_remote_and_local_branch_success",
            "type": "ordinary_success",
            "command": "git delete-branch feature-remote",
            "actual_args": ["feature-remote"],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "state_before": {"local_branches": before_local, "remote_branches": before_remote},
            "state_after": {"local_branches": after_local, "remote_branches": after_remote, "remote_heads": remote_ls},
            "passed": True
        })
        print(f"[+] Case 4 passed: local and remote branches deleted successfully.")

    # Rejection of zero-case run
    if len(cases_executed) == 0 or total_assertions == 0:
        print("[!] ERROR: Zero-case run rejected!", file=sys.stderr)
        sys.exit(1)

    # Invoke native Bats test suite
    bats_bin = shutil.which("bats")
    bats_test_file = os.path.join(repo_root, "tests/git-delete-branch.bats")
    bats_result = subprocess.run([bats_bin, bats_test_file], cwd=repo_root, capture_output=True, text=True)
    print(f"[*] Native Bats execution:\n{bats_result.stdout}")
    if bats_result.returncode != 0:
        print(f"[!] Bats test suite failed:\n{bats_result.stderr}", file=sys.stderr)
        sys.exit(bats_result.returncode)

    report = {
        "task": "R13-T021",
        "target": "bin/git-delete-branch",
        "tool_versions": tool_versions,
        "total_cases": len(cases_executed),
        "total_assertions": total_assertions,
        "cases": cases_executed,
        "bats_suite": {
            "file": "tests/git-delete-branch.bats",
            "exit_code": bats_result.returncode,
            "stdout": bats_result.stdout.strip()
        },
        "all_passed": True
    }

    report_path = os.path.join(work_dir, "results.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"[*] Report saved to {report_path}")
    print(f"[SUCCESS] All {len(cases_executed)} cases and {total_assertions} assertions passed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
