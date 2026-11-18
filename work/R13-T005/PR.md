# Description

Make `git undo` fail clearly when Git is unavailable or the current repository has no commits, and exercise success/failure paths with isolated state.

# Related Issue

Fixes: #10

# Type of Change

- Bug Fix
- Tests
- Documentation

# Changes Made

- Add explicit Git/repository preflight checks to `bin/git-undo`.
- Document the repository prerequisites in `man/git-undo.md`.
- Add Bats coverage for a successful soft undo and for running without Git on `PATH`.
- Record actual arguments, exit status, before/after refs, files, local identity config, and tool versions in `work/R13-T005/`.

# Screenshots / Recordings

Not applicable; this change has no UI.

# Testing

- `make test` — see `work/R13-T005/make-test.log`.
- `python3 work/R13-T005/check.py` — passed both focused scenarios.

# Checklist

- [x] Tested changes locally.
- [x] Added tests.
- [x] Updated documentation.
- [x] Followed the project coding style.
- [x] Ran relevant tests and checks.

# Additional Notes

Git history and identity configuration are created only inside Bats temporary repositories; the missing-dependency scenario executes the real script with an isolated `PATH`.
