#!/usr/bin/env python3
"""Execute the documented git-sed example and record its observed state."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK = pathlib.Path(__file__).resolve().parent
TEST_FILE = ROOT / "tests" / "git-sed.bats"
TEST_NAME = "executes the documented git-sed example and verifies its state"
EXPECTED_ARGV = ["git-sed", "-f", "g", "hello", "goodbye", "--", "note.txt"]


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
    with tempfile.TemporaryDirectory(prefix="r13-t007-") as temp_dir:
        scenario_log = pathlib.Path(temp_dir) / "scenarios.jsonl"
        result = run(args, extra_env={"R13_SCENARIO_LOG": str(scenario_log)})
        scenarios = [json.loads(line) for line in scenario_log.read_text(encoding="utf-8").splitlines()]

    output = result.stdout + result.stderr
    passed = [line.split(" ", 2)[2] for line in output.splitlines() if line.startswith("ok ")]
    plan = next((line for line in output.splitlines() if line.startswith("1..")), None)
    report = {
        "task": "R13-T007",
        "command": args,
        "expected": {"exit_status": 0, "test_count": 1, "test_names": [TEST_NAME]},
        "actual": {
            "exit_status": result.returncode,
            "tap_plan": plan,
            "passed_test_names": passed,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "scenarios": scenarios,
        },
        "inputs": {
            "tracked_file_before": "hello hello\n",
            "command_argv": EXPECTED_ARGV,
            "expected_file_after": "goodbye goodbye\n",
            "expected_numstat": "1\t1\tnote.txt",
        },
        "versions": {
            "git": version(["git", "--version"]),
            "bash": version(["bash", "--version"]),
            "bats": version(["bats", "--version"]),
            "python": sys.version.split()[0],
        },
    }
    (WORK / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if result.returncode != 0 or plan != "1..1" or passed != [TEST_NAME] or len(scenarios) != 1:
        print(output, end="")
        return result.returncode or 1
    scenario = scenarios[0]
    before, after = scenario["before"], scenario["after"]
    if scenario["argv"] != EXPECTED_ARGV or scenario["exit_status"] != 0:
        print("The documented command arguments or status differed.", file=sys.stderr)
        return 1
    if before["file"] != "hello hello\n" or after["file"] != "goodbye goodbye\n":
        print("The documented replacement result differed.", file=sys.stderr)
        return 1
    if before["head"] != after["head"] or after["status"] != [" M note.txt"] or after["staged_diff"]:
        print("The documented working-tree state differed.", file=sys.stderr)
        return 1
    print(f"PASS: documented git-sed example; results saved to {WORK / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
