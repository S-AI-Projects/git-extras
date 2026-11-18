#!/usr/bin/env python3
"""Run and verify git-abort's focused Bats integration checks."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK = pathlib.Path(__file__).resolve().parent
TEST_FILE = ROOT / "tests" / "git-abort.bats"
FAILURE_TEST = "explicit git-dir abort with no active operation is a safe failure"
SUCCESS_TESTS = ["works with cherry pick", "works with merge", "works with rebase", "works with revert"]
EXPECTED_ARGV = ["git", "--git-dir", ".git", "abort"]
EXPECTED_DIAGNOSTIC = "No active operation found; nothing to abort or continue"


def run(args: list[str], *, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:{ROOT / 'bin'}:{env.get('PATH', '')}"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True, check=False)


def version(args: list[str]) -> str:
    result = run(args)
    return (result.stdout or result.stderr).splitlines()[0] if result.returncode == 0 else "unavailable"


def main() -> int:
    args = ["bats", str(TEST_FILE)]
    with tempfile.TemporaryDirectory(prefix="r13-t009-") as temp_dir:
        scenario_log = pathlib.Path(temp_dir) / "scenarios.jsonl"
        result = run(args, extra_env={"R13_SCENARIO_LOG": str(scenario_log)})
        lines = scenario_log.read_text(encoding="utf-8").splitlines() if scenario_log.exists() else []
        scenarios = [json.loads(line) for line in lines]

    output = result.stdout + result.stderr
    passed = [line.split(" ", 2)[2] for line in output.splitlines() if line.startswith("ok ")]
    plan = next((line for line in output.splitlines() if line.startswith("1..")), None)
    report = {
        "task": "R13-T009",
        "command": args,
        "expected": {"exit_status": 0, "test_count": 5, "failure_test": FAILURE_TEST, "success_tests": SUCCESS_TESTS},
        "actual": {
            "exit_status": result.returncode,
            "tap_plan": plan,
            "passed_test_names": passed,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "scenarios": scenarios,
        },
        "inputs": {"failure_argv": EXPECTED_ARGV, "expected_failure_status": 1, "expected_success_status": 0},
        "versions": {
            "git": version(["git", "--version"]),
            "bash": version(["bash", "--version"]),
            "bats": version(["bats", "--version"]),
            "python": sys.version.split()[0],
        },
    }
    (WORK / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    expected_tests = [FAILURE_TEST, *SUCCESS_TESTS]
    if result.returncode != 0 or plan != "1..5" or passed != expected_tests or len(scenarios) != 1:
        print(output, end="")
        return result.returncode or 1
    scenario = scenarios[0]
    if scenario["argv"] != EXPECTED_ARGV or scenario["exit_status"] != 1:
        print("The explicit git-dir failure arguments or status differed.", file=sys.stderr)
        return 1
    if EXPECTED_DIAGNOSTIC not in scenario["output"]:
        print("The no-active-operation diagnostic was missing.", file=sys.stderr)
        return 1
    if scenario["before"] != scenario["after"] or scenario["before"]["operation_markers"]:
        print("The safe failure changed the repository or found an active operation.", file=sys.stderr)
        return 1
    print(f"PASS: 1 failure and 4 abort success cases; results saved to {WORK / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
