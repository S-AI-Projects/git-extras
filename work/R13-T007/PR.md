# Description

Add a complete `git sed` usage example that sets up a tracked file, replaces text, shows the output, and verifies the resulting working-tree diff. Execute the same example in Bats so the documentation stays accurate.

# Related Issue

Fixes: #12

# Type of Change

- Tests
- Documentation

# Changes Made

- Add a fresh-repository example using `git sed -f g` with a pathspec.
- Show the replaced file contents and `git diff --numstat` result.
- Add a focused Bats test that executes and verifies the example.
- Record the actual arguments, exit status, before/after state, and tool versions in `work/R13-T007/`.

# Screenshots / Recordings

Not applicable; this change has no UI.

# Testing

- `make test` — see `work/R13-T007/make-test.log`.
- `python3 work/R13-T007/check.py` — passed the documented example and state assertions.

# Checklist

- [x] Tested changes locally.
- [x] Added tests.
- [x] Updated documentation.
- [x] Followed the project coding style.
- [x] Ran relevant tests and checks.

# Additional Notes

The example leaves the replacement unstaged and does not create a commit, matching the default behavior of `git sed`.
