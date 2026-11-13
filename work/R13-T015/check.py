#!/usr/bin/env python3
"""Verification runner for R13-T015: git-create-branch environment isolation,

deterministic configuration, and missing-dependency handling.

Asserts:
- Deterministic behavior with local config preferences (git-extras.create-branch.remote).
- Temporary working directory isolation without global state pollution.
- Stubbed external commands and missing-dependency branch execution.
- Success with local branches, --from start points, and -r/--remote tracking.
- Optional arguments (-h, --help).
- Documented invalid combinations (missing branch argument).
- Invariants: unrelated branches, commits, and configs remain unchanged.
- Zero-case run rejection.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORK_DIR = REPO_ROOT / "work" / "R13-T015"


def get_tool_versions():
    versions = {}

    # Python
    versions["python"] = sys.version.split()[0]

    # Git
    try:
        res = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True)
        versions["git"] = res.stdout.strip()
    except Exception as e:
        versions["git"] = f"error: {e}"

    # Bash
    bash_path = shutil.which("bash") or "/bin/bash"
    try:
        res = subprocess.run([bash_path, "--version"], capture_output=True, text=True, check=True)
        versions["bash"] = res.stdout.splitlines()[0].strip()
    except Exception as e:
        versions["bash"] = f"error: {e}"

    # Bats
    bats_path = shutil.which("bats") or "/opt/homebrew/bin/bats"
    try:
        res = subprocess.run([bats_path, "--version"], capture_output=True, text=True, check=True)
        versions["bats"] = res.stdout.strip()
    except Exception as e:
        versions["bats"] = f"error: {e}"

    return versions


def run_native_bats_tests():
    bats_exec = shutil.which("bats") or "/opt/homebrew/bin/bats"
    bats_test_file = REPO_ROOT / "tests" / "git-create-branch.bats"
    if not bats_test_file.exists():
        raise FileNotFoundError(f"Bats test file not found: {bats_test_file}")

    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:{REPO_ROOT / 'bin'}:{env.get('PATH', '')}"

    result = subprocess.run(
        [bats_exec, str(bats_test_file)],
        capture_output=True,
        text=True,
        env=env,
    )

    test_lines = []
    passed = 0
    failed = 0

    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("ok ") or line.startswith("not ok "):
            test_lines.append(line)
            if line.startswith("ok "):
                passed += 1
            else:
                failed += 1

    return {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "passed": passed,
        "failed": failed,
        "tests": test_lines,
    }


def capture_git_state(repo_dir):
    """Captures branch, refs, remote tracking, and working tree state."""
    state = {}

    # Current branch
    res = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    state["current_branch"] = res.stdout.strip()

    # HEAD commit SHA
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    state["head_sha"] = res.stdout.strip() if res.returncode == 0 else ""

    # Local refs
    res = subprocess.run(
        ["git", "for-each-ref", "refs/heads", "--format=%(refname) %(objectname)"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    local_refs = {}
    if res.returncode == 0:
        for line in res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) == 2:
                local_refs[parts[0]] = parts[1]
    state["local_refs"] = local_refs

    # Remote refs
    res = subprocess.run(
        ["git", "for-each-ref", "refs/remotes", "--format=%(refname) %(objectname)"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    remote_refs = {}
    if res.returncode == 0:
        for line in res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) == 2:
                remote_refs[parts[0]] = parts[1]
    state["remote_refs"] = remote_refs

    # Branch config
    res = subprocess.run(
        ["git", "config", "--get-regexp", r"^branch\."],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    branch_configs = {}
    if res.returncode == 0:
        for line in res.stdout.splitlines():
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                branch_configs[parts[0]] = parts[1]
    state["branch_configs"] = branch_configs

    # Status porcelain
    res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    state["status_porcelain"] = res.stdout.strip()

    return state


def setup_test_repository(base_dir, with_remote=False, remote_name="origin"):
    """Sets up an isolated test repository with commits A/B/C and branches main/topic.

    Optionally configures a local bare remote for deterministic testing.
    """
    repo_dir = base_dir / "work_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    def git(*args, check=True):
        return subprocess.run(
            ["git", *args],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=check,
        )

    git("init", "--initial-branch", "main")
    git("config", "user.name", "Test User")
    git("config", "user.email", "test@example.com")

    # Commit A
    (repo_dir / "fileA.txt").write_text("Commit A content\n")
    git("add", "fileA.txt")
    git("commit", "-m", "Commit A")

    # Commit B on main
    (repo_dir / "fileB.txt").write_text("Commit B content\n")
    git("add", "fileB.txt")
    git("commit", "-m", "Commit B")

    # Branch topic with Commit C
    git("branch", "topic")
    git("checkout", "topic")
    (repo_dir / "fileC.txt").write_text("Commit C content on topic\n")
    git("add", "fileC.txt")
    git("commit", "-m", "Commit C")

    # Return to main
    git("checkout", "main")

    bare_remote_dir = None
    if with_remote:
        bare_remote_dir = base_dir / f"{remote_name}.git"
        subprocess.run(["git", "init", "--bare", str(bare_remote_dir)], check=True, capture_output=True)
        git("remote", "add", remote_name, str(bare_remote_dir))
        git("push", "-u", remote_name, "main")

    return repo_dir, bare_remote_dir


def run_check_case(case_name, cmd_args, expected_exit, assert_fn, setup_remote=False, remote_name="origin", local_config=None, stub_mktemp=False):
    """Runs a single isolated check case inside a fresh temporary directory."""
    with tempfile.TemporaryDirectory(prefix=f"check_cb_{case_name}_") as tmp_str:
        tmp_path = Path(tmp_str)
        repo_dir, bare_remote = setup_test_repository(tmp_path, with_remote=setup_remote, remote_name=remote_name)

        if local_config:
            for k, v in local_config.items():
                subprocess.run(["git", "config", k, v], cwd=repo_dir, check=True)

        env = os.environ.copy()
        extra_bin = str(REPO_ROOT / "bin")

        if stub_mktemp:
            stub_dir = tmp_path / "stub_bin"
            stub_dir.mkdir(parents=True, exist_ok=True)
            stub_mktemp_file = stub_dir / "mktemp"
            stub_mktemp_file.write_text("#!/bin/sh\nexit 1\n")
            stub_mktemp_file.chmod(0o755)
            env["PATH"] = f"{stub_dir}:/opt/homebrew/bin:{extra_bin}:{env.get('PATH', '')}"
        else:
            env["PATH"] = f"/opt/homebrew/bin:{extra_bin}:{env.get('PATH', '')}"

        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "isolated_global_gitconfig")

        before_state = capture_git_state(repo_dir)

        # Run git-create-branch
        cmd = [str(REPO_ROOT / "bin" / "git-create-branch"), *cmd_args]
        proc = subprocess.run(
            cmd,
            cwd=repo_dir,
            capture_output=True,
            text=True,
            env=env,
        )

        after_state = capture_git_state(repo_dir)

        assertion_error = None
        try:
            if proc.returncode != expected_exit:
                raise AssertionError(
                    f"Expected exit code {expected_exit}, got {proc.returncode}.\n"
                    f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
                )
            assert_fn(before_state, after_state, proc.stdout, proc.stderr, repo_dir)
        except Exception as err:
            assertion_error = str(err)

        return {
            "name": case_name,
            "command": "git create-branch " + " ".join(cmd_args),
            "actual_arguments": cmd_args,
            "expected_exit": expected_exit,
            "actual_exit": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "passed": assertion_error is None,
            "error": assertion_error,
            "before_state": before_state,
            "after_state": after_state,
        }


def main():
    print("=== Starting git-create-branch verification (work/R13-T015) ===")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Tool Versions
    tool_versions = get_tool_versions()
    print("Tool versions detected:")
    for k, v in tool_versions.items():
        print(f"  {k}: {v}")
    with open(WORK_DIR / "tool_versions.json", "w", encoding="utf-8") as f:
        json.dump(tool_versions, f, indent=2)

    # 2. Native Bats Tests
    print("\n--- Running Native Bats Tests (tests/git-create-branch.bats) ---")
    bats_res = run_native_bats_tests()
    print(f"Native Bats test results: {bats_res['passed']} passed, {bats_res['failed']} failed (total {len(bats_res['tests'])})")
    with open(WORK_DIR / "native_test_names.txt", "w", encoding="utf-8") as f:
        for t in bats_res["tests"]:
            f.write(t + "\n")

    if bats_res["failed"] > 0 or bats_res["exit_code"] != 0:
        print(f"Native Bats test failures:\n{bats_res['stdout']}\n{bats_res['stderr']}")
        sys.exit(1)

    # 3. Focused Isolated Shell Checks
    print("\n--- Running Focused Isolated Shell Checks ---")

    cases_to_run = []

    # Case 1: Create local branch from HEAD (default start point)
    def assert_local_branch(before, after, stdout, stderr, repo):
        assert after["current_branch"] == "feat-local", "Current branch must be feat-local"
        assert after["head_sha"] == before["head_sha"], "New branch must point to previous HEAD SHA"
        assert "refs/heads/feat-local" in after["local_refs"], "Local ref for feat-local created"
        # Unrelated state: main and topic refs intact
        assert before["local_refs"]["refs/heads/main"] == after["local_refs"]["refs/heads/main"]
        assert before["local_refs"]["refs/heads/topic"] == after["local_refs"]["refs/heads/topic"]

    cases_to_run.append({
        "case_name": "create_local_branch_from_head",
        "cmd_args": ["feat-local"],
        "expected_exit": 0,
        "assert_fn": assert_local_branch,
    })

    # Case 2: Create local branch using --from start_point
    def assert_from_branch(before, after, stdout, stderr, repo):
        assert after["current_branch"] == "feat-from-topic", "Current branch must be feat-from-topic"
        assert after["head_sha"] == before["local_refs"]["refs/heads/topic"], "Branch must point to topic SHA"
        assert "refs/heads/feat-from-topic" in after["local_refs"]

    cases_to_run.append({
        "case_name": "create_local_branch_with_from_option",
        "cmd_args": ["--from", "topic", "feat-from-topic"],
        "expected_exit": 0,
        "assert_fn": assert_from_branch,
    })

    # Case 3: Create branch with -r remote tracking using local bare remote (deterministic)
    def assert_remote_branch(before, after, stdout, stderr, repo):
        assert after["current_branch"] == "feat-remote", "Current branch must be feat-remote"
        assert after["branch_configs"].get("branch.feat-remote.remote") == "origin", "Remote tracking set to origin"
        assert "refs/remotes/origin/feat-remote" in after["remote_refs"], "Remote tracking ref exists"

    cases_to_run.append({
        "case_name": "create_remote_tracking_branch_with_remote_option",
        "cmd_args": ["-r", "feat-remote"],
        "expected_exit": 0,
        "assert_fn": assert_remote_branch,
        "setup_remote": True,
    })

    # Case 4: Deterministic local config preference (git-extras.create-branch.remote)
    def assert_pref_branch(before, after, stdout, stderr, repo):
        assert after["current_branch"] == "feat-pref", "Current branch must be feat-pref"
        assert after["branch_configs"].get("branch.feat-pref.remote") == "custom-remote", "Remote tracking set to preference"

    cases_to_run.append({
        "case_name": "deterministic_local_config_remote_preference",
        "cmd_args": ["feat-pref"],
        "expected_exit": 0,
        "assert_fn": assert_pref_branch,
        "setup_remote": True,
        "remote_name": "custom-remote",
        "local_config": {"git-extras.create-branch.remote": "custom-remote"},
    })

    # Case 5: Missing-dependency branch - unreachable/missing remote
    def assert_missing_remote(before, after, stdout, stderr, repo):
        assert "Error connecting to remote 'nonexistent-remote'" in stdout or "Error connecting to remote 'nonexistent-remote'" in stderr
        # Active branch and refs remained unchanged
        assert after["current_branch"] == before["current_branch"]
        assert after["local_refs"] == before["local_refs"]

    cases_to_run.append({
        "case_name": "missing_dependency_branch_unreachable_remote",
        "cmd_args": ["-r", "nonexistent-remote", "bad-branch"],
        "expected_exit": 128,
        "assert_fn": assert_missing_remote,
    })

    # Case 6: Missing-dependency branch - stubbed external command failure (mktemp)
    def assert_stub_mktemp(before, after, stdout, stderr, repo):
        assert "mktemp required" in stderr or "mktemp is required" in stderr
        assert after["current_branch"] == before["current_branch"]
        assert after["local_refs"] == before["local_refs"]

    cases_to_run.append({
        "case_name": "missing_dependency_branch_stubbed_mktemp_failure",
        "cmd_args": ["-r", "origin", "fail-mktemp-branch"],
        "expected_exit": 1,
        "assert_fn": assert_stub_mktemp,
        "setup_remote": True,
        "stub_mktemp": True,
    })

    # Case 7: Optional argument --help
    def assert_help(before, after, stdout, stderr, repo):
        assert "Usage: git create-branch" in stdout
        assert after["local_refs"] == before["local_refs"]

    cases_to_run.append({
        "case_name": "optional_argument_help_flag",
        "cmd_args": ["--help"],
        "expected_exit": 0,
        "assert_fn": assert_help,
    })

    # Case 8: Optional argument -h
    def assert_short_help(before, after, stdout, stderr, repo):
        assert "Usage: git create-branch" in stdout
        assert after["local_refs"] == before["local_refs"]

    cases_to_run.append({
        "case_name": "optional_argument_short_help_flag",
        "cmd_args": ["-h"],
        "expected_exit": 0,
        "assert_fn": assert_short_help,
    })

    # Case 9: Documented invalid combination - missing branch argument
    def assert_missing_branch(before, after, stdout, stderr, repo):
        assert "branch argument required." in stderr
        assert after["local_refs"] == before["local_refs"]

    cases_to_run.append({
        "case_name": "documented_invalid_combination_missing_branch",
        "cmd_args": [],
        "expected_exit": 1,
        "assert_fn": assert_missing_branch,
    })

    # Zero-case run rejection
    if len(cases_to_run) == 0:
        raise RuntimeError("Zero-case run rejected: No check cases defined.")

    results = []
    has_failure = False

    for c in cases_to_run:
        res = run_check_case(
            case_name=c["case_name"],
            cmd_args=c["cmd_args"],
            expected_exit=c["expected_exit"],
            assert_fn=c["assert_fn"],
            setup_remote=c.get("setup_remote", False),
            remote_name=c.get("remote_name", "origin"),
            local_config=c.get("local_config"),
            stub_mktemp=c.get("stub_mktemp", False),
        )
        status_label = "PASS" if res["passed"] else "FAIL"
        print(f"[{status_label}] {res['name']}")
        print(f"  Args: {res['command']}")
        print(f"  Exit Status: {res['actual_exit']} (expected: {res['expected_exit']})")
        if not res["passed"]:
            print(f"  Error: {res['error']}")
            has_failure = True
        else:
            print(f"  Branch: '{res['before_state']['current_branch']}' -> '{res['after_state']['current_branch']}'")
        results.append(res)

    # 4. Save results.json
    results_path = WORK_DIR / "results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "tool_versions": tool_versions,
                "observed_option_tokens": ["--remote", "--from"],
                "native_bats": {
                    "total": len(bats_res["tests"]),
                    "passed": bats_res["passed"],
                    "failed": bats_res["failed"],
                    "tests": bats_res["tests"],
                },
                "focused_checks": results,
            },
            f,
            indent=2,
        )

    # 5. Save summary.txt
    summary_path = WORK_DIR / "summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("=== git-create-branch Verification Summary (R13-T015) ===\n\n")
        f.write("Tool Versions:\n")
        for k, v in tool_versions.items():
            f.write(f"  {k}: {v}\n")
        f.write("\nObserved Option Tokens: --remote, --from\n")
        f.write(f"\nNative Bats Tests ({len(bats_res['tests'])}):\n")
        for t in bats_res["tests"]:
            f.write(f"  {t}\n")
        f.write(f"\nFocused Shell Checks ({len(results)}):\n")
        for r in results:
            stat = "PASS" if r["passed"] else "FAIL"
            f.write(f"  [{stat}] {r['name']}\n")
            f.write(f"    Command: {r['command']}\n")
            f.write(f"    Exit Status: {r['actual_exit']} (expected {r['expected_exit']})\n")
            f.write(f"    Before Branch: {r['before_state']['current_branch']}\n")
            f.write(f"    After Branch:  {r['after_state']['current_branch']}\n")
            if r["error"]:
                f.write(f"    Error: {r['error']}\n")
            f.write("\n")

    print(f"\n=== Verification Complete: {sum(1 for r in results if r['passed'])}/{len(results)} checks passed ===")
    print(f"Results saved to: {results_path}")
    print(f"Summary saved to: {summary_path}")

    if has_failure:
        sys.exit(1)


if __name__ == "__main__":
    main()

