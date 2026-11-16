# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command contrib
}

setup() {
	test_util.cd_test
	test_util.git_init

	git config user.name "Jane Doe"
	git config user.email "jane@example.com"
	mkdir -p "docs and notes"
	printf '%s\n' "Document content" > "docs and notes/notes with space.txt"
	printf '%s\n' "Source content" > "source.txt"
	git add .
	git commit -m "Jane commit: added docs and source"

	git config user.name "John Smith"
	git config user.email "john@example.com"
	printf '%s\n' "John content" > "john.txt"
	git add .
	git commit -m "John commit: added john file"
}

@test "git-contrib without arguments fails and displays error" {
	run git contrib
	assert_failure
	assert_equal "$status" 1
	assert_line -p "user name required."
}

@test "git-contrib with empty string fails and displays error" {
	run git contrib ""
	assert_failure
	assert_equal "$status" 1
	assert_line -p "user name required."
}

@test "git-contrib finds commits for author with spaces in name" {
	run git contrib "Jane Doe"
	assert_success
	assert_line -p "Jane commit: added docs and source"
	refute_line -p "John commit"
}

@test "git-contrib finds commits using wildcard pattern" {
	# Create a file matching wildcard to ensure glob expansion does not alter the pattern
	touch "Jane Doe.txt"

	run git contrib "Jane*"
	assert_success
	assert_line -p "Jane commit: added docs and source"
	refute_line -p "John commit"
}

@test "git-contrib preserves path containing spaces after double dash" {
	run git contrib "Jane Doe" -- "docs and notes/notes with space.txt"
	assert_success
	assert_line -p "Jane commit: added docs and source"

	run git contrib "John Smith" -- "docs and notes/notes with space.txt"
	assert_success
	assert_output ""
}
