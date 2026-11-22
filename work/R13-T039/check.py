#!/usr/bin/env python3
"""Automated check runner for R13-T039: git-local-commits condition protection with regression."""

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


def create_test_environment(base_dir: pathlib.Path) -> tuple[pathlib.Path, dict[str, str]]:
    global_config = base_dir / "isolated-global.gitconfig"
    global_config.write_text("", encoding="utf-8")

    bare_remote = base_dir / "remote.git"
    bare_remote.mkdir()
    init_bare = run(["git", "init", "--bare", "--initial-branch", "main"], cwd=bare_remote)
    if init_bare.returncode != 0:
        raise RuntimeError(f"Failed to init bare remote: {init_bare.stderr}")

    repo = base_dir / "repo"
    repo.mkdir()

    # Prepend this checkout's bin to PATH and wrap with necessary helpers
    command_bin = base_dir / "bin"
    command_bin.mkdir()
    wrapper = command_bin / "git-local-commits"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        f"source {str(ROOT / 'helper/reset-env')!r}\n"
        f"source {str(ROOT / 'helper/git-extra-utility')!r}\n"
        f"source {str(ROOT / 'helper/is-git-repo')!r}\n"
        f"source {str(ROOT / 'helper/has-git-commit')!r}\n"
        f"exec {str(ROOT / 'bin/git-local-commits')!r} \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{command_bin}:{ROOT / 'bin'}:{env.get('PATH', '')}"
    env["GIT_CONFIG_GLOBAL"] = str(global_config)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_AUTHOR_NAME"] = "Test User"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "Test User"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"

    git(repo, "init", "--initial-branch", "main", env=env)
    git(repo, "remote", "add", "origin", str(bare_remote), env=env)

    # Commit A: pushed to origin/main
    file_a = repo / "file_a.txt"
    file_a.write_text("Commit A content\n", encoding="utf-8")
    git(repo, "add", "file_a.txt", env=env)
    git(repo, "commit", "-m", "Commit A (upstream)", env=env)
    git(repo, "push", "-u", "origin", "main", env=env)

    # Branch topic at Commit A tracking origin/main
    git(repo, "branch", "--track", "topic", "origin/main", env=env)

    # Commit B: local unpushed commit 1
    file_b = repo / "file_b.txt"
    file_b.write_text("Commit B content\n", encoding="utf-8")
    git(repo, "add", "file_b.txt", env=env)
    git(repo, "commit", "-m", "Commit B (local 1)", env=env)

    # Commit C: local unpushed commit 2
    file_c = repo / "file_c.txt"
    file_c.write_text("Commit C content\n", encoding="utf-8")
    git(repo, "add", "file_c.txt", env=env)
    git(repo, "commit", "-m", "Commit C (local 2)", env=env)

    return repo, env


def run_direct_case(
    case_name: str,
    args: list[str],
    expectations: dict,
    *,
    branch_switch: str | None = None,
) -> dict:
    with tempfile.TemporaryDirectory() as temp_dir:
        base_dir = pathlib.Path(temp_dir)
        repo, env = create_test_environment(base_dir)

        if branch_switch:
            if branch_switch == "topic":
                git(repo, "checkout", "topic", env=env)
            elif branch_switch == "untracked":
                git(repo, "checkout", "-b", "untracked", env=env)

        before_state = get_repo_state(repo, env=env)

        cmd = ["git-local-commits", *args]
        res = run(cmd, cwd=repo, env=env)

        after_state = get_repo_state(repo, env=env)

        passed = True
        case_errors: list[str] = []

        expected_exit = expectations.get("exit_status")
        if expected_exit is not None and res.returncode != expected_exit:
            passed = False
            case_errors.append(f"Expected exit code {expected_exit}, got {res.returncode}")

        for pattern in expectations.get("stdout_contains", []):
            if pattern not in res.stdout:
                passed = False
                case_errors.append(f"stdout missing expected pattern: {pattern!r}")

        for pattern in expectations.get("stdout_excludes", []):
            if pattern in res.stdout:
                passed = False
                case_errors.append(f"stdout unexpectedly contained: {pattern!r}")

        for pattern in expectations.get("stderr_contains", []):
            if pattern not in res.stderr:
                passed = False
                case_errors.append(f"stderr missing expected pattern: {pattern!r}")

        # Verify state preservation where expected
        expected_state = expectations.get("after_state", {})
        for key, exp_val in expected_state.items():
            actual_val = after_state.get(key)
            if exp_val == "<before>":
                if actual_val != before_state.get(key):
                    passed = False
                    case_errors.append(f"State '{key}' changed unexpectedly: {actual_val} != {before_state.get(key)}")
            elif actual_val != exp_val:
                passed = False
                case_errors.append(f"State '{key}' expected {exp_val!r}, got {actual_val!r}")

        if not passed:
            ERRORS.extend([f"[{case_name}] {e}" for e in case_errors])

        return {
            "name": case_name,
            "args": args,
            "exit_status": res.returncode,
            "passed": passed,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "errors": case_errors,
        }


def main() -> int:
    tool_versions = {
        "git": get_version(["git", "--version"]),
        "bash": get_version(["bash", "--version"]),
        "python": get_version(["python3", "--version"]),
        "bats": get_version(["bats", "--version"]),
    }

    (WORK_DIR / "tool_versions.json").write_text(
        json.dumps(tool_versions, indent=2) + "\n",
        encoding="utf-8",
    )

    bats_test_file = ROOT / "tests/git-local-commits.bats"
    if not bats_test_file.exists():
        ERRORS.append(f"Bats test file not found at {bats_test_file}")
        return 1

    # Extract test names from bats file
    native_test_names: list[str] = []
    for line in bats_test_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("@test "):
            test_title = line[6:].strip().strip('"').strip("'").rstrip("{").strip().strip('"').strip("'")
            native_test_names.append(test_title)

    (WORK_DIR / "native_test_names.txt").write_text(
        "\n".join(native_test_names) + "\n",
        encoding="utf-8",
    )

    bats_env = os.environ.copy()
    bats_env["PATH"] = f"/opt/homebrew/bin:{ROOT / 'bin'}:{bats_env.get('PATH', '')}"
    bats_result = run(["bats", str(bats_test_file)], cwd=ROOT, env=bats_env)
    bats_passed = bats_result.returncode == 0
    if not bats_passed:
        ERRORS.append(f"Bats tests failed (exit {bats_result.returncode}):\n{bats_result.stdout}\n{bats_result.stderr}")

    cases: list[dict] = []

    # Case 1: Local commits only success (rejects mutant missing @{upstream}..@)
    cases.append(
        run_direct_case(
            "local-commits-only-success",
            [],
            {
                "exit_status": 0,
                "stdout_contains": ["Commit B (local 1)", "Commit C (local 2)"],
                "stdout_excludes": ["Commit A (upstream)"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
        )
    )

    # Case 2: Positional arguments forwarding --oneline
    cases.append(
        run_direct_case(
            "pos-args-oneline-success",
            ["--oneline"],
            {
                "exit_status": 0,
                "stdout_contains": ["Commit B (local 1)", "Commit C (local 2)"],
                "stdout_excludes": ["Commit A (upstream)", "Author:", "Date:"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
        )
    )

    # Case 3: Positional arguments pathspec limiting
    cases.append(
        run_direct_case(
            "pos-args-pathspec-success",
            ["--oneline", "--", "file_b.txt"],
            {
                "exit_status": 0,
                "stdout_contains": ["Commit B (local 1)"],
                "stdout_excludes": ["Commit C (local 2)", "Commit A (upstream)"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
        )
    )

    # Case 4: Help flag -h
    cases.append(
        run_direct_case(
            "help-flag-short-success",
            ["-h"],
            {
                "exit_status": 0,
                "stdout_contains": ["Usage: git local-commits"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
        )
    )

    # Case 5: Help flag --help
    cases.append(
        run_direct_case(
            "help-flag-long-success",
            ["--help"],
            {
                "exit_status": 0,
                "stdout_contains": ["Usage: git local-commits"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
        )
    )

    # Case 6: Upstream tracking topic with 0 unpushed commits
    cases.append(
        run_direct_case(
            "zero-local-commits-topic-success",
            [],
            {
                "exit_status": 0,
                "stdout_excludes": ["Commit A", "Commit B", "Commit C"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
            branch_switch="topic",
        )
    )

    # Case 7: Missing upstream failure
    cases.append(
        run_direct_case(
            "missing-upstream-failure",
            [],
            {
                "exit_status": 128,
                "stderr_contains": ["fatal: no upstream configured for branch 'untracked'"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
            branch_switch="untracked",
        )
    )

    # Case 8: Explicit Mutant Rejection Verification
    # Simulates mutant condition (running `git log "$@"` without range restriction)
    # Asserts that the mutant incorrectly includes upstream commit A, proving the regression test kills it.
    with tempfile.TemporaryDirectory() as temp_dir:
        base_dir = pathlib.Path(temp_dir)
        repo, env = create_test_environment(base_dir)
        mutant_res = run(["git", "log", "--oneline"], cwd=repo, env=env)
        if "Commit A (upstream)" not in mutant_res.stdout:
            ERRORS.append("Mutant simulation failed: git log without range did not contain upstream commit")
        actual_res = run(["git-local-commits", "--oneline"], cwd=repo, env=env)
        if "Commit A (upstream)" in actual_res.stdout:
            ERRORS.append("Regression test failed: git-local-commits leaked upstream commit")
        cases.append({
            "name": "mutant-rejection-demonstration",
            "args": ["--oneline"],
            "exit_status": 0,
            "passed": ("Commit A (upstream)" not in actual_res.stdout and "Commit A (upstream)" in mutant_res.stdout),
            "stdout": actual_res.stdout,
            "stderr": actual_res.stderr,
            "errors": [],
        })

    # Requirement: reject zero-case run
    if len(cases) == 0:
        ERRORS.append("Zero-case run detected; at least one assertion must execute.")

    passed_all = (len(ERRORS) == 0) and all(c["passed"] for c in cases) and bats_passed

    report = {
        "task_id": "R13-T039",
        "item": "git-local-commits",
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

    print(f"R13-T039: Executed {len(cases)} direct checks and {len(native_test_names)} native Bats tests.")
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
