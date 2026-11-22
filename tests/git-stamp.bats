# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command stamp
}

setup() {
	test_util.cd_test
	test_util.git_init

	printf '%s\n' 'base content' > base.txt
	git add base.txt
	git commit -m "Commit A"

	printf '%s\n' 'other content' > other.txt
	git add other.txt
	git commit -m "Commit B"

	git switch -c topic
	printf '%s\n' 'topic content' > topic.txt
	git add topic.txt
	git commit -m "Commit C"

	git switch main
}

@test "git-stamp: appends stamp to commit message while preserving tree and working directory" {
	local before_head before_tree before_topic
	before_head=$(git rev-parse HEAD)
	before_tree=$(git rev-parse HEAD^{tree})
	before_topic=$(git rev-parse topic)

	run git stamp Issue FOO-123
	assert_success

	# Intended change: HEAD commit SHA changes and commit message contains stamp
	local after_head after_tree after_topic
	after_head=$(git rev-parse HEAD)
	after_tree=$(git rev-parse HEAD^{tree})
	after_topic=$(git rev-parse topic)

	assert [ "$after_head" != "$before_head" ]
	run git log -1 --pretty=%B
	assert_line -p "Commit B"
	assert_line -p "Issue FOO-123"

	# Unrelated state unchanged: tree object, topic branch, working tree
	assert_equal "$after_tree" "$before_tree"
	assert_equal "$after_topic" "$before_topic"

	run git status --porcelain
	assert_output ""
}

@test "git-stamp: --replace removes previous stamp with same id while preserving other stamps" {
	git stamp Issue FOO-123
	git stamp Review https://example.com/r/1

	local before_tree before_topic
	before_tree=$(git rev-parse HEAD^{tree})
	before_topic=$(git rev-parse topic)

	run git stamp --replace issue BAR-456
	assert_success

	run git log -1 --pretty=%B
	assert_line -p "Review https://example.com/r/1"
	assert_line -p "issue BAR-456"
	refute_line -p "FOO-123"

	# Tree and unrelated branch unchanged
	assert_equal "$(git rev-parse HEAD^{tree})" "$before_tree"
	assert_equal "$(git rev-parse topic)" "$before_topic"
	assert_equal "$(git status --porcelain)" ""
}

@test "git-stamp: fails when identifier is missing without altering repository state" {
	local before_head before_msg before_tree
	before_head=$(git rev-parse HEAD)
	before_msg=$(git log -1 --pretty=%B)
	before_tree=$(git rev-parse HEAD^{tree})

	run git stamp
	assert_failure
	assert_line -p "error: missing stamp identifier"

	# Repository state unchanged
	assert_equal "$(git rev-parse HEAD)" "$before_head"
	assert_equal "$(git log -1 --pretty=%B)" "$before_msg"
	assert_equal "$(git rev-parse HEAD^{tree})" "$before_tree"
	assert_equal "$(git status --porcelain)" ""
}

@test "git-stamp: fails with --replace when identifier is missing" {
	local before_head
	before_head=$(git rev-parse HEAD)

	run git stamp --replace
	assert_failure
	assert_line -p "error: missing stamp identifier"

	assert_equal "$(git rev-parse HEAD)" "$before_head"
}

