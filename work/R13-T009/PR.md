# Description

Clarify the no-active-operation diagnostic for `git abort`, document the safe failure, and test the plugin through Git's explicit `--git-dir` invocation. The existing Bats cases also exercise aborting cherry-pick, merge, rebase, and revert operations.

# Related Issue

Fixes: #14

# Type of Change

- Bug fix
- Tests
- Documentation

# Changes Made

- Explain that no active operation exits 1 and leaves repository state unchanged.
- Add an integration case invoking `git --git-dir .git abort` with no operation active.
- Keep the existing four real operation abort checks in the focused check entry point.
- Record actual arguments, status, repository state, and tool versions in `work/R13-T009/`.

# Screenshots / Recordings

Not applicable; this is a command-line change.

# Testing

- `make test` — see `work/R13-T009/make-test.log`.
- `python3 work/R13-T009/check.py` — passed the no-op failure and four successful abort workflows.

# Checklist

- [x] Tested changes locally.
- [x] Added tests.
- [x] Updated documentation.
- [x] Followed the project coding style.
- [x] Ran relevant tests and checks.

# Additional Notes

All Git state is created under the Bats temporary directory. The focused run does not depend on a public remote or unrelated service.
