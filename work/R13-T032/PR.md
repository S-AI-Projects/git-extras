# R13-T032: Exercise argument boundaries: git-release

## Short Summary

Exercises and fortifies the argument boundaries for `git-release` by testing the minimum accepted argument list (`<tagname>`), optional arguments (`-m`, `--no-empty-commit`), and the documented invalid combination of mutually exclusive signing flags (`-s` and `-u`), while safeguarding against missing tag arguments when options are provided (`make test` passed 89/89, `check.py` passed 10/10).

## Related Issue

Fixes: #34

## Type of Change

- [x] Bug Fix / Contract preservation
- [x] Tests
- [x] Documentation

## Changes Made

- Fortified argument boundary handling in `bin/git-release` by ensuring `version` or `semver` is present after option parsing (`if [ -z "$version" ] && [ -z "$semver" ]; then exit_with_msg "tag required"; fi`) before release hooks and commits execute.
- Clarified mutually exclusive tag signing flags `[-s | -u <key-id>]` in `man/git-release.md`, `man/git-release.1`, and `man/git-release.html`, explicitly documenting that `-s` and `-u` cannot be used together and that a tagname or `--semver` is required.
- Added native Bats test suite in `tests/git-release.bats` testing minimum accepted argument list, optional custom commit message `-m`, optional `--no-empty-commit`, rejection of invalid `-s` and `-u` combination, and rejection of missing tag argument (5/5 passed).
- Created automated test runner in `work/R13-T032/check.py` to assert argument boundaries and repository state in isolated temporary Git repositories with commits A/B/C, branches main/topic, and a local bare remote. Evidence recorded in `work/R13-T032/results.json`.

## Testing & Results

- `make test`: **89/89 passed** (100% repository test pass rate)
- `python3 work/R13-T032/check.py`: **5/5 direct isolated cases and 5/5 Bats tests passed**
- `python3 scripts/checkstyle.py`: **0 issues found**
- All repository state changes remained strictly isolated within temporary directories with isolated global Git configuration (`GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL`), leaving user and system configurations unchanged.

## Checklist

- [x] Tested changes locally.
- [x] Added native Bats tests (`tests/git-release.bats`).
- [x] Updated documentation (`man/git-release.md`, `man/git-release.1`, `man/git-release.html`).
- [x] Followed the project coding guidelines.
- [x] Ran relevant tests and checks (`make test && python3 work/R13-T032/check.py`).
- [x] Complete this task and its checks.
- [x] Add the required evidence and link your pull request here.
- [x] Select this S-AI-Projects fork as the PR base repository.
- [x] Request instructor review.
