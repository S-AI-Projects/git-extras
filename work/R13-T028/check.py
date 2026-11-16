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
STANDUP_BIN = REPO_ROOT / "bin" / "git-standup"


def run_checks():
    results = {
        "task_id": "R13-T028",
        "timestamp": time.time(),
        "tests": [],
        "passed": 0,
        "failed": 0,
        "status": "pending",
    }

    test_dir = tempfile.mkdtemp(prefix="git_standup_test_")
    env = os.environ.copy()
    env["PATH"] = f"{REPO_ROOT / 'bin'}:{env['PATH']}"
    env["GIT_AUTHOR_NAME"] = "Test Author"
    env["GIT_AUTHOR_EMAIL"] = "author@example.com"
    env["GIT_COMMITTER_NAME"] = "Test Author"
    env["GIT_COMMITTER_EMAIL"] = "author@example.com"

    try:
        # Initialize test git repository
        subprocess.run(["git", "init"], cwd=test_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test Author"],
            cwd=test_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "author@example.com"],
            cwd=test_dir,
            check=True,
            capture_output=True,
        )

        test_file = Path(test_dir) / "sample.txt"
        test_file.write_text("sample content\n")
        subprocess.run(["git", "add", "."], cwd=test_dir, check=True, capture_output=True)

        commit_ts = str(int(time.time()) - 86400)
        commit_env = env.copy()
        commit_env["GIT_AUTHOR_DATE"] = f"@{commit_ts}"
        commit_env["GIT_COMMITTER_DATE"] = f"@{commit_ts}"
        subprocess.run(
            ["git", "commit", "-m", "Sample commit for standup"],
            cwd=test_dir,
            env=commit_env,
            check=True,
            capture_output=True,
        )

        # Check 1: Invalid invocation -d 0 fails with diagnostic message on stderr
        proc = subprocess.run(
            [str(STANDUP_BIN), "-d", "0"],
            cwd=test_dir,
            env=env,
            capture_output=True,
            text=True,
        )
        passed = (
            proc.returncode == 1
            and "Specify days less than one is invalid" in proc.stderr
            and "-d requires a positive integer" in proc.stderr
        )
        results["tests"].append(
            {
                "name": "invalid_invocation_fails_with_diagnostic",
                "passed": passed,
                "exit_code": proc.returncode,
                "stderr": proc.stderr.strip(),
            }
        )

        # Check 2: Corrected invocation -d 2 succeeds with commit output
        proc = subprocess.run(
            [str(STANDUP_BIN), "-d", "2"],
            cwd=test_dir,
            env=env,
            capture_output=True,
            text=True,
        )
        passed = proc.returncode == 0 and "Sample commit for standup" in proc.stdout
        results["tests"].append(
            {
                "name": "corrected_invocation_succeeds",
                "passed": passed,
                "exit_code": proc.returncode,
                "stdout": proc.stdout.strip(),
            }
        )

        # Check 3: Invocation with -a all succeeds
        proc = subprocess.run(
            [str(STANDUP_BIN), "-a", "all", "-d", "2"],
            cwd=test_dir,
            env=env,
            capture_output=True,
            text=True,
        )
        passed = proc.returncode == 0 and "Sample commit for standup" in proc.stdout
        results["tests"].append(
            {
                "name": "standup_all_authors_succeeds",
                "passed": passed,
                "exit_code": proc.returncode,
            }
        )

        # Check 4: Help invocation -h
        proc = subprocess.run(
            [str(STANDUP_BIN), "-h"],
            cwd=test_dir,
            env=env,
            capture_output=True,
            text=True,
        )
        passed = proc.returncode == 0 and "Usage:" in proc.stdout
        results["tests"].append(
            {
                "name": "standup_help_succeeds",
                "passed": passed,
                "exit_code": proc.returncode,
            }
        )

        # Check 5: Bats suite
        bats_proc = subprocess.run(
            ["bats", str(REPO_ROOT / "tests" / "git-standup.bats")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        passed = bats_proc.returncode == 0 and "ok 1" in bats_proc.stdout
        results["tests"].append(
            {
                "name": "bats_suite",
                "passed": passed,
                "exit_code": bats_proc.returncode,
                "output": bats_proc.stdout.strip(),
            }
        )

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)

    # Reject zero-case run
    if not results["tests"]:
        raise RuntimeError("No tests were executed!")

    results["passed"] = sum(1 for t in results["tests"] if t["passed"])
    results["failed"] = sum(1 for t in results["tests"] if not t["passed"])
    results["status"] = "passed" if results["failed"] == 0 else "failed"

    work_dir = Path(__file__).resolve().parent
    work_dir.mkdir(parents=True, exist_ok=True)
    results_file = work_dir / "results.json"
    results_file.write_text(json.dumps(results, indent=2) + "\n")

    print(json.dumps(results, indent=2))
    if results["status"] != "passed":
        sys.exit(1)


if __name__ == "__main__":
    run_checks()
