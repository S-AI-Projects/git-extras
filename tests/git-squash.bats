#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command squash
}

setup() {
	test_util.cd_test
	test_util.git_init

	printf '%s\n' 'base' > base.txt
	git add base.txt
	git commit -m A

	git switch -c topic
	printf '%s\n' 'from B' > B.txt
	git add B.txt
	git commit -m B
	printf '%s\n' 'from C' > C.txt
	git add C.txt
	git commit -m C

	git switch main
}

@test "squashes a topic branch into the index without moving HEAD" {
	local before_head
	before_head=$(git rev-parse HEAD)

	run git squash topic
	assert_success
	assert_line -p 'Squash commit -- not updating HEAD'

	run git rev-parse HEAD
	assert_output "$before_head"

	run git diff --cached --name-only
	assert_line B.txt
	assert_line C.txt

	run git status --short
	assert_line 'A  B.txt'
	assert_line 'A  C.txt'
}

@test "rejects a missing source without changing repository state" {
	local before_head
	before_head=$(git rev-parse HEAD)

	run git squash
	assert_failure
	assert_line -p 'Source branch or commit reference required.'

	run git rev-parse HEAD
	assert_output "$before_head"
	run git status --short
	assert_output ''
}

@test "commits the squash with concatenated messages" {
	local before_head
	before_head=$(git rev-parse HEAD)

	run git squash --squash-msg topic
	assert_success

	run git rev-parse HEAD
	refute_output "$before_head"

	run git log -1 --format=%B
	assert_line B
	assert_line C

	run git status --short
	assert_output ''
}

@test "rejects a message with --squash-msg without changing state" {
	local before_head
	before_head=$(git rev-parse HEAD)

	run git squash --squash-msg topic message
	assert_failure
	assert_line -p 'When commit message is given, --squash-msg is not allowed.'

	run git rev-parse HEAD
	assert_output "$before_head"
	run git status --short
	assert_output ''
}
