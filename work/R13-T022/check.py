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

    print("[*] Running check for R13-T022 (git-changelog)...")
    tool_versions = get_tool_versions(repo_root)
    print(f"[*] Tool versions: {tool_versions}")

    cases_executed = []
    total_assertions = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["HOME"] = tmpdir
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = os.path.join(tmpdir, ".gitconfig")
        env["GIT_EDITOR"] = "true"

        install_bin = prepare_command(repo_root, tmpdir, "changelog")
        env["PATH"] = f"{install_bin}:{os.path.join(repo_root, 'bin')}:{env.get('PATH', '')}"

        local_repo = os.path.join(tmpdir, "repo")
        os.makedirs(local_repo, exist_ok=True)
        subprocess.run(["git", "init", "--initial-branch", "main"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=local_repo, env=env, check=True, capture_output=True)

        # Create initial commits and a tag
        with open(os.path.join(local_repo, "a.txt"), "w") as f:
            f.write("commit A\n")
        subprocess.run(["git", "add", "."], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Commit A"], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "tag", "-a", "v1.0.0", "-m", "Tag v1.0.0"], cwd=local_repo, env=env, check=True, capture_output=True)

        with open(os.path.join(local_repo, "b.txt"), "w") as f:
            f.write("commit B\n")
        subprocess.run(["git", "add", "."], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Commit B"], cwd=local_repo, env=env, check=True, capture_output=True)

        with open(os.path.join(local_repo, "c.txt"), "w") as f:
            f.write("commit C\n")
        subprocess.run(["git", "add", "."], cwd=local_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Commit C"], cwd=local_repo, env=env, check=True, capture_output=True)
        commit_c_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=local_repo, text=True, env=env).strip()

        # Case 1: Minimum accepted argument list (e.g. --stdout)
        code, stdout, stderr = run_cmd(["git", "changelog", "--list", "--stdout"], cwd=local_repo, env=env)
        assert code == 0, f"Expected exit code 0 for minimum argument list, got {code}, stderr: {stderr}"
        assert "Commit C" in stdout, f"Expected 'Commit C' in output: {stdout}"
        total_assertions += 2
        cases_executed.append({
            "name": "minimum_accepted_argument_list",
            "type": "minimum_arguments_success",
            "command": "git changelog --list --stdout",
            "actual_args": ["--list", "--stdout"],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "output_contains": "Commit C",
            "passed": True
        })
        print("[+] Case 1 passed: Minimum accepted argument list succeeds.")

        # Case 2: Optional arguments: --all, --prune-old, --list
        out_file = os.path.join(local_repo, "CHANGELOG.md")
        with open(out_file, "w") as f:
            f.write("Existing changelog content that should be pruned\n")
        code, stdout, stderr = run_cmd(["git", "changelog", "--all", "--prune-old", "--list", "CHANGELOG.md"], cwd=local_repo, env=env)
        assert code == 0, f"Expected exit code 0 with optional args, got {code}, stderr: {stderr}"
        assert os.path.exists(out_file), "Expected CHANGELOG.md to exist"
        with open(out_file, "r") as f:
            content = f.read()
        assert "Commit A" in content, "Commit A should be in output due to --all"
        assert "Commit B" in content, "Commit B should be in output"
        assert "Commit C" in content, "Commit C should be in output"
        assert "Existing changelog content" not in content, "--prune-old should replace existing content"
        total_assertions += 6
        cases_executed.append({
            "name": "optional_arguments_all_prune_old_list",
            "type": "optional_arguments_success",
            "command": "git changelog --all --prune-old --list CHANGELOG.md",
            "actual_args": ["--all", "--prune-old", "--list", "CHANGELOG.md"],
            "expected_exit_code": 0,
            "actual_exit_code": code,
            "passed": True
        })
        print("[+] Case 2 passed: Optional arguments (--all, --prune-old, --list) succeed.")

        # Case 3: Documented invalid combination: --start-tag combined with --start-commit
        code, stdout, stderr = run_cmd(["git", "changelog", "--start-tag", "v1.0.0", "--start-commit", commit_c_sha], cwd=local_repo, env=env)
        assert code == 1, f"Expected exit code 1 for invalid combination, got {code}"
        assert "--start-tag could not use with --start-commit!" in stdout or "--start-tag could not use with --start-commit!" in stderr, f"Expected error message not found: {stdout} {stderr}"
        total_assertions += 2
        cases_executed.append({
            "name": "invalid_combination_start_tag_and_start_commit",
            "type": "documented_invalid_combination",
            "command": "git changelog --start-tag v1.0.0 --start-commit <sha>",
            "actual_args": ["--start-tag", "v1.0.0", "--start-commit", commit_c_sha],
            "expected_exit_code": 1,
            "actual_exit_code": code,
            "expected_error": "--start-tag could not use with --start-commit!",
            "passed": True
        })
        print("[+] Case 3 passed: Documented invalid combination properly rejected.")

        # Case 4: Documented invalid combination: non-existent start-tag
        code, stdout, stderr = run_cmd(["git", "changelog", "--start-tag", "nonexistent-tag"], cwd=local_repo, env=env)
        assert code == 1, f"Expected exit code 1 for missing tag, got {code}"
        assert "Specified start-tag does not exist!" in stdout or "Specified start-tag does not exist!" in stderr, f"Expected error message: {stdout} {stderr}"
        total_assertions += 2
        cases_executed.append({
            "name": "invalid_start_tag_does_not_exist",
            "type": "documented_invalid_combination",
            "command": "git changelog --start-tag nonexistent-tag",
            "actual_args": ["--start-tag", "nonexistent-tag"],
            "expected_exit_code": 1,
            "actual_exit_code": code,
            "expected_error": "Specified start-tag does not exist!",
            "passed": True
        })
        print("[+] Case 4 passed: Nonexistent start tag rejected.")

    # Rejection of zero-case run
    if len(cases_executed) == 0 or total_assertions == 0:
        print("[!] ERROR: Zero-case run rejected!", file=sys.stderr)
        sys.exit(1)

    # Invoke Bats native tests
    bats_bin = shutil.which("bats")
    bats_test_file = os.path.join(repo_root, "tests/git-changelog.bats")
    bats_result = subprocess.run([bats_bin, bats_test_file], cwd=repo_root, capture_output=True, text=True)
    print(f"[*] Native Bats execution:\n{bats_result.stdout}")
    if bats_result.returncode != 0:
        print(f"[!] Bats tests failed:\n{bats_result.stderr}", file=sys.stderr)
        sys.exit(bats_result.returncode)

    report = {
        "task": "R13-T022",
        "target": "bin/git-changelog",
        "tool_versions": tool_versions,
        "total_cases": len(cases_executed),
        "total_assertions": total_assertions,
        "cases": cases_executed,
        "bats_suite": {
            "file": "tests/git-changelog.bats",
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
