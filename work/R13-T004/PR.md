# Description

Preserve filenames containing spaces and shell metacharacters when `git effort` enumerates tracked files by reading NUL-delimited `git ls-files` output. Document the quoting and pathspec behavior.

# Related Issue

Fixes: #9

# Type of Change

- Bug Fix
- Tests
- Documentation

# Changes Made

- Replace unquoted command-substitution array construction with NUL-delimited filename reads.
- Add Bats coverage for a quoted path containing spaces and a wildcard character, and for default enumeration beside a shell-glob sibling.
- Record actual `git log` argv, repository state, expected versus actual paths, and tool versions in `work/R13-T004/`.

# Screenshots / Recordings

Not applicable; this change has no UI.

# Testing

- `make test` — see `work/R13-T004/make-test.log`.
- `python3 work/R13-T004/check.py` — passed both focused path-boundary cases.

# Checklist

- [x] Tested changes locally.
- [x] Added tests.
- [x] Updated documentation.
- [x] Followed the project coding style.
- [x] Ran relevant tests and checks.

# Additional Notes

The command remains read-only. Bats creates its repository, filenames, and Git wrapper under per-test temporary directories.
