# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command get
}

setup() {
	test_util.cd_test
	test_util.git_init

	# Create a source bare repository to clone from
	local source_repo="$BATS_TEST_TMPDIR/source.git"
	git init --bare --initial-branch main "$source_repo"

	# Populate source repo
	local work_dir="$BATS_TEST_TMPDIR/work"
	git clone "$source_repo" "$work_dir"
	cd "$work_dir"
	printf '%s\n' 'initial content' > file.txt
	git add file.txt
	git commit -m "Commit A"
	git push origin main

	# Add topic branch
	git switch -c topic
	printf '%s\n' 'topic content' > topic.txt
	git add topic.txt
	git commit -m "Commit B"
	git push origin topic

	cd "$BATS_TEST_TMPDIR"
	rm -rf "$work_dir"
}

@test "git-get: displays usage when invoked with no arguments" {
	run git get
	assert_success
	assert_line -p "usage: git-get <url>"
	assert_line -p "Clone a repository in a particular directory."
}

@test "git-get: displays usage with -h and --help" {
	run git get -h
	assert_success
	assert_line -p "usage: git-get <url>"

	run git-get --help
	assert_success
	assert_line -p "usage: git-get <url>"
}

@test "git-get: fails when git-extras.get.clone-path is not set" {
	run git get "$BATS_TEST_TMPDIR/source.git"
	assert_failure
	assert_line -p "Git configuration key 'git-extras.get.clone-path' must be set to a directory to clone under"
}

@test "git-get: clones repository into configured clone-path" {
	local target_dir="$BATS_TEST_TMPDIR/clones"
	git config --global git-extras.get.clone-path "$target_dir"

	run git get "$BATS_TEST_TMPDIR/source.git"
	assert_success

	assert [ -d "$target_dir/source" ]
	assert [ -f "$target_dir/source/file.txt" ]
	assert_equal "$(cd "$target_dir/source" && git branch --show-current)" "main"
}

@test "git-get: strips trailing slash and .git extension" {
	local target_dir="$BATS_TEST_TMPDIR/clones"
	git config --global git-extras.get.clone-path "$target_dir"

	run git get "$BATS_TEST_TMPDIR/source.git/"
	assert_success

	assert [ -d "$target_dir/source" ]
}

@test "git-get: forwards additional options to git clone" {
	local target_dir="$BATS_TEST_TMPDIR/clones"
	git config --global git-extras.get.clone-path "$target_dir"

	run git get "$BATS_TEST_TMPDIR/source.git" --branch topic
	assert_success

	assert [ -d "$target_dir/source" ]
	assert_equal "$(cd "$target_dir/source" && git branch --show-current)" "topic"
	assert [ -f "$target_dir/source/topic.txt" ]
}
