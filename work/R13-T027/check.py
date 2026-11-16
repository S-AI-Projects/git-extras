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

    print("[*] Running check for R13-T027 (git-coauthor)...")
    tool_versions = get_tool_versions(repo_root)
    print(f"[*] Tool versions: {tool_versions}")

    cases_executed = []
    total_assertions = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["HOME"] = tmpdir
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = os.path.join(tmpdir, ".gitconfig")

        install_bin = prepare_command(repo_root, tmpdir, ["coauthor"])
        env["PATH"] = f"{install_bin}:{os.path.join(repo_root, 'bin')}:{env.get('PATH', '')}"

        local_repo = os.path.join(tmpdir, "repo")
        os.makedirs(local_repo, exist_ok=True)
        subprocess.run(["git", "init", "--initial-branch", "main"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=local_repo, env=env, check=True, capture_output=True)

        with open(os.path.join(local_repo, "init.txt"), "w") as f:
            f.write("Initial\n")
        subprocess.run(["git", "add", "."], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Implement authentication"], cwd=local_repo, env=env, check=True, capture_output=True)

        # Case 1: Missing co-author argument failure
        code, stdout, stderr = run_cmd(["git", "coauthor"], cwd=local_repo, env=env)
        assert code == 1, f"Expected exit code 1, got {code}"
        assert "co-author required." in stderr, f"Expected 'co-author required.' in stderr: {stderr}"
        total_assertions += 2
        cases_executed.append({
            "name": "missing_coauthor_name_failure",
            "type": "documented_failure",
            "command": "git coauthor",
            "actual_args": [],
            "expected_exit_code": 1,
            "actual_exit_code": code,
            "passed": True
        })
        print("[+] Case 1 passed: Missing co-author name exits 1.")

        # Case 2: Missing email argument failure
        code, stdout, stderr = run_cmd(["git", "coauthor", "Jane Doe"], cwd=local_repo, env=env)
        assert code == 1, f"Expected exit code 1, got {code}"
        assert "co-author email required." in stderr, f"Expected 'co-author email required.' in stderr: {stderr}"
        total_assertions += 2
        cases_executed.append({
            "name": "missing_coauthor_email_failure",
            "type": "documented_failure",
            "command": "git coauthor 'Jane Doe'",
            "actual_args": ["Jane Doe"],
            "expected_exit_code": 1,
            "actual_exit_code": code,
            "passed": True
        })
        print("[+] Case 2 passed: Missing co-author email exits 1.")

        # Case 3: Execute exact documented usage example
        msg_before = subprocess.check_output(["git", "log", "-n", "1", "--format=%B"], cwd=local_repo, text=True, env=env).strip()
        code, stdout, stderr = run_cmd(["git", "coauthor", "Jane Doe", "jane@example.com"], cwd=local_repo, env=env)
        msg_after = subprocess.check_output(["git", "log", "-n", "1", "--format=%B"], cwd=local_repo, text=True, env=env).strip()

        assert code == 0, f"Expected exit code 0, got {code}, stderr: {stderr}"
        assert "Implement authentication" in msg_after, "Original commit title missing"
        assert "Co-authored-by: Jane Doe <jane@example.com>" in msg_after, "Co-author trailer missing"
        total_assertions += 3
        cases_executed.append({
            "name": "documented_usage_example_success",
            "type": "documented_example_success",
            "command": "git coauthor 'Jane Doe' jane@example.com",
            "actual_args": ["Jane Doe", "jane@example.com"],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "message_before": msg_before,
            "message_after": msg_after,
            "passed": True
        })
        print("[+] Case 3 passed: Documented usage example executes successfully and verifies commit message state.")

        # Case 4: Multiple co-authors appended
        code, stdout, stderr = run_cmd(["git", "coauthor", "Bob Smith", "bob@example.com"], cwd=local_repo, env=env)
        msg_multi = subprocess.check_output(["git", "log", "-n", "1", "--format=%B"], cwd=local_repo, text=True, env=env).strip()

        assert code == 0, f"Expected exit code 0 on second coauthor, got {code}"
        assert "Co-authored-by: Jane Doe <jane@example.com>" in msg_multi, "First co-author missing"
        assert "Co-authored-by: Bob Smith <bob@example.com>" in msg_multi, "Second co-author missing"
        total_assertions += 3
        cases_executed.append({
            "name": "append_multiple_coauthors_success",
            "type": "documented_example_success",
            "command": "git coauthor 'Bob Smith' bob@example.com",
            "actual_args": ["Bob Smith", "bob@example.com"],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "message_after": msg_multi,
            "passed": True
        })
        print("[+] Case 4 passed: Multiple co-authors appended successfully.")

    # Rejection of zero-case run
    if len(cases_executed) == 0 or total_assertions == 0:
        print("[!] ERROR: Zero-case run rejected!", file=sys.stderr)
        sys.exit(1)

    # Invoke Bats native tests
    bats_bin = shutil.which("bats")
    bats_test_file = os.path.join(repo_root, "tests/git-coauthor.bats")
    bats_result = subprocess.run([bats_bin, bats_test_file], cwd=repo_root, capture_output=True, text=True)
    print(f"[*] Native Bats execution:\n{bats_result.stdout}")
    if bats_result.returncode != 0:
        print(f"[!] Bats tests failed:\n{bats_result.stderr}", file=sys.stderr)
        sys.exit(bats_result.returncode)

    report = {
        "task": "R13-T027",
        "target": "bin/git-coauthor",
        "tool_versions": tool_versions,
        "total_cases": len(cases_executed),
        "total_assertions": total_assertions,
        "cases": cases_executed,
        "bats_suite": {
            "file": "tests/git-coauthor.bats",
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
