# R13-T040: Explain a failing invocation: git-delete-tag [man/git-delete-tag.md]

## Summary

This pull request enhances error diagnostics and troubleshooting guidance for `git-delete-tag`, halts execution cleanly if local or remote tag deletion fails, adds `-h` / `--help` usage documentation, and verifies failing branches along with subsequent corrected invocations using native Bats and an automated test harness.

- **Source Refinement (`bin/git-delete-tag`)**:
  - Added `-h` / `--help` flag handling to output command usage.
  - Improved missing argument diagnostic: prints clear error message and hints to inspect existing tags using `git tag -l`.
  - Added error checking after local tag deletion (`git tag -d`) to immediately stop execution and output actionable troubleshooting advice rather than attempting invalid remote deletions.
  - Added remote deletion error handling with troubleshooting hints.
- **Documentation Synchronization (`man/git-delete-tag.*`)**:
  - Updated synopsis, options, and added a DIAGNOSTICS section across `man/git-delete-tag.md`, `man/git-delete-tag.1`, and `man/git-delete-tag.html`.
- **Native Bats Test Suite (`tests/git-delete-tag.bats`)**:
  - Validates missing argument failure and diagnostic messages.
  - Validates non-existent tag failure and troubleshooting hints.
  - Validates corrected single-tag deletion succeeding locally and on remote.
  - Validates multi-tag deletion locally and remotely.
  - Validates `-h` and `--help` usage messages.
- **Automated Verification Harness (`work/R13-T040/check.py`)**:
  - Executes isolated checks with commits A/B/C, tracking branch `topic`, and bare remote.
  - Records inputs, exit status, stdout/stderr, and before/after repository tag states.
  - Generates `results.json`, `tool_versions.json`, and `native_test_names.txt`.

## Verification Checklist

- [x] Tested in temporary Git repository with commits A/B/C, branches main/topic and local bare remote
- [x] Prepended checkout's `bin/` to PATH without installing globally or using public remotes
- [x] Verified failing invocations (missing argument, nonexistent tag) and diagnostic output
- [x] Verified corrected invocation succeeding afterwards locally and on remote
- [x] Native Bats test suite passed (`bats ./tests/git-delete-tag.bats`)
- [x] Automated check suite passed (`python3 work/R13-T040/check.py`)
- [x] Code style checks passed (`python3 scripts/checkstyle.py`)
- [x] Repository test suite verified (`make test`)
