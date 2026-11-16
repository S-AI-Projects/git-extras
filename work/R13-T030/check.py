#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BIN_DIR = REPO_ROOT / "bin"
MERGE_INTO_BIN = BIN_DIR / "git-merge-into"


def get_tool_versions():
    versions = {}
    for tool in ["git", "bash", "bats", "python3"]:
        try:
            res = subprocess.run([tool, "--version"], capture_output=True, text=True, check=True)
            versions[tool] = res.stdout.strip().split("\n")[0]
        except Exception as e:
            versions[tool] = f"unknown ({e})"
    return versions


def run_checks():
    work_dir = Path(__file__).resolve().parent
    work_dir.mkdir(parents=True, exist_ok=True)
    results_file = work_dir / "results.json"

    tool_versions = get_tool_versions()

    results = {
        "task_id": "R13-T030",
        "timestamp": time.time(),
        "tool_versions": tool_versions,
        "test_cases": [],
        "mutation_check": {},
        "passed": 0,
        "failed": 0,
        "status": "pending",
    }

    test_root = tempfile.mkdtemp(prefix="git_merge_into_check_")
    isolated_config = Path(test_root) / "gitconfig"
    isolated_config.write_text("")

    base_env = os.environ.copy()
    base_env["GIT_CONFIG_NOSYSTEM"] = "1"
    base_env["GIT_CONFIG_GLOBAL"] = str(isolated_config)
    base_env["PATH"] = f"{BIN_DIR}:{base_env['PATH']}"
    base_env["GIT_AUTHOR_NAME"] = "Tester"
    base_env["GIT_AUTHOR_EMAIL"] = "tester@example.com"
    base_env["GIT_COMMITTER_NAME"] = "Tester"
    base_env["GIT_COMMITTER_EMAIL"] = "tester@example.com"

    try:
        # Check 1: Help flag
        proc = subprocess.run(
            [str(MERGE_INTO_BIN), "-h"],
            cwd=test_root,
            env=base_env,
            capture_output=True,
            text=True,
        )
        passed = proc.returncode == 0 and "Usage: git merge-into" in proc.stdout
        results["test_cases"].append(
            {
                "name": "help_flag",
                "args": ["-h"],
                "expected_exit": 0,
                "actual_exit": proc.returncode,
                "passed": passed,
                "output": proc.stdout.strip(),
            }
        )

        # Check 2: Missing arguments fails
        proc = subprocess.run(
            [str(MERGE_INTO_BIN)],
            cwd=test_root,
            env=base_env,
            capture_output=True,
            text=True,
        )
        passed = proc.returncode == 1 and "Usage: git merge-into" in proc.stdout
        results["test_cases"].append(
            {
                "name": "missing_arguments_failure",
                "args": [],
                "expected_exit": 1,
                "actual_exit": proc.returncode,
                "passed": passed,
                "output": proc.stdout.strip(),
            }
        )

        # Setup repo with Commits A/B on main, branch topic with Commit C
        repo_dir = Path(test_root) / "repo"
        repo_dir.mkdir()
        subprocess.run(["git", "init", "--initial-branch", "main"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo_dir, check=True)

        # Commit A
        (repo_dir / "a.txt").write_text("Commit A\n")
        subprocess.run(["git", "add", "a.txt"], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Commit A"], cwd=repo_dir, check=True)

        # Commit B
        (repo_dir / "b.txt").write_text("Commit B\n")
        subprocess.run(["git", "add", "b.txt"], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Commit B"], cwd=repo_dir, check=True)

        # Branch topic with Commit C
        subprocess.run(["git", "checkout", "-b", "topic"], cwd=repo_dir, check=True)
        (repo_dir / "c.txt").write_text("Commit C\n")
        subprocess.run(["git", "add", "c.txt"], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Commit C"], cwd=repo_dir, check=True)

        # Check 3: Fast-forward merge with --ff-only
        before_head = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()
        before_main_log = subprocess.run(["git", "log", "main", "--oneline", "-n", "1"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()

        proc = subprocess.run(
            [str(MERGE_INTO_BIN), "main", "--ff-only"],
            cwd=repo_dir,
            env=base_env,
            capture_output=True,
            text=True,
        )
        after_head = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()
        after_main_log = subprocess.run(["git", "log", "main", "--oneline", "-n", "1"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()

        passed = (
            proc.returncode == 0
            and before_head == "topic"
            and after_head == "topic"
            and "Commit C" in after_main_log
        )
        results["test_cases"].append(
            {
                "name": "fast_forward_merge_with_ff_only",
                "args": ["main", "--ff-only"],
                "expected_exit": 0,
                "actual_exit": proc.returncode,
                "before_branch": before_head,
                "after_branch": after_head,
                "before_main_head": before_main_log,
                "after_main_head": after_main_log,
                "passed": passed,
            }
        )

        # Check 4: Mutation verification
        # Introduce a temporary one-condition mutant:
        # Original: if [ "${!#}" = '--ff-only' ]; then
        # Mutant:   if false; then (condition bypassed/disabled)
        # Create a fresh test repo where topic is ahead of main (valid fast-forward input)
        mutant_test_dir = Path(test_root) / "mutant_repo"
        mutant_test_dir.mkdir()
        subprocess.run(["git", "init", "--initial-branch", "main"], cwd=mutant_test_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=mutant_test_dir, check=True)
        subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=mutant_test_dir, check=True)
        (mutant_test_dir / "f1.txt").write_text("Base\n")
        subprocess.run(["git", "add", "f1.txt"], cwd=mutant_test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Base commit"], cwd=mutant_test_dir, check=True)
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=mutant_test_dir, check=True)
        (mutant_test_dir / "f2.txt").write_text("Feature\n")
        subprocess.run(["git", "add", "f2.txt"], cwd=mutant_test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Feature commit"], cwd=mutant_test_dir, check=True)

        mutant_bin = Path(test_root) / "git-merge-into-mutant"
        original_code = MERGE_INTO_BIN.read_text()
        mutated_code = original_code.replace(
            "if [ \"${!#}\" = '--ff-only' ]; then",
            "if false; then",
        )
        mutant_bin.write_text(mutated_code)
        mutant_bin.chmod(0o755)

        # Run valid input "main --ff-only" against original binary on a copy
        orig_copy_dir = Path(test_root) / "orig_repo"
        shutil.copytree(mutant_test_dir, orig_copy_dir)

        orig_proc = subprocess.run(
            [str(MERGE_INTO_BIN), "main", "--ff-only"],
            cwd=orig_copy_dir,
            env=base_env,
            capture_output=True,
            text=True,
        )

        # Run valid input against the mutant binary
        mutant_proc = subprocess.run(
            [str(mutant_bin), "main", "--ff-only"],
            cwd=mutant_test_dir,
            env=base_env,
            capture_output=True,
            text=True,
        )

        # Original succeeds (exit 0) while mutant fails (exit 129 because it falls through to checkout --ff-only)
        mutant_rejected = (orig_proc.returncode == 0 and mutant_proc.returncode != 0)
        results["mutation_check"] = {
            "mutant_description": "Mutated condition: `if [ \"${!#}\" = '--ff-only' ]; then` -> `if false; then`",
            "valid_input": ["main", "--ff-only"],
            "original_exit_code": orig_proc.returncode,
            "mutant_exit_code": mutant_proc.returncode,
            "mutant_rejected": mutant_rejected,
            "explanation": "Valid fast-forward input succeeds on unmutated command but is rejected/broken on mutant, killing the mutant.",
        }
        results["test_cases"].append(
            {
                "name": "one_condition_mutant_rejected",
                "passed": mutant_rejected,
                "details": results["mutation_check"],
            }
        )

        # Diverge branches in repo_dir: Commit D on main, Commit E on topic
        subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True)
        (repo_dir / "d.txt").write_text("Commit D\n")
        subprocess.run(["git", "add", "d.txt"], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Commit D on main"], cwd=repo_dir, check=True)

        subprocess.run(["git", "checkout", "topic"], cwd=repo_dir, check=True)
        (repo_dir / "e.txt").write_text("Commit E\n")
        subprocess.run(["git", "add", "e.txt"], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Commit E on topic"], cwd=repo_dir, check=True)

        # Check 5: Non-fast-forward merge with --ff-only is rejected
        diverged_main_head = subprocess.run(["git", "log", "main", "--oneline", "-n", "1"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()
        proc = subprocess.run(
            [str(MERGE_INTO_BIN), "main", "--ff-only"],
            cwd=repo_dir,
            env=base_env,
            capture_output=True,
            text=True,
        )
        post_reject_main_head = subprocess.run(["git", "log", "main", "--oneline", "-n", "1"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()
        post_reject_head = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()

        passed = (
            proc.returncode != 0
            and post_reject_head == "topic"
            and diverged_main_head == post_reject_main_head
            and "Commit E" not in post_reject_main_head
        )
        results["test_cases"].append(
            {
                "name": "diverged_ff_only_rejection",
                "args": ["main", "--ff-only"],
                "expected_exit_nonzero": True,
                "actual_exit": proc.returncode,
                "main_unchanged": diverged_main_head == post_reject_main_head,
                "passed": passed,
            }
        )

        # Check 6: Native Bats suite
        bats_proc = subprocess.run(
            ["bats", str(REPO_ROOT / "tests" / "git-merge-into.bats")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        passed = bats_proc.returncode == 0 and "ok 1" in bats_proc.stdout
        results["test_cases"].append(
            {
                "name": "native_bats_suite",
                "args": [str(REPO_ROOT / "tests" / "git-merge-into.bats")],
                "expected_exit": 0,
                "actual_exit": bats_proc.returncode,
                "passed": passed,
                "output": bats_proc.stdout.strip(),
            }
        )

    finally:
        shutil.rmtree(test_root, ignore_errors=True)

    # Rejection of zero-case run
    if not results["test_cases"]:
        raise RuntimeError("Rejection: zero test cases executed!")

    results["passed"] = sum(1 for tc in results["test_cases"] if tc["passed"])
    results["failed"] = sum(1 for tc in results["test_cases"] if not tc["passed"])
    results["status"] = "passed" if results["failed"] == 0 else "failed"

    results_file.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))

    if results["status"] != "passed":
        sys.exit(1)


if __name__ == "__main__":
    run_checks()
