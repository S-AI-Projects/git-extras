# Description

Add a regression test for a valid Forgejo pull request URL with a query suffix. The test confirms the pull request number, local branch, fetched ref, and remote configuration are still derived from the URL path.

# Related Issue

Fixes: #15

# Type of Change

- Tests

# Changes Made

- Cover `https://codeberg.org/owner/repository/pulls/51?diff=split` using a local bare remote and URL rewrite.
- Verify a temporary one-condition URL matcher mutant is rejected, then run all `git-mr` tests against the unmodified command.
- Record inputs, expected and actual results, and tool versions in `work/R13-T010/`.

# Screenshots / Recordings

Not applicable; this is a command-line test change.

# Testing

- `make test` — see `work/R13-T010/make-test.log`.
- `python3 work/R13-T010/check.py` — the regression rejected the mutant and all four unmutated `git-mr` tests passed.

# Checklist

- [x] Tested changes locally.
- [x] Added tests.
- [x] Updated documentation.
- [x] Followed the project coding style.
- [x] Ran relevant tests and checks.

# Additional Notes

The mutation runs in a temporary copy of the test tree and is removed with that temporary directory. No mutation is committed, and the test uses only a local bare remote.
