#!/usr/bin/env python3
"""Run focused git-squash checks and save their inputs and observed state."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
EVIDENCE = pathlib.Path(__file__).resolve().parent
ERRORS: list[str] = []


def run(command: list[str], *, cwd: pathlib.Path, env: dict[str, str] | None = None):
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def output(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return {
        "exit_status": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def git(repo: pathlib.Path, *args: str, env: dict[str, str]) -> str:
    result = run(["git", *args], cwd=repo, env=env)
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def state(repo: pathlib.Path, *, env: dict[str, str]) -> dict[str, str]:
    return {
        "head": git(repo, "rev-parse", "HEAD", env=env),
        "branch": git(repo, "branch", "--show-current", env=env),
        "status_porcelain": git(repo, "status", "--short", env=env),
        "staged_paths": git(repo, "diff", "--cached", "--name-only", env=env),
        "latest_commit_message": git(repo, "log", "-1", "--format=%B", env=env),
    }


def create_repo(directory: pathlib.Path, global_config: pathlib.Path) -> tuple[pathlib.Path, dict[str, str]]:
    repo = directory / "repo"
    repo.mkdir()
    command_bin = directory / "command-bin"
    command_bin.mkdir()
    wrapper = command_bin / "git-squash"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        f"source {str(ROOT / 'helper/reset-env')!r}\n"
        f"source {str(ROOT / 'helper/git-extra-utility')!r}\n"
        f"source {str(ROOT / 'helper/is-git-repo')!r}\n"
        f"exec {str(ROOT / 'bin/git-squash')!r} \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(global_config),
            "PATH": f"{command_bin}:{ROOT / 'bin'}:{env.get('PATH', '')}",
        }
    )

    result = run(["git", "init", "--initial-branch", "main"], cwd=repo, env=env)
    if result.returncode:
        raise RuntimeError(result.stderr)
    git(repo, "config", "user.name", "Task Check", env=env)
    git(repo, "config", "user.email", "task-check@example.invalid", env=env)

    (repo / "base.txt").write_text("A\n", encoding="utf-8")
    git(repo, "add", "base.txt", env=env)
    git(repo, "commit", "-m", "A", env=env)
    git(repo, "switch", "-c", "topic", env=env)
    (repo / "B.txt").write_text("B\n", encoding="utf-8")
    git(repo, "add", "B.txt", env=env)
    git(repo, "commit", "-m", "B", env=env)
    (repo / "C.txt").write_text("C\n", encoding="utf-8")
    git(repo, "add", "C.txt", env=env)
    git(repo, "commit", "-m", "C", env=env)
    git(repo, "switch", "main", env=env)
    return repo, env


def direct_case(name: str, args: list[str], expectations: dict[str, object]) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=f"R13-T001-{name}-") as temp_name:
        directory = pathlib.Path(temp_name)
        repo, env = create_repo(directory, directory / "isolated-global.gitconfig")
        before = state(repo, env=env)
        command = ["git", "squash", *args]
        result = run(command, cwd=repo, env=env)
        after = state(repo, env=env)
        actual = output(result)
        actual["after_state"] = after
        actual["before_state"] = before

        if result.returncode != expectations["exit_status"]:
            ERRORS.append(
                f"{name}: expected exit {expectations['exit_status']}, got {result.returncode}"
            )
        if "stdout_contains" in expectations and expectations["stdout_contains"] not in result.stdout:
            ERRORS.append(f"{name}: expected stdout to contain {expectations['stdout_contains']!r}")
        if "stderr_contains" in expectations and expectations["stderr_contains"] not in result.stderr:
            ERRORS.append(f"{name}: expected stderr to contain {expectations['stderr_contains']!r}")
        for key, expected in expectations.get("after_state", {}).items():
            observed = after[key]
            if expected == "<before>" and observed != before[key]:
                ERRORS.append(f"{name}: expected {key} unchanged ({before[key]!r}), got {observed!r}")
            elif expected == "<changed>" and observed == before[key]:
                ERRORS.append(f"{name}: expected {key} to change, but it remained {observed!r}")
            elif isinstance(expected, str) and expected not in ("<before>", "<changed>") and expected not in observed:
                ERRORS.append(f"{name}: expected {key} to contain {expected!r}, got {observed!r}")
        return {
            "name": name,
            "command_argv": command,
            "expected": expectations,
            "actual": actual,
        }


def version(command: list[str]) -> str:
    result = run(command, cwd=ROOT)
    return (result.stdout or result.stderr).splitlines()[0]


def main() -> int:
    bats = shutil.which("bats")
    if not bats:
        ERRORS.append("Bats executable not found; install bats-core to run the repository tests")
        bats_result = None
    else:
        bats_result = run([bats, "tests/git-squash.bats"], cwd=ROOT)
        if bats_result.returncode:
            ERRORS.append(f"focused Bats tests exited {bats_result.returncode}")
        for test_name in (
            "squashes a topic branch into the index without moving HEAD",
            "rejects a missing source without changing repository state",
            "commits the squash with concatenated messages",
            "rejects a message with --squash-msg without changing state",
        ):
            if test_name not in bats_result.stdout:
                ERRORS.append(f"focused Bats output did not report test {test_name!r}")

    cases = [
        direct_case(
            "ordinary-success",
            ["topic"],
            {
                "exit_status": 0,
                "stdout_contains": "Squash commit -- not updating HEAD",
                "after_state": {
                    "head": "<before>",
                    "status_porcelain": "A  B.txt",
                    "staged_paths": "B.txt",
                },
            },
        ),
        direct_case(
            "missing-source",
            [],
            {
                "exit_status": 1,
                "stderr_contains": "Source branch or commit reference required.",
                "after_state": {
                    "head": "<before>",
                    "status_porcelain": "",
                    "staged_paths": "",
                },
            },
        ),
        direct_case(
            "squash-msg-success",
            ["--squash-msg", "topic"],
            {
                "exit_status": 0,
                "after_state": {
                    "head": "<changed>",
                    "status_porcelain": "",
                    "latest_commit_message": "B",
                },
            },
        ),
    ]

    versions = {
        "git": version(["git", "--version"]),
        "bash": version(["bash", "--version"]),
        "python": sys.version.splitlines()[0],
        "bats": version([bats, "--version"]) if bats else "unavailable",
    }
    report: dict[str, object] = {
        "task": "R13-T001",
        "repository": str(ROOT),
        "native_test_command": [bats or "bats", "tests/git-squash.bats"],
        "native_test_exit_status": bats_result.returncode if bats_result else None,
        "native_test_stdout": bats_result.stdout if bats_result else "",
        "native_test_stderr": bats_result.stderr if bats_result else "",
        "tool_versions": versions,
        "cases": cases,
        "assertions_passed": not ERRORS,
        "errors": ERRORS,
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"task": report["task"], "tool_versions": versions}, indent=2))
    for case in cases:
        actual = case["actual"]
        print(
            f"{case['name']}: argv={case['command_argv']!r} "
            f"exit={actual['exit_status']} before={actual['before_state']} after={actual['after_state']}"
        )
    if bats_result:
        print(bats_result.stdout, end="")
    if ERRORS:
        for error in ERRORS:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"Saved evidence to {EVIDENCE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
