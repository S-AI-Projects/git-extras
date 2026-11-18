# Description

Improve the unknown-template diagnostic and document how to find a valid name. Add a focused test that exercises the failure and then the corrected invocation, using a temporary cached list and a local `curl` stub.

# Related Issue

Fixes: #13

# Type of Change

- Bug fix
- Tests
- Documentation

# Changes Made

- Explain the non-zero unknown-template failure and how to list or refresh template names.
- Verify `--replace Vmi` fails without changing the existing `.gitignore`.
- Verify the corrected `--replace Vim` succeeds using a local fixture, with no public network access.
- Record actual arguments, exit statuses, before/after state, and tool versions in `work/R13-T008/`.

# Screenshots / Recordings

Not applicable; this is a command-line change.

# Testing

- `make test` — see `work/R13-T008/make-test.log`.
- `python3 work/R13-T008/check.py` — passed both failure and corrected invocation assertions.

# Checklist

- [x] Tested changes locally.
- [x] Added tests.
- [x] Updated documentation.
- [x] Followed the project coding style.
- [x] Ran relevant tests and checks.

# Additional Notes

The test overrides `curl` with a local fixture and uses an isolated XDG cache, so neither GitHub nor user configuration is touched.
