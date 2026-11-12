#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = REPO_ROOT / "bin"
EVIDENCE_FILE = Path(__file__).resolve().parent / "evidence.json"


def run_cmd(cmd, cwd=None, env=None):
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
    )


def init_sample_repo(repo_path: Path, create_topic: bool = True):
    repo_path.mkdir(parents=True, exist_ok=True)
    run_cmd(["git", "init", "--initial-branch", "main"], cwd=repo_path)
    run_cmd(["git", "config", "user.name", "Test User"], cwd=repo_path)
    run_cmd(["git", "config", "user.email", "test@example.com"], cwd=repo_path)

    for label in ["A", "B", "C"]:
        (repo_path / "history.txt").write_text(f"Commit {label}\n")
        run_cmd(["git", "add", "history.txt"], cwd=repo_path)
        run_cmd(["git", "commit", "-m", label], cwd=repo_path)

    if create_topic:
        run_cmd(["git", "branch", "topic"], cwd=repo_path)


def snapshot_repo(repo_path: Path):
    head = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_path).stdout.strip()
    main_ref = run_cmd(["git", "rev-parse", "refs/heads/main"], cwd=repo_path).stdout.strip()
    topic_res = run_cmd(["git", "rev-parse", "refs/heads/topic"], cwd=repo_path)
    topic_ref = topic_res.stdout.strip() if topic_res.returncode == 0 else None
    branches = sorted(
        line.strip().lstrip("* ")
        for line in run_cmd(["git", "branch"], cwd=repo_path).stdout.splitlines()
        if line.strip()
    )
    status = run_cmd(["git", "status", "--porcelain"], cwd=repo_path).stdout.strip()
    return {
        "head": head,
        "main_ref": main_ref,
        "topic_ref": topic_ref,
        "branches": branches,
        "status": status,
    }


def main():
    tmp_dir = Path(tempfile.mkdtemp(prefix="git-bulk-check-"))
    evidence = {"cases": []}

    try:
        global_cfg = tmp_dir / "gitconfig"
        env = os.environ.copy()
        env["PATH"] = f"{BIN_DIR}:{env.get('PATH', '')}"
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = str(global_cfg)

        ws_dir = tmp_dir / "workspace"
        repo_a = ws_dir / "repo-a"
        hidden_repo = ws_dir / ".hidden" / "repo-hidden"
        ext_repo = tmp_dir / "external-repo"
        sym_repo = ws_dir / "repo-symlink"

        init_sample_repo(repo_a, create_topic=True)
        init_sample_repo(hidden_repo, create_topic=True)
        init_sample_repo(ext_repo, create_topic=True)
        os.symlink(ext_repo, sym_repo)

        # Register workspace
        reg = run_cmd(["git", "bulk", "--addworkspace", "demo", str(ws_dir)], cwd=tmp_dir, env=env)
        assert reg.returncode == 0, f"Failed to register workspace: {reg.stderr}"

        # Before snapshot
        before = {
            "repo_a": snapshot_repo(repo_a),
            "hidden_repo": snapshot_repo(hidden_repo),
            "ext_repo": snapshot_repo(ext_repo),
        }

        # Case 1 (Success): Create a new branch across workspace while skipping hidden and symlinks
        res_ok = run_cmd(
            [
                "git",
                "bulk",
                "--no-follow-hidden",
                "--no-follow-symlinks",
                "--quiet",
                "-w",
                "demo",
                "branch",
                "bulk-tested",
            ],
            cwd=tmp_dir,
            env=env,
        )
        assert res_ok.returncode == 0, f"Expected success, got {res_ok.returncode}: {res_ok.stderr}"
        assert "Executing bulk operation in workspace" not in res_ok.stderr, "Quiet flag failed to suppress banner"

        after = {
            "repo_a": snapshot_repo(repo_a),
            "hidden_repo": snapshot_repo(hidden_repo),
            "ext_repo": snapshot_repo(ext_repo),
        }

        # Assertions on state transitions
        assert "bulk-tested" in after["repo_a"]["branches"], "Expected branch 'bulk-tested' in repo_a"
        assert after["repo_a"]["main_ref"] == before["repo_a"]["main_ref"], "Unrelated main ref changed"
        assert after["repo_a"]["topic_ref"] == before["repo_a"]["topic_ref"], "Unrelated topic ref changed"
        assert "bulk-tested" not in after["hidden_repo"]["branches"], "--no-follow-hidden failed"
        assert "bulk-tested" not in after["ext_repo"]["branches"], "--no-follow-symlinks failed"

        evidence["cases"].append({
            "name": "success_scoped_branch_creation",
            "command": "git bulk --no-follow-hidden --no-follow-symlinks --quiet -w demo branch bulk-tested",
            "exit_code": res_ok.returncode,
            "before": before,
            "after": after,
        })

        # Case 2 (Failure / Edge case): Unknown workspace
        res_fail = run_cmd(["git", "bulk", "-w", "invalid-ws", "status"], cwd=tmp_dir, env=env)
        assert res_fail.returncode != 0, "Expected non-zero exit code for invalid workspace"
        assert "unknown workspace name: invalid-ws" in res_fail.stderr, f"Unexpected stderr: {res_fail.stderr}"

        evidence["cases"].append({
            "name": "failure_unknown_workspace",
            "command": "git bulk -w invalid-ws status",
            "exit_code": res_fail.returncode,
            "stderr": res_fail.stderr.strip(),
        })

        # Tool versions
        git_ver = run_cmd(["git", "--version"]).stdout.strip()
        py_ver = run_cmd(["python3", "--version"]).stdout.strip()
        evidence["versions"] = {"git": git_ver, "python": py_ver}

        EVIDENCE_FILE.write_text(json.dumps(evidence, indent=2) + "\n")
        print("ALL CHECKS PASSED")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
