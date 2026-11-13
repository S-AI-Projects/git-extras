#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run_cmd(cmd, cwd=None, env=None):
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def get_tool_versions(env):
    tools = {
        "git": ["git", "--version"],
        "bash": ["bash", "--version"],
        "bats": ["bats", "--version"],
        "python3": ["python3", "--version"],
    }
    versions = {}
    for name, cmd in tools.items():
        try:
            res = run_cmd(cmd, env=env)
            versions[name] = res["stdout"].splitlines()[0] if res["stdout"] else res["stderr"]
        except FileNotFoundError:
            versions[name] = "not installed"
    return versions


def main():
    repo_root = Path(__file__).resolve().parents[2]
    bin_dir = repo_root / "bin"
    evidence_dir = repo_root / "work" / "R13-T044"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["GIT_CONFIG_NOSYSTEM"] = "1"

    cases = []

    with tempfile.TemporaryDirectory(prefix="r13_t044_check_") as tmp:
        tmp_path = Path(tmp)
        env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "isolated_global_gitconfig")

        local_repo = tmp_path / "work repo with spaces"
        local_repo.mkdir()
        bare_remote = tmp_path / "bare remote with spaces.git"
        bare_remote.mkdir()

        run_cmd(["git", "init", "--initial-branch", "main"], cwd=local_repo, env=env)
        run_cmd(["git", "config", "user.name", "Test User"], cwd=local_repo, env=env)
        run_cmd(["git", "config", "user.email", "test@example.com"], cwd=local_repo, env=env)

        (local_repo / "file.txt").write_text("A\n")
        run_cmd(["git", "add", "file.txt"], cwd=local_repo, env=env)
        run_cmd(["git", "commit", "-m", "Commit A"], cwd=local_repo, env=env)

        run_cmd(["git", "checkout", "-b", "topic"], cwd=local_repo, env=env)
        (local_repo / "file.txt").write_text("B\n")
        run_cmd(["git", "commit", "-am", "Commit B"], cwd=local_repo, env=env)

        (local_repo / "file.txt").write_text("C\n")
        run_cmd(["git", "commit", "-am", "Commit C"], cwd=local_repo, env=env)

        run_cmd(["git", "checkout", "main"], cwd=local_repo, env=env)

        run_cmd(["git", "init", "--bare", "--initial-branch", "main"], cwd=bare_remote, env=env)
        run_cmd(["git", "push", str(bare_remote), "topic:refs/pull/101/head"], cwd=local_repo, env=env)
        run_cmd(["git", "push", str(bare_remote), "topic:refs/pull/101/merge"], cwd=local_repo, env=env)

        (local_repo / "unrelated_a.txt").write_text("keep a\n")
        (local_repo / "unrelated_b.txt").write_text("keep b\n")
        (local_repo / "refs" / "heads" / "pr").mkdir(parents=True)
        (local_repo / "refs" / "heads" / "pr" / "unrelated_file").write_text("keep glob\n")

        before_branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=local_repo, env=env)["stdout"]
        res_success = run_cmd(["git-pr", "--merge", "101", str(bare_remote)], cwd=local_repo, env=env)
        after_branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=local_repo, env=env)["stdout"]
        stored_remote = run_cmd(["git", "config", "--local", "--get", "branch.pr/101.remote"], cwd=local_repo, env=env)["stdout"]
        stored_merge = run_cmd(["git", "config", "--local", "--get", "branch.pr/101.merge"], cwd=local_repo, env=env)["stdout"]

        passed_1 = (
            res_success["returncode"] == 0
            and after_branch == "pr/101"
            and stored_remote == str(bare_remote)
            and stored_merge == "refs/pull/101/merge"
            and (local_repo / "unrelated_a.txt").exists()
            and (local_repo / "unrelated_b.txt").exists()
        )
        cases.append({
            "name": "quoted_path_with_spaces_and_merge",
            "inputs": ["git-pr", "--merge", "101", str(bare_remote)],
            "expected": {
                "returncode": 0,
                "after_branch": "pr/101",
                "stored_remote": str(bare_remote),
                "stored_merge": "refs/pull/101/merge",
            },
            "actual": {
                "returncode": res_success["returncode"],
                "before_branch": before_branch,
                "after_branch": after_branch,
                "stored_remote": stored_remote,
                "stored_merge": stored_merge,
                "stdout": res_success["stdout"],
                "stderr": res_success["stderr"],
            },
            "passed": passed_1,
        })

        wildcard_arg = "bad*pattern*101"
        res_wildcard = run_cmd(["git-pr", wildcard_arg], cwd=local_repo, env=env)
        run_cmd(["git", "checkout", "main"], cwd=local_repo, env=env)
        run_cmd(["git", "checkout", "main"], cwd=local_repo, env=env)
        res_clean = run_cmd(["git-pr", "clean"], cwd=local_repo, env=env)
        glob_file_intact = (local_repo / "refs" / "heads" / "pr" / "unrelated_file").exists()

        passed_2 = (
            res_wildcard["returncode"] != 0
            and f"{wildcard_arg} doesn't match the pr id pattern." in res_wildcard["stdout"]
            and res_clean["returncode"] == 0
            and glob_file_intact
        )
        cases.append({
            "name": "wildcard_argument_boundary_and_clean_glob_safety",
            "inputs": [["git-pr", wildcard_arg], ["git-pr", "clean"]],
            "expected": {
                "wildcard_returncode_nonzero": True,
                "wildcard_stdout_contains": f"{wildcard_arg} doesn't match the pr id pattern.",
                "clean_returncode": 0,
                "unrelated_glob_file_intact": True,
            },
            "actual": {
                "wildcard_returncode": res_wildcard["returncode"],
                "wildcard_stdout": res_wildcard["stdout"],
                "clean_returncode": res_clean["returncode"],
                "unrelated_glob_file_intact": glob_file_intact,
            },
            "passed": passed_2,
        })

        res_empty = run_cmd(["git-pr"], cwd=local_repo, env=env)
        passed_3 = (
            res_empty["returncode"] != 0
            and "pr number required." in res_empty["stderr"]
        )
        cases.append({
            "name": "missing_pr_argument_edge_failure",
            "inputs": ["git-pr"],
            "expected": {
                "returncode_nonzero": True,
                "stderr": "pr number required.",
            },
            "actual": {
                "returncode": res_empty["returncode"],
                "stdout": res_empty["stdout"],
                "stderr": res_empty["stderr"],
            },
            "passed": passed_3,
        })

    bats_res = run_cmd(["bats", "tests/git-pr.bats"], cwd=repo_root, env=env)
    cases.append({
        "name": "native_bats_git_pr",
        "inputs": ["bats", "tests/git-pr.bats"],
        "expected": {"returncode": 0},
        "actual": {
            "returncode": bats_res["returncode"],
            "stdout": bats_res["stdout"],
            "stderr": bats_res["stderr"],
        },
        "passed": bats_res["returncode"] == 0,
    })

    all_passed = len(cases) > 0 and all(c["passed"] for c in cases)
    report = {
        "task": "R13-T044",
        "item": "git-pr",
        "total_cases": len(cases),
        "all_passed": all_passed,
        "tool_versions": get_tool_versions(env),
        "cases": cases,
    }

    report_file = evidence_dir / "report.json"
    report_file.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
