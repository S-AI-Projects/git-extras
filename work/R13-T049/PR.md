## Description
Integrate focused test checks and characterization for `git-mr` in `tests/git-mr.bats`, implement `-h`/`--help` option tokens in `bin/git-mr`, and document diagnostic error states in `man/git-mr.md`. Includes repeatable test harness in `work/R13-T049/check.py` validating numeric ID, GitLab URL, Codeberg URL, missing argument boundaries, non-existent MR ref rejection, and `clean` subcommands in isolated temporary environments.

## Related Issue
Fixes: #50

## Type of Change
- [x] Bug Fix
- [x] New Feature
- [x] Tests
- [x] Documentation
- [x] Refactoring / Maintenance

## Changes Made
- Updated `bin/git-mr`:
  - Added `-h` / `--help` flag handling to display synopsis usage (resolving previously broken `--help` mentioned in error output).
  - Quoted ref globs in `clean` subcommand to prevent shell expansion issues.
- Updated `man/git-mr.md`:
  - Added `[-h|--help]` to synopsis and options.
  - Added `## DIAGNOSTICS & ERRORS` section documenting failure behavior on missing arguments and remote reference lookup failures.
- Updated `tests/git-mr.bats`:
  - Expanded Bats test suite to 8 tests covering numeric ID checkout, explicit remote checkout, GitLab merge request URL, Forgejo/Codeberg pull request URL, help options (`-h`/`--help`), missing argument failure, non-existent MR ref failure, and `clean` cleanup.
- Added `work/R13-T049/check.py` and saved full verification report in `work/R13-T049/verification_report.json` and `work/R13-T049/report.json`.

## Screenshots / Recordings
N/A (CLI tool and test suite)

## Testing
- `bats tests/git-mr.bats` (8/8 passing)
- `python3 work/R13-T049/check.py` (8/8 verification checks passing in isolated temporary environments)

## Checklist
- [x] I have tested my changes locally.
- [x] I have added or updated tests, if needed.
- [x] I have updated documentation, if needed.
- [x] I have followed the project's coding guidelines.
- [x] I have run the relevant tests and checks.
- [x] I have addressed previous review feedback, if applicable.

## Additional Notes
All tests and verification executions run inside isolated temporary repositories without modifying global or user Git configuration. Evidence is stored in `work/R13-T049/`.
