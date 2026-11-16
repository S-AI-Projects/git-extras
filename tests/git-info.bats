# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command info
}

setup() {
	test_util.cd_test
	test_util.git_init
	printf '%s\n' "Initial" > README.md
	git add .
	git commit -m 'Initial commit'
	git branch topic
}

@test "git-info shows repo details and configuration by default" {
	run git info
	assert_success
	assert_line -p "Remote URLs:"
	assert_line -p "Remote Branches:"
	assert_line -p "Local Branches:"
	assert_line -p "Most Recent Commit:"
	assert_line -p "Configuration (.git/config):"
	assert_line -p "Initial commit"
	assert_line -p "topic"
}

@test "git-info --no-config suppresses configuration section" {
	run git info --no-config
	assert_success
	assert_line -p "Remote URLs:"
	assert_line -p "Local Branches:"
	assert_line -p "Most Recent Commit:"
	refute_line -p "Configuration (.git/config):"
}

@test "git-info --color and -c flags work" {
	run git info --color
	assert_success
	assert_line -p "Local Branches:"

	run git info -c
	assert_success
	assert_line -p "Local Branches:"
}

@test "git-info preserves repo state and unrelated files" {
	local head_before
	head_before="$(git rev-parse HEAD)"
	local status_before
	status_before="$(git status --porcelain)"

	run git info
	assert_success

	local head_after
	head_after="$(git rev-parse HEAD)"
	local status_after
	status_after="$(git status --porcelain)"

	assert_equal "$head_before" "$head_after"
	assert_equal "$status_before" "$status_after"
}

@test "git-info fails outside a git repository" {
	local non_repo="$BATS_FILE_TMPDIR/non_repo_dir"
	mkdir -p "$non_repo"
	cd "$non_repo"

	run git info
	assert_failure
}
