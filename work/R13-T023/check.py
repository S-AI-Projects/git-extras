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

def snapshot_repo_state(repo_dir, env):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_dir, text=True, env=env).strip()
    refs = subprocess.check_output(["git", "show-ref"], cwd=repo_dir, text=True, env=env).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_dir, text=True, env=env).strip()
    config = subprocess.check_output(["git", "config", "--list"], cwd=repo_dir, text=True, env=env).strip()
    return {
        "head": head,
        "refs": refs,
        "status": status,
        "config": config
    }

def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    work_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(work_dir, exist_ok=True)

    print("[*] Running check for R13-T023 (git-info)...")
    tool_versions = get_tool_versions(repo_root)
    print(f"[*] Tool versions: {tool_versions}")

    cases_executed = []
    total_assertions = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["HOME"] = tmpdir
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = os.path.join(tmpdir, ".gitconfig")

        install_bin = prepare_command(repo_root, tmpdir, "info")
        env["PATH"] = f"{install_bin}:{os.path.join(repo_root, 'bin')}:{env.get('PATH', '')}"

        local_repo = os.path.join(tmpdir, "repo")
        os.makedirs(local_repo, exist_ok=True)
        subprocess.run(["git", "init", "--initial-branch", "main"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=local_repo, env=env, check=True, capture_output=True)

        unrelated_file = os.path.join(local_repo, "unrelated_file.txt")
        with open(unrelated_file, "w") as f:
            f.write("Important data that must remain unchanged\n")
        subprocess.run(["git", "add", "."], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit on main"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "branch", "feature-x"], cwd=local_repo, env=env, check=True, capture_output=True)

        # Case 1: Standard git-info execution with state verification
        state_before = snapshot_repo_state(local_repo, env)
        code, stdout, stderr = run_cmd(["git", "info"], cwd=local_repo, env=env)
        state_after = snapshot_repo_state(local_repo, env)

        assert code == 0, f"Expected git-info to exit 0, got {code}"
        assert "Remote URLs:" in stdout, "Expected 'Remote URLs:' in output"
        assert "Local Branches:" in stdout, "Expected 'Local Branches:' in output"
        assert "Configuration (.git/config):" in stdout, "Expected 'Configuration (.git/config):' in output"
        assert state_before["head"] == state_after["head"], "HEAD commit SHA unexpectedly changed"
        assert state_before["refs"] == state_after["refs"], "Git refs unexpectedly changed"
        assert state_before["status"] == state_after["status"], "Working tree status unexpectedly changed"
        assert state_before["config"] == state_after["config"], "Git configuration unexpectedly changed"
        with open(unrelated_file, "r") as f:
            assert f.read() == "Important data that must remain unchanged\n", "Unrelated file content altered"
        total_assertions += 9

        cases_executed.append({
            "name": "standard_git_info_state_invariants",
            "type": "state_transition_success",
            "command": "git info",
            "actual_args": [],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "state_before": state_before,
            "state_after": state_after,
            "unrelated_state_preserved": True,
            "passed": True
        })
        print("[+] Case 1 passed: git info succeeds and leaves repository state strictly unchanged.")

        # Case 2: git-info with --no-config
        state_before = snapshot_repo_state(local_repo, env)
        code, stdout, stderr = run_cmd(["git", "info", "--no-config"], cwd=local_repo, env=env)
        state_after = snapshot_repo_state(local_repo, env)

        assert code == 0, f"Expected git-info --no-config to exit 0, got {code}"
        assert "Local Branches:" in stdout, "Expected 'Local Branches:' in output"
        assert "Configuration (.git/config):" not in stdout, "Expected configuration section to be suppressed"
        assert state_before == state_after, "State changed after git-info --no-config"
        total_assertions += 4

        cases_executed.append({
            "name": "git_info_no_config_suppression",
            "type": "state_transition_success",
            "command": "git info --no-config",
            "actual_args": ["--no-config"],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "config_suppressed": True,
            "unrelated_state_preserved": True,
            "passed": True
        })
        print("[+] Case 2 passed: git info --no-config suppresses config and preserves state.")

        # Case 3: Documented failure/edge-state outside git repository
        non_git_dir = os.path.join(tmpdir, "not_a_repo")
        os.makedirs(non_git_dir, exist_ok=True)
        code, stdout, stderr = run_cmd(["git", "info"], cwd=non_git_dir, env=env)

        assert code != 0, f"Expected non-zero exit code outside git repo, got {code}"
        assert not os.path.exists(os.path.join(non_git_dir, ".git")), "No git repository created on failure"
        total_assertions += 2

        cases_executed.append({
            "name": "git_info_non_git_repository_failure",
            "type": "failure_edge_state",
            "command": "git info",
            "cwd": "not_a_repo",
            "actual_args": [],
            "expected_exit_code": "non-zero",
            "actual_exit_code": code,
            "unrelated_state_preserved": True,
            "passed": True
        })
        print("[+] Case 3 passed: git info properly rejected outside git repository.")

    # Rejection of zero-case run
    if len(cases_executed) == 0 or total_assertions == 0:
        print("[!] ERROR: Zero-case run rejected!", file=sys.stderr)
        sys.exit(1)

    # Invoke Bats native tests
    bats_bin = shutil.which("bats")
    bats_test_file = os.path.join(repo_root, "tests/git-info.bats")
    bats_result = subprocess.run([bats_bin, bats_test_file], cwd=repo_root, capture_output=True, text=True)
    print(f"[*] Native Bats execution:\n{bats_result.stdout}")
    if bats_result.returncode != 0:
        print(f"[!] Bats tests failed:\n{bats_result.stderr}", file=sys.stderr)
        sys.exit(bats_result.returncode)

    report = {
        "task": "R13-T023",
        "target": "man/git-info.md",
        "tool_versions": tool_versions,
        "total_cases": len(cases_executed),
        "total_assertions": total_assertions,
        "cases": cases_executed,
        "bats_suite": {
            "file": "tests/git-info.bats",
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
