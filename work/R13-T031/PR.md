# Description

Specify the command contract for `git-unlock` and add focused Bats and isolated test coverage for ordinary success and supported empty/missing-state cases. The command contract specifies clearing the `--no-skip-worktree` bit on tracked files in the Git index, requiring a non-empty filename argument, and exiting with status 1 on omitted or empty arguments.

# Related Issue

Fixes: #4

# Type of Change

- Tests
- Documentation
- Bug Fix

# Changes Made

- Clarified and fortified argument handling in `bin/git-unlock` by separating options with `--` to avoid parsing filenames as flags while preserving the pinned validation check (`test -z "$filename" && echo "filename required." 1>&2 && exit 1`).
- Updated `man/git-unlock.md` to document the `--no-skip-worktree` contract, tracked file requirement, and exit status 1 with error on omitted or empty arguments.
- Updated `man/git-unlock.1` and `man/git-unlock.html` in place to keep generated documentation synchronized.
- Added native Bats test suite in `tests/git-unlock.bats` covering:
  - Successful unlocking of a locked file (`--skip-worktree` to `--no-skip-worktree`)
  - Unlocking an already unlocked file without changing state
  - Rejection of omitted filename argument with exit status 1
  - Rejection of empty filename argument with exit status 1
  - Rejection of untracked/non-existent files
- Created automated checker in `work/R13-T031/check.py` to assert command contract execution and state isolation across temporary repositories with commits A/B/C, branches main/topic, and a local bare remote.
- Saved execution results, expected vs actual values, tool versions, and native test names in `work/R13-T031/results.json`, `work/R13-T031/tool_versions.json`, and `work/R13-T031/native_test_names.txt`.

# Screenshots / Recordings

Not applicable; command-line utility.

# Testing

- `make test` — 89/89 tests passed.
- `python3 work/R13-T031/check.py` — 5/5 direct isolated checks and 5/5 native Bats tests passed.
- `python3 scripts/checkstyle.py` — 0 issues found.
- All state changes remained inside isolated temporary directories with isolated global Git configurations (`GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL`), leaving user and system configurations unchanged.

# Checklist

- [x] Tested changes locally.
- [x] Added tests.
- [x] Updated documentation.
- [x] Followed the project coding style.
- [x] Ran relevant tests and checks.

# Additional Notes

The check reports actual command arguments, exit status, stdout, stderr, and repository before/after state in `work/R13-T031/results.json`.
