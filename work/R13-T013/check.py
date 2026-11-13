#!/usr/bin/env python3
"""Verification runner for R13-T013: git-rename-branch state transitions.

Asserts:
- Minimum accepted arguments (1 argument: rename current branch; 2 arguments: rename other branch).
- Optional arguments (-h, --help).
- Remote upstream tracking state transitions (--set-upstream, --short).
- Documented invalid combinations (missing argument, unknown option, too many arguments).
- Edge-states (non-existent branch, target branch already exists).
- Verification that unrelated states (unrelated branch refs, remote refs, working directory files) remain unchanged.
- Zero-case run rejection.
- Isolated execution in temporary directories without touching global state.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORK_DIR = REPO_ROOT / "work" / "R13-T013"


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
    bats_test_file = REPO_ROOT / "tests" / "git-rename-branch.bats"
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
    """Captures the relevant refs, HEAD, and config state of the repository."""
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

    # Status / dirty state
    res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    state["status_porcelain"] = res.stdout.strip()

    return state


def setup_test_repository(base_dir, with_remote=False):
    """Sets up a test git repository with commits A/B/C and branches main/topic.

    Optionally configures a local bare remote 'origin'.
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

    # Commit B
    (repo_dir / "fileB.txt").write_text("Commit B content\n")
    git("add", "fileB.txt")
    git("commit", "-m", "Commit B")

    # Branch topic at Commit B
    git("branch", "topic")

    # Checkout topic and make Commit C
    git("checkout", "topic")
    (repo_dir / "fileC.txt").write_text("Commit C content on topic\n")
    git("add", "fileC.txt")
    git("commit", "-m", "Commit C")

    # Back to main
    git("checkout", "main")

    bare_remote_dir = None
    if with_remote:
        bare_remote_dir = base_dir / "bare_remote.git"
        subprocess.run(["git", "init", "--bare", str(bare_remote_dir)], check=True, capture_output=True)
        git("remote", "add", "origin", str(bare_remote_dir))
        git("push", "-u", "origin", "main")
        git("checkout", "topic")
        git("push", "-u", "origin", "topic")
        git("checkout", "main")

    return repo_dir, bare_remote_dir


def run_check_case(case_name, setup_remote, initial_branch, cmd_args, expected_exit, assert_fn):
    """Runs a single isolated check case in its own temporary environment."""
    with tempfile.TemporaryDirectory(prefix=f"check_rename_{case_name}_") as tmp_str:
        tmp_path = Path(tmp_str)
        repo_dir, bare_remote = setup_test_repository(tmp_path, with_remote=setup_remote)

        # Checkout the desired starting branch
        subprocess.run(["git", "checkout", initial_branch], cwd=repo_dir, check=True, capture_output=True)

        env = os.environ.copy()
        env["PATH"] = f"/opt/homebrew/bin:{REPO_ROOT / 'bin'}:{env.get('PATH', '')}"
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "isolated_global_gitconfig")

        before_state = capture_git_state(repo_dir)

        # Run the command
        cmd = [str(REPO_ROOT / "bin" / "git-rename-branch"), *cmd_args]
        proc = subprocess.run(
            cmd,
            cwd=repo_dir,
            capture_output=True,
            text=True,
            env=env,
        )

        after_state = capture_git_state(repo_dir)

        # Perform custom assertions
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
            "command": "git rename-branch " + " ".join(cmd_args),
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
    print("=== Starting git-rename-branch verification (work/R13-T013) ===")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Tool Versions
    tool_versions = get_tool_versions()
    print("Tool versions detected:")
    for k, v in tool_versions.items():
        print(f"  {k}: {v}")
    with open(WORK_DIR / "tool_versions.json", "w", encoding="utf-8") as f:
        json.dump(tool_versions, f, indent=2)

    # 2. Native Bats Tests
    print("\n--- Running Native Bats Tests (tests/git-rename-branch.bats) ---")
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

    # Case 1: Minimum accepted arguments - rename current branch without remote (1 argument)
    def assert_rename_current(before, after, stdout, stderr, repo):
        # Intended change: topic ref gone, topic-renamed ref created with same commit
        topic_before_sha = before["local_refs"].get("refs/heads/topic")
        assert topic_before_sha is not None, "refs/heads/topic should exist before"
        assert "refs/heads/topic" not in after["local_refs"], "refs/heads/topic should be removed"
        assert after["local_refs"].get("refs/heads/topic-renamed") == topic_before_sha, "refs/heads/topic-renamed should point to old topic SHA"
        assert after["current_branch"] == "topic-renamed", "current branch should be topic-renamed"
        # Unrelated state unchanged: main branch ref and SHA must remain identical
        assert before["local_refs"]["refs/heads/main"] == after["local_refs"]["refs/heads/main"], "Unrelated branch 'main' SHA must remain unchanged"
        assert after["status_porcelain"] == "", "Working directory must remain clean"

    cases_to_run.append((
        "minimum_accepted_arguments_rename_current_branch",
        False,       # setup_remote
        "topic",     # initial_branch
        ["topic-renamed"],
        0,           # expected exit
        assert_rename_current,
    ))

    # Case 2: Rename other branch without checkout (2 arguments)
    def assert_rename_other(before, after, stdout, stderr, repo):
        # Intended change: topic renamed to topic-v2
        topic_before_sha = before["local_refs"].get("refs/heads/topic")
        assert topic_before_sha is not None, "refs/heads/topic should exist before"
        assert "refs/heads/topic" not in after["local_refs"], "refs/heads/topic should be removed"
        assert after["local_refs"].get("refs/heads/topic-v2") == topic_before_sha, "refs/heads/topic-v2 should point to old topic SHA"
        # Unrelated state unchanged: current branch remains main, main SHA unchanged
        assert after["current_branch"] == "main", "Current branch must remain main"
        assert before["local_refs"]["refs/heads/main"] == after["local_refs"]["refs/heads/main"], "Unrelated branch 'main' SHA must remain unchanged"
        assert after["status_porcelain"] == "", "Working directory must remain clean"

    cases_to_run.append((
        "rename_other_branch_two_arguments",
        False,
        "main",
        ["topic", "topic-v2"],
        0,
        assert_rename_other,
    ))

    # Case 3: Rename branch tracking remote with upstream update (--short, --set-upstream)
    def assert_rename_with_remote(before, after, stdout, stderr, repo):
        # Intended change:
        # 1. Local topic -> feature-v2
        topic_sha = before["local_refs"].get("refs/heads/topic")
        assert "refs/heads/topic" not in after["local_refs"], "refs/heads/topic removed"
        assert after["local_refs"].get("refs/heads/feature-v2") == topic_sha, "feature-v2 points to topic SHA"
        # 2. Remote topic deleted, remote feature-v2 pushed
        assert "refs/remotes/origin/topic" not in after["remote_refs"], "refs/remotes/origin/topic removed"
        assert after["remote_refs"].get("refs/remotes/origin/feature-v2") == topic_sha, "origin/feature-v2 exists with topic SHA"
        # 3. Upstream tracking updated
        assert after["branch_configs"].get("branch.feature-v2.remote") == "origin", "upstream remote set"
        assert after["branch_configs"].get("branch.feature-v2.merge") == "refs/heads/feature-v2", "upstream merge set"
        # Unrelated state unchanged:
        # main and origin/main must remain completely untouched
        assert before["local_refs"]["refs/heads/main"] == after["local_refs"]["refs/heads/main"], "Unrelated main SHA unchanged"
        assert before["remote_refs"]["refs/remotes/origin/main"] == after["remote_refs"]["refs/remotes/origin/main"], "Unrelated origin/main SHA unchanged"

    cases_to_run.append((
        "rename_branch_with_upstream_remote",
        True,        # setup_remote
        "topic",     # initial_branch
        ["feature-v2"],
        0,
        assert_rename_with_remote,
    ))

    # Case 4: Optional argument --help
    def assert_help(before, after, stdout, stderr, repo):
        assert "Usage: git rename-branch" in stdout, "Usage message expected in stdout"
        # Unrelated state: ALL local refs unchanged
        assert before["local_refs"] == after["local_refs"], "Refs must remain untouched"
        assert before["current_branch"] == after["current_branch"], "Branch must remain untouched"

    cases_to_run.append((
        "optional_argument_help_flag",
        False,
        "main",
        ["--help"],
        0,
        assert_help,
    ))

    # Case 5: Optional argument -h
    def assert_short_help(before, after, stdout, stderr, repo):
        assert "Usage: git rename-branch" in stdout, "Usage message expected in stdout"
        assert before["local_refs"] == after["local_refs"], "Refs must remain untouched"

    cases_to_run.append((
        "optional_argument_short_help_flag",
        False,
        "main",
        ["-h"],
        0,
        assert_short_help,
    ))

    # Case 6: Documented invalid combination - missing branch name (0 args)
    def assert_missing_branch(before, after, stdout, stderr, repo):
        assert "new branch name required." in stderr, "Expected 'new branch name required.' in stderr"
        assert before["local_refs"] == after["local_refs"], "Refs must remain untouched"

    cases_to_run.append((
        "documented_invalid_combination_missing_branch",
        False,
        "main",
        [],
        1,
        assert_missing_branch,
    ))

    # Case 7: Documented invalid combination - unknown option
    def assert_unknown_option(before, after, stdout, stderr, repo):
        assert "error: unknown option" in stderr, "Expected 'error: unknown option' in stderr"
        assert before["local_refs"] == after["local_refs"], "Refs must remain untouched"

    cases_to_run.append((
        "documented_invalid_combination_unknown_option",
        False,
        "main",
        ["--invalid-flag"],
        1,
        assert_unknown_option,
    ))

    # Case 8: Documented invalid combination - too many arguments
    def assert_too_many_arguments(before, after, stdout, stderr, repo):
        assert "error: too many arguments" in stderr, "Expected 'error: too many arguments' in stderr"
        assert before["local_refs"] == after["local_refs"], "Refs must remain untouched"

    cases_to_run.append((
        "documented_invalid_combination_too_many_arguments",
        False,
        "main",
        ["branch1", "branch2", "branch3"],
        1,
        assert_too_many_arguments,
    ))

    # Case 9: Edge-state - renaming non-existent branch fails
    def assert_non_existent_branch(before, after, stdout, stderr, repo):
        assert before["local_refs"] == after["local_refs"], "Refs must remain unchanged"

    cases_to_run.append((
        "edge_state_non_existent_branch",
        False,
        "main",
        ["non-existent-branch", "new-branch"],
        128,  # Git branch -m exits 128 when branch does not exist
        assert_non_existent_branch,
    ))

    # Case 10: Edge-state - renaming to an already existing branch fails
    def assert_existing_target(before, after, stdout, stderr, repo):
        assert before["local_refs"] == after["local_refs"], "Refs must remain unchanged when target branch exists"

    cases_to_run.append((
        "edge_state_target_branch_already_exists",
        False,
        "topic",
        ["topic", "main"],
        128,  # Git branch -m exits 128 because main already exists
        assert_existing_target,
    ))

    # Zero-case run rejection
    if len(cases_to_run) == 0:
        raise RuntimeError("Zero-case run rejected: No check cases defined.")

    results = []
    has_failure = False

    for name, remote, init_branch, args, exp_exit, fn in cases_to_run:
        res = run_check_case(name, remote, init_branch, args, exp_exit, fn)
        status_label = "PASS" if res["passed"] else "FAIL"
        print(f"[{status_label}] {res['name']}")
        print(f"  Args: {res['command']}")
        print(f"  Exit Status: {res['actual_exit']} (expected: {res['expected_exit']})")
        if not res["passed"]:
            print(f"  Error: {res['error']}")
            has_failure = True
        else:
            before_branch = res["before_state"]["current_branch"]
            after_branch = res["after_state"]["current_branch"]
            print(f"  Branch: '{before_branch}' -> '{after_branch}'")
        results.append(res)

    # 4. Save results.json
    results_path = WORK_DIR / "results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "tool_versions": tool_versions,
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
        f.write("=== git-rename-branch Verification Summary (R13-T013) ===\n\n")
        f.write("Tool Versions:\n")
        for k, v in tool_versions.items():
            f.write(f"  {k}: {v}\n")
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
