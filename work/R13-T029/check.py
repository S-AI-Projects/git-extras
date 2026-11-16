#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BIN_DIR = REPO_ROOT / "bin"
FORK_BIN = BIN_DIR / "git-fork"


def get_tool_versions():
    versions = {}
    for tool in ["git", "bash", "bats", "python3"]:
        try:
            res = subprocess.run([tool, "--version"], capture_output=True, text=True, check=True)
            versions[tool] = res.stdout.strip().split("\n")[0]
        except Exception as e:
            versions[tool] = f"unknown ({e})"
    return versions


def run_checks():
    work_dir = Path(__file__).resolve().parent
    work_dir.mkdir(parents=True, exist_ok=True)
    results_file = work_dir / "results.json"

    tool_versions = get_tool_versions()

    results = {
        "task_id": "R13-T029",
        "timestamp": time.time(),
        "tool_versions": tool_versions,
        "test_cases": [],
        "passed": 0,
        "failed": 0,
        "status": "pending",
    }

    test_root = tempfile.mkdtemp(prefix="git_fork_check_")
    isolated_config = Path(test_root) / "gitconfig"
    isolated_config.write_text("")

    base_env = os.environ.copy()
    base_env["GIT_CONFIG_NOSYSTEM"] = "1"
    base_env["GIT_CONFIG_GLOBAL"] = str(isolated_config)
    base_env["PATH"] = f"{BIN_DIR}:{base_env['PATH']}"
    base_env["GIT_AUTHOR_NAME"] = "Student Tester"
    base_env["GIT_AUTHOR_EMAIL"] = "student@example.com"
    base_env["GIT_COMMITTER_NAME"] = "Student Tester"
    base_env["GIT_COMMITTER_EMAIL"] = "student@example.com"

    mock_bin_dir = Path(test_root) / "mock_bin"
    mock_bin_dir.mkdir(parents=True, exist_ok=True)
    mock_curl = mock_bin_dir / "curl"
    mock_curl.write_text("#!/usr/bin/env bash\nexit 0\n")
    mock_curl.chmod(0o755)

    try:
        # Check 1: git-fork -h (usage screen)
        proc = subprocess.run(
            [str(FORK_BIN), "-h"],
            cwd=test_root,
            env=base_env,
            capture_output=True,
            text=True,
        )
        passed = proc.returncode == 0 and "Usage: git fork" in proc.stdout
        results["test_cases"].append(
            {
                "name": "help_screen_invocation",
                "args": ["-h"],
                "input": None,
                "expected_exit": 0,
                "actual_exit": proc.returncode,
                "expected_stdout_contains": "Usage: git fork",
                "passed": passed,
                "output": proc.stdout.strip(),
            }
        )

        # Check 2: Outside repo without url fails
        empty_dir = Path(test_root) / "empty"
        empty_dir.mkdir()
        proc = subprocess.run(
            [str(FORK_BIN)],
            cwd=empty_dir,
            env=base_env,
            capture_output=True,
            text=True,
        )
        passed = proc.returncode == 1 and "github repo needs to be specified as an argument" in proc.stdout
        results["test_cases"].append(
            {
                "name": "missing_repo_url_failure",
                "args": [],
                "input": None,
                "expected_exit": 1,
                "actual_exit": proc.returncode,
                "expected_output_contains": "github repo needs to be specified as an argument",
                "passed": passed,
                "output": proc.stdout.strip(),
            }
        )

        # Check 3: Missing username aborts
        proc = subprocess.run(
            [str(FORK_BIN), "owner/repo"],
            cwd=test_root,
            env=base_env,
            input="\n",
            capture_output=True,
            text=True,
        )
        passed = proc.returncode == 1 and "git username required" in proc.stdout
        results["test_cases"].append(
            {
                "name": "missing_username_failure",
                "args": ["owner/repo"],
                "input": "\\n",
                "expected_exit": 1,
                "actual_exit": proc.returncode,
                "expected_output_contains": "git username required",
                "passed": passed,
                "output": proc.stdout.strip(),
            }
        )

        # Check 4: Missing token aborts
        env_no_token = base_env.copy()
        env_no_token.pop("GITHUB_TOKEN", None)
        proc = subprocess.run(
            [str(FORK_BIN), "owner/repo"],
            cwd=test_root,
            env=env_no_token,
            input="myuser\n",
            capture_output=True,
            text=True,
        )
        passed = proc.returncode == 1 and "GITHUB_TOKEN, or git config git-extras.github-personal-access-token required" in proc.stdout
        results["test_cases"].append(
            {
                "name": "missing_token_failure",
                "args": ["owner/repo"],
                "input": "myuser\\n",
                "expected_exit": 1,
                "actual_exit": proc.returncode,
                "expected_output_contains": "GITHUB_TOKEN, or git config git-extras.github-personal-access-token required",
                "passed": passed,
                "output": proc.stdout.strip(),
            }
        )

        # Check 5: Fork API failure
        mock_fail_bin = Path(test_root) / "mock_fail_bin"
        mock_fail_bin.mkdir(parents=True, exist_ok=True)
        (mock_fail_bin / "curl").write_text("#!/usr/bin/env bash\nexit 1\n")
        (mock_fail_bin / "curl").chmod(0o755)

        env_fail = base_env.copy()
        env_fail["PATH"] = f"{mock_fail_bin}:{env_fail['PATH']}"
        env_fail["GITHUB_TOKEN"] = "dummy_token"
        proc = subprocess.run(
            [str(FORK_BIN), "owner/repo"],
            cwd=test_root,
            env=env_fail,
            input="myuser\n",
            capture_output=True,
            text=True,
        )
        passed = proc.returncode == 1 and "fork failed" in proc.stdout
        results["test_cases"].append(
            {
                "name": "api_fork_failure",
                "args": ["owner/repo"],
                "input": "myuser\\n",
                "expected_exit": 1,
                "actual_exit": proc.returncode,
                "expected_output_contains": "fork failed",
                "passed": passed,
                "output": proc.stdout.strip(),
            }
        )

        # Setup local bare remotes and test repo with commits A/B/C and branches main/topic
        remotes_dir = Path(test_root) / "remotes"
        upstream_bare = remotes_dir / "upstream_org" / "myproject.git"
        user_bare = remotes_dir / "myuser" / "myproject.git"
        upstream_bare.mkdir(parents=True, exist_ok=True)
        user_bare.mkdir(parents=True, exist_ok=True)

        subprocess.run(["git", "init", "--bare", "--initial-branch", "main", str(upstream_bare)], check=True, capture_output=True)
        subprocess.run(["git", "init", "--bare", "--initial-branch", "main", str(user_bare)], check=True, capture_output=True)

        seed_dir = Path(test_root) / "seed"
        subprocess.run(["git", "clone", str(upstream_bare), str(seed_dir)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=seed_dir, check=True)
        subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=seed_dir, check=True)

        # Commit A on main
        (seed_dir / "file_a.txt").write_text("Commit A\n")
        subprocess.run(["git", "add", "file_a.txt"], cwd=seed_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Commit A"], cwd=seed_dir, check=True)

        # Commit B on main
        (seed_dir / "file_b.txt").write_text("Commit B\n")
        subprocess.run(["git", "add", "file_b.txt"], cwd=seed_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Commit B"], cwd=seed_dir, check=True)

        # Branch topic with Commit C
        subprocess.run(["git", "checkout", "-b", "topic"], cwd=seed_dir, check=True)
        (seed_dir / "file_c.txt").write_text("Commit C\n")
        subprocess.run(["git", "add", "file_c.txt"], cwd=seed_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Commit C"], cwd=seed_dir, check=True)

        # Push main and topic to upstream_bare and user_bare
        subprocess.run(["git", "push", "origin", "main", "topic"], cwd=seed_dir, check=True, capture_output=True)
        subprocess.run(["git", "push", str(user_bare), "main", "topic"], cwd=seed_dir, check=True, capture_output=True)

        # Check 6: Successful in-repo fork
        work_clone = Path(test_root) / "work_clone"
        subprocess.run(["git", "clone", str(upstream_bare), str(work_clone)], check=True, capture_output=True)

        before_remotes = subprocess.run(["git", "remote", "-v"], cwd=work_clone, capture_output=True, text=True, check=True).stdout.strip()
        env_success = base_env.copy()
        env_success["PATH"] = f"{mock_bin_dir}:{env_success['PATH']}"
        env_success["GITHUB_TOKEN"] = "token123"
        env_success["GIT_REMOTE_PREFIX"] = f"{remotes_dir}/"

        proc = subprocess.run(
            [str(FORK_BIN)],
            cwd=work_clone,
            env=env_success,
            input="myuser\nn\n",
            capture_output=True,
            text=True,
        )
        after_remotes = subprocess.run(["git", "remote", "-v"], cwd=work_clone, capture_output=True, text=True, check=True).stdout.strip()

        passed = (
            proc.returncode == 0
            and "upstream" in after_remotes
            and str(upstream_bare) in after_remotes
            and "origin" in after_remotes
            and str(user_bare) in after_remotes
        )
        results["test_cases"].append(
            {
                "name": "in_repo_fork_success",
                "args": [],
                "input": "myuser\\nn\\n",
                "expected_exit": 0,
                "actual_exit": proc.returncode,
                "before_remotes": before_remotes,
                "after_remotes": after_remotes,
                "passed": passed,
            }
        )

        # Check 7: Successful clone fork
        clone_parent = Path(test_root) / "clone_parent"
        clone_parent.mkdir()
        proc = subprocess.run(
            [str(FORK_BIN), "upstream_org/myproject"],
            cwd=clone_parent,
            env=env_success,
            input="myuser\nn\n",
            capture_output=True,
            text=True,
        )
        cloned_repo = clone_parent / "myproject"
        cloned_remotes = ""
        if cloned_repo.is_dir():
            cloned_remotes = subprocess.run(["git", "remote", "-v"], cwd=cloned_repo, capture_output=True, text=True, check=True).stdout.strip()

        passed = (
            proc.returncode == 0
            and cloned_repo.is_dir()
            and str(user_bare) in cloned_remotes
            and str(upstream_bare) in cloned_remotes
        )
        results["test_cases"].append(
            {
                "name": "clone_by_url_fork_success",
                "args": ["upstream_org/myproject"],
                "input": "myuser\\nn\\n",
                "expected_exit": 0,
                "actual_exit": proc.returncode,
                "cloned_repo_exists": cloned_repo.is_dir(),
                "cloned_remotes": cloned_remotes,
                "passed": passed,
            }
        )

        # Check 8: Bats suite execution
        bats_proc = subprocess.run(
            ["bats", str(REPO_ROOT / "tests" / "git-fork.bats")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        passed = bats_proc.returncode == 0 and "ok 1" in bats_proc.stdout
        results["test_cases"].append(
            {
                "name": "native_bats_suite",
                "args": [str(REPO_ROOT / "tests" / "git-fork.bats")],
                "expected_exit": 0,
                "actual_exit": bats_proc.returncode,
                "passed": passed,
                "output": bats_proc.stdout.strip(),
            }
        )

    finally:
        shutil.rmtree(test_root, ignore_errors=True)

    # Rejection of zero-case run
    if not results["test_cases"]:
        raise RuntimeError("Rejection: zero test cases executed!")

    results["passed"] = sum(1 for tc in results["test_cases"] if tc["passed"])
    results["failed"] = sum(1 for tc in results["test_cases"] if not tc["passed"])
    results["status"] = "passed" if results["failed"] == 0 else "failed"

    results_file.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))

    if results["status"] != "passed":
        sys.exit(1)


if __name__ == "__main__":
    run_checks()
