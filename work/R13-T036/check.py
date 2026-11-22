#!/usr/bin/env python3
"""Automated check runner for R13-T036: git-get source responsibility clarification."""

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


def run(command: list[str], *, cwd: pathlib.Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
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

    # Create command wrapper ensuring repository helpers are sourced
    command_bin = base_dir / "bin"
    command_bin.mkdir()
    wrapper = command_bin / "git-get"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        f"source {str(ROOT / 'helper/reset-env')!r}\n"
        f"source {str(ROOT / 'helper/git-extra-utility')!r}\n"
        f"exec {str(ROOT / 'bin/git-get')!r} \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)

    clones_dir = base_dir / "clones"
    clones_dir.mkdir()

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
    (repo / "base.txt").write_text("Commit A content\n", encoding="utf-8")
    git(repo, "add", "base.txt", env=env)
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

    return repo, env, bare_remote, clones_dir


def run_direct_case(
    name: str,
    args: list[str],
    expectations: dict[str, object],
    *,
    setup_fn=None,
    assert_fn=None,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=f"R13-T036-{name}-") as tmpdir:
        base_dir = pathlib.Path(tmpdir)
        repo, env, bare_remote, clones_dir = create_test_environment(base_dir)

        if setup_fn:
            setup_fn(repo, env, bare_remote, clones_dir)

        # Substitute placeholder in args
        resolved_args = []
        for a in args:
            if a == "<bare_remote>":
                resolved_args.append(str(bare_remote))
            elif a == "<bare_remote_slash>":
                resolved_args.append(f"{bare_remote}/")
            else:
                resolved_args.append(a)

        before = get_repo_state(repo, env=env)
        cmd = ["git", "get", *resolved_args]
        res = run(cmd, cwd=repo, env=env)
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

        if "stderr_contains" in expectations:
            if expectations["stderr_contains"] not in res.stderr:
                ERRORS.append(
                    f"{name}: expected stderr to contain {expectations['stderr_contains']!r}, got {res.stderr!r}"
                )
                passed = False

        if "stdout_contains" in expectations:
            if expectations["stdout_contains"] not in res.stdout:
                ERRORS.append(
                    f"{name}: expected stdout to contain {expectations['stdout_contains']!r}, got {res.stdout!r}"
                )
                passed = False

        if assert_fn:
            custom_ok = assert_fn(clones_dir, env)
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
            "arguments": resolved_args,
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
    }

    (WORK_DIR / "tool_versions.json").write_text(
        json.dumps(tool_versions, indent=2) + "\n",
        encoding="utf-8",
    )

    # 1. Native Bats suite
    bats_bin = shutil.which("bats") or "/opt/homebrew/bin/bats"
    bats_test_file = ROOT / "tests" / "git-get.bats"
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

    # Case 1: No arguments prints usage
    cases.append(
        run_direct_case(
            "usage-no-args-success",
            [],
            {
                "exit_status": 0,
                "stdout_contains": "usage: git-get <url>",
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "",
                },
            },
        )
    )

    # Case 2: Help flag prints usage
    cases.append(
        run_direct_case(
            "usage-help-flag-success",
            ["-h"],
            {
                "exit_status": 0,
                "stdout_contains": "usage: git-get <url>",
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "",
                },
            },
        )
    )

    # Case 3: Missing git-extras.get.clone-path configuration failure
    cases.append(
        run_direct_case(
            "missing-clone-path-config-failure",
            ["<bare_remote>"],
            {
                "exit_status": 1,
                "stderr_contains": "Git configuration key 'git-extras.get.clone-path' must be set to a directory to clone under",
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "",
                },
            },
        )
    )

    # Case 4: Successful clone under configured path
    def setup_clone_path(repo: pathlib.Path, env: dict[str, str], bare_remote: pathlib.Path, clones_dir: pathlib.Path):
        git(repo, "config", "git-extras.get.clone-path", str(clones_dir), env=env)

    def assert_clone_main(clones_dir: pathlib.Path, env: dict[str, str]) -> bool:
        target = clones_dir / "remote"
        if not target.is_dir():
            ERRORS.append("Expected cloned directory 'remote' does not exist")
            return False
        if not (target / "base.txt").exists():
            ERRORS.append("Expected cloned file 'base.txt' does not exist")
            return False
        branch = git(target, "branch", "--show-current", env=env)
        if branch != "main":
            ERRORS.append(f"Expected cloned branch 'main', got {branch!r}")
            return False
        return True

    cases.append(
        run_direct_case(
            "clone-success",
            ["<bare_remote>"],
            {
                "exit_status": 0,
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "",
                },
            },
            setup_fn=setup_clone_path,
            assert_fn=assert_clone_main,
        )
    )

    # Case 5: Forward additional clone options (e.g. --branch topic)
    def assert_clone_topic(clones_dir: pathlib.Path, env: dict[str, str]) -> bool:
        target = clones_dir / "remote"
        if not target.is_dir():
            ERRORS.append("Expected cloned directory 'remote' does not exist")
            return False
        branch = git(target, "branch", "--show-current", env=env)
        if branch != "topic":
            ERRORS.append(f"Expected cloned branch 'topic', got {branch!r}")
            return False
        return True

    cases.append(
        run_direct_case(
            "clone-branch-option-success",
            ["<bare_remote>", "--branch", "topic"],
            {
                "exit_status": 0,
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "",
                },
            },
            setup_fn=setup_clone_path,
            assert_fn=assert_clone_topic,
        )
    )

    # Case 6: URL with trailing slash
    cases.append(
        run_direct_case(
            "trailing-slash-stripping-success",
            ["<bare_remote_slash>"],
            {
                "exit_status": 0,
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "",
                },
            },
            setup_fn=setup_clone_path,
            assert_fn=assert_clone_main,
        )
    )

    # Check requirement: zero-case run must be rejected
    if len(cases) == 0:
        ERRORS.append("Zero-case run detected; at least one assertion must execute.")

    passed_all = (len(ERRORS) == 0) and all(c["passed"] for c in cases) and bats_passed

    report = {
        "task_id": "R13-T036",
        "item": "git-get",
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

    print(f"R13-T036: Executed {len(cases)} direct checks and {len(native_test_names)} native Bats tests.")
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
