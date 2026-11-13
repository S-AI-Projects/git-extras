# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command undo
}

setup() {
	test_util.cd_test
}

_create_repo_with_commits() {
	test_util.git_init

	printf '%s\n' 'content A' > fileA
	git add fileA
	git commit -m "commit A"

	printf '%s\n' 'content B' > fileB
	git add fileB
	git commit -m "commit B"

	printf '%s\n' 'content C' > fileC
	git add fileC
	git commit -m "commit C"
}

@test "undo removes latest commit with default options" {
	_create_repo_with_commits

	run git undo
	assert_success
	assert_output ""

	# Repository state assertions
	local head_msg
	head_msg=$(git log -1 --pretty=%B)
	assert_equal "$head_msg" "commit B"

	local commit_count
	commit_count=$(git rev-list --count HEAD)
	assert_equal "$commit_count" "2"

	# Changes from commit C remain staged
	run git diff --cached --name-only
	assert_success
	assert_line "fileC"
}

@test "undo multiple commits with positional count" {
	_create_repo_with_commits

	run git undo 2
	assert_success
	assert_output ""

	# Repository state assertions
	local head_msg
	head_msg=$(git log -1 --pretty=%B)
	assert_equal "$head_msg" "commit A"

	local commit_count
	commit_count=$(git rev-list --count HEAD)
	assert_equal "$commit_count" "1"
}

@test "undo with --soft leaves changes unstaged" {
	_create_repo_with_commits

	run git undo --soft
	assert_success
	assert_output ""

	# Repository state assertions
	local head_msg
	head_msg=$(git log -1 --pretty=%B)
	assert_equal "$head_msg" "commit B"

	# Staging area is reset, changes are unstaged
	run git diff --cached --name-only
	assert_success
	assert_output ""

	run git status --porcelain
	assert_success
	assert_line -p "fileC"
}

@test "undo with -s leaves changes unstaged" {
	_create_repo_with_commits

	run git undo -s
	assert_success
	assert_output ""

	# Repository state assertions
	local head_msg
	head_msg=$(git log -1 --pretty=%B)
	assert_equal "$head_msg" "commit B"

	run git diff --cached --name-only
	assert_success
	assert_output ""
}

@test "undo with --hard removes changes completely" {
	_create_repo_with_commits

	run git undo --hard
	assert_success
	assert_line -p "HEAD is now at"

	# Repository state assertions
	local head_msg
	head_msg=$(git log -1 --pretty=%B)
	assert_equal "$head_msg" "commit B"

	assert_file_not_exists fileC

	run git status --porcelain
	assert_success
	assert_output ""
}

@test "undo with --count option" {
	_create_repo_with_commits

	run git undo --count 2
	assert_success
	assert_output ""

	# Repository state assertions
	local head_msg
	head_msg=$(git log -1 --pretty=%B)
	assert_equal "$head_msg" "commit A"

	local commit_count
	commit_count=$(git rev-list --count HEAD)
	assert_equal "$commit_count" "1"
}

@test "undo with -c option" {
	_create_repo_with_commits

	run git undo -c 2
	assert_success
	assert_output ""

	# Repository state assertions
	local head_msg
	head_msg=$(git log -1 --pretty=%B)
	assert_equal "$head_msg" "commit A"
}

@test "undo with --count=n option" {
	_create_repo_with_commits

	run git undo --count=2
	assert_success
	assert_output ""

	# Repository state assertions
	local head_msg
	head_msg=$(git log -1 --pretty=%B)
	assert_equal "$head_msg" "commit A"
}

@test "undo with --help shows usage" {
	_create_repo_with_commits

	run git-undo --help
	assert_success
	assert_line -p "Usage: git undo"
	assert_line -p "--soft"
	assert_line -p "--hard"
	assert_line -p "--count"
	assert_line -p "--help"
}

@test "undo with help argument shows usage" {
	_create_repo_with_commits

	run git undo help
	assert_success
	assert_line -p "Usage: git undo"
	assert_line -p "--soft"
	assert_line -p "--hard"
	assert_line -p "--count"
	assert_line -p "--help"

	# Repository state is unchanged
	local head_msg
	head_msg=$(git log -1 --pretty=%B)
	assert_equal "$head_msg" "commit C"
}

@test "undo fails in repository without commits" {
	test_util.git_init

	run git undo
	assert_failure
	assert_line -p "Not git commit found!"

	# Repository has no commits
	run git rev-parse --verify HEAD
	assert_failure
}

@test "undo fails outside of a git repository" {
	run git undo
	assert_failure
	assert_line -p "Not a git repo!"
}

@test "undo fails when count exceeds commit count" {
	_create_repo_with_commits

	run git undo 5
	assert_failure
	assert_output "Only 3 commits, cannot undo 5"

	# Repository state is unchanged
	local head_msg
	head_msg=$(git log -1 --pretty=%B)
	assert_equal "$head_msg" "commit C"

	local commit_count
	commit_count=$(git rev-list --count HEAD)
	assert_equal "$commit_count" "3"
}

@test "hard undo fails when trying to undo all commits" {
	_create_repo_with_commits

	run git undo --hard 3
	assert_failure
	assert_output "Cannot hard undo all commits"

	# Repository state is unchanged
	local head_msg
	head_msg=$(git log -1 --pretty=%B)
	assert_equal "$head_msg" "commit C"

	local commit_count
	commit_count=$(git rev-list --count HEAD)
	assert_equal "$commit_count" "3"
}

@test "undo rejects zero count" {
	_create_repo_with_commits

	run git undo 0
	assert_failure
	assert_output "Invalid undo count: 0"

	# Repository state is unchanged
	local head_msg
	head_msg=$(git log -1 --pretty=%B)
	assert_equal "$head_msg" "commit C"
}

@test "undo rejects invalid parameter" {
	_create_repo_with_commits

	run git undo --invalid-flag
	assert_failure
	assert_output "Invalid parameter: --invalid-flag"

	# Repository state is unchanged
	local head_msg
	head_msg=$(git log -1 --pretty=%B)
	assert_equal "$head_msg" "commit C"
}
