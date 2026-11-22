# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command unlock
}

setup() {
	test_util.cd_test
	test_util.git_init

	printf '%s\n' 'content A' > A.txt
	printf '%s\n' 'content B' > B.txt
	git add A.txt B.txt
	git commit -m "initial commit"

	git update-index --skip-worktree A.txt
}

@test "git-unlock: successfully unlocks a locked file" {
	run git ls-files -v A.txt
	assert_output "S A.txt"

	run git unlock A.txt
	assert_success
	assert_output ""

	run git ls-files -v A.txt
	assert_output "H A.txt"
}

@test "git-unlock: unlocking an already unlocked file succeeds without changing state" {
	run git ls-files -v B.txt
	assert_output "H B.txt"

	run git unlock B.txt
	assert_success
	assert_output ""

	run git ls-files -v B.txt
	assert_output "H B.txt"
}

@test "git-unlock: fails when filename argument is omitted" {
	run git unlock
	assert_failure
	assert_output "filename required."

	run git ls-files -v A.txt
	assert_output "S A.txt"
}

@test "git-unlock: fails when filename argument is empty" {
	run git unlock ""
	assert_failure
	assert_output "filename required."

	run git ls-files -v A.txt
	assert_output "S A.txt"
}

@test "git-unlock: fails when file is untracked or does not exist" {
	run git unlock nonexistent.txt
	assert_failure

	run git ls-files -v A.txt
	assert_output "S A.txt"
}
