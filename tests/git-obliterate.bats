#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command obliterate
}

setup() {
	test_util.cd_test
	test_util.git_init
}

@test "executes documented usage example with setup, command, output and state verification" {
	# Documented Setup:
	echo "safe content" > safe.txt
	echo "secret content" > secret.txt
	git add safe.txt secret.txt
	git commit -q -m "Initial commit with secret"
	echo "updated safe content" >> safe.txt
	git commit -q -am "Update safe file"

	# Documented Command:
	run git obliterate secret.txt
	assert_success
	assert_line -p "Ref 'refs/heads/main' was rewritten"

	# Documented State verification:
	run git log -- secret.txt
	assert_output ""

	[ ! -f secret.txt ]
	[ -f safe.txt ]

	run git ls-files
	assert_output "safe.txt"
}

@test "fails with error when filename is missing" {
	run git obliterate
	assert_failure 1
	assert_line -p "file required."
}

@test "fails with error when only option separator is passed" {
	run git obliterate --
	assert_failure 1
	assert_line -p "file required."
}

@test "displays usage information with -h or --help" {
	run git obliterate -h
	assert_success
	assert_line -p "Usage: git obliterate"

	run git-obliterate --help
	assert_success
	assert_line -p "Usage: git obliterate"
}

@test "removes file restricted to a rev-list range using separator token" {
	echo "base" > base.txt
	git add base.txt
	git commit -q -m "Base commit"

	git checkout -b topic main
	echo "topic secret" > secret_topic.txt
	git add secret_topic.txt
	git commit -q -m "Add topic secret"

	run git obliterate secret_topic.txt -- topic ^main
	assert_success
	assert_line -p "Ref 'refs/heads/topic' was rewritten"

	run git log -- secret_topic.txt
	assert_output ""
	[ ! -f secret_topic.txt ]
}
