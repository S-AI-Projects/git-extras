#!/usr/bin/env python3
"""Run and record the focused git-rebase-patch Bats contract tests."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK = pathlib.Path(__file__).resolve().parent
TEST_FILE = ROOT / "tests" / "git-rebase-patch.bats"
EXPECTED_CASES = [
    "applies one patch-file argument whose path contains spaces",
    "rejects a missing patch-file argument with usage",
    "rejects an extra positional argument with usage",
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
    with tempfile.TemporaryDirectory(prefix="r13-t002-") as temp_dir:
        scenario_log = pathlib.Path(temp_dir) / "scenarios.jsonl"
        result = run(args, extra_env={"R13_SCENARIO_LOG": str(scenario_log)})
        scenarios = [json.loads(line) for line in scenario_log.read_text(encoding="utf-8").splitlines()]
    output = result.stdout + result.stderr
    observed = [line.split(" ", 2)[2] for line in output.splitlines() if line.startswith("ok ")]
    plan = next((line for line in output.splitlines() if line.startswith("1..")), None)

    report = {
        "task": "R13-T002",
        "command": args,
        "expected": {
            "exit_status": 0,
            "test_count": len(EXPECTED_CASES),
            "test_names": EXPECTED_CASES,
        },
        "actual": {
            "exit_status": result.returncode,
            "tap_plan": plan,
            "passed_test_names": observed,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "scenarios": scenarios,
        },
        "inputs": [
            "A patch file located under the temporary repository's .git directory with a path containing spaces.",
            "The same command invoked with no patch-file argument.",
            "The same command invoked with an unsupported extra positional argument.",
        ],
        "versions": {
            "git": version(["git", "--version"]),
            "bash": version(["bash", "--version"]),
            "bats": version(["bats", "--version"]),
            "python": sys.version.split()[0],
        },
    }
    (WORK / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if result.returncode != 0:
        print(output, end="")
        return result.returncode or 1
    if plan != f"1..{len(EXPECTED_CASES)}" or observed != EXPECTED_CASES:
        print("Focused Bats output did not match the non-zero expected case set.", file=sys.stderr)
        print(output, end="")
        return 1
    if [scenario["name"] for scenario in scenarios] != EXPECTED_CASES:
        print("Scenario evidence is missing or out of order.", file=sys.stderr)
        return 1
    expected_statuses = [0, 2, 2]
    if [scenario["exit_status"] for scenario in scenarios] != expected_statuses:
        print("Scenario exit statuses did not match expectations.", file=sys.stderr)
        return 1
    if scenarios[0]["before"]["head"] == scenarios[0]["after"]["head"] or scenarios[0]["after"]["status"]:
        print("The successful patch case did not leave the expected committed clean state.", file=sys.stderr)
        return 1
    if any(s["before"] != s["after"] for s in scenarios[1:]):
        print("A rejected argument case changed repository state.", file=sys.stderr)
        return 1
    print(f"PASS: {len(observed)} focused git-rebase-patch cases; results saved to {WORK / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
