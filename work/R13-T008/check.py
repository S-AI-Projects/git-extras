#!/usr/bin/env python3
"""Run and verify the git-ignore-io failure and corrected invocation."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK = pathlib.Path(__file__).resolve().parent
TEST_FILE = ROOT / "tests" / "git-ignore-io.bats"
TEST_NAME = "diagnoses an unknown template and succeeds with the corrected name"
EXPECTED = {
    "failure": {
        "argv": ["git-ignore-io", "--replace", "Vmi"],
        "status": 1,
        "diagnostic": "Template not found: Vmi. Use --list-alphabetically to see available templates.",
    },
    "success": {
        "argv": ["git-ignore-io", "--replace", "Vim"],
        "status": 0,
        "file": "# Vim rules\n*.swp\n\n",
    },
}


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
    with tempfile.TemporaryDirectory(prefix="r13-t008-") as temp_dir:
        scenario_log = pathlib.Path(temp_dir) / "scenarios.jsonl"
        result = run(args, extra_env={"R13_SCENARIO_LOG": str(scenario_log)})
        lines = scenario_log.read_text(encoding="utf-8").splitlines() if scenario_log.exists() else []
        scenarios = [json.loads(line) for line in lines]

    output = result.stdout + result.stderr
    passed = [line.split(" ", 2)[2] for line in output.splitlines() if line.startswith("ok ")]
    plan = next((line for line in output.splitlines() if line.startswith("1..")), None)
    report = {
        "task": "R13-T008",
        "command": args,
        "expected": {"exit_status": 0, "test_count": 1, "test_names": [TEST_NAME], **EXPECTED},
        "actual": {
            "exit_status": result.returncode,
            "tap_plan": plan,
            "passed_test_names": passed,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "scenarios": scenarios,
        },
        "inputs": {"cached_templates": ["Vim", "Python"], "original_gitignore": "keep-me\n"},
        "versions": {
            "git": version(["git", "--version"]),
            "bash": version(["bash", "--version"]),
            "bats": version(["bats", "--version"]),
            "python": sys.version.split()[0],
        },
    }
    (WORK / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if result.returncode != 0 or plan != "1..1" or passed != [TEST_NAME] or len(scenarios) != 2:
        print(output, end="")
        return result.returncode or 1
    failure, success = scenarios
    if failure["argv"] != EXPECTED["failure"]["argv"] or failure["exit_status"] != EXPECTED["failure"]["status"]:
        print("The invalid invocation arguments or exit status differed.", file=sys.stderr)
        return 1
    if EXPECTED["failure"]["diagnostic"] not in failure["output"]:
        print("The failure diagnostic was missing.", file=sys.stderr)
        return 1
    if failure["before"]["gitignore"] != failure["after"]["gitignore"] or failure["after"]["temporary_files"]:
        print("The failing invocation changed or left temporary state.", file=sys.stderr)
        return 1
    if success["argv"] != EXPECTED["success"]["argv"] or success["exit_status"] != EXPECTED["success"]["status"]:
        print("The corrected invocation arguments or exit status differed.", file=sys.stderr)
        return 1
    if success["after"]["gitignore"] != EXPECTED["success"]["file"] or success["after"]["temporary_files"]:
        print("The corrected invocation did not produce the expected file state.", file=sys.stderr)
        return 1
    if failure["before"]["head"] != success["after"]["head"]:
        print("The invocations unexpectedly changed the repository commit.", file=sys.stderr)
        return 1
    print(f"PASS: failure and corrected invocation; results saved to {WORK / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
