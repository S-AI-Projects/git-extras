# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command create-branch
}

setup() {
	test_util.cd_test
	test_util.git_init

	# Commits A, B, C on main and topic
	printf '%s\n' 'Commit A' > fileA
	git add fileA
	git commit -m "Commit A"

	printf '%s\n' 'Commit B' > fileB
	git add fileB
	git commit -m "Commit B"

	git branch topic
	git checkout topic
	printf '%s\n' 'Commit C' > fileC
	git add fileC
	git commit -m "Commit C"

	git checkout main
}

@test "git-create-branch: create local branch from HEAD" {
	local main_sha
	main_sha=$(git rev-parse HEAD)

	run git create-branch my-local-branch
	assert_success

	local current
	current=$(git branch --show-current)
	assert_equal "$current" "my-local-branch"

	local branch_sha
	branch_sha=$(git rev-parse HEAD)
	assert_equal "$branch_sha" "$main_sha"
}

@test "git-create-branch: create local branch using --from start_point" {
	local topic_sha
	topic_sha=$(git rev-parse refs/heads/topic)

	run git create-branch --from topic my-topic-branch
	assert_success

	local current
	current=$(git branch --show-current)
	assert_equal "$current" "my-topic-branch"

	local branch_sha
	branch_sha=$(git rev-parse HEAD)
	assert_equal "$branch_sha" "$topic_sha"
}

@test "git-create-branch: create branch with -r remote tracking using local bare remote" {
	local bare_dir="$BATS_TEST_TMPDIR/bare_origin.git"
	git init --bare "$bare_dir"
	git remote add origin "$bare_dir"
	git push -u origin main

	run git create-branch -r remote-feature
	assert_success

	local current
	current=$(git branch --show-current)
	assert_equal "$current" "remote-feature"

	local tracking_remote
	tracking_remote=$(git config branch.remote-feature.remote)
	assert_equal "$tracking_remote" "origin"

	run git rev-parse --verify refs/remotes/origin/remote-feature
	assert_success
}

@test "git-create-branch: create branch with remote preference in local config" {
	local bare_dir="$BATS_TEST_TMPDIR/bare_pref.git"
	git init --bare "$bare_dir"
	git remote add pref-remote "$bare_dir"
	git push -u pref-remote main

	# Set local git config preference
	git config git-extras.create-branch.remote pref-remote

	run git create-branch pref-feature
	assert_success

	local current
	current=$(git branch --show-current)
	assert_equal "$current" "pref-feature"

	local tracking_remote
	tracking_remote=$(git config branch.pref-feature.remote)
	assert_equal "$tracking_remote" "pref-remote"
}

@test "git-create-branch: missing-dependency branch with unreachable/missing remote" {
	run git create-branch -r nonexistent-remote bad-branch
	assert_failure
	assert_line -p "Error connecting to remote 'nonexistent-remote'"
}

@test "git-create-branch: optional argument --help shows usage" {
	run git-create-branch --help
	assert_success
	assert_line -p "Usage: git create-branch"
}

@test "git-create-branch: optional argument -h shows usage" {
	run git-create-branch -h
	assert_success
	assert_line -p "Usage: git create-branch"
}

@test "git-create-branch: invalid argument combination - missing branch argument" {
	run git create-branch
	assert_failure
	assert_line -p "branch argument required."
}

@test "git-create-branch: missing-dependency branch when mktemp is unavailable" {
	local stub_dir="$BATS_TEST_TMPDIR/stub_bin"
	mkdir -p "$stub_dir"
	# Create a stub environment without mktemp
	run env PATH="$stub_dir:/bin:/usr/bin" bash -c "
		unalias -a
		type -t mktemp || true
	"
	# Using isolated script execution where mktemp fails
	local bare_dir="$BATS_TEST_TMPDIR/bare_mktemp.git"
	git init --bare "$bare_dir"
	git remote add origin "$bare_dir"

	# Stub mktemp to fail
	printf '#!/bin/sh\nexit 1\n' > "$stub_dir/mktemp"
	chmod +x "$stub_dir/mktemp"

	run env PATH="$stub_dir:$PATH" git create-branch -r mktemp-fail-branch
	assert_failure
	assert_line -p "mktemp required"
}

