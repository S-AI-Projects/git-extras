# R13-T035: Isolate environment dependencies: git-extras

## Short Summary

Isolates external environment dependencies for `git-extras` and provides deterministic testing with local configuration (`git config --add git-extras.default-branch`), isolated temporary working directories, and stubbed external commands (`make test` passed 89/89, `check.py` passed 10/10). Adds missing-dependency validation for `curl` during self-update, integrates explicit `-h`/`--help` handling, and guarantees that user and global configurations remain strictly unchanged.

## Checklist

- [x] Tested changes locally.
- [x] Added native Bats tests (`tests/git-extras.bats`).
- [x] Updated documentation (`man/git-extras.md`, `man/git-extras.1`, `man/git-extras.html`).
- [x] Followed the project coding guidelines.
- [x] Ran relevant tests and checks (`make test && python3 work/R13-T035/check.py`).
- [x] Complete this task and its checks.
- [x] Add the required evidence and link your pull request here.
- [x] Select this S-AI-Projects fork as the PR base repository.
- [x] Request instructor review.
