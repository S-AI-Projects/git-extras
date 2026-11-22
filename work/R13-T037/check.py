#!/usr/bin/env python3
"""Automated check runner for R13-T037: git-scp documented usage example and verification."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK_DIR = pathlib.Path(__file__).resolve().parent
ERRORS: list[str] = []


def run(command: list[str], *, cwd: pathlib.Path, env: dict[str, str] | None = None, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def get_version(command: list[str], *, cwd: pathlib.Path = ROOT) -> str:
    res = run(command, cwd=cwd)
    output = (res.stdout or res.stderr).strip().splitlines()
    return output[0] if output else "unknown"


def git(repo: pathlib.Path, *args: str, env: dict[str, str]) -> str:
    res = run(["git", *args], cwd=repo, env=env)
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed (exit {res.returncode}): {res.stderr}")
    return res.stdout.strip()


def get_repo_state(repo: pathlib.Path, *, env: dict[str, str]) -> dict[str, str]:
    return {
        "head": git(repo, "rev-parse", "HEAD", env=env),
        "branch": git(repo, "branch", "--show-current", env=env),
        "topic_ref": git(repo, "rev-parse", "topic", env=env),
        "status_short": git(repo, "status", "--short", env=env),
    }


def create_test_environment(base_dir: pathlib.Path) -> tuple[pathlib.Path, dict[str, str], pathlib.Path, pathlib.Path]:
    global_config = base_dir / "isolated-global.gitconfig"
    global_config.write_text("", encoding="utf-8")

    bare_remote = base_dir / "remote.git"
    bare_remote.mkdir()
    init_bare = run(["git", "init", "--bare", "--initial-branch", "main"], cwd=bare_remote)
    if init_bare.returncode != 0:
        raise RuntimeError(f"Failed to init bare remote: {init_bare.stderr}")

    repo = base_dir / "repo"
    repo.mkdir()

    staging_dir = base_dir / "staging"

    # Create command wrapper ensuring repository helpers are sourced
    command_bin = base_dir / "bin"
    command_bin.mkdir()
    wrapper = command_bin / "git-scp"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        f"source {str(ROOT / 'helper/reset-env')!r}\n"
        f"source {str(ROOT / 'helper/git-extra-utility')!r}\n"
        f"source {str(ROOT / 'helper/is-git-repo')!r}\n"
        f"exec {str(ROOT / 'bin/git-scp')!r} \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(global_config),
            "PATH": f"{command_bin}:{ROOT / 'bin'}:/opt/homebrew/bin:{env.get('PATH', '')}",
        }
    )

    init_res = run(["git", "init", "--initial-branch", "main"], cwd=repo, env=env)
    if init_res.returncode != 0:
        raise RuntimeError(f"Failed to init repo: {init_res.stderr}")

    git(repo, "config", "user.name", "Kushal Pandya", env=env)
    git(repo, "config", "user.email", "kushalpandya037@gmail.com", env=env)
    git(repo, "remote", "add", "origin", str(bare_remote), env=env)

    # Commit A
    (repo / "tracked.txt").write_text("hello\n", encoding="utf-8")
    git(repo, "add", "tracked.txt", env=env)
    git(repo, "commit", "-m", "Commit A", env=env)

    # Commit B
    (repo / "other.txt").write_text("Commit B content\n", encoding="utf-8")
    git(repo, "add", "other.txt", env=env)
    git(repo, "commit", "-m", "Commit B", env=env)

    # Commit C on topic branch
    git(repo, "switch", "-c", "topic", env=env)
    (repo / "topic.txt").write_text("Topic content\n", encoding="utf-8")
    git(repo, "add", "topic.txt", env=env)
    git(repo, "commit", "-m", "Commit C", env=env)

    # Return to main
    git(repo, "switch", "main", env=env)
    git(repo, "push", "-u", "origin", "main", env=env)
    git(repo, "push", "origin", "topic", env=env)

    # Setup git-scp remotes
    git(repo, "remote", "add", "staging", str(staging_dir), env=env)
    git(repo, "remote", "add", "fake", str(base_dir / "never-created"), env=env)

    # Add uncommitted modification to tracked.txt
    with open(repo / "tracked.txt", "a", encoding="utf-8") as f:
        f.write("world\n")

    return repo, env, staging_dir, base_dir / "never-created"


def run_direct_case(
    name: str,
    args: list[str],
    expectations: dict[str, object],
    *,
    input_text: str | None = None,
    setup_fn=None,
    assert_fn=None,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=f"R13-T037-{name}-") as tmpdir:
        base_dir = pathlib.Path(tmpdir)
        repo, env, staging_dir, fake_dir = create_test_environment(base_dir)

        if setup_fn:
            setup_fn(repo, env, staging_dir, fake_dir)

        before = get_repo_state(repo, env=env)
        cmd = ["git", "scp", *args]
        res = run(cmd, cwd=repo, env=env, input_text=input_text)
        after = get_repo_state(repo, env=env)

        actual = {
            "exit_status": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "before_state": before,
            "after_state": after,
        }

        passed = True
        if res.returncode != expectations["exit_status"]:
            ERRORS.append(
                f"{name}: expected exit code {expectations['exit_status']}, got {res.returncode}"
            )
            passed = False

        if "stdout_contains" in expectations:
            for item in expectations["stdout_contains"]:
                if item not in res.stdout:
                    ERRORS.append(
                        f"{name}: expected stdout to contain {item!r}, got {res.stdout!r}"
                    )
                    passed = False

        if "stderr_contains" in expectations:
            if expectations["stderr_contains"] not in res.stderr:
                ERRORS.append(
                    f"{name}: expected stderr to contain {expectations['stderr_contains']!r}, got {res.stderr!r}"
                )
                passed = False

        if assert_fn:
            custom_ok = assert_fn(repo, staging_dir, fake_dir, env)
            if not custom_ok:
                passed = False

        for state_key, expected_val in expectations.get("after_state", {}).items():
            observed = after[state_key]
            if expected_val == "<before>" and observed != before[state_key]:
                ERRORS.append(
                    f"{name}: expected {state_key} unchanged ({before[state_key]!r}), got {observed!r}"
                )
                passed = False
            elif expected_val == "<changed>" and observed == before[state_key]:
                ERRORS.append(f"{name}: expected {state_key} to change, but remained unchanged")
                passed = False

        return {
            "name": name,
            "arguments": args,
            "command": cmd,
            "expected": expectations,
            "actual": actual,
            "passed": passed,
        }


def main() -> int:
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    tool_versions = {
        "git": get_version(["git", "--version"]),
        "bash": get_version(["bash", "--version"]),
        "bats": get_version(["bats", "--version"]),
        "python3": get_version(["python3", "--version"]),
        "make": get_version(["make", "--version"]),
        "rsync": get_version(["rsync", "--version"]),
    }

    (WORK_DIR / "tool_versions.json").write_text(
        json.dumps(tool_versions, indent=2) + "\n",
        encoding="utf-8",
    )

    # 1. Native Bats suite
    bats_bin = shutil.which("bats") or "/opt/homebrew/bin/bats"
    bats_test_file = ROOT / "tests" / "git-scp.bats"
    bats_result = run([bats_bin, "--tap", str(bats_test_file)], cwd=ROOT)

    native_test_names: list[str] = []
    bats_passed = (bats_result.returncode == 0)
    for line in bats_result.stdout.splitlines():
        if line.startswith("ok "):
            parts = line.split(" ", 2)
            if len(parts) >= 3:
                native_test_names.append(parts[2].strip())
        elif line.startswith("not ok "):
            bats_passed = False
            ERRORS.append(f"Native Bats failed: {line}")

    if not bats_passed:
        ERRORS.append(f"Bats test suite exited with {bats_result.returncode}")

    (WORK_DIR / "native_test_names.txt").write_text(
        "\n".join(native_test_names) + "\n",
        encoding="utf-8",
    )

    # 2. Direct isolated test scenarios
    cases: list[dict[str, object]] = []

    # Case 1: Complete documented usage example with setup, command, output and state verification
    def assert_usage_example(repo: pathlib.Path, staging_dir: pathlib.Path, fake_dir: pathlib.Path, env: dict[str, str]) -> bool:
        dest_file = staging_dir / "tracked.txt"
        if not dest_file.exists():
            ERRORS.append(f"Destination file {dest_file} does not exist after git scp")
            return False
        dest_content = dest_file.read_text(encoding="utf-8")
        source_content = (repo / "tracked.txt").read_text(encoding="utf-8")
        if dest_content != source_content:
            ERRORS.append(f"Destination content {dest_content!r} does not match source {source_content!r}")
            return False
        return True

    cases.append(
        run_direct_case(
            "complete-usage-example-success",
            ["--verbose", "staging"],
            {
                "exit_status": 0,
                "stdout_contains": [
                    "diff --git a/tracked.txt b/tracked.txt",
                    "+world",
                    "Pushing to staging",
                    "tracked.txt",
                ],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "M  tracked.txt",
                },
            },
            assert_fn=assert_usage_example,
        )
    )

    # Case 2: Dry-run preview
    def assert_dry_run(repo: pathlib.Path, staging_dir: pathlib.Path, fake_dir: pathlib.Path, env: dict[str, str]) -> bool:
        if fake_dir.exists():
            ERRORS.append(f"Dry run should never create destination directory {fake_dir}")
            return False
        return True

    cases.append(
        run_direct_case(
            "dry-run-preview-success",
            ["-n", "fake"],
            {
                "exit_status": 0,
                "stdout_contains": ["tracked.txt", "DRY RUN"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "<before>",
                },
            },
            assert_fn=assert_dry_run,
        )
    )

    # Case 3: Non-existent remote error
    cases.append(
        run_direct_case(
            "nonexistent-remote-failure",
            ["missing_remote"],
            {
                "exit_status": 1,
                "stdout_contains": ["Remote missing_remote does not exist in your git config"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "<before>",
                },
            },
        )
    )

    # Case 4: Interactive mode abort
    cases.append(
        run_direct_case(
            "interactive-abort-success",
            ["-i", "fake"],
            {
                "exit_status": 0,
                "stdout_contains": ["Aborted, nothing synced."],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "<before>",
                },
            },
            input_text="n\n",
            assert_fn=assert_dry_run,
        )
    )

    # Case 5: Sanitize configuration with --add and --get-all
    def setup_sanitize(repo: pathlib.Path, env: dict[str, str], staging_dir: pathlib.Path, fake_dir: pathlib.Path):
        git(repo, "config", "--add", "extras.scp.sanitize", "dos2unix", env=env)

    cases.append(
        run_direct_case(
            "sanitize-config-success",
            ["--verbose", "-n", "fake"],
            {
                "exit_status": 0,
                "stdout_contains": ["DRY RUN"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "<before>",
                },
            },
            setup_fn=setup_sanitize,
            assert_fn=assert_dry_run,
        )
    )

    # Check requirement: zero-case run must be rejected
    if len(cases) == 0:
        ERRORS.append("Zero-case run detected; at least one assertion must execute.")

    passed_all = (len(ERRORS) == 0) and all(c["passed"] for c in cases) and bats_passed

    report = {
        "task_id": "R13-T037",
        "item": "git-scp",
        "tool_versions": tool_versions,
        "total_checks": len(cases) + len(native_test_names),
        "passed": passed_all,
        "failures": ERRORS,
        "native_bats": {
            "test_file": str(bats_test_file),
            "exit_status": bats_result.returncode,
            "test_count": len(native_test_names),
            "test_names": native_test_names,
        },
        "cases": cases,
    }

    (WORK_DIR / "results.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"R13-T037: Executed {len(cases)} direct checks and {len(native_test_names)} native Bats tests.")
    if passed_all:
        print("ALL CHECKS PASSED.")
        return 0
    else:
        print(f"FAILED with {len(ERRORS)} errors:")
        for err in ERRORS:
            print(f"  - {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
