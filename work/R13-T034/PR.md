# R13-T034: Preserve quoted arguments: git-paste

## Short Summary

Preserves quoted argument boundaries and prevents premature shell expansion in `git-paste` when handling path arguments containing spaces and arguments containing wildcard characters (`make test` passed 89/89, `check.py` passed 10/10). Explicitly asserts that shell expansion does not affect unrelated files in the working directory, introduces standalone `-h`/`--help` support without requiring external utilities, and verifies documented failure states when `pastebinit` is missing or when invalid revisions are passed.

## Checklist

- [x] Tested changes locally.
- [x] Added native Bats tests (`tests/git-paste.bats`).
- [x] Updated documentation (`man/git-paste.md`, `man/git-paste.1`, `man/git-paste.html`).
- [x] Followed the project coding guidelines.
- [x] Ran relevant tests and checks (`make test && python3 work/R13-T034/check.py`).
- [x] Complete this task and its checks.
- [x] Add the required evidence and link your pull request here.
- [x] Select this S-AI-Projects fork as the PR base repository.
- [x] Request instructor review.
