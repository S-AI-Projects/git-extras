# R13-T036: Clarify one source responsibility: git-get

## Short Summary

Adds a comprehensive characterization test suite for `git-get` and refactors argument inspection and shift handling in `bin/git-get` (`make test` passed 89/89, `check.py` passed 12/12). Clarifies argument boundary conditions by replacing arithmetic evaluation and removing unreachable defensive shift branches while strictly preserving observable behavior across URL parsing, trailing slash stripping, option forwarding, and missing clone-path errors.

## Checklist

- [x] Tested changes locally.
- [x] Added native Bats tests (`tests/git-get.bats`).
- [x] Updated documentation (`man/git-get.md`, `man/git-get.1`, `man/git-get.html`).
- [x] Followed the project coding guidelines.
- [x] Ran relevant tests and checks (`make test && python3 work/R13-T036/check.py`).
- [x] Complete this task and its checks.
- [x] Add the required evidence and link your pull request here.
- [x] Select this S-AI-Projects fork as the PR base repository.
- [x] Request instructor review.
