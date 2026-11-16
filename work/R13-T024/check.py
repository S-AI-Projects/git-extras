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

    print("[*] Running check for R13-T024 (git-contrib)...")
    tool_versions = get_tool_versions(repo_root)
    print(f"[*] Tool versions: {tool_versions}")

    cases_executed = []
    total_assertions = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["HOME"] = tmpdir
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = os.path.join(tmpdir, ".gitconfig")

        install_bin = prepare_command(repo_root, tmpdir, "contrib")
        env["PATH"] = f"{install_bin}:{os.path.join(repo_root, 'bin')}:{env.get('PATH', '')}"

        # Create repo in path containing spaces
        local_repo = os.path.join(tmpdir, "repo with spaces")
        os.makedirs(local_repo, exist_ok=True)
        subprocess.run(["git", "init", "--initial-branch", "main"], cwd=local_repo, env=env, check=True, capture_output=True)

        # Commits from Jane Doe
        subprocess.run(["git", "config", "user.name", "Jane Doe"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "jane@example.com"], cwd=local_repo, env=env, check=True, capture_output=True)

        dir_with_spaces = os.path.join(local_repo, "docs and guides")
        os.makedirs(dir_with_spaces, exist_ok=True)
        spaced_file = os.path.join(dir_with_spaces, "guide with space.txt")
        with open(spaced_file, "w") as f:
            f.write("Jane's guide content\n")
        subprocess.run(["git", "add", "."], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Jane commit: add guide with space"], cwd=local_repo, env=env, check=True, capture_output=True)

        # Commits from John Smith
        subprocess.run(["git", "config", "user.name", "John Smith"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "john@example.com"], cwd=local_repo, env=env, check=True, capture_output=True)
        other_file = os.path.join(local_repo, "other.txt")
        with open(other_file, "w") as f:
            f.write("John's content\n")
        subprocess.run(["git", "add", "."], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "John commit: add other file"], cwd=local_repo, env=env, check=True, capture_output=True)

        # Create a working directory file matching wildcard 'Jane*' to assert no glob expansion
        wildcard_file = os.path.join(local_repo, "Jane Doe.txt")
        with open(wildcard_file, "w") as f:
            f.write("This file must not expand into command line arguments\n")

        # Case 1: Failure/Edge-state: missing argument
        code, stdout, stderr = run_cmd(["git", "contrib"], cwd=local_repo, env=env)
        assert code == 1, f"Expected exit code 1 for missing user, got {code}"
        assert "user name required." in stderr, f"Expected 'user name required.' in stderr, got: {stderr}"
        total_assertions += 2
        cases_executed.append({
            "name": "missing_username_failure",
            "type": "failure_edge_state",
            "command": "git contrib",
            "actual_args": [],
            "expected_exit_code": 1,
            "actual_exit_code": code,
            "passed": True
        })
        print("[+] Case 1 passed: missing username exits 1 with required message.")

        # Case 2: Author name with spaces
        code, stdout, stderr = run_cmd(["git", "contrib", "Jane Doe"], cwd=local_repo, env=env)
        assert code == 0, f"Expected exit code 0, got {code}, stderr: {stderr}"
        assert "Jane commit: add guide with space" in stdout, f"Commit not found in output: {stdout}"
        assert "John commit" not in stdout, "John commit should not appear for Jane Doe"
        total_assertions += 3
        cases_executed.append({
            "name": "author_with_spaces_success",
            "type": "quoted_argument_success",
            "command": "git contrib 'Jane Doe'",
            "actual_args": ["Jane Doe"],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "passed": True
        })
        print("[+] Case 2 passed: author name with spaces preserves exact argument boundaries.")

        # Case 3: Wildcard pattern in argument with file existing in directory
        code, stdout, stderr = run_cmd(["git", "contrib", "Jane*"], cwd=local_repo, env=env)
        assert code == 0, f"Expected exit code 0, got {code}, stderr: {stderr}"
        assert "Jane commit: add guide with space" in stdout, f"Commit not found for wildcard author: {stdout}"
        assert "John commit" not in stdout, "John commit should not appear for Jane*"
        # Check that unrelated wildcard file remains untouched
        assert os.path.exists(wildcard_file), "Unrelated file unexpectedly modified or removed"
        with open(wildcard_file, "r") as f:
            assert f.read() == "This file must not expand into command line arguments\n", "Unrelated file modified"
        total_assertions += 4
        cases_executed.append({
            "name": "wildcard_author_argument_success",
            "type": "wildcard_argument_success",
            "command": "git contrib 'Jane*'",
            "actual_args": ["Jane*"],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "unrelated_files_preserved": True,
            "passed": True
        })
        print("[+] Case 3 passed: wildcard argument preserved and unrelated files unaffected.")

        # Case 4: Path containing spaces after double dash
        code, stdout, stderr = run_cmd(["git", "contrib", "Jane Doe", "--", "docs and guides/guide with space.txt"], cwd=local_repo, env=env)
        assert code == 0, f"Expected exit code 0, got {code}, stderr: {stderr}"
        assert "Jane commit: add guide with space" in stdout, "Expected commit in path search"

        code_empty, stdout_empty, _ = run_cmd(["git", "contrib", "John Smith", "--", "docs and guides/guide with space.txt"], cwd=local_repo, env=env)
        assert code_empty == 0
        assert stdout_empty.strip() == "", f"Expected empty output for John on Jane's file, got: {stdout_empty}"
        total_assertions += 3
        cases_executed.append({
            "name": "path_with_spaces_after_double_dash",
            "type": "path_quoting_success",
            "command": "git contrib 'Jane Doe' -- 'docs and guides/guide with space.txt'",
            "actual_args": ["Jane Doe", "--", "docs and guides/guide with space.txt"],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "passed": True
        })
        print("[+] Case 4 passed: path containing spaces correctly preserved.")

    # Rejection of zero-case run
    if len(cases_executed) == 0 or total_assertions == 0:
        print("[!] ERROR: Zero-case run rejected!", file=sys.stderr)
        sys.exit(1)

    # Invoke Bats native tests
    bats_bin = shutil.which("bats")
    bats_test_file = os.path.join(repo_root, "tests/git-contrib.bats")
    bats_result = subprocess.run([bats_bin, bats_test_file], cwd=repo_root, capture_output=True, text=True)
    print(f"[*] Native Bats execution:\n{bats_result.stdout}")
    if bats_result.returncode != 0:
        print(f"[!] Bats tests failed:\n{bats_result.stderr}", file=sys.stderr)
        sys.exit(bats_result.returncode)

    report = {
        "task": "R13-T024",
        "target": "man/git-contrib.md",
        "tool_versions": tool_versions,
        "total_cases": len(cases_executed),
        "total_assertions": total_assertions,
        "cases": cases_executed,
        "bats_suite": {
            "file": "tests/git-contrib.bats",
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
