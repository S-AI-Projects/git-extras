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

def prepare_command(repo_root, tmpdir, cmd_name):
    install_bin = os.path.join(tmpdir, "install_bin")
    os.makedirs(install_bin, exist_ok=True)
    target = os.path.join(install_bin, f"git-{cmd_name}")
    src = os.path.join(repo_root, "bin", f"git-{cmd_name}")

    with open(src, "r") as f:
        lines = f.readlines()

    with open(target, "w") as out:
        out.write(lines[0])
        for helper in ["helper/reset-env", "helper/git-extra-utility", "helper/is-git-repo", "helper/has-git-commit"]:
            helper_path = os.path.join(repo_root, helper)
            if os.path.exists(helper_path):
                with open(helper_path, "r") as hf:
                    out.write(hf.read())
                    out.write("\n")
        out.writelines(lines[1:])
    os.chmod(target, 0o755)
    return install_bin

def run_cmd(args, cwd, env=None):
    res = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    work_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(work_dir, exist_ok=True)

    print("[*] Running check for R13-T025 (git-show-merged-branches)...")
    tool_versions = get_tool_versions(repo_root)
    print(f"[*] Tool versions: {tool_versions}")

    cases_executed = []
    total_assertions = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["HOME"] = tmpdir
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = os.path.join(tmpdir, ".gitconfig")

        install_bin = prepare_command(repo_root, tmpdir, "show-merged-branches")
        env["PATH"] = f"{install_bin}:{os.path.join(repo_root, 'bin')}:{env.get('PATH', '')}"

        local_repo = os.path.join(tmpdir, "repo")
        os.makedirs(local_repo, exist_ok=True)
        subprocess.run(["git", "init", "--initial-branch", "main"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=local_repo, env=env, check=True, capture_output=True)

        with open(os.path.join(local_repo, "init.txt"), "w") as f:
            f.write("Initial\n")
        subprocess.run(["git", "add", "."], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=local_repo, env=env, check=True, capture_output=True)

        subprocess.run(["git", "branch", "feature-merged"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "-b", "feature-unmerged"], cwd=local_repo, env=env, check=True, capture_output=True)
        with open(os.path.join(local_repo, "unmerged.txt"), "w") as f:
            f.write("Unmerged\n")
        subprocess.run(["git", "add", "."], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Unmerged commit"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=local_repo, env=env, check=True, capture_output=True)

        # Case 1: Standard successful run
        code, stdout, stderr = run_cmd(["git", "show-merged-branches"], cwd=local_repo, env=env)
        assert code == 0, f"Expected exit code 0, got {code}"
        assert "feature-merged" in stdout, "Expected 'feature-merged' in output"
        assert "feature-unmerged" not in stdout, "'feature-unmerged' should not be listed"
        assert "main" not in stdout, "Default branch 'main' should not be listed"
        total_assertions += 4
        cases_executed.append({
            "name": "standard_merged_branches_success",
            "type": "standard_success",
            "command": "git show-merged-branches",
            "actual_args": [],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "passed": True
        })
        print("[+] Case 1 passed: Standard merged branch listing succeeds.")

        # Case 2: Deterministic local config overriding default branch
        subprocess.run(["git", "config", "git-extras.default-branch", "feature-merged"], cwd=local_repo, env=env, check=True, capture_output=True)
        code, stdout, stderr = run_cmd(["git", "show-merged-branches"], cwd=local_repo, env=env)
        assert code == 0, f"Expected exit code 0, got {code}"
        assert "feature-merged" not in stdout, "'feature-merged' should be excluded as configured default branch"
        total_assertions += 2
        cases_executed.append({
            "name": "deterministic_local_config_isolation",
            "type": "config_isolation_success",
            "command": "git show-merged-branches (with git-extras.default-branch=feature-merged)",
            "actual_args": [],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "passed": True
        })
        print("[+] Case 2 passed: Local configuration deterministically isolates default branch.")

        # Restore local config
        subprocess.run(["git", "config", "--unset", "git-extras.default-branch"], cwd=local_repo, env=env, check=True, capture_output=True)

        # Case 3: Explicit target commit argument
        code, stdout, stderr = run_cmd(["git", "show-merged-branches", "main"], cwd=local_repo, env=env)
        assert code == 0, f"Expected exit code 0 with explicit target, got {code}"
        assert "feature-merged" in stdout, "Expected 'feature-merged' in output with explicit target"
        total_assertions += 2
        cases_executed.append({
            "name": "explicit_target_branch_success",
            "type": "argument_success",
            "command": "git show-merged-branches main",
            "actual_args": ["main"],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "passed": True
        })
        print("[+] Case 3 passed: Explicit target commit argument succeeds.")

        # Case 4: Missing-dependency branch (stubbed grep failure)
        stub_cmd = [
            "bash", "-c",
            """
            command() {
                if [ "$1" = "-v" ] && [ "$2" = "grep" ]; then
                    return 1
                fi
                builtin command "$@"
            }
            export -f command
            git show-merged-branches
            """
        ]
        code, stdout, stderr = run_cmd(stub_cmd, cwd=local_repo, env=env)
        assert code == 1, f"Expected exit code 1 for missing grep dependency, got {code}"
        assert "grep required." in stderr, f"Expected 'grep required.' in stderr, got: {stderr}"
        total_assertions += 2
        cases_executed.append({
            "name": "missing_grep_dependency_failure",
            "type": "missing_dependency_failure",
            "command": "git show-merged-branches (stubbed missing grep)",
            "actual_args": [],
            "expected_exit_code": 1,
            "actual_exit_code": code,
            "expected_stderr": "grep required.",
            "passed": True
        })
        print("[+] Case 4 passed: Missing dependency branch handled with exit code 1.")

    # Rejection of zero-case run
    if len(cases_executed) == 0 or total_assertions == 0:
        print("[!] ERROR: Zero-case run rejected!", file=sys.stderr)
        sys.exit(1)

    # Invoke Bats native tests
    bats_bin = shutil.which("bats")
    bats_test_file = os.path.join(repo_root, "tests/git-show-merged-branches.bats")
    bats_result = subprocess.run([bats_bin, bats_test_file], cwd=repo_root, capture_output=True, text=True)
    print(f"[*] Native Bats execution:\n{bats_result.stdout}")
    if bats_result.returncode != 0:
        print(f"[!] Bats tests failed:\n{bats_result.stderr}", file=sys.stderr)
        sys.exit(bats_result.returncode)

    report = {
        "task": "R13-T025",
        "target": "man/git-show-merged-branches.md",
        "tool_versions": tool_versions,
        "total_cases": len(cases_executed),
        "total_assertions": total_assertions,
        "cases": cases_executed,
        "bats_suite": {
            "file": "tests/git-show-merged-branches.bats",
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
