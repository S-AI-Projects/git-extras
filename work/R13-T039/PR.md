# R13-T039: Protect a condition with a regression: git-local-commits [man/git-local-commits.md]

## Summary

This pull request introduces regression protection against mutations for `git-local-commits`, ensures robust positional argument handling, and adds `-h` / `--help` flag support with synchronized documentation and full test suite coverage.

- **Source Clarification (`bin/git-local-commits`)**: Added clean handling for `-h` and `--help` flags displaying command usage directly without invalid invocation of `git log` options.
- **Documentation Updates (`man/git-local-commits.*`)**: Synchronized synopsis, options, and manual references across `man/git-local-commits.md`, `man/git-local-commits.1`, and `man/git-local-commits.html`.
- **Bats Test Coverage (`tests/git-local-commits.bats`)**: Added native Bats test suite covering:
  - Strict exclusion of upstream commits and detection of local unpushed commits (killing mutant conditions lacking `@{upstream}..@`).
  - Forwarding of positional arguments, formatting options (`--oneline`), and pathspecs (`-- file`).
  - Clean display of usage information upon `-h` and `--help`.
  - Proper failure handling when a branch does not have a configured upstream.
- **Automated Verification Harness (`work/R13-T039/check.py`)**: Implemented standalone runner verifying 8 focused test cases and all Bats tests in an isolated sandbox with commits A/B/C, tracking/untracked branches, and a local bare remote. Generated `results.json`, `tool_versions.json`, and `native_test_names.txt`.

## Verification Checklist

- [x] Tested in temporary Git repository with commits A/B/C, branches main/topic and local bare remote
- [x] Prepended checkout's `bin/` to PATH without installing globally or using public remotes
- [x] Verified rejection of mutant condition lacking upstream range restriction
- [x] Native Bats test suite passed (`bats ./tests/git-local-commits.bats`)
- [x] Automated check suite passed (`python3 work/R13-T039/check.py`)
- [x] Code style checks passed (`python3 scripts/checkstyle.py`)
- [x] Repository test suite verified (`make test`)
