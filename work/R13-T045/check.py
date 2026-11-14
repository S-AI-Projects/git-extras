#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = Path(__file__).resolve().parent


def get_version(cmd):
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        out = (res.stdout or res.stderr).strip().splitlines()
        return out[0] if out else "unknown"
    except Exception as exc:
        return f"unavailable ({exc})"


def main():
    # 1. Collect tool versions
    tool_versions = {
        "git": get_version(["git", "--version"]),
        "bash": get_version(["bash", "--version"]),
        "bats": get_version(["bats", "--version"]),
        "make": get_version(["make", "--version"]),
        "python3": get_version(["python3", "--version"]),
    }

    # 2. Run the native Bats test suite for git-gh-pages
    bats_file = REPO_ROOT / "tests" / "git-gh-pages.bats"
    bats_proc = subprocess.run(
        ["bats", str(bats_file)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    tap_lines = [
        line.strip()
        for line in bats_proc.stdout.splitlines()
        if re.match(r"^(ok|not ok)\s+\d+", line.strip())
    ]

    # Reject zero-case runs or any failing Bats assertions
    if bats_proc.returncode != 0 or len(tap_lines) < 2:
        sys.stderr.write("ERROR: Bats suite failed or ran fewer than 2 cases.\n")
        sys.stderr.write(bats_proc.stdout + "\n" + bats_proc.stderr + "\n")
        sys.exit(1)

    if any(line.startswith("not ok") for line in tap_lines):
        sys.stderr.write("ERROR: One or more Bats assertions failed.\n")
        sys.stderr.write(bats_proc.stdout + "\n")
        sys.exit(1)

    # 3. Direct isolated end-to-end verification recording before/after state
    bin_dir = str(REPO_ROOT / "bin")
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["GIT_CONFIG_NOSYSTEM"] = "1"

    case_records = []

    with tempfile.TemporaryDirectory(prefix="r13-t045-verify-") as tmp:
        tmp_path = Path(tmp)
        env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "gitconfig")

        remote_base = tmp_path / "remotes" / "testuser"
        remote_base.mkdir(parents=True)
        bare_remote = remote_base / "testrepo.git"
        subprocess.run(["git", "init", "--bare", str(bare_remote)], check=True, capture_output=True)

        work_repo = tmp_path / "repo"
        work_repo.mkdir()
        subprocess.run(["git", "init", "--initial-branch", "main"], cwd=work_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=work_repo, env=env, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=work_repo, env=env, check=True)

        for msg in ("A", "B"):
            (work_repo / "file.txt").write_text(f"{msg}\n")
            subprocess.run(["git", "add", "file.txt"], cwd=work_repo, env=env, check=True)
            subprocess.run(["git", "commit", "-m", msg], cwd=work_repo, env=env, check=True, capture_output=True)

        subprocess.run(["git", "checkout", "-b", "topic"], cwd=work_repo, env=env, check=True, capture_output=True)
        (work_repo / "file.txt").write_text("C\n")
        subprocess.run(["git", "add", "file.txt"], cwd=work_repo, env=env, check=True)
        subprocess.run(["git", "commit", "-m", "C"], cwd=work_repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=work_repo, env=env, check=True, capture_output=True)

        before_branches = subprocess.run(
            ["git", "branch", "--format=%(refname:short)"],
            cwd=work_repo, env=env, capture_output=True, text=True, check=True
        ).stdout.strip().splitlines()

        # Success case execution
        success_env = env.copy()
        success_env["GIT_GH_PAGES_REMOTE_BASE"] = str(tmp_path / "remotes")
        success_args = ["git-gh-pages", "testuser", "testrepo"]
        success_res = subprocess.run(
            success_args, cwd=work_repo, env=success_env, capture_output=True, text=True, check=False
        )

        after_branches = subprocess.run(
            ["git", "branch", "--format=%(refname:short)"],
            cwd=work_repo, env=env, capture_output=True, text=True, check=True
        ).stdout.strip().splitlines()

        remote_ref = subprocess.run(
            ["git", f"--git-dir={bare_remote}", "rev-parse", "--verify", "refs/heads/gh-pages"],
            capture_output=True, text=True, check=False
        )

        assert success_res.returncode == 0, f"Expected exit 0, got {success_res.returncode}"
        assert "gh-pages" in after_branches, "Expected gh-pages branch locally"
        assert (work_repo / "index.html").read_text().strip() == "My Page", "Expected index.html content"
        assert remote_ref.returncode == 0, "Expected gh-pages pushed to local bare remote"

        case_records.append({
            "case": "success_isolated_bare_remote",
            "arguments": success_args,
            "expected_exit_code": 0,
            "actual_exit_code": success_res.returncode,
            "before_state": {"local_branches": before_branches, "remote_has_gh_pages": False},
            "after_state": {
                "local_branches": after_branches,
                "index_html": (work_repo / "index.html").read_text().strip(),
                "remote_has_gh_pages": remote_ref.returncode == 0,
            },
        })

        # Failure edge-case execution (missing required username/repository)
        fail_args = ["git-gh-pages"]
        fail_res = subprocess.run(
            fail_args, input="\n\n", cwd=work_repo, env=env, capture_output=True, text=True, check=False
        )
        assert fail_res.returncode != 0, "Expected non-zero exit code for missing arguments"
        assert "Error: GitHub username and repository name are required." in fail_res.stderr

        case_records.append({
            "case": "failure_missing_arguments",
            "arguments": fail_args,
            "expected_exit_code": "non-zero",
            "actual_exit_code": fail_res.returncode,
            "stderr": fail_res.stderr.strip(),
        })

    # 4. Save evidence JSON
    evidence = {
        "task_id": "R13-T045",
        "item": "git-gh-pages",
        "tool_versions": tool_versions,
        "bats_output": tap_lines,
        "cases": case_records,
    }
    evidence_path = EVIDENCE_DIR / "evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"Verification passed ({len(case_records)} cases). Evidence saved to {evidence_path}.")


if __name__ == "__main__":
    main()
