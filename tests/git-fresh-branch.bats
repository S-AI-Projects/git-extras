# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command fresh-branch
}

setup() {
	test_util.cd_test
	test_util.git_init

	printf '%s\n' 'data A' > fileA
	git add fileA
	git commit -m "commit A"
}

@test "git-fresh-branch: minimum accepted arguments creates fresh branch" {
	run git fresh-branch my-fresh-branch
	assert_success

	# Verify active branch is my-fresh-branch
	local current_branch
	current_branch=$(git branch --show-current)
	assert_equal "$current_branch" "my-fresh-branch"

	# Fresh branch is an orphan branch with no commits yet
	run git rev-parse --verify HEAD
	assert_failure

	# Working directory is clean
	run git status --porcelain
	assert_success
	assert_output ""
}

@test "git-fresh-branch: optional argument --help shows usage" {
	run git-fresh-branch --help
	assert_success
	assert_line -p "Usage: git fresh-branch"

	# Active branch is unchanged
	local current_branch
	current_branch=$(git branch --show-current)
	assert_equal "$current_branch" "main"
}

@test "git-fresh-branch: optional argument -h shows usage" {
	run git-fresh-branch -h
	assert_success
	assert_line -p "Usage: git fresh-branch"
}

@test "git-fresh-branch: invalid argument combination - missing branch name" {
	run git fresh-branch
	assert_failure
	assert_line -p "branch required."

	local current_branch
	current_branch=$(git branch --show-current)
	assert_equal "$current_branch" "main"
}

@test "git-fresh-branch: invalid argument combination - unknown option" {
	run git fresh-branch --invalid-flag
	assert_failure
	assert_line -p "error: unknown option"
}

@test "git-fresh-branch: invalid argument combination - too many arguments" {
	run git fresh-branch branch1 branch2
	assert_failure
	assert_line -p "error: too many arguments"
}

@test "git-fresh-branch: aborted when untracked changes prompt is declined" {
	printf '%s\n' 'untracked data' > untracked.txt
	run bash -c "echo 'n' | git fresh-branch new-branch"
	assert_success

	# Branch was not created, current branch remains main
	local current_branch
	current_branch=$(git branch --show-current)
	assert_equal "$current_branch" "main"

	# Untracked file still exists
	assert_file_exists untracked.txt
}

@test "git-fresh-branch: succeeds when untracked changes prompt is confirmed" {
	printf '%s\n' 'untracked data' > untracked.txt
	run bash -c "echo 'y' | git fresh-branch new-branch"
	assert_success

	local current_branch
	current_branch=$(git branch --show-current)
	assert_equal "$current_branch" "new-branch"

	# Untracked file was cleaned
	assert_file_not_exists untracked.txt
}
