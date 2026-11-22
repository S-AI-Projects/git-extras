#!/usr/bin/env python3
"""
Verification runner for Task R13-T050: git-browse-ci regression mutation protection.
Validates branch-remote resolution via rev-parse --abbrev-ref, rejection of the
&> /dev/null stdout-dropping mutant, fallback to origin, explicit remote arguments,
remote not found error exit, and native Bats test suite execution.
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
BATS_TEST = REPO_ROOT / "tests" / "git-browse-ci.bats"
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
    mock_bin = REPO_ROOT / "tests" / "bin"
    base_env = os.environ.copy()
    base_env["PATH"] = f"{mock_bin}:{BIN_DIR}:{base_env.get('PATH', '')}"

    results = []
    failures = []

    with tempfile.TemporaryDirectory(prefix="r13_t050_check_") as tmp:
        tmp_path = Path(tmp)
        isolated_env = base_env.copy()
        isolated_env["GIT_CONFIG_NOSYSTEM"] = "1"
        isolated_env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "gitconfig")
        isolated_env["OSTYPE"] = "darwin"

        # 1. Native Bats test execution for git-browse-ci
        bats_executable = str(BATS_BIN) if BATS_BIN.exists() else "bats"
        bats_cmd = [bats_executable, "--tap", str(BATS_TEST)]
        bats_res = run_cmd(bats_cmd, REPO_ROOT, isolated_env)
        tap_cases = [
            line for line in bats_res["stdout"].splitlines()
            if line.startswith(("ok ", "not ok "))
        ]
        bats_passed = bats_res["returncode"] == 0 and len(tap_cases) > 0
        results.append({
            "name": "native_bats_git_browse_ci",
            "command": bats_cmd,
            "returncode": bats_res["returncode"],
            "stdout": bats_res["stdout"],
            "stderr": bats_res["stderr"],
            "executed_cases": len(tap_cases),
            "passed": bats_passed,
        })
        if not bats_passed:
            failures.append("Native Bats test suite failed or ran zero test cases.")

        # 2. Setup temporary repository fixture with commits A/B/C, main/topic branches
        work_dir = tmp_path / "repo"
        work_dir.mkdir()

        run_cmd(["git", "init", "--initial-branch", "main"], work_dir, isolated_env)
        run_cmd(["git", "config", "user.name", "Test User"], work_dir, isolated_env)
        run_cmd(["git", "config", "user.email", "test@example.com"], work_dir, isolated_env)

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

        # Configure origin and upstream remotes
        run_cmd(["git", "remote", "add", "origin", "https://github.com/origin-org/git-extras"], work_dir, isolated_env)
        run_cmd(["git", "remote", "add", "upstream", "https://github.com/upstream-org/git-extras"], work_dir, isolated_env)
        run_cmd(["git", "config", "branch.topic.remote", "upstream"], work_dir, isolated_env)

        # Case 1: Regression check - branch.topic.remote is correctly resolved via rev-parse --abbrev-ref
        reg_res = run_cmd(["git-browse-ci"], work_dir, isolated_env)
        reg_passed = (
            reg_res["returncode"] == 0
            and reg_res["stdout"] == "open https://github.com/upstream-org/git-extras/actions"
        )
        results.append({
            "name": "branch_remote_resolution_regression",
            "arguments": [],
            "expected": {
                "returncode": 0,
                "stdout": "open https://github.com/upstream-org/git-extras/actions",
            },
            "actual": {
                "returncode": reg_res["returncode"],
                "stdout": reg_res["stdout"],
            },
            "passed": reg_passed,
        })
        if not reg_passed:
            failures.append("Branch remote resolution regression assertion failed.")

        # Case 2: Mutation verification - simulate the mutant where &> /dev/null drops stdout
        # The mutant would execute: branch=$(git rev-parse --abbrev-ref HEAD &> /dev/null) -> branch="" -> falls back to origin
        mutant_script = """#!/usr/bin/env bash
branch=$(git rev-parse --abbrev-ref HEAD &> /dev/null)
remote=$(git config branch."${branch}".remote 2> /dev/null || echo "origin")
echo "mutant_remote:$remote"
"""
        mutant_path = tmp_path / "mutant.sh"
        mutant_path.write_text(mutant_script)
        mutant_path.chmod(0o755)
        mutant_res = run_cmd([str(mutant_path)], work_dir, isolated_env)
        mutant_rejected = (mutant_res["stdout"] == "mutant_remote:origin")
        results.append({
            "name": "mutant_rejected_demonstration",
            "description": "Mutant with &> /dev/null drops branch name and incorrectly falls back to origin",
            "mutant_output": mutant_res["stdout"],
            "expected_rejection": "mutant_remote:origin",
            "passed": mutant_rejected,
        })
        if not mutant_rejected:
            failures.append("Mutant rejection demonstration failed.")

        # Case 3: Fallback to origin when branch has no configured remote
        run_cmd(["git", "checkout", "main"], work_dir, isolated_env)
        # main has no branch.main.remote set
        fallback_res = run_cmd(["git-browse-ci"], work_dir, isolated_env)
        fallback_passed = (
            fallback_res["returncode"] == 0
            and fallback_res["stdout"] == "open https://github.com/origin-org/git-extras/actions"
        )
        results.append({
            "name": "fallback_to_origin",
            "arguments": [],
            "expected": {
                "returncode": 0,
                "stdout": "open https://github.com/origin-org/git-extras/actions",
            },
            "actual": {
                "returncode": fallback_res["returncode"],
                "stdout": fallback_res["stdout"],
            },
            "passed": fallback_passed,
        })
        if not fallback_passed:
            failures.append("Fallback to origin assertion failed.")

        # Case 4: Explicit remote argument overrides branch remote
        explicit_res = run_cmd(["git-browse-ci", "upstream"], work_dir, isolated_env)
        explicit_passed = (
            explicit_res["returncode"] == 0
            and explicit_res["stdout"] == "open https://github.com/upstream-org/git-extras/actions"
        )
        results.append({
            "name": "explicit_remote_argument",
            "arguments": ["upstream"],
            "expected": {
                "returncode": 0,
                "stdout": "open https://github.com/upstream-org/git-extras/actions",
            },
            "actual": {
                "returncode": explicit_res["returncode"],
                "stdout": explicit_res["stdout"],
            },
            "passed": explicit_passed,
        })
        if not explicit_passed:
            failures.append("Explicit remote argument assertion failed.")

        # Case 5: Failure condition - non-existent remote exits 1
        fail_res = run_cmd(["git-browse-ci", "nonexistent-remote"], work_dir, isolated_env)
        combined_output = fail_res["stdout"] + fail_res["stderr"]
        fail_passed = (
            fail_res["returncode"] == 1
            and "Remote not found" in combined_output
        )
        results.append({
            "name": "nonexistent_remote_failure",
            "arguments": ["nonexistent-remote"],
            "expected": {"returncode": 1, "output_contains": "Remote not found"},
            "actual": {"returncode": fail_res["returncode"], "output": combined_output},
            "passed": fail_passed,
        })
        if not fail_passed:
            failures.append("Nonexistent remote failure assertion failed.")

        # Case 6: GitLab and Bitbucket remote URL parsing
        run_cmd(["git", "remote", "add", "gitlab", "git@gitlab.com:owner/project.git"], work_dir, isolated_env)
        run_cmd(["git", "remote", "add", "bitbucket", "https://bitbucket.org/owner/project.git"], work_dir, isolated_env)

        gl_res = run_cmd(["git-browse-ci", "gitlab"], work_dir, isolated_env)
        bb_res = run_cmd(["git-browse-ci", "bitbucket"], work_dir, isolated_env)

        gl_passed = gl_res["returncode"] == 0 and gl_res["stdout"] == "open http://gitlab.com/owner/project/-/pipelines"
        bb_passed = bb_res["returncode"] == 0 and bb_res["stdout"] == "open https://bitbucket.org/owner/project/addon/pipelines/home"

        results.append({
            "name": "gitlab_remote_ci_url",
            "arguments": ["gitlab"],
            "expected": {"returncode": 0, "stdout": "open http://gitlab.com/owner/project/-/pipelines"},
            "actual": {"returncode": gl_res["returncode"], "stdout": gl_res["stdout"]},
            "passed": gl_passed,
        })
        results.append({
            "name": "bitbucket_remote_ci_url",
            "arguments": ["bitbucket"],
            "expected": {"returncode": 0, "stdout": "open https://bitbucket.org/owner/project/addon/pipelines/home"},
            "actual": {"returncode": bb_res["returncode"], "stdout": bb_res["stdout"]},
            "passed": bb_passed,
        })
        if not (gl_passed and bb_passed):
            failures.append("GitLab/Bitbucket remote URL assertion failed.")

    tool_versions = {
        "git": get_version(["git", "--version"], isolated_env),
        "bash": get_version(["bash", "--version"], isolated_env),
        "bats": get_version([bats_executable, "--version"], isolated_env),
        "python3": get_version(["python3", "--version"], isolated_env),
    }

    report = {
        "task_id": "R13-T050",
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
