#!/usr/bin/env python3
"""Run and record git-guilt characterization cases."""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK = pathlib.Path(__file__).resolve().parent
TEST_FILE = ROOT / "tests" / "git-guilt.bats"
EXPECTED_CASES = [
    "characterizes positive and negative contribution bars at the 50-line boundary",
    "characterizes email labeling without changing contribution counts",
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


def expected_output(name_positive: str, name_negative: str) -> str:
    positive = "+" * (48 - len("50"))
    negative = "-" * (48 - len("-50"))
    return f"{name_positive:<29} {positive}(50)\n{name_negative:<29} {negative}(-50)"


def main() -> int:
    args = ["bats", str(TEST_FILE)]
    with tempfile.TemporaryDirectory(prefix="r13-t006-") as temp_dir:
        scenario_log = pathlib.Path(temp_dir) / "scenarios.jsonl"
        result = run(args, extra_env={"R13_SCENARIO_LOG": str(scenario_log)})
        scenarios = [json.loads(line) for line in scenario_log.read_text(encoding="utf-8").splitlines()]

    output = result.stdout + result.stderr
    passed = [line.split(" ", 2)[2] for line in output.splitlines() if line.startswith("ok ")]
    plan = next((line for line in output.splitlines() if line.startswith("1..")), None)
    report = {
        "task": "R13-T006",
        "command": args,
        "expected": {
            "bats_exit_status": 0,
            "scenario_exit_statuses": [1, 1],
            "test_count": len(EXPECTED_CASES),
            "test_names": EXPECTED_CASES,
        },
        "actual": {
            "bats_exit_status": result.returncode,
            "tap_plan": plan,
            "passed_test_names": passed,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "scenarios": scenarios,
        },
        "inputs": {
            "commits": ["A (Alice, 50 lines)", "B (Bob, replaces all 50 lines)"],
            "branches": ["main", "topic"],
            "date_range": ["2020-01-01", "2020-01-02"],
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
        print("Expected both characterization scenarios.", file=sys.stderr)
        return 1
    for index, (scenario, names) in enumerate(zip(
        scenarios,
        [("Bob", "Alice"), ("bob@example.com", "alice@example.com")],
        strict=True,
    )):
        if scenario["exit_status"] != 1 or scenario["argv"][0] != "git-guilt":
            print("The characterized command exit status or argv differed.", file=sys.stderr)
            return 1
        before = scenario["before"]
        if index == 0:
            valid_argv = len(scenario["argv"]) == 3 and scenario["argv"][1:] == [before["base_ref"], before["topic_ref"]]
        else:
            valid_argv = len(scenario["argv"]) == 4 and scenario["argv"][1] == "--email" and scenario["argv"][2:] == [before["base_ref"], before["topic_ref"]]
        if not valid_argv:
            return 1
        plain = re.sub(r"\x1b\[[0-9;]*m", "", scenario["output"])
        if plain != expected_output(*names):
            print(f"Output changed for {scenario['name']}.", file=sys.stderr)
            return 1
        if scenario["before"] != scenario["after"]:
            print(f"Repository state changed in {scenario['name']}.", file=sys.stderr)
            return 1
    print(f"PASS: {len(scenarios)} git-guilt characterization cases; results saved to {WORK / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
