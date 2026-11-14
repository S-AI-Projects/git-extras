# Description

Fix the `git squash` argument contract and add focused coverage for successful, missing-source, and incompatible-option cases. The command now preserves positional arguments while parsing `--squash-msg`, rejects missing sources and unsupported options, and reports its usage.

# Related Issue

Fixes: #1

# Type of Change

- Bug Fix
- Tests
- Documentation

# Changes Made

- Corrected argument parsing and validation in `bin/git-squash`.
- Clarified supported syntax and staged versus committed behavior in `man/git-squash.md`.
- Added four Bats cases in `tests/git-squash.bats`.
- Added the isolated command checker and recorded results in [`work/R13-T001/check.py`](work/R13-T001/check.py) and [`work/R13-T001/results.json`](work/R13-T001/results.json).

# Screenshots / Recordings

Not applicable; this change has no UI.

# Testing

- `make test` — passed, 88 tests.
- `python3 work/R13-T001/check.py` — passed three isolated command scenarios and all four focused Bats cases.
- Full suite used GNU Bash 5.3 and rsync 3.5.2 via a command-local `PATH` on macOS.

# Checklist

- [x] Tested changes locally.
- [x] Added tests.
- [x] Updated documentation.
- [x] Followed the project coding style.
- [x] Ran relevant tests and checks.

# Additional Notes

The checker records the actual command arguments, exit status, output, repository state before and after each scenario, and tool versions in `work/R13-T001/results.json`.
