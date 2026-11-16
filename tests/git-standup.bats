# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command standup
}

setup() {
	test_util.cd_test
	test_util.git_init
	printf '%s\n' "Initial" > init.txt
	git add .
	local ts=$(( $(date +%s) - 86400 ))
	GIT_AUTHOR_DATE="@$ts" GIT_COMMITTER_DATE="@$ts" git commit -m "Initial commit for standup"
}

@test "git-standup with invalid -d 0 fails with diagnostic message" {
	run git standup -d 0
	assert_failure
	assert_equal "$status" 1
	assert_line -p "Specify days less than one is invalid"
}

@test "git-standup with corrected -d 2 invocation succeeds" {
	run git standup -d 2
	assert_success
	assert_line -p "Initial commit for standup"
}

@test "git-standup with -a all succeeds" {
	run git standup -a all -d 2
	assert_success
	assert_line -p "Initial commit for standup"
}

@test "git-standup with -h displays usage screen" {
	run git standup -h
	assert_success
	assert_line -p "Usage:"
}
