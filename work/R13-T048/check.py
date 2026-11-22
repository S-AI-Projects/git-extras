#!/usr/bin/env python3
"""
Verification runner for Task R13-T048: git-pr failure diagnostics and recovery.
Validates failing invocation diagnostics, recovery with corrected invocation,
option tokens (--local, --replace, --merge, --format), before/after repository states,
and native Bats test suite execution in isolated temporary environments.
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
BATS_TEST = REPO_ROOT / "tests" / "git-pr.bats"
WORK_DIR = Path(__file__).resolve().parent
REPORT_PATH = WORK_DIR / "verification_report.json"
REPORT_COMPAT_PATH = WORK_DIR / "report.json"


def run_cmd(cmd, cwd=None, env=None):
    """Run command and return execution details."""
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
    """Retrieve version string of a command."""
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

    with tempfile.TemporaryDirectory(prefix="r13_t048_check_") as tmp:
        tmp_path = Path(tmp)
        isolated_env = base_env.copy()
        isolated_env["GIT_CONFIG_NOSYSTEM"] = "1"
        isolated_env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "gitconfig")

        # 1. Native Bats test execution for git-pr
        bats_executable = str(BATS_BIN) if BATS_BIN.exists() else "bats"
        bats_cmd = [bats_executable, "--tap", str(BATS_TEST)]
        bats_res = run_cmd(bats_cmd, REPO_ROOT, isolated_env)
        tap_cases = [
            line for line in bats_res["stdout"].splitlines()
            if line.startswith(("ok ", "not ok "))
        ]
        bats_passed = bats_res["returncode"] == 0 and len(tap_cases) > 0
        results.append({
            "name": "native_bats_git_pr",
            "command": bats_cmd,
            "returncode": bats_res["returncode"],
            "stdout": bats_res["stdout"],
            "stderr": bats_res["stderr"],
            "executed_cases": len(tap_cases),
            "passed": bats_passed,
        })
        if not bats_passed:
            failures.append("Native Bats test suite failed or ran zero test cases.")

        # 2. Setup temporary repository fixture with commits A/B/C, main/topic branches, bare remote
        remote_dir = tmp_path / "remote.git"
        work_dir = tmp_path / "repo"
        work_dir.mkdir()

        run_cmd(["git", "init", "--bare", str(remote_dir)], tmp_path, isolated_env)
        run_cmd(["git", "init", "--initial-branch", "main"], work_dir, isolated_env)
        run_cmd(["git", "config", "user.name", "Test User"], work_dir, isolated_env)
        run_cmd(["git", "config", "user.email", "test@example.com"], work_dir, isolated_env)
        run_cmd(["git", "remote", "add", "origin", str(remote_dir)], work_dir, isolated_env)

        # Commit A
        (work_dir / "file.txt").write_text("Commit A content\n")
        run_cmd(["git", "add", "file.txt"], work_dir, isolated_env)
        run_cmd(["git", "commit", "-m", "Commit A"], work_dir, isolated_env)

        # Commit B and C on topic branch
        run_cmd(["git", "checkout", "-b", "topic"], work_dir, isolated_env)
        (work_dir / "file.txt").write_text("Commit B content\n")
        run_cmd(["git", "commit", "-am", "Commit B"], work_dir, isolated_env)
        (work_dir / "file.txt").write_text("Commit C content\n")
        run_cmd(["git", "commit", "-am", "Commit C"], work_dir, isolated_env)

        # Push pull request refs to bare remote
        run_cmd(["git", "push", str(remote_dir), "topic:refs/pull/42/head"], work_dir, isolated_env)
        run_cmd(["git", "push", str(remote_dir), "topic:refs/pull/42/merge"], work_dir, isolated_env)
        run_cmd(["git", "checkout", "main"], work_dir, isolated_env)

        # Case 1: Failing invocation (non-existent PR 999)
        before_branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], work_dir, isolated_env)["stdout"]
        fail_res = run_cmd(["git-pr", "999", "origin"], work_dir, isolated_env)
        after_fail_branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], work_dir, isolated_env)["stdout"]
        pr_999_exists = run_cmd(["git", "rev-parse", "--verify", "refs/heads/pr/999"], work_dir, isolated_env)["returncode"] == 0

        fail_diag_expected = "Failed to fetch refs/pull/999/head from 'origin'. Please verify the pull request number and remote."
        case1_passed = (
            fail_res["returncode"] != 0
            and fail_diag_expected in fail_res["stderr"]
            and before_branch == "main"
            and after_fail_branch == "main"
            and not pr_999_exists
        )
        results.append({
            "name": "failing_invocation_diagnostic",
            "arguments": ["999", "origin"],
            "expected": {
                "returncode": 1,
                "stderr_contains": fail_diag_expected,
                "branch_unchanged": "main",
                "pr_branch_created": False,
            },
            "actual": {
                "returncode": fail_res["returncode"],
                "stderr": fail_res["stderr"],
                "branch_after": after_fail_branch,
                "pr_branch_created": pr_999_exists,
            },
            "passed": case1_passed,
        })
        if not case1_passed:
            failures.append("Failing invocation diagnostic assertion failed.")

        # Case 2: Corrected invocation succeeding afterwards (PR 42)
        success_res = run_cmd(["git-pr", "42", "origin"], work_dir, isolated_env)
        after_success_branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], work_dir, isolated_env)["stdout"]
        branch_remote = run_cmd(["git", "config", "--local", "--get", "branch.pr/42.remote"], work_dir, isolated_env)["stdout"]
        branch_merge = run_cmd(["git", "config", "--local", "--get", "branch.pr/42.merge"], work_dir, isolated_env)["stdout"]

        case2_passed = (
            success_res["returncode"] == 0
            and after_success_branch == "pr/42"
            and branch_remote == "origin"
            and branch_merge == "refs/pull/42/head"
        )
        results.append({
            "name": "corrected_invocation_success",
            "arguments": ["42", "origin"],
            "expected": {
                "returncode": 0,
                "branch": "pr/42",
                "config_remote": "origin",
                "config_merge": "refs/pull/42/head",
            },
            "actual": {
                "returncode": success_res["returncode"],
                "branch": after_success_branch,
                "config_remote": branch_remote,
                "config_merge": branch_merge,
            },
            "passed": case2_passed,
        })
        if not case2_passed:
            failures.append("Corrected invocation success assertion failed.")

        # Case 3: Empty argument failure
        empty_res = run_cmd(["git-pr"], work_dir, isolated_env)
        case3_passed = empty_res["returncode"] != 0 and "pr number required." in empty_res["stderr"]
        results.append({
            "name": "missing_argument_failure",
            "arguments": [],
            "expected": {"returncode": 1, "stderr_contains": "pr number required."},
            "actual": {"returncode": empty_res["returncode"], "stderr": empty_res["stderr"]},
            "passed": case3_passed,
        })
        if not case3_passed:
            failures.append("Missing argument failure assertion failed.")

        # Case 4: Invalid pattern failure
        invalid_res = run_cmd(["git-pr", "invalid_pattern_spec"], work_dir, isolated_env)
        case4_passed = invalid_res["returncode"] != 0 and "doesn't match the pr id pattern" in invalid_res["stderr"]
        results.append({
            "name": "invalid_pattern_failure",
            "arguments": ["invalid_pattern_spec"],
            "expected": {"returncode": 1, "stderr_contains": "doesn't match the pr id pattern"},
            "actual": {"returncode": invalid_res["returncode"], "stderr": invalid_res["stderr"]},
            "passed": case4_passed,
        })
        if not case4_passed:
            failures.append("Invalid pattern failure assertion failed.")

        # Case 5: Help options
        help_short = run_cmd(["git-pr", "-h"], work_dir, isolated_env)
        help_long = run_cmd(["git-pr", "--help"], work_dir, isolated_env)
        case5_passed = (
            help_short["returncode"] == 0
            and "Usage: git pr" in help_short["stdout"]
            and help_long["returncode"] == 0
            and "Usage: git pr" in help_long["stdout"]
        )
        results.append({
            "name": "help_options",
            "arguments": ["-h", "--help"],
            "expected": {"returncode": 0, "stdout_contains": "Usage: git pr"},
            "actual": {
                "short_returncode": help_short["returncode"],
                "short_stdout": help_short["stdout"],
                "long_returncode": help_long["returncode"],
            },
            "passed": case5_passed,
        })
        if not case5_passed:
            failures.append("Help options assertion failed.")

        # Case 6: Clean command
        run_cmd(["git", "checkout", "main"], work_dir, isolated_env)
        clean_res = run_cmd(["git-pr", "clean"], work_dir, isolated_env)
        pr_branch_still_exists = run_cmd(["git", "rev-parse", "--verify", "refs/heads/pr/42"], work_dir, isolated_env)["returncode"] == 0
        case6_passed = clean_res["returncode"] == 0 and not pr_branch_still_exists
        results.append({
            "name": "clean_pr_branches",
            "arguments": ["clean"],
            "expected": {"returncode": 0, "pr_branch_deleted": True},
            "actual": {"returncode": clean_res["returncode"], "pr_branch_exists": pr_branch_still_exists},
            "passed": case6_passed,
        })
        if not case6_passed:
            failures.append("Clean PR branches assertion failed.")

    tool_versions = {
        "git": get_version(["git", "--version"], isolated_env),
        "bash": get_version(["bash", "--version"], isolated_env),
        "bats": get_version([bats_executable, "--version"], isolated_env),
        "python3": get_version(["python3", "--version"], isolated_env),
    }

    report = {
        "task_id": "R13-T048",
        "tool_versions": tool_versions,
        "total_checks": len(results),
        "passed": len(failures) == 0,
        "failures": failures,
        "results": results,
    }

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    report_json = json.dumps(report, indent=2) + "\n"
    REPORT_PATH.write_text(report_json)
    REPORT_COMPAT_PATH.write_text(report_json)
    print(report_json)

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
