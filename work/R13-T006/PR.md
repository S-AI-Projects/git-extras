# Description

Characterize the current positive/negative contribution display and email labels, then collapse the duplicated positive/negative bar-formatting branches into one sign-and-magnitude path without changing the output.

# Related Issue

Fixes: #11

# Type of Change

- Refactoring / Maintenance
- Tests

# Changes Made

- Add deterministic temporary-repository tests for ±50-line output and email labeling.
- Normalize the signed count once, then share the same width threshold and loop for both bar directions.
- Record exact argv, exit status, before/after refs and files, output, and tool versions in `work/R13-T006/`.

# Screenshots / Recordings

Not applicable; this change has no UI.

# Testing

- `make test` — see `work/R13-T006/make-test.log`.
- `python3 work/R13-T006/check.py` — verifies the exact text rendering for both names and email modes.

# Checklist

- [x] Tested changes locally.
- [x] Added tests.
- [x] Followed the project coding style.
- [x] Ran relevant tests and checks.

# Additional Notes

The simplified branch makes the shared condition explicit: absolute contribution count selects compact bars or capped bars, while the sign controls color and bar character. The command's existing exit status of 1 when debug output is omitted is captured and preserved by this characterization task.
