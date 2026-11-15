#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = REPO_ROOT / "bin"
BATS_BIN = REPO_ROOT / "vendor" / "bats-core" / "bin" / "bats"
BATS_TEST = REPO_ROOT / "tests" / "git-lock.bats"
REPORT_PATH = Path(__file__).resolve().parent / "verification_report.json"


def run_cmd(cmd, cwd, env):
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
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

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        isolated_env = base_env.copy()
        isolated_env["GIT_CONFIG_NOSYSTEM"] = "1"
        isolated_env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "gitconfig")

        # 1. Run native Bats test suite for git-lock
        bats_cmd = [str(BATS_BIN) if BATS_BIN.exists() else "bats", "--tap", str(BATS_TEST)]
        bats_res = run_cmd(bats_cmd, REPO_ROOT, isolated_env)
        tap_cases = [line for line in bats_res["stdout"].splitlines() if line.startswith(("ok ", "not ok "))]
        bats_res["executed_cases"] = len(tap_cases)
        results.append({"name": "native_bats_git_lock", **bats_res})

        if bats_res["returncode"] != 0 or len(tap_cases) == 0:
            failures.append("Native Bats suite failed or executed 0 cases.")

        # 2. Isolated repo with bare remote, commits A/B/C, branches main and topic
        remote_dir = tmp_path / "remote.git"
        work_dir = tmp_path / "repo"
        work_dir.mkdir()

        run_cmd(["git", "init", "--bare", str(remote_dir)], tmp_path, isolated_env)
        run_cmd(["git", "init", "--initial-branch", "main"], work_dir, isolated_env)
        run_cmd(["git", "config", "user.name", "Test User"], work_dir, isolated_env)
        run_cmd(["git", "config", "user.email", "test@example.com"], work_dir, isolated_env)
        run_cmd(["git", "remote", "add", "origin", str(remote_dir)], work_dir, isolated_env)

        for label in ("A", "B", "C"):
            (work_dir / "app.cfg").write_text(f"version={label}\n")
            run_cmd(["git", "add", "app.cfg"], work_dir, isolated_env)
            run_cmd(["git", "commit", "-m", f"Commit {label}"], work_dir, isolated_env)

        run_cmd(["git", "checkout", "-b", "topic"], work_dir, isolated_env)
        run_cmd(["git", "checkout", "main"], work_dir, isolated_env)

        # Success case: lock tracked file
        before_ls = run_cmd(["git", "ls-files", "-v", "app.cfg"], work_dir, isolated_env)["stdout"]
        lock_ok = run_cmd(["git", "lock", "app.cfg"], work_dir, isolated_env)
        after_ls = run_cmd(["git", "ls-files", "-v", "app.cfg"], work_dir, isolated_env)["stdout"]
        (work_dir / "app.cfg").write_text("local_secret=123\n")
        status_after = run_cmd(["git", "status", "--short"], work_dir, isolated_env)["stdout"]

        success_passed = (
            lock_ok["returncode"] == 0
            and before_ls == "H app.cfg"
            and after_ls == "S app.cfg"
            and status_after == ""
        )
        results.append({
            "name": "cli_lock_tracked_file_success",
            "arguments": ["app.cfg"],
            "expected": {"returncode": 0, "before_ls": "H app.cfg", "after_ls": "S app.cfg", "status": ""},
            "actual": {
                "returncode": lock_ok["returncode"],
                "before_ls": before_ls,
                "after_ls": after_ls,
                "status": status_after,
            },
            "passed": success_passed,
        })
        if not success_passed:
            failures.append("CLI tracked file lock assertion failed.")

        # Edge/failure case: missing filename
        lock_missing = run_cmd(["git", "lock"], work_dir, isolated_env)
        missing_passed = lock_missing["returncode"] == 1 and lock_missing["stderr"] == "filename required."
        results.append({
            "name": "cli_lock_missing_filename_failure",
            "arguments": [],
            "expected": {"returncode": 1, "stderr": "filename required."},
            "actual": {"returncode": lock_missing["returncode"], "stderr": lock_missing["stderr"]},
            "passed": missing_passed,
        })
        if not missing_passed:
            failures.append("CLI missing filename assertion failed.")

        # Edge/failure case: untracked file
        (work_dir / "untracked.cfg").write_text("temp=1\n")
        lock_untracked = run_cmd(["git", "lock", "untracked.cfg"], work_dir, isolated_env)
        untracked_passed = lock_untracked["returncode"] != 0
        results.append({
            "name": "cli_lock_untracked_file_failure",
            "arguments": ["untracked.cfg"],
            "expected": {"returncode_nonzero": True},
            "actual": {"returncode": lock_untracked["returncode"], "stderr": lock_untracked["stderr"]},
            "passed": untracked_passed,
        })
        if not untracked_passed:
            failures.append("CLI untracked file assertion failed.")

    report = {
        "task_id": "R13-T046",
        "tool_versions": {
            "git": get_version(["git", "--version"], base_env),
            "bash": get_version(["bash", "--version"], base_env),
            "bats": get_version([str(BATS_BIN) if BATS_BIN.exists() else "bats", "--version"], base_env),
            "python3": get_version(["python3", "--version"], base_env),
        },
        "total_checks": len(results),
        "passed": len(failures) == 0 and len(results) > 0,
        "failures": failures,
        "results": results,
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

    if failures or len(results) == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
