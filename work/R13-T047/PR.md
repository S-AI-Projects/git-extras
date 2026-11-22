## Description
Publish a tested usage example for `git-obliterate` with complete setup, command execution, expected output, and state verification in `man/git-obliterate.md`. Adds characterization tests in `tests/git-obliterate.bats` covering the documented success workflow, missing filename failure, option separator handling, help tokens (`-h`/`--help`), and range filtering with `--`.

## Related Issue
Fixes: #48

## Type of Change
- [x] Bug Fix
- [x] New Feature
- [x] Tests
- [x] Documentation
- [x] Refactoring / Maintenance

## Changes Made
- Updated `bin/git-obliterate` to support `-h` and `--help` option tokens displaying synopsis usage, normalized option separator comparison to `test "$i" = '--'`, and clarified argument parsing.
- Updated `man/git-obliterate.md` to document positional argument requirements (`<files...>` required; exits 1 with `file required.`), rev-list option separator `--`, and added a full usage example with setup, command, output, and state verification.
- Added comprehensive native Bats test suite in `tests/git-obliterate.bats` using `tests/test_util.sh` (5 test cases passing).
- Added verification script `work/R13-T047/check.py` and saved full verification report in `work/R13-T047/verification_report.json` and `work/R13-T047/report.json`.

## Screenshots / Recordings
N/A (CLI command documentation and test suite)

## Testing
- `bats tests/git-obliterate.bats` (5/5 passing)
- `python3 work/R13-T047/check.py` (6/6 verification checks passing)

## Checklist
- [x] I have tested my changes locally.
- [x] I have added or updated tests, if needed.
- [x] I have updated documentation, if needed.
- [x] I have followed the project's coding guidelines.
- [x] I have run the relevant tests and checks.
- [x] I have addressed previous review feedback, if applicable.

## Additional Notes
All tests and verification executions run inside isolated temporary repositories without modifying global or user Git configuration. Evidence is stored in `work/R13-T047/`.
