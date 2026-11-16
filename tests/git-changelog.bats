# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command changelog
}

setup() {
	test_util.cd_test
	test_util.git_init
	export GIT_EDITOR="true"
	printf '%s\n' "Initial" > init.txt
	git add .
	git commit -m 'initial commit'
}

@test "excludes commits matching a pathspec" {
	mkdir src docs
	touch src/keep
	git add .
	git commit -m 'keep commit'
	touch docs/exclude
	git add .
	git commit -m 'exclude commit'

	run git changelog --all --list --stdout --exclude docs
	assert_success
	assert_output '  * keep commit
  * initial commit'
}

@test "minimum accepted argument list succeeds with default stdout output" {
	printf '%s\n' 'feature' > feat.txt
	git add .
	git commit -m 'feat: add feature'

	run git changelog --list --stdout
	assert_success
	assert_line -p 'feat: add feature'
	assert_line -p 'initial commit'
}

@test "optional arguments --all and --prune-old succeed" {
	printf '%s\n' 'commit 2' > file2.txt
	git add .
	git commit -m 'second commit'
	git tag -a v1.0.0 -m 'version 1.0.0'

	printf '%s\n' 'commit 3' > file3.txt
	git add .
	git commit -m 'third commit'

	# With --all and --prune-old to a custom file
	run git changelog --all --prune-old --list MyHistory.md
	assert_success
	[ -f MyHistory.md ]
	run cat MyHistory.md
	assert_line -p 'third commit'
	assert_line -p 'second commit'
	assert_line -p 'initial commit'
}

@test "fails when mutually exclusive --start-tag and --start-commit are combined" {
	git tag -a v0.1.0 -m 'v0.1.0'
	local commit_sha
	commit_sha="$(git rev-parse HEAD)"

	run git changelog --start-tag v0.1.0 --start-commit "$commit_sha"
	assert_failure
	assert_equal "$status" 1
	assert_line -p '--start-tag could not use with --start-commit!'
}

@test "fails when start-tag does not exist" {
	run git changelog --start-tag does-not-exist
	assert_failure
	assert_equal "$status" 1
	assert_line -p 'Specified start-tag does not exist!'
}

@test "fails when --exclude is passed without a pathspec" {
	run git changelog --exclude
	assert_failure
	assert_equal "$status" 1
	assert_line -p '--exclude requires a pathspec'
}
