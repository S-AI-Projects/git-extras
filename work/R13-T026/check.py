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

def prepare_command(repo_root, tmpdir, cmd_names):
    install_bin = os.path.join(tmpdir, "install_bin")
    os.makedirs(install_bin, exist_ok=True)
    for cmd_name in cmd_names:
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

    print("[*] Running check for R13-T026 (git-delete-submodule)...")
    tool_versions = get_tool_versions(repo_root)
    print(f"[*] Tool versions: {tool_versions}")

    cases_executed = []
    total_assertions = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["HOME"] = tmpdir
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = os.path.join(tmpdir, ".gitconfig")

        install_bin = prepare_command(repo_root, tmpdir, ["delete-submodule", "root"])
        env["PATH"] = f"{install_bin}:{os.path.join(repo_root, 'bin')}:{env.get('PATH', '')}"

        local_repo = os.path.join(tmpdir, "main_repo")
        os.makedirs(local_repo, exist_ok=True)
        subprocess.run(["git", "init", "--initial-branch", "main"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=local_repo, env=env, check=True, capture_output=True)

        with open(os.path.join(local_repo, "init.txt"), "w") as f:
            f.write("Initial\n")
        subprocess.run(["git", "add", "."], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=local_repo, env=env, check=True, capture_output=True)

        # Case 1: Missing argument failure
        code, stdout, stderr = run_cmd(["git", "delete-submodule"], cwd=local_repo, env=env)
        assert code == 1, f"Expected exit code 1, got {code}"
        assert "Submodule required" in stderr, f"Expected 'Submodule required' in stderr: {stderr}"
        total_assertions += 2
        cases_executed.append({
            "name": "missing_submodule_argument_failure",
            "type": "characterization_failure",
            "command": "git delete-submodule",
            "actual_args": [],
            "expected_exit_code": 1,
            "actual_exit_code": code,
            "passed": True
        })
        print("[+] Case 1 passed: Missing submodule argument fails with code 1.")

        # Case 2: Missing .gitmodules file failure
        code, stdout, stderr = run_cmd(["git", "delete-submodule", "sub"], cwd=local_repo, env=env)
        assert code == 2, f"Expected exit code 2, got {code}"
        assert ".gitmodules file not found" in stderr, f"Expected '.gitmodules file not found' in stderr: {stderr}"
        total_assertions += 2
        cases_executed.append({
            "name": "missing_gitmodules_file_failure",
            "type": "characterization_failure",
            "command": "git delete-submodule sub",
            "actual_args": ["sub"],
            "expected_exit_code": 2,
            "actual_exit_code": code,
            "passed": True
        })
        print("[+] Case 2 passed: Missing .gitmodules fails with code 2.")

        # Case 3: Submodule not found in .gitmodules failure
        with open(os.path.join(local_repo, ".gitmodules"), "w") as f:
            f.write("# empty gitmodules\n")
        subprocess.run(["git", "add", ".gitmodules"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add dummy gitmodules"], cwd=local_repo, env=env, check=True, capture_output=True)

        code, stdout, stderr = run_cmd(["git", "delete-submodule", "nonexistent"], cwd=local_repo, env=env)
        assert code == 3, f"Expected exit code 3, got {code}"
        assert "Submodule not found" in stderr, f"Expected 'Submodule not found' in stderr: {stderr}"
        total_assertions += 2
        cases_executed.append({
            "name": "submodule_not_found_failure",
            "type": "characterization_failure",
            "command": "git delete-submodule nonexistent",
            "actual_args": ["nonexistent"],
            "expected_exit_code": 3,
            "actual_exit_code": code,
            "passed": True
        })
        print("[+] Case 3 passed: Submodule not found in .gitmodules fails with code 3.")

        # Case 4: Successful submodule deletion
        sub_repo = os.path.join(tmpdir, "sub_repo")
        os.makedirs(sub_repo, exist_ok=True)
        subprocess.run(["git", "init", "--initial-branch", "main"], cwd=sub_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Sub User"], cwd=sub_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "sub@example.com"], cwd=sub_repo, env=env, check=True, capture_output=True)
        with open(os.path.join(sub_repo, "sub_file.txt"), "w") as f:
            f.write("sub content\n")
        subprocess.run(["git", "add", "."], cwd=sub_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Sub initial commit"], cwd=sub_repo, env=env, check=True, capture_output=True)

        subprocess.run(["git", "-c", "protocol.file.allow=always", "submodule", "add", sub_repo, "my_sub"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add submodule my_sub"], cwd=local_repo, env=env, check=True, capture_output=True)

        assert os.path.exists(os.path.join(local_repo, "my_sub")), "Submodule dir should exist before deletion"

        code, stdout, stderr = run_cmd(["git", "delete-submodule", "my_sub"], cwd=local_repo, env=env)
        assert code == 0, f"Expected exit code 0 on deletion, got {code}, stderr: {stderr}"
        assert "Successfully deleted my_sub." in stdout, f"Success message not in stdout: {stdout}"
        assert not os.path.exists(os.path.join(local_repo, "my_sub")), "Submodule directory should be deleted"
        total_assertions += 4
        cases_executed.append({
            "name": "successful_submodule_deletion",
            "type": "characterization_success",
            "command": "git delete-submodule my_sub",
            "actual_args": ["my_sub"],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "passed": True
        })
        print("[+] Case 4 passed: Submodule successfully deleted and state cleaned up.")

    # Rejection of zero-case run
    if len(cases_executed) == 0 or total_assertions == 0:
        print("[!] ERROR: Zero-case run rejected!", file=sys.stderr)
        sys.exit(1)

    # Invoke Bats native tests
    bats_bin = shutil.which("bats")
    bats_test_file = os.path.join(repo_root, "tests/git-delete-submodule.bats")
    bats_result = subprocess.run([bats_bin, bats_test_file], cwd=repo_root, capture_output=True, text=True)
    print(f"[*] Native Bats execution:\n{bats_result.stdout}")
    if bats_result.returncode != 0:
        print(f"[!] Bats tests failed:\n{bats_result.stderr}", file=sys.stderr)
        sys.exit(bats_result.returncode)

    report = {
        "task": "R13-T026",
        "target": "man/git-delete-submodule.md",
        "tool_versions": tool_versions,
        "total_cases": len(cases_executed),
        "total_assertions": total_assertions,
        "cases": cases_executed,
        "bats_suite": {
            "file": "tests/git-delete-submodule.bats",
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
