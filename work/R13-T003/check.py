#!/usr/bin/env python3
"""Run and record the isolated git-gh-pages state-transition test."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK = pathlib.Path(__file__).resolve().parent
TEST_FILE = ROOT / "tests" / "git-gh-pages.bats"
TEST_NAME = "creates gh-pages while preserving the original branch state"


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
    with tempfile.TemporaryDirectory(prefix="r13-t003-") as temp_dir:
        scenario_log = pathlib.Path(temp_dir) / "scenarios.jsonl"
        result = run(args, extra_env={"R13_SCENARIO_LOG": str(scenario_log)})
        scenarios = [json.loads(line) for line in scenario_log.read_text(encoding="utf-8").splitlines()]

    output = result.stdout + result.stderr
    passed = [line.split(" ", 2)[2] for line in output.splitlines() if line.startswith("ok ")]
    plan = next((line for line in output.splitlines() if line.startswith("1..")), None)
    report = {
        "task": "R13-T003",
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
            "stdin": ["sampleuser", "samplerepo"],
            "external_git_push": "intercepted by a temporary git wrapper; no network push is performed",
        },
        "versions": {
            "git": version(["git", "--version"]),
            "bash": version(["bash", "--version"]),
            "bats": version(["bats", "--version"]),
            "python": sys.version.split()[0],
        },
    }
    (WORK / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if result.returncode != 0 or plan != "1..1" or passed != [TEST_NAME]:
        print(output, end="")
        return result.returncode or 1
    if len(scenarios) != 1:
        print("Expected exactly one recorded state-transition scenario.", file=sys.stderr)
        return 1
    scenario = scenarios[0]
    before, after = scenario["before"], scenario["after"]
    if (
        scenario["exit_status"] != 0
        or len(scenario["argv"]) != 1
        or pathlib.Path(scenario["argv"][0]).resolve() != ROOT / "bin" / "git-gh-pages"
    ):
        print("Command arguments or exit status differed from expectations.", file=sys.stderr)
        return 1
    if before["branch"] != "main" or after["branch"] != "gh-pages":
        print("Expected the active branch to transition from main to gh-pages.", file=sys.stderr)
        return 1
    if before["main_ref"] != after["main_ref"] or before["topic_ref"] != after["topic_ref"]:
        print("The unrelated main or topic branch ref changed.", file=sys.stderr)
        return 1
    if before["files"]["unrelated.txt"] != after["files"]["unrelated.txt"]:
        print("The unrelated file changed.", file=sys.stderr)
        return 1
    if after["files"]["index.html"] != "My Page\n" or after["files"]["tracked.txt"] != "base value\n":
        print("The expected page file or stashed working-tree restoration is missing.", file=sys.stderr)
        return 1
    if not after["stash_list"] or after["remote_origin"] != "https://github.com/sampleuser/samplerepo.git":
        print("Expected stash or origin remote state was not recorded.", file=sys.stderr)
        return 1
    if after["push_argv"] != ["push -u origin gh-pages"]:
        print("The expected push command was not intercepted.", file=sys.stderr)
        return 1
    if after["status"]:
        print("The resulting work tree is not clean.", file=sys.stderr)
        return 1
    print(f"PASS: isolated state-transition test; results saved to {WORK / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
