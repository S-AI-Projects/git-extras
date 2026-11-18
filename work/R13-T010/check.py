#!/usr/bin/env python3
"""Kill a temporary git-mr URL matcher mutant, then run its regression suite."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK = pathlib.Path(__file__).resolve().parent
TEST_NAME = "checks out a Forgejo pull request URL with a query suffix"
ORIGINAL_CONDITION = "pulls/([0-9]+).*$"
MUTANT_CONDITION = "pulls/([0-9]+)$"


def run(args: list[str], *, cwd: pathlib.Path, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:{ROOT / 'bin'}:{env.get('PATH', '')}"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=False)


def version(args: list[str]) -> str:
    result = run(args, cwd=ROOT)
    return (result.stdout or result.stderr).splitlines()[0] if result.returncode == 0 else "unavailable"


def copy_test_tree(destination: pathlib.Path) -> None:
    for name in ("bin", "helper", "tests", "vendor"):
        shutil.copytree(ROOT / name, destination / name)
    for name in ("need_git_commit", "not_need_git_repo"):
        shutil.copy2(ROOT / name, destination / name)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="r13-t010-mutant-") as temp_dir:
        mutant_root = pathlib.Path(temp_dir) / "checkout"
        mutant_root.mkdir()
        copy_test_tree(mutant_root)
        mutant_source = mutant_root / "bin" / "git-mr"
        source_text = mutant_source.read_text(encoding="utf-8")
        if source_text.count(ORIGINAL_CONDITION) != 1:
            raise RuntimeError("Expected exactly one URL matcher condition to mutate")
        mutant_source.write_text(source_text.replace(ORIGINAL_CONDITION, MUTANT_CONDITION), encoding="utf-8")
        mutant_source.chmod(0o755)
        mutant_args = ["bats", "--filter", "query suffix", "tests/git-mr.bats"]
        mutant = run(mutant_args, cwd=mutant_root)
        mutant_output = mutant.stdout + mutant.stderr

    native_args = ["bats", str(ROOT / "tests" / "git-mr.bats")]
    native = run(native_args, cwd=ROOT)
    native_output = native.stdout + native.stderr
    native_passes = [line.split(" ", 2)[2] for line in native_output.splitlines() if line.startswith("ok ")]
    native_plan = next((line for line in native_output.splitlines() if line.startswith("1..")), None)
    report = {
        "task": "R13-T010",
        "mutant": {
            "command": mutant_args,
            "condition_before": ORIGINAL_CONDITION,
            "condition_after": MUTANT_CONDITION,
            "expected": {"exit_status": "non-zero", "test_name": TEST_NAME},
            "actual": {"exit_status": mutant.returncode, "stdout": mutant.stdout, "stderr": mutant.stderr},
        },
        "regression": {
            "command": native_args,
            "expected": {
                "exit_status": 0,
                "test_count": 4,
                "test_names": [
                    "checks out a merge request by numeric id",
                    "checks out a merge request by numeric id and explicit remote",
                    "checks out a Forgejo/Codeberg pull request by URL",
                    TEST_NAME,
                ],
            },
            "actual": {
                "exit_status": native.returncode,
                "tap_plan": native_plan,
                "passed_test_names": native_passes,
                "stdout": native.stdout,
                "stderr": native.stderr,
            },
        },
        "input": "https://codeberg.org/owner/repository/pulls/51?diff=split",
        "versions": {
            "git": version(["git", "--version"]),
            "bash": version(["bash", "--version"]),
            "bats": version(["bats", "--version"]),
            "python": sys.version.split()[0],
        },
    }
    (WORK / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if mutant.returncode == 0 or TEST_NAME not in mutant_output:
        print("The query-suffix regression did not reject the temporary mutant.", file=sys.stderr)
        print(mutant_output, end="")
        return 1
    expected_names = report["regression"]["expected"]["test_names"]
    if native.returncode != 0 or native_plan != "1..4" or native_passes != expected_names:
        print("The unmutated git-mr regression suite did not pass.", file=sys.stderr)
        print(native_output, end="")
        return native.returncode or 1
    print(f"PASS: mutant rejected and 4 git-mr tests passed; results saved to {WORK / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
