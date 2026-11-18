#!/usr/bin/env bats
# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command rebase-patch
}

setup() {
	test_util.cd_test
	test_util.git_init

	printf '%s\n' 'base' > target.txt
	printf '%s\n' 'original' > unrelated.txt
	git add target.txt unrelated.txt
	git commit -m 'A: add base files'

	patch_file="$BATS_TEST_TMPDIR/.git/patch with spaces.diff"
	printf '%s\n' 'patched' > target.txt
	git diff -- target.txt > "$patch_file"
	git checkout -- target.txt

	printf '%s\n' 'later' >> unrelated.txt
	git add unrelated.txt
	git commit -m 'B: update unrelated file'

	git switch -c topic
	printf '%s\n' 'topic' > topic.txt
	git add topic.txt
	git commit -m 'C: add topic file'
}

record_scenario() {
	local name="$1" status="$2" before_head="$3" before_branch="$4" before_status="$5" after_head="$6" after_branch="$7" after_status="$8" output="$9"
	shift 9
	[[ -n "${R13_SCENARIO_LOG:-}" ]] || return 0
	python3 - "$R13_SCENARIO_LOG" "$name" "$status" "$before_head" "$before_branch" "$before_status" "$after_head" "$after_branch" "$after_status" "$output" "$@" <<'PY'
import json
import sys

path, name, status, before_head, before_branch, before_status, after_head, after_branch, after_status, output, *argv = sys.argv[1:]
record = {
    "name": name,
    "argv": argv,
    "exit_status": int(status),
    "before": {"head": before_head, "branch": before_branch, "status": before_status.splitlines()},
    "after": {"head": after_head, "branch": after_branch, "status": after_status.splitlines()},
    "output": output,
}
with open(path, "a", encoding="utf-8") as stream:
    stream.write(json.dumps(record) + "\n")
PY
}

@test "applies one patch-file argument whose path contains spaces" {
	before_head="$(git rev-parse HEAD)"
	before_branch="$(git branch --show-current)"
	before_status="$(git status --porcelain)"
	run git rebase-patch "$patch_file"
	record_scenario "$BATS_TEST_DESCRIPTION" "$status" "$before_head" "$before_branch" "$before_status" "$(git rev-parse HEAD)" "$(git branch --show-current)" "$(git status --porcelain)" "$output" git rebase-patch "$patch_file"
	assert_success
	assert_output --partial 'Patch applied to'

	assert_equal "$(cat target.txt)" 'patched'
	assert_equal "$(cat unrelated.txt)" $'original\nlater'
	assert_equal "$(cat topic.txt)" 'topic'
	assert_equal "$(git branch --show-current)" 'topic'
	assert_equal "$(git status --porcelain)" ''
}

@test "rejects a missing patch-file argument with usage" {
	before_head="$(git rev-parse HEAD)"
	before_branch="$(git branch --show-current)"
	before_status="$(git status --porcelain)"
	run git rebase-patch
	record_scenario "$BATS_TEST_DESCRIPTION" "$status" "$before_head" "$before_branch" "$before_status" "$(git rev-parse HEAD)" "$(git branch --show-current)" "$(git status --porcelain)" "$output" git rebase-patch
	assert_failure 2
	assert_output --partial 'Usage: git rebase-patch <patch-file>'
	assert_equal "$(git rev-parse HEAD)" "$before_head"
	assert_equal "$(git status --porcelain)" "$before_status"
	assert_equal "$(git branch --show-current)" 'topic'
}

@test "rejects an extra positional argument with usage" {
	before_head="$(git rev-parse HEAD)"
	before_branch="$(git branch --show-current)"
	before_status="$(git status --porcelain)"
	run git rebase-patch "$patch_file" extra
	record_scenario "$BATS_TEST_DESCRIPTION" "$status" "$before_head" "$before_branch" "$before_status" "$(git rev-parse HEAD)" "$(git branch --show-current)" "$(git status --porcelain)" "$output" git rebase-patch "$patch_file" extra
	assert_failure 2
	assert_output --partial 'Usage: git rebase-patch <patch-file>'
	assert_equal "$(git rev-parse HEAD)" "$before_head"
	assert_equal "$(git status --porcelain)" "$before_status"
	assert_equal "$(git branch --show-current)" 'topic'
}
