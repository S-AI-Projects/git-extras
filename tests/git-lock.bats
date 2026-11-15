#!/usr/bin/env bats

load test_util.sh

setup_file() {
	test_util.setup_file
	test_util.install_command lock
}

setup() {
	test_util.cd_test
	test_util.git_init
}

@test "git-lock marks a tracked file with skip-worktree" {
	echo "initial" > config.txt
	git add config.txt
	git commit -m "add config"

	run git lock config.txt
	assert_success

	run git ls-files -v config.txt
	assert_output "S config.txt"

	echo "local-only-change" > config.txt
	run git status --short
	assert_output ""
}

@test "git-lock fails when filename is missing" {
	run git lock
	assert_failure
	assert_output "filename required."
}

@test "git-lock fails on an untracked file" {
	echo "untracked" > untracked.txt

	run git lock untracked.txt
	assert_failure
}
