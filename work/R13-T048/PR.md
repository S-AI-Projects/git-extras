## Description
Explain a failing invocation for `git-pr` with diagnostics and troubleshooting guidance in `bin/git-pr` and `man/git-pr.md`. Adds characterization tests in `tests/git-pr.bats` demonstrating a non-existent pull request failure with explicit diagnostic output, caller state preservation, recovery with a corrected invocation, invalid pattern/missing argument boundaries, `--merge` flag support, and `clean` subcommands.

## Related Issue
Fixes: #49

## Type of Change
- [x] Bug Fix
- [x] New Feature
- [x] Tests
- [x] Documentation
- [x] Refactoring / Maintenance

## Changes Made
- Updated `bin/git-pr`:
  - Added failure diagnostic when fetching pull request refs fails in `pull()`: explains that the ref could not be fetched from the remote and instructs the user to verify the pull request number and remote.
  - Added synopsis usage hints for missing arguments and unmatched pull request ID patterns.
  - Added `-h` / `--help` flag handling to display synopsis usage.
- Updated `man/git-pr.md`:
  - Added `## DIAGNOSTICS & TROUBLESHOOTING` section documenting failure scenarios, expected error outputs, and the corrected invocation example.
  - Documented `-h | --help` options.
- Added `tests/git-pr.bats`:
  - 6 Bats tests covering failing invocation with diagnostic, corrected invocation success, missing argument error, pattern failure, help flags, `--merge` checkout, and `clean`.
- Added `work/R13-T048/check.py` and saved full verification report in `work/R13-T048/verification_report.json` and `work/R13-T048/report.json`.

## Screenshots / Recordings
N/A (CLI tool and test suite)

## Testing
- `bats tests/git-pr.bats` (6/6 passing)
- `python3 work/R13-T048/check.py` (6/6 verification checks passing in isolated temporary environments)

## Checklist
- [x] I have tested my changes locally.
- [x] I have added or updated tests, if needed.
- [x] I have updated documentation, if needed.
- [x] I have followed the project's coding guidelines.
- [x] I have run the relevant tests and checks.
- [x] I have addressed previous review feedback, if applicable.

## Additional Notes
All tests and verification executions run inside isolated temporary repositories without modifying global or user Git configuration. Evidence is stored in `work/R13-T048/`.
