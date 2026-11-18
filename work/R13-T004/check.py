#!/usr/bin/env python3
"""Run and record focused git-effort path-boundary tests."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK = pathlib.Path(__file__).resolve().parent
TEST_FILE = ROOT / "tests" / "git-effort.bats"
EXPECTED_CASES = [
    "passes one quoted path containing spaces and a wildcard as one argument",
    "enumerates special filenames without shell glob expansion",
]
SPECIAL_PATH = "dir with spaces/name[*].txt"
EXPECTED_DEFAULT_PATHS = [
    "dir with spaces/name*.txt",
    SPECIAL_PATH,
    "topic.txt",
    "unrelated.txt",
]


def run(
    args: list[str], *, cwd: pathlib.Path = ROOT, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:{ROOT / 'bin'}:{env.get('PATH', '')}"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=False)


def version(args: list[str]) -> str:
    result = run(args)
    return (result.stdout or result.stderr).splitlines()[0] if result.returncode == 0 else "unavailable"


def main() -> int:
    args = ["bats", str(TEST_FILE)]
    with tempfile.TemporaryDirectory(prefix="r13-t004-") as temp_dir:
        scenario_log = pathlib.Path(temp_dir) / "scenarios.jsonl"
        result = run(args, extra_env={"R13_SCENARIO_LOG": str(scenario_log)})
        scenarios = [json.loads(line) for line in scenario_log.read_text(encoding="utf-8").splitlines()]

    output = result.stdout + result.stderr
    passed = [line.split(" ", 2)[2] for line in output.splitlines() if line.startswith("ok ")]
    plan = next((line for line in output.splitlines() if line.startswith("1..")), None)
    report = {
        "task": "R13-T004",
        "command": args,
        "expected": {"exit_status": 0, "test_count": len(EXPECTED_CASES), "test_names": EXPECTED_CASES},
        "actual": {
            "exit_status": result.returncode,
            "tap_plan": plan,
            "passed_test_names": passed,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "scenarios": scenarios,
        },
        "inputs": {
            "commits": ["A", "B", "C"],
            "branches": ["main", "topic"],
            "quoted_path": SPECIAL_PATH,
            "unrelated_glob_sibling": "dir with spaces/name*.txt",
        },
        "versions": {
            "git": version(["git", "--version"]),
            "bash": version(["bash", "--version"]),
            "bats": version(["bats", "--version"]),
            "python": sys.version.split()[0],
        },
    }
    (WORK / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if result.returncode != 0 or plan != f"1..{len(EXPECTED_CASES)}" or passed != EXPECTED_CASES:
        print(output, end="")
        return result.returncode or 1
    if [scenario["name"] for scenario in scenarios] != EXPECTED_CASES:
        print("Expected exactly the two focused argument-boundary scenarios.", file=sys.stderr)
        return 1
    first, second = scenarios
    if first["exit_status"] != 0 or first["argv"] != ["git-effort", SPECIAL_PATH]:
        print("The quoted path was not preserved as one command argument.", file=sys.stderr)
        return 1
    if [call[-1] for call in first["git_log_argv"]] != [SPECIAL_PATH]:
        print("The Git log call did not receive exactly the quoted path.", file=sys.stderr)
        return 1
    if second["exit_status"] != 0:
        print("Default path enumeration failed.", file=sys.stderr)
        return 1
    observed_paths = sorted(call[-1] for call in second["git_log_argv"])
    if observed_paths != sorted(EXPECTED_DEFAULT_PATHS):
        print(f"Default path arguments differed: {observed_paths!r}", file=sys.stderr)
        return 1
    if first["before"] != first["after"] or second["before"] != second["after"]:
        print("The read-only effort command changed repository state.", file=sys.stderr)
        return 1
    print(f"PASS: {len(scenarios)} focused git-effort cases; results saved to {WORK / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
