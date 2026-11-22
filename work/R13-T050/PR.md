## Description
Protect condition in `bin/git-browse-ci` by ensuring `git rev-parse --abbrev-ref HEAD` preserves stdout (redirecting only stderr with `2> /dev/null` rather than `&> /dev/null`). This allows `git-browse-ci` to correctly identify the current branch and look up `branch.<branch>.remote` instead of discarding stdout and always falling back to `origin`. Adds characterization regression tests in `tests/git-browse-ci.bats` that reject the mutant, and adds exit status documentation in `man/git-browse-ci.md`.

## Related Issue
Fixes: #51

## Type of Change
- [x] Bug Fix
- [x] New Feature
- [x] Tests
- [x] Documentation
- [x] Refactoring / Maintenance

## Changes Made
- Updated `bin/git-browse-ci`:
  - Corrected branch detection from `git rev-parse --abbrev-ref HEAD &> /dev/null` to `git rev-parse --abbrev-ref HEAD 2> /dev/null`, ensuring stdout containing the branch name is preserved.
  - Used parameter expansion `${1-}` to safely check for argument existence.
- Updated `man/git-browse-ci.md`:
  - Added `## DIAGNOSTICS & EXIT STATUS` section documenting exit codes (0 for success, 1 when remote is not found).
- Updated `tests/git-browse-ci.bats`:
  - Added regression test verifying default invocation uses branch configured remote over `origin`, explicitly rejecting the mutant.
  - Added test verifying fallback to `origin` when no remote is configured for the branch.
  - Added test for non-existent remote failure (exit status 1 and error message).
- Added `work/R13-T050/check.py` and saved full verification report in `work/R13-T050/verification_report.json` and `work/R13-T050/report.json`.

## Screenshots / Recordings
N/A (CLI tool and test suite)

## Testing
- `bats tests/git-browse-ci.bats` (23/23 passing)
- `python3 work/R13-T050/check.py` (8/8 verification checks passing in isolated temporary environments)

## Checklist
- [x] I have tested my changes locally.
- [x] I have added or updated tests, if needed.
- [x] I have updated documentation, if needed.
- [x] I have followed the project's coding guidelines.
- [x] I have run the relevant tests and checks.
- [x] I have addressed previous review feedback, if applicable.

## Additional Notes
All tests and verification executions run inside isolated temporary repositories without modifying global or user Git configuration. Evidence is stored in `work/R13-T050/`.
