#!/usr/bin/env python3
"""Automated check runner for R13-T034: git-paste argument quoting and boundaries."""

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
        "unrelated_hash": git(repo, "hash-object", "unrelated_file.txt", env=env),
        "wildcard_target_hash": git(repo, "hash-object", "file_wildcard_target.txt", env=env),
    }


def create_test_environment(base_dir: pathlib.Path, *, with_mock_pastebinit: bool = True) -> tuple[pathlib.Path, dict[str, str], pathlib.Path | None]:
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
    wrapper = command_bin / "git-paste"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        f"source {str(ROOT / 'helper/reset-env')!r}\n"
        f"source {str(ROOT / 'helper/git-extra-utility')!r}\n"
        f"source {str(ROOT / 'helper/is-git-repo')!r}\n"
        f"exec {str(ROOT / 'bin/git-paste')!r} \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)

    mock_dir = None
    if with_mock_pastebinit:
        mock_dir = base_dir / "mock_bin"
        mock_dir.mkdir()
        pastebinit_stub = mock_dir / "pastebinit"
        pastebinit_stub.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '%s\\n' \"$@\" > {str(base_dir / 'pastebinit_args.txt')!r}\n"
            f"cat > {str(base_dir / 'pastebinit_stdin.txt')!r}\n"
            "printf 'https://pastebin.example.com/mock-paste\\n'\n",
            encoding="utf-8",
        )
        pastebinit_stub.chmod(0o755)

    path_entries = [str(command_bin), str(ROOT / "bin"), "/opt/homebrew/bin", "/usr/bin", "/bin"]
    if mock_dir:
        path_entries.insert(0, str(mock_dir))

    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(global_config),
            "PATH": ":".join(path_entries),
        }
    )

    init_res = run(["git", "init", "--initial-branch", "main"], cwd=repo, env=env)
    if init_res.returncode != 0:
        raise RuntimeError(f"Failed to init repo: {init_res.stderr}")

    git(repo, "config", "user.name", "Kushal Pandya", env=env)
    git(repo, "config", "user.email", "kushalpandya037@gmail.com", env=env)
    git(repo, "remote", "add", "origin", str(bare_remote), env=env)

    # Commit A
    spaces_dir = repo / "dir with spaces"
    spaces_dir.mkdir()
    (spaces_dir / "file with spaces 1.txt").write_text("Commit A file 1\n", encoding="utf-8")
    (spaces_dir / "file with spaces 2.txt").write_text("Commit A file 2\n", encoding="utf-8")
    (repo / "unrelated_file.txt").write_text("Unrelated content A\n", encoding="utf-8")
    (repo / "file_wildcard_target.txt").write_text("Wildcard target content\n", encoding="utf-8")
    git(repo, "add", "-A", env=env)
    git(repo, "commit", "-m", "Commit A", env=env)

    # Commit B: Modify file with spaces
    (spaces_dir / "file with spaces 1.txt").write_text("Commit B file 1 modified\n", encoding="utf-8")
    git(repo, "commit", "-am", "Commit B", env=env)

    # Commit C on topic branch
    git(repo, "switch", "-c", "topic", env=env)
    (repo / "unrelated_file.txt").write_text("Commit C topic content\n", encoding="utf-8")
    git(repo, "commit", "-am", "Commit C", env=env)

    # Return to main
    git(repo, "switch", "main", env=env)
    git(repo, "push", "-u", "origin", "main", env=env)
    git(repo, "push", "origin", "topic", env=env)

    return repo, env, base_dir


def run_direct_case(
    name: str,
    args: list[str],
    expectations: dict[str, object],
    *,
    with_mock_pastebinit: bool = True,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=f"R13-T034-{name}-") as tmpdir:
        base_dir = pathlib.Path(tmpdir)
        repo, env, run_dir = create_test_environment(base_dir, with_mock_pastebinit=with_mock_pastebinit)

        before = get_repo_state(repo, env=env)
        cmd = ["git", "paste", *args]
        res = run(cmd, cwd=repo, env=env)
        after = get_repo_state(repo, env=env)

        captured_args = ""
        captured_stdin = ""
        if run_dir:
            args_file = run_dir / "pastebinit_args.txt"
            stdin_file = run_dir / "pastebinit_stdin.txt"
            if args_file.exists():
                captured_args = args_file.read_text(encoding="utf-8")
            if stdin_file.exists():
                captured_stdin = stdin_file.read_text(encoding="utf-8")

        actual = {
            "exit_status": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "captured_args": captured_args,
            "captured_stdin_snippet": captured_stdin[:300] if captured_stdin else "",
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

        if "stdin_contains" in expectations:
            if expectations["stdin_contains"] not in captured_stdin:
                ERRORS.append(
                    f"{name}: expected stdin to contain {expectations['stdin_contains']!r}"
                )
                passed = False

        if "stdin_refutes" in expectations:
            if expectations["stdin_refutes"] in captured_stdin:
                ERRORS.append(
                    f"{name}: expected stdin NOT to contain {expectations['stdin_refutes']!r}"
                )
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
    }

    (WORK_DIR / "tool_versions.json").write_text(
        json.dumps(tool_versions, indent=2) + "\n",
        encoding="utf-8",
    )

    # 1. Native Bats suite
    bats_bin = shutil.which("bats") or "/opt/homebrew/bin/bats"
    bats_test_file = ROOT / "tests" / "git-paste.bats"
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

    # Case 1: Quoted path with spaces
    cases.append(
        run_direct_case(
            "quoted-path-with-spaces-success",
            ["-1", "HEAD", "--", "dir with spaces/file with spaces 1.txt"],
            {
                "exit_status": 0,
                "stdout_contains": "https://pastebin.example.com/mock-paste",
                "stdin_contains": "dir with spaces/file with spaces 1.txt",
                "stdin_refutes": "unrelated_file.txt",
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "",
                    "unrelated_hash": "<before>",
                    "wildcard_target_hash": "<before>",
                },
            },
        )
    )

    # Case 2: Argument containing wildcard character
    cases.append(
        run_direct_case(
            "wildcard-argument-success",
            ["-1", "HEAD", "--", "dir with spaces/*.txt"],
            {
                "exit_status": 0,
                "stdout_contains": "https://pastebin.example.com/mock-paste",
                "stdin_contains": "dir with spaces/file with spaces 1.txt",
                "stdin_refutes": "unrelated_file.txt",
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "",
                    "unrelated_hash": "<before>",
                    "wildcard_target_hash": "<before>",
                },
            },
        )
    )

    # Case 3: Display help with -h
    cases.append(
        run_direct_case(
            "help-option-success",
            ["-h"],
            {
                "exit_status": 0,
                "stdout_contains": "usage: git paste",
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "",
                    "unrelated_hash": "<before>",
                    "wildcard_target_hash": "<before>",
                },
            },
            with_mock_pastebinit=False,
        )
    )

    # Case 4: Documented failure when pastebinit is missing
    cases.append(
        run_direct_case(
            "missing-pastebinit-documented-failure",
            ["-1"],
            {
                "exit_status": 1,
                "stderr_contains": "To run 'git paste', you need to install pastebinit in your system",
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "",
                    "unrelated_hash": "<before>",
                    "wildcard_target_hash": "<before>",
                },
            },
            with_mock_pastebinit=False,
        )
    )

    # Case 5: Documented failure on invalid revision argument
    cases.append(
        run_direct_case(
            "invalid-git-argument-failure",
            ["nonexistent_revision_12345"],
            {
                "exit_status": 128,
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "",
                    "unrelated_hash": "<before>",
                    "wildcard_target_hash": "<before>",
                },
            },
        )
    )

    # Check requirement: zero-case run must be rejected
    if len(cases) == 0:
        ERRORS.append("Zero-case run detected; at least one assertion must execute.")

    passed_all = (len(ERRORS) == 0) and all(c["passed"] for c in cases) and bats_passed

    report = {
        "task_id": "R13-T034",
        "item": "git-paste",
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

    print(f"R13-T034: Executed {len(cases)} direct checks and {len(native_test_names)} native Bats tests.")
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
