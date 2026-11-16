# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command delete-branch
}

setup() {
	test_util.cd_test
	test_util.git_init
	git commit --allow-empty -m "Initial commit"
}

@test "git-delete-branch without arguments fails and displays error" {
	run git delete-branch
	assert_failure
	assert_equal "$status" 1
	assert_line -p "branch required."
}

@test "git-delete-branch with empty argument fails and displays error" {
	run git delete-branch ""
	assert_failure
	assert_equal "$status" 1
	assert_line -p "branch required."
}

@test "git-delete-branch deletes a local branch" {
	git branch topic
	run git branch --list
	assert_line -p "topic"

	run git delete-branch topic
	assert_success

	run git branch --list
	refute_line -p "topic"
	assert_line -p "main"
}

@test "git-delete-branch deletes multiple local branches" {
	git branch topic1
	git branch topic2

	run git delete-branch topic1 topic2
	assert_success

	run git branch --list
	refute_line -p "topic1"
	refute_line -p "topic2"
	assert_line -p "main"
}

@test "git-delete-branch deletes local branch and remote tracking branch" {
	local remote_repo="$BATS_TEST_TMPDIR/remote.git"
	git init --bare "$remote_repo"
	git remote add origin "$remote_repo"
	git push origin main

	git checkout -b topic-remote
	git commit --allow-empty -m "Commit on topic-remote"
	git push -u origin topic-remote
	git checkout main

	run git branch -r
	assert_line -p "origin/topic-remote"

	run git delete-branch topic-remote
	assert_success

	run git branch --list
	refute_line -p "topic-remote"

	run git branch -r
	refute_line -p "origin/topic-remote"

	run git ls-remote --heads origin topic-remote
	assert_success
	assert_output ""
}
