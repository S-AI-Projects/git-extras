#!/usr/bin/env python3
"""Automated check runner for R13-T040: git-delete-tag failing invocation explanation and correction."""

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


def get_repo_state(repo: pathlib.Path, *, env: dict[str, str]) -> dict[str, object]:
    local_tags_raw = git(repo, "tag", "-l", env=env)
    local_tags = [t for t in local_tags_raw.splitlines() if t.strip()]

    remote_tags_res = run(["git", "ls-remote", "--tags", "origin"], cwd=repo, env=env)
    remote_tags = []
    if remote_tags_res.returncode == 0:
        for line in remote_tags_res.stdout.splitlines():
            line = line.strip()
            if "refs/tags/" in line:
                tag = line.split("refs/tags/")[-1].replace("^{}", "")
                if tag not in remote_tags:
                    remote_tags.append(tag)

    return {
        "head": git(repo, "rev-parse", "HEAD", env=env),
        "branch": git(repo, "branch", "--show-current", env=env),
        "topic_ref": git(repo, "rev-parse", "topic", env=env),
        "status_short": git(repo, "status", "--short", env=env),
        "local_tags": sorted(local_tags),
        "remote_tags": sorted(remote_tags),
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
    wrapper = command_bin / "git-delete-tag"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        f"source {str(ROOT / 'helper/reset-env')!r}\n"
        f"source {str(ROOT / 'helper/git-extra-utility')!r}\n"
        f"source {str(ROOT / 'helper/is-git-repo')!r}\n"
        f"exec {str(ROOT / 'bin/git-delete-tag')!r} \"$@\"\n",
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
    file_a.write_text("Commit A\n", encoding="utf-8")
    git(repo, "add", "file_a.txt", env=env)
    git(repo, "commit", "-m", "Commit A", env=env)
    git(repo, "push", "-u", "origin", "main", env=env)

    # Branch topic
    git(repo, "branch", "--track", "topic", "origin/main", env=env)

    # Commit B on main
    file_b = repo / "file_b.txt"
    file_b.write_text("Commit B\n", encoding="utf-8")
    git(repo, "add", "file_b.txt", env=env)
    git(repo, "commit", "-m", "Commit B", env=env)

    # Commit C on main
    file_c = repo / "file_c.txt"
    file_c.write_text("Commit C\n", encoding="utf-8")
    git(repo, "add", "file_c.txt", env=env)
    git(repo, "commit", "-m", "Commit C", env=env)
    git(repo, "push", "origin", "main", env=env)

    return repo, env


def run_direct_case(
    case_name: str,
    args: list[str],
    expectations: dict,
    *,
    setup_tags: list[str] | None = None,
) -> dict:
    with tempfile.TemporaryDirectory() as temp_dir:
        base_dir = pathlib.Path(temp_dir)
        repo, env = create_test_environment(base_dir)

        if setup_tags:
            for tag in setup_tags:
                git(repo, "tag", tag, env=env)
                git(repo, "push", "origin", tag, env=env)

        before_state = get_repo_state(repo, env=env)

        cmd = ["git-delete-tag", *args]
        res = run(cmd, cwd=repo, env=env)

        after_state = get_repo_state(repo, env=env)

        passed = True
        case_errors: list[str] = []

        expected_exit = expectations.get("exit_status")
        if expected_exit is not None and res.returncode != expected_exit:
            passed = False
            case_errors.append(f"Expected exit code {expected_exit}, got {res.returncode}")

        combined_output = f"{res.stdout}\n{res.stderr}"

        for pattern in expectations.get("output_contains", []):
            if pattern not in combined_output:
                passed = False
                case_errors.append(f"Output missing expected pattern: {pattern!r}")

        for pattern in expectations.get("output_excludes", []):
            if pattern in combined_output:
                passed = False
                case_errors.append(f"Output unexpectedly contained: {pattern!r}")

        expected_tags_present = expectations.get("tags_present")
        if expected_tags_present is not None:
            for tag in expected_tags_present:
                if tag not in after_state["local_tags"] or tag not in after_state["remote_tags"]:
                    passed = False
                    case_errors.append(f"Expected tag {tag!r} to be present in local & remote tags")

        expected_tags_absent = expectations.get("tags_absent")
        if expected_tags_absent is not None:
            for tag in expected_tags_absent:
                if tag in after_state["local_tags"] or tag in after_state["remote_tags"]:
                    passed = False
                    case_errors.append(f"Expected tag {tag!r} to be absent from local & remote tags")

        # State preservation where expected
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
            "before_state": before_state,
            "after_state": after_state,
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

    bats_test_file = ROOT / "tests/git-delete-tag.bats"
    if not bats_test_file.exists():
        ERRORS.append(f"Bats test file not found at {bats_test_file}")
        return 1

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

    # Case 1: Missing tag argument failure with diagnostic explanation
    cases.append(
        run_direct_case(
            "missing-tag-arg-failure",
            [],
            {
                "exit_status": 1,
                "output_contains": [
                    "Error: Tag name required",
                    "Hint: Use 'git tag -l'",
                ],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
        )
    )

    # Case 2: Non-existent tag deletion failure with troubleshooting hint
    cases.append(
        run_direct_case(
            "nonexistent-tag-failure",
            ["nonexistent-v0"],
            {
                "exit_status": 1,
                "output_contains": [
                    "Hint: Tag deletion failed. Run 'git tag -l'",
                ],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
        )
    )

    # Case 3: Corrected invocation succeeding afterwards (single tag)
    cases.append(
        run_direct_case(
            "corrected-single-tag-success",
            ["v1.0.0"],
            {
                "exit_status": 0,
                "output_contains": ["Deleted tag 'v1.0.0'"],
                "tags_absent": ["v1.0.0"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
            setup_tags=["v1.0.0"],
        )
    )

    # Case 4: Multiple tags deletion success
    cases.append(
        run_direct_case(
            "multiple-tags-success",
            ["v2.0.1", "v2.0.2"],
            {
                "exit_status": 0,
                "output_contains": ["Deleted tag 'v2.0.1'", "Deleted tag 'v2.0.2'"],
                "tags_absent": ["v2.0.1", "v2.0.2"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
            setup_tags=["v2.0.1", "v2.0.2"],
        )
    )

    # Case 5: Help flag -h
    cases.append(
        run_direct_case(
            "help-flag-short-success",
            ["-h"],
            {
                "exit_status": 0,
                "output_contains": ["Usage: git delete-tag <tagname>..."],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
        )
    )

    # Case 6: Help flag --help
    cases.append(
        run_direct_case(
            "help-flag-long-success",
            ["--help"],
            {
                "exit_status": 0,
                "output_contains": ["Usage: git delete-tag <tagname>..."],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
        )
    )

    # Requirement: reject zero-case run
    if len(cases) == 0:
        ERRORS.append("Zero-case run detected; at least one assertion must execute.")

    passed_all = (len(ERRORS) == 0) and all(c["passed"] for c in cases) and bats_passed

    report = {
        "task_id": "R13-T040",
        "item": "git-delete-tag",
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

    print(f"R13-T040: Executed {len(cases)} direct checks and {len(native_test_names)} native Bats tests.")
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
