# Description

Make the `git rebase-patch` argument boundary explicit and test it. A quoted patch-file path is accepted as one argument; a missing patch file or an extra positional argument receives a usage error before repository state changes.

# Related Issue

Fixes: #7

# Type of Change

- Bug Fix
- Tests
- Documentation

# Changes Made

- Require exactly one patch-file argument in `bin/git-rebase-patch`.
- Document the exact argument contract in `man/git-rebase-patch.md`.
- Add focused Bats cases for a patch path containing spaces, a missing argument, and an unsupported extra argument.
- Add the isolated checker and recorded evidence in `work/R13-T002/`.

# Screenshots / Recordings

Not applicable; this change has no UI.

# Testing

- `make test` — see `work/R13-T002/make-test.log`.
- `python3 work/R13-T002/check.py` — runs and asserts all three focused Bats cases.

# Checklist

- [x] Tested changes locally.
- [x] Added tests.
- [x] Updated documentation.
- [x] Followed the project coding style.
- [x] Ran relevant tests and checks.

# Additional Notes

All command scenarios use Bats temporary repositories; the patch fixture is stored inside the temporary repository's `.git` directory to keep the work tree clean.
