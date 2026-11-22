#!/usr/bin/env python3
"""
Verification script for Task R13-T047: git-obliterate
Validates documented usage examples, bats test suite execution,
option tokens and positional-argument handling, before/after repository states,
and error/boundary conditions in isolated temporary environments.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = REPO_ROOT / "bin"
BATS_BIN = REPO_ROOT / "vendor" / "bats-core" / "bin" / "bats"
BATS_TEST = REPO_ROOT / "tests" / "git-obliterate.bats"
WORK_DIR = Path(__file__).resolve().parent
REPORT_PATH = WORK_DIR / "verification_report.json"


def run_cmd(cmd, cwd=None, env=None):
    """Run command and return dictionary of outputs."""
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else str(REPO_ROOT),
        env=env,
        text=True,
        capture_output=True,
    )
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def get_version(cmd, env):
    """Retrieve version string of a tool."""
    try:
        res = subprocess.run(cmd, env=env, text=True, capture_output=True)
        out = (res.stdout or res.stderr).strip().splitlines()
        return out[0] if out else "unknown"
    except Exception as exc:
        return f"unavailable ({exc})"


def main():
    base_env = os.environ.copy()
    base_env["PATH"] = f"{BIN_DIR}:{base_env.get('PATH', '')}"

    results = []
    failures = []

    with tempfile.TemporaryDirectory(prefix="r13_t047_check_") as tmp:
        tmp_path = Path(tmp)
        isolated_env = base_env.copy()
        isolated_env["GIT_CONFIG_NOSYSTEM"] = "1"
        isolated_env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "gitconfig")

        # 1. Native Bats test execution for git-obliterate
        bats_executable = str(BATS_BIN) if BATS_BIN.exists() else "bats"
        bats_cmd = [bats_executable, "--tap", str(BATS_TEST)]
        bats_res = run_cmd(bats_cmd, REPO_ROOT, isolated_env)
        tap_cases = [
            line for line in bats_res["stdout"].splitlines()
            if line.startswith(("ok ", "not ok "))
        ]
        bats_passed = bats_res["returncode"] == 0 and len(tap_cases) > 0
        results.append({
            "name": "native_bats_git_obliterate",
            "command": bats_cmd,
            "returncode": bats_res["returncode"],
            "stdout": bats_res["stdout"],
            "stderr": bats_res["stderr"],
            "executed_cases": len(tap_cases),
            "passed": bats_passed,
        })
        if not bats_passed:
            failures.append("Native Bats test suite failed or ran zero test cases.")

        # 2. Temporary repository with bare remote, commits A/B/C, branches main/topic
        remote_dir = tmp_path / "remote.git"
        work_dir = tmp_path / "repo"
        work_dir.mkdir()

        run_cmd(["git", "init", "--bare", str(remote_dir)], tmp_path, isolated_env)
        run_cmd(["git", "init", "--initial-branch", "main"], work_dir, isolated_env)
        run_cmd(["git", "config", "user.name", "Test User"], work_dir, isolated_env)
        run_cmd(["git", "config", "user.email", "test@example.com"], work_dir, isolated_env)
        run_cmd(["git", "remote", "add", "origin", str(remote_dir)], work_dir, isolated_env)

        # Commit A
        (work_dir / "safe.txt").write_text("safe content A\n")
        (work_dir / "secret.txt").write_text("secret token 123\n")
        run_cmd(["git", "add", "safe.txt", "secret.txt"], work_dir, isolated_env)
        run_cmd(["git", "commit", "-m", "Commit A with safe and secret files"], work_dir, isolated_env)

        # Commit B
        (work_dir / "safe.txt").write_text("safe content B\n")
        (work_dir / "secret.txt").write_text("secret token 456\n")
        run_cmd(["git", "commit", "-am", "Commit B updating safe and secret"], work_dir, isolated_env)

        # Commit C
        (work_dir / "safe.txt").write_text("safe content C\n")
        run_cmd(["git", "commit", "-am", "Commit C updating safe only"], work_dir, isolated_env)

        # Push to remote and setup branch topic
        run_cmd(["git", "push", "-u", "origin", "main"], work_dir, isolated_env)
        run_cmd(["git", "checkout", "-b", "topic"], work_dir, isolated_env)
        run_cmd(["git", "checkout", "main"], work_dir, isolated_env)

        # Record before-state for success scenario
        before_log = run_cmd(["git", "log", "--oneline", "--", "secret.txt"], work_dir, isolated_env)["stdout"]
        before_ls = run_cmd(["git", "ls-files"], work_dir, isolated_env)["stdout"]
        before_file_exists = (work_dir / "secret.txt").exists()

        # Run documented success command
        obliterate_res = run_cmd(["git-obliterate", "secret.txt"], work_dir, isolated_env)

        # Record after-state for success scenario
        after_log = run_cmd(["git", "log", "--", "secret.txt"], work_dir, isolated_env)["stdout"]
        after_ls = run_cmd(["git", "ls-files"], work_dir, isolated_env)["stdout"]
        after_file_exists = (work_dir / "secret.txt").exists()
        safe_file_intact = (work_dir / "safe.txt").read_text() == "safe content C\n"

        success_passed = (
            obliterate_res["returncode"] == 0
            and before_file_exists
            and not after_file_exists
            and before_log != ""
            and after_log == ""
            and "secret.txt" not in after_ls
            and "safe.txt" in after_ls
            and safe_file_intact
            and "Ref 'refs/heads/main' was rewritten" in obliterate_res["stdout"]
        )
        results.append({
            "name": "cli_documented_example_success",
            "arguments": ["secret.txt"],
            "expected": {
                "returncode": 0,
                "before_file_exists": True,
                "after_file_exists": False,
                "after_log_empty": True,
                "secret_in_ls_files": False,
                "safe_file_intact": True,
            },
            "actual": {
                "returncode": obliterate_res["returncode"],
                "before_log_commits": len(before_log.splitlines()),
                "after_log": after_log,
                "before_file_exists": before_file_exists,
                "after_file_exists": after_file_exists,
                "ls_files_after": after_ls.splitlines(),
                "safe_file_intact": safe_file_intact,
            },
            "passed": success_passed,
        })
        if not success_passed:
            failures.append("CLI documented example success assertion failed.")

        # 3. Documented failure case: missing filename argument
        fail_missing = run_cmd(["git-obliterate"], work_dir, isolated_env)
        missing_passed = (
            fail_missing["returncode"] == 1
            and fail_missing["stderr"] == "file required."
        )
        results.append({
            "name": "cli_missing_filename_failure",
            "arguments": [],
            "expected": {"returncode": 1, "stderr": "file required."},
            "actual": {
                "returncode": fail_missing["returncode"],
                "stderr": fail_missing["stderr"],
            },
            "passed": missing_passed,
        })
        if not missing_passed:
            failures.append("CLI missing filename assertion failed.")

        # 4. Documented failure case: separator token '--' without filename
        fail_sep = run_cmd(["git-obliterate", "--"], work_dir, isolated_env)
        sep_passed = (
            fail_sep["returncode"] == 1
            and fail_sep["stderr"] == "file required."
        )
        results.append({
            "name": "cli_separator_only_failure",
            "arguments": ["--"],
            "expected": {"returncode": 1, "stderr": "file required."},
            "actual": {
                "returncode": fail_sep["returncode"],
                "stderr": fail_sep["stderr"],
            },
            "passed": sep_passed,
        })
        if not sep_passed:
            failures.append("CLI separator-only assertion failed.")

        # 5. Option token handling: -h and --help
        help_short = run_cmd(["git-obliterate", "-h"], work_dir, isolated_env)
        help_long = run_cmd(["git-obliterate", "--help"], work_dir, isolated_env)
        help_passed = (
            help_short["returncode"] == 0
            and "Usage: git obliterate" in help_short["stdout"]
            and help_long["returncode"] == 0
            and "Usage: git obliterate" in help_long["stdout"]
        )
        results.append({
            "name": "cli_help_option_tokens",
            "arguments": ["-h", "--help"],
            "expected": {
                "returncode": 0,
                "stdout_contains": "Usage: git obliterate <files...> [-- <rev-list options...>]",
            },
            "actual": {
                "short_returncode": help_short["returncode"],
                "short_stdout": help_short["stdout"],
                "long_returncode": help_long["returncode"],
                "long_stdout": help_long["stdout"],
            },
            "passed": help_passed,
        })
        if not help_passed:
            failures.append("CLI help option token assertion failed.")

        # 6. Rev-list range option token: obliterate on topic branch only
        run_cmd(["git", "checkout", "topic"], work_dir, isolated_env)
        (work_dir / "topic_secret.txt").write_text("topic secret data\n")
        run_cmd(["git", "add", "topic_secret.txt"], work_dir, isolated_env)
        run_cmd(["git", "commit", "-m", "Commit on topic with topic secret"], work_dir, isolated_env)

        topic_range_res = run_cmd(
            ["git-obliterate", "topic_secret.txt", "--", "topic", "^main"],
            work_dir,
            isolated_env,
        )
        topic_log_after = run_cmd(["git", "log", "--", "topic_secret.txt"], work_dir, isolated_env)["stdout"]
        topic_file_exists = (work_dir / "topic_secret.txt").exists()

        range_passed = (
            topic_range_res["returncode"] == 0
            and not topic_file_exists
            and topic_log_after == ""
            and "Ref 'refs/heads/topic' was rewritten" in topic_range_res["stdout"]
        )
        results.append({
            "name": "cli_range_separator_token_success",
            "arguments": ["topic_secret.txt", "--", "topic", "^main"],
            "expected": {
                "returncode": 0,
                "topic_file_exists": False,
                "topic_log_empty": True,
            },
            "actual": {
                "returncode": topic_range_res["returncode"],
                "topic_file_exists": topic_file_exists,
                "topic_log_after": topic_log_after,
            },
            "passed": range_passed,
        })
        if not range_passed:
            failures.append("CLI range separator assertion failed.")

    report = {
        "task_id": "R13-T047",
        "tool_versions": {
            "git": get_version(["git", "--version"], base_env),
            "bash": get_version(["bash", "--version"], base_env),
            "bats": get_version([bats_executable, "--version"], base_env),
            "python3": get_version(["python3", "--version"], base_env),
        },
        "total_checks": len(results),
        "passed": len(failures) == 0 and len(results) > 0,
        "failures": failures,
        "results": results,
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    # Also save report.json for compatibility
    (WORK_DIR / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    print(json.dumps(report, indent=2))

    if failures or len(results) == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
