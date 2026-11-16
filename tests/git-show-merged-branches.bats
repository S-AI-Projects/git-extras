# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command show-merged-branches
}

setup() {
	test_util.cd_test
	test_util.git_init
	printf '%s\n' "Initial" > init.txt
	git add .
	git commit -m "Initial commit"

	git branch feature-merged
	git branch feature-unmerged
	git checkout feature-unmerged
	printf '%s\n' "unmerged" > unmerged.txt
	git add .
	git commit -m "Unmerged commit"
	git checkout main
}

@test "git-show-merged-branches lists merged branches excluding default branch" {
	run git show-merged-branches
	assert_success
	assert_output "feature-merged"
}

@test "git-show-merged-branches respects local git-extras.default-branch configuration" {
	git config git-extras.default-branch feature-merged
	run git show-merged-branches
	assert_success
	# Since feature-merged is configured as default, it should be excluded
	assert_output ""
}

@test "git-show-merged-branches accepts an explicit commit target" {
	run git show-merged-branches main
	assert_success
	assert_output "feature-merged"
}

@test "git-show-merged-branches fails when grep dependency is missing" {
	local stub_dir="$BATS_TEST_TMPDIR/stub_bin"
	mkdir -p "$stub_dir"
	# Create a restricted PATH without grep
	local safe_path
	safe_path="$(dirname "$(command -v git)")"

	run env PATH="$BATS_FILE_TMPDIR/bin:$safe_path" /bin/bash -c '
		# override command -v grep to fail
		command() {
			if [ "$1" = "-v" ] && [ "$2" = "grep" ]; then
				return 1
			fi
			builtin command "$@"
		}
		export -f command
		git show-merged-branches
	'
	assert_failure
	assert_line -p "grep required."
}
