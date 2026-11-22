# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	PATH="$BATS_TEST_DIRNAME/../bin:$PATH"
}

setup() {
	test_util.cd_test
	test_util.git_init

	echo "commit A content" > file.txt
	git add file.txt
	git commit -m "Commit A"

	git checkout -b topic
	echo "commit B content" >> file.txt
	git commit -am "Commit B"

	echo "commit C content" >> file.txt
	git commit -am "Commit C"

	git checkout main

	remote_dir="$BATS_TEST_TMPDIR/remote.git"
	git init --bare --initial-branch main "$remote_dir"
	git push "$remote_dir" topic:refs/pull/42/head
	git push "$remote_dir" topic:refs/pull/42/merge

	git remote add origin "$remote_dir"
}

@test "git-pr: fails with diagnostic on missing pull request ref, then succeeds on corrected invocation" {
	# Before state: on main, branch pr/999 does not exist
	run git rev-parse --abbrev-ref HEAD
	assert_success
	assert_output 'main'

	# Failing invocation: non-existent PR 999 on origin
	run git pr 999 origin
	assert_failure 1
	assert_output --partial "Failed to fetch refs/pull/999/head from 'origin'. Please verify the pull request number and remote."

	# State verification after failure: still on main, no branch created
	run git rev-parse --abbrev-ref HEAD
	assert_success
	assert_output 'main'
	run git rev-parse --verify refs/heads/pr/999
	assert_failure

	# Corrected invocation: existing PR 42 on origin
	run git pr 42 origin
	assert_success

	# State verification after success: switched to pr/42, remote and merge tracking configured
	run git rev-parse --abbrev-ref HEAD
	assert_success
	assert_output 'pr/42'

	run git config --local --get branch.pr/42.remote
	assert_success
	assert_output 'origin'

	run git config --local --get branch.pr/42.merge
	assert_success
	assert_output 'refs/pull/42/head'
}

@test "git-pr: fails with diagnostic when no argument is passed" {
	run git pr
	assert_failure 1
	assert_output --partial "pr number required."
}

@test "git-pr: fails with diagnostic when invalid pattern is provided" {
	run git pr invalid_arg_spec
	assert_failure 1
	assert_output --partial "invalid_arg_spec doesn't match the pr id pattern."
}

@test "git-pr: displays help synopsis with -h or --help" {
	run git-pr -h
	assert_success
	assert_output --partial "Usage: git pr"

	run git-pr --help
	assert_success
	assert_output --partial "Usage: git pr"
}

@test "git-pr: supports --merge option to checkout merge ref" {
	run git pr --merge 42 origin
	assert_success

	run git rev-parse --abbrev-ref HEAD
	assert_success
	assert_output 'pr/42'

	run git config --local --get branch.pr/42.merge
	assert_success
	assert_output 'refs/pull/42/merge'
}

@test "git-pr: clean deletes local pr branches" {
	run git pr 42 origin
	assert_success

	git checkout main

	run git rev-parse --verify refs/heads/pr/42
	assert_success

	run git pr clean
	assert_success

	run git rev-parse --verify refs/heads/pr/42
	assert_failure
}
