# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command coauthor
}

setup() {
	test_util.cd_test
	test_util.git_init
	printf '%s\n' "Initial" > init.txt
	git add .
	git commit -m "Initial commit"
}

@test "git-coauthor without arguments fails and displays error" {
	run git coauthor
	assert_failure
	assert_equal "$status" 1
	assert_line -p "co-author required."
}

@test "git-coauthor with missing email fails and displays error" {
	run git coauthor "Jane Doe"
	assert_failure
	assert_equal "$status" 1
	assert_line -p "co-author email required."
}

@test "git-coauthor executes documented usage example and adds co-author" {
	printf '%s\n' "auth code" > auth.txt
	git add .
	git commit -m "Implement authentication"

	run git coauthor "Jane Doe" jane@example.com
	assert_success

	run git log -n 1 --format="%B"
	assert_line -p "Implement authentication"
	assert_line -p "Co-authored-by: Jane Doe <jane@example.com>"
}

@test "git-coauthor appends additional co-author to commit with existing co-author" {
	printf '%s\n' "feature" > feat.txt
	git add .
	git commit -m "Feature commit"

	run git coauthor "Jane Doe" jane@example.com
	assert_success

	run git coauthor "Bob Smith" bob@example.com
	assert_success

	run git log -n 1 --format="%B"
	assert_line -p "Feature commit"
	assert_line -p "Co-authored-by: Jane Doe <jane@example.com>"
	assert_line -p "Co-authored-by: Bob Smith <bob@example.com>"
}
