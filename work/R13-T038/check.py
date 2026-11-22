#!/usr/bin/env python3
"""Automated check runner for R13-T038: git-ignore-io focused check and service isolation."""

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
    gitignore_content = ""
    gitignore_file = repo / ".gitignore"
    if gitignore_file.exists():
        gitignore_content = gitignore_file.read_text(encoding="utf-8")

    return {
        "head": git(repo, "rev-parse", "HEAD", env=env),
        "branch": git(repo, "branch", "--show-current", env=env),
        "topic_ref": git(repo, "rev-parse", "topic", env=env),
        "status_short": git(repo, "status", "--short", env=env),
        "gitignore": gitignore_content,
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

    # Create command wrapper ensuring repository helpers are sourced
    command_bin = base_dir / "bin"
    command_bin.mkdir()
    wrapper = command_bin / "git-ignore-io"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        f"source {str(ROOT / 'helper/reset-env')!r}\n"
        f"source {str(ROOT / 'helper/git-extra-utility')!r}\n"
        f"source {str(ROOT / 'helper/is-git-repo')!r}\n"
        f"exec {str(ROOT / 'bin/git-ignore-io')!r} \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)

    # Stub curl to deliver offline fixtures
    mock_bin = base_dir / "mock_bin"
    mock_bin.mkdir()
    curl_stub = mock_bin / "curl"
    curl_stub.write_text(
        "#!/usr/bin/env bash\n"
        "url=''\n"
        "for arg; do case \"$arg\" in http*) url=\"$arg\" ;; esac; done\n"
        "case \"$url\" in\n"
        "  *Python.gitignore) printf '# Python\\n*.py[cod]\\n__pycache__/\\n' ;;\n"
        "  *Vim.gitignore) printf '# Vim\\n[._]*.s[a-w][a-z]\\n*.un~\\n' ;;\n"
        "  *Node.gitignore) printf '# Node\\nnode_modules/\\nnpm-debug.log\\n' ;;\n"
        "  *) exit 22 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    curl_stub.chmod(0o755)

    # Isolated XDG cache pre-seeded to prevent network access to GitHub
    cache_dir = base_dir / "cache"
    extras_cache = cache_dir / "git-extras"
    extras_cache.mkdir(parents=True)
    gi_list = extras_cache / "gi_list"
    gi_list.write_text("C\nGlobal/Vim\nNode\nPython\nRust\n", encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(global_config),
            "XDG_CACHE_HOME": str(cache_dir),
            "PATH": f"{mock_bin}:{command_bin}:{ROOT / 'bin'}:/opt/homebrew/bin:{env.get('PATH', '')}",
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

    return repo, env


def run_direct_case(
    name: str,
    args: list[str],
    expectations: dict[str, object],
    *,
    setup_fn=None,
    assert_fn=None,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=f"R13-T038-{name}-") as tmpdir:
        base_dir = pathlib.Path(tmpdir)
        repo, env = create_test_environment(base_dir)

        if setup_fn:
            setup_fn(repo, env)

        before = get_repo_state(repo, env=env)
        cmd = ["git", "ignore-io", *args]
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
            custom_ok = assert_fn(repo, env)
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
            elif isinstance(expected_val, str) and expected_val not in ("<before>", "<changed>") and expected_val not in observed:
                ERRORS.append(
                    f"{name}: expected {state_key} to contain {expected_val!r}, got {observed!r}"
                )
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
    bats_test_file = ROOT / "tests" / "git-ignore-io.bats"
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

    # Case 1: Help flag
    cases.append(
        run_direct_case(
            "help-flag-success",
            ["-h"],
            {
                "exit_status": 0,
                "stdout_contains": ["Usage:"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "status_short": "",
                    "gitignore": "",
                },
            },
        )
    )

    # Case 2: Replace template
    def assert_no_temp_files(repo: pathlib.Path, env: dict[str, str]) -> bool:
        tmp_files = list(repo.glob(".gitignore.tmp.*"))
        if tmp_files:
            ERRORS.append(f"Found leftover temp files: {tmp_files}")
            return False
        return True

    cases.append(
        run_direct_case(
            "replace-template-success",
            ["--replace", "Python"],
            {
                "exit_status": 0,
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "gitignore": "*.py[cod]",
                },
            },
            assert_fn=assert_no_temp_files,
        )
    )

    # Case 3: Append template
    def setup_existing_gitignore(repo: pathlib.Path, env: dict[str, str]):
        (repo / ".gitignore").write_text("# Initial\n*.log\n", encoding="utf-8")

    cases.append(
        run_direct_case(
            "append-template-success",
            ["--append", "Vim"],
            {
                "exit_status": 0,
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                    "gitignore": "[._]*.s[a-w][a-z]",
                },
            },
            setup_fn=setup_existing_gitignore,
            assert_fn=assert_no_temp_files,
        )
    )

    # Case 4: List alphabetically
    cases.append(
        run_direct_case(
            "list-alphabetically-success",
            ["--list-alphabetically"],
            {
                "exit_status": 0,
                "stdout_contains": ["Python", "Global/Vim"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
        )
    )

    # Case 5: List in table format
    cases.append(
        run_direct_case(
            "list-in-table-success",
            ["--list-in-table"],
            {
                "exit_status": 0,
                "stdout_contains": ["Python"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
        )
    )

    # Case 6: Unknown template failure
    cases.append(
        run_direct_case(
            "unknown-template-failure",
            ["NonexistentTemplate"],
            {
                "exit_status": 1,
                "stderr_contains": "Template not found: NonexistentTemplate",
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
        )
    )

    # Case 7: Missing types failure
    cases.append(
        run_direct_case(
            "missing-types-replace-failure",
            ["--replace"],
            {
                "exit_status": 1,
                "stdout_contains": ["There should be at least one type"],
                "after_state": {
                    "head": "<before>",
                    "branch": "<before>",
                    "topic_ref": "<before>",
                },
            },
        )
    )

    # Check requirement: zero-case run must be rejected
    if len(cases) == 0:
        ERRORS.append("Zero-case run detected; at least one assertion must execute.")

    passed_all = (len(ERRORS) == 0) and all(c["passed"] for c in cases) and bats_passed

    report = {
        "task_id": "R13-T038",
        "item": "git-ignore-io",
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

    print(f"R13-T038: Executed {len(cases)} direct checks and {len(native_test_names)} native Bats tests.")
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
