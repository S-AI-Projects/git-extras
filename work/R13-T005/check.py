#!/usr/bin/env python3
"""Run and record git-undo success and missing-dependency tests."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK = pathlib.Path(__file__).resolve().parent
TEST_FILE = ROOT / "tests" / "git-undo.bats"
EXPECTED_CASES = [
    "undo removes one latest commit using only temporary repository config",
    "reports a missing git executable without changing the repository",
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
    with tempfile.TemporaryDirectory(prefix="r13-t005-") as temp_dir:
        scenario_log = pathlib.Path(temp_dir) / "scenarios.jsonl"
        result = run(args, extra_env={"R13_SCENARIO_LOG": str(scenario_log)})
        scenarios = [json.loads(line) for line in scenario_log.read_text(encoding="utf-8").splitlines()]

    output = result.stdout + result.stderr
    passed = [line.split(" ", 2)[2] for line in output.splitlines() if line.startswith("ok ")]
    plan = next((line for line in output.splitlines() if line.startswith("1..")), None)
    report = {
        "task": "R13-T005",
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
            "temporary_repository": "three commits A/B/C, main and topic branches, local user.name/user.email",
            "success_invocation": ["git-undo"],
            "dependency_failure": "run the actual script under /bin/bash with PATH containing no git executable",
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
        print("Expected the success and missing-dependency scenarios.", file=sys.stderr)
        return 1
    success, missing_git = scenarios
    before, after = success["before"], success["after"]
    if success["exit_status"] != 0 or success["argv"] != ["git-undo"]:
        print("The successful command arguments or exit status differed.", file=sys.stderr)
        return 1
    if before["branch"] != "topic" or after["branch"] != "topic" or before["head"] == after["head"]:
        print("The successful undo did not move topic back one commit.", file=sys.stderr)
        return 1
    if before["main_ref"] != after["main_ref"] or after["user_name"] != "Name" or after["user_email"] != "name@example.com":
        print("An unrelated branch or local identity config changed.", file=sys.stderr)
        return 1
    if after["files"]["a.txt"] != "A\nB\nC\n" or after["status"] != ["M  a.txt"]:
        print("Soft undo did not preserve the removed commit as a staged change.", file=sys.stderr)
        return 1
    if missing_git["exit_status"] != 127 or missing_git["before"] != missing_git["after"]:
        print("Missing-git handling did not fail cleanly without changing repo state.", file=sys.stderr)
        return 1
    print(f"PASS: {len(scenarios)} git-undo scenarios; results saved to {WORK / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
