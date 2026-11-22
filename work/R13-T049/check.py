#!/usr/bin/env python3
"""
Verification runner for Task R13-T049: git-mr tooling integration and focused checks.
Validates checkout by ID, checkout by remote, GitLab URL, Forgejo/Codeberg URL,
help option tokens (-h/--help), argument boundaries, cleanup via `clean`,
and native Bats test execution in isolated temporary environments.
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
BATS_TEST = REPO_ROOT / "tests" / "git-mr.bats"
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

    with tempfile.TemporaryDirectory(prefix="r13_t049_check_") as tmp:
        tmp_path = Path(tmp)
        isolated_env = base_env.copy()
        isolated_env["GIT_CONFIG_NOSYSTEM"] = "1"
        isolated_env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "gitconfig")

        # 1. Native Bats test execution for git-mr
        bats_executable = str(BATS_BIN) if BATS_BIN.exists() else "bats"
        bats_cmd = [bats_executable, "--tap", str(BATS_TEST)]
        bats_res = run_cmd(bats_cmd, REPO_ROOT, isolated_env)
        tap_cases = [
            line for line in bats_res["stdout"].splitlines()
            if line.startswith(("ok ", "not ok "))
        ]
        bats_passed = bats_res["returncode"] == 0 and len(tap_cases) > 0
        results.append({
            "name": "native_bats_git_mr",
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

        # Push MR head ref and pull ref to bare remote
        run_cmd(["git", "push", str(remote_dir), "topic:refs/merge-requests/51/head"], work_dir, isolated_env)
        run_cmd(["git", "push", str(remote_dir), "topic:refs/pull/51/head"], work_dir, isolated_env)
        run_cmd(["git", "checkout", "main"], work_dir, isolated_env)

        # Case 1: Checkout by numeric ID
        id_res = run_cmd(["git-mr", "51"], work_dir, isolated_env)
        branch_after_id = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], work_dir, isolated_env)["stdout"]
        merge_config = run_cmd(["git", "config", "--get", "branch.mr/51.merge"], work_dir, isolated_env)["stdout"]
        case1_passed = (
            id_res["returncode"] == 0
            and branch_after_id == "mr/51"
            and merge_config == "refs/merge-requests/51/head"
        )
        results.append({
            "name": "checkout_by_numeric_id",
            "arguments": ["51"],
            "expected": {"returncode": 0, "branch": "mr/51", "merge_ref": "refs/merge-requests/51/head"},
            "actual": {"returncode": id_res["returncode"], "branch": branch_after_id, "merge_ref": merge_config},
            "passed": case1_passed,
        })
        if not case1_passed:
            failures.append("Checkout by numeric ID failed.")

        # Case 2: Clean branches
        run_cmd(["git", "checkout", "main"], work_dir, isolated_env)
        clean_res = run_cmd(["git-mr", "clean"], work_dir, isolated_env)
        mr_51_exists = run_cmd(["git", "rev-parse", "--verify", "refs/heads/mr/51"], work_dir, isolated_env)["returncode"] == 0
        case2_passed = clean_res["returncode"] == 0 and not mr_51_exists
        results.append({
            "name": "clean_mr_branches",
            "arguments": ["clean"],
            "expected": {"returncode": 0, "mr_branch_deleted": True},
            "actual": {"returncode": clean_res["returncode"], "mr_branch_exists": mr_51_exists},
            "passed": case2_passed,
        })
        if not case2_passed:
            failures.append("Clean MR branches failed.")

        # Case 3: GitLab URL with insteadOf rewriting
        run_cmd(["git", "config", "--local", f"url.{remote_dir}.insteadOf", "https://gitlab.com/owner/repository.git"], work_dir, isolated_env)
        gitlab_res = run_cmd(["git-mr", "https://gitlab.com/owner/repository/merge_requests/51"], work_dir, isolated_env)
        branch_after_gl = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], work_dir, isolated_env)["stdout"]
        case3_passed = gitlab_res["returncode"] == 0 and branch_after_gl == "mr/51"
        results.append({
            "name": "checkout_by_gitlab_url",
            "arguments": ["https://gitlab.com/owner/repository/merge_requests/51"],
            "expected": {"returncode": 0, "branch": "mr/51"},
            "actual": {"returncode": gitlab_res["returncode"], "branch": branch_after_gl},
            "passed": case3_passed,
        })
        if not case3_passed:
            failures.append("Checkout by GitLab URL failed.")

        # Clean again
        run_cmd(["git", "checkout", "main"], work_dir, isolated_env)
        run_cmd(["git-mr", "clean"], work_dir, isolated_env)

        # Case 4: Forgejo / Codeberg pull URL
        run_cmd(["git", "config", "--local", f"url.{remote_dir}.insteadOf", "https://codeberg.org/owner/repository.git"], work_dir, isolated_env)
        codeberg_res = run_cmd(["git-mr", "https://codeberg.org/owner/repository/pulls/51"], work_dir, isolated_env)
        branch_after_cb = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], work_dir, isolated_env)["stdout"]
        cb_merge = run_cmd(["git", "config", "--get", "branch.mr/51.merge"], work_dir, isolated_env)["stdout"]
        case4_passed = codeberg_res["returncode"] == 0 and branch_after_cb == "mr/51" and cb_merge == "refs/pull/51/head"
        results.append({
            "name": "checkout_by_codeberg_url",
            "arguments": ["https://codeberg.org/owner/repository/pulls/51"],
            "expected": {"returncode": 0, "branch": "mr/51", "merge_ref": "refs/pull/51/head"},
            "actual": {"returncode": codeberg_res["returncode"], "branch": branch_after_cb, "merge_ref": cb_merge},
            "passed": case4_passed,
        })
        if not case4_passed:
            failures.append("Checkout by Codeberg URL failed.")

        # Clean again
        run_cmd(["git", "checkout", "main"], work_dir, isolated_env)
        run_cmd(["git-mr", "clean"], work_dir, isolated_env)

        # Case 5: Missing argument failure
        empty_res = run_cmd(["git-mr"], work_dir, isolated_env)
        case5_passed = empty_res["returncode"] == 1 and "mr number or URL required. See --help for usage." in empty_res["stderr"]
        results.append({
            "name": "missing_argument_failure",
            "arguments": [],
            "expected": {"returncode": 1, "stderr_contains": "mr number or URL required. See --help for usage."},
            "actual": {"returncode": empty_res["returncode"], "stderr": empty_res["stderr"]},
            "passed": case5_passed,
        })
        if not case5_passed:
            failures.append("Missing argument failure assertion failed.")

        # Case 6: Non-existent MR reference failure
        fail_res = run_cmd(["git-mr", "999"], work_dir, isolated_env)
        mr_999_exists = run_cmd(["git", "rev-parse", "--verify", "refs/heads/mr/999"], work_dir, isolated_env)["returncode"] == 0
        case6_passed = fail_res["returncode"] != 0 and not mr_999_exists
        results.append({
            "name": "missing_remote_ref_failure",
            "arguments": ["999"],
            "expected": {"returncode_nonzero": True, "mr_branch_created": False},
            "actual": {"returncode": fail_res["returncode"], "mr_branch_created": mr_999_exists},
            "passed": case6_passed,
        })
        if not case6_passed:
            failures.append("Missing remote ref failure assertion failed.")

        # Case 7: Help options (-h, --help)
        help_short = run_cmd(["git-mr", "-h"], work_dir, isolated_env)
        help_long = run_cmd(["git-mr", "--help"], work_dir, isolated_env)
        case7_passed = (
            help_short["returncode"] == 0
            and "Usage: git mr" in help_short["stdout"]
            and help_long["returncode"] == 0
            and "Usage: git mr" in help_long["stdout"]
        )
        results.append({
            "name": "help_options",
            "arguments": ["-h", "--help"],
            "expected": {"returncode": 0, "stdout_contains": "Usage: git mr"},
            "actual": {
                "short_returncode": help_short["returncode"],
                "short_stdout": help_short["stdout"],
                "long_returncode": help_long["returncode"],
            },
            "passed": case7_passed,
        })
        if not case7_passed:
            failures.append("Help options assertion failed.")

    tool_versions = {
        "git": get_version(["git", "--version"], isolated_env),
        "bash": get_version(["bash", "--version"], isolated_env),
        "bats": get_version([bats_executable, "--version"], isolated_env),
        "python3": get_version(["python3", "--version"], isolated_env),
    }

    report = {
        "task_id": "R13-T049",
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
