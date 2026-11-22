# R13-T037: Publish a tested usage example: git-scp

## Short Summary

Publishes a verified, complete usage example in `man/git-scp.md` detailing setup, command invocation with `--verbose`, output inspection, and destination state verification (`make test` passed 89/89, `check.py` passed 10/10). Directly exercises the documented scenario in focused native tests to prevent documentation drift, and verifies non-existent remote failure handling and sanitization configuration via `--get-all`.

## Checklist

- [x] Tested changes locally.
- [x] Added native Bats tests (`tests/git-scp.bats`).
- [x] Updated documentation (`man/git-scp.md`, `man/git-scp.1`, `man/git-scp.html`).
- [x] Followed the project coding guidelines.
- [x] Ran relevant tests and checks (`make test && python3 work/R13-T037/check.py`).
- [x] Complete this task and its checks.
- [x] Add the required evidence and link your pull request here.
- [x] Select this S-AI-Projects fork as the PR base repository.
- [x] Request instructor review.
