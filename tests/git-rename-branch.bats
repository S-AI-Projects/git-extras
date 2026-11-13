# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command rename-branch
}

setup() {
	test_util.cd_test
	test_util.git_init

	printf '%s\n' 'commit A' > fileA
	git add fileA
	git commit -m "commit A"

	printf '%s\n' 'commit B' > fileB
	git add fileB
	git commit -m "commit B"

	git branch topic
}

@test "git-rename-branch: rename current branch without remote (1 argument)" {
	git checkout topic
	local main_sha
	main_sha=$(git rev-parse refs/heads/main)

	run git rename-branch topic-renamed
	assert_success

	# Current branch should be topic-renamed
	local current_branch
	current_branch=$(git branch --show-current)
	assert_equal "$current_branch" "topic-renamed"

	# Old branch ref removed, new branch ref exists
	run git rev-parse --verify refs/heads/topic
	assert_failure

	run git rev-parse --verify refs/heads/topic-renamed
	assert_success

	# Unrelated state unchanged: main branch ref is intact
	local main_after
	main_after=$(git rev-parse refs/heads/main)
	assert_equal "$main_sha" "$main_after"
}

@test "git-rename-branch: rename another branch without checkout (2 arguments)" {
	local main_sha
	main_sha=$(git rev-parse refs/heads/main)
	local topic_sha
	topic_sha=$(git rev-parse refs/heads/topic)

	run git rename-branch topic topic-v2
	assert_success

	# Current branch still main
	local current_branch
	current_branch=$(git branch --show-current)
	assert_equal "$current_branch" "main"

	# topic removed, topic-v2 created pointing to topic_sha
	run git rev-parse --verify refs/heads/topic
	assert_failure

	local new_sha
	new_sha=$(git rev-parse refs/heads/topic-v2)
	assert_equal "$new_sha" "$topic_sha"

	# Unrelated state unchanged: main branch SHA is intact
	local main_after
	main_after=$(git rev-parse refs/heads/main)
	assert_equal "$main_sha" "$main_after"
}

@test "git-rename-branch: rename branch with remote upstream tracking" {
	# Create a local bare remote repository
	local bare_remote="$BATS_TEST_TMPDIR/bare_remote.git"
	git init --bare "$bare_remote"
	git remote add origin "$bare_remote"

	# Push main to origin
	git push -u origin main
	local main_remote_sha
	main_remote_sha=$(git rev-parse refs/remotes/origin/main)

	# Checkout topic and push to origin with tracking
	git checkout topic
	git push -u origin topic
	local topic_sha
	topic_sha=$(git rev-parse refs/heads/topic)

	# Rename topic to feature-branch
	run git rename-branch feature-branch
	assert_success

	# Current branch is feature-branch
	local current_branch
	current_branch=$(git branch --show-current)
	assert_equal "$current_branch" "feature-branch"

	# Local old branch gone, new exists
	run git rev-parse --verify refs/heads/topic
	assert_failure
	local feature_sha
	feature_sha=$(git rev-parse refs/heads/feature-branch)
	assert_equal "$feature_sha" "$topic_sha"

	# Remote old branch gone, remote new branch exists
	run git rev-parse --verify refs/remotes/origin/topic
	assert_failure
	local remote_feature_sha
	remote_feature_sha=$(git rev-parse refs/remotes/origin/feature-branch)
	assert_equal "$remote_feature_sha" "$topic_sha"

	# Upstream tracking updated
	local tracking_remote
	tracking_remote=$(git config branch.feature-branch.remote)
	assert_equal "$tracking_remote" "origin"
	local tracking_merge
	tracking_merge=$(git config branch.feature-branch.merge)
	assert_equal "$tracking_merge" "refs/heads/feature-branch"

	# Unrelated state: main ref and origin/main ref remain completely unchanged
	local main_remote_after
	main_remote_after=$(git rev-parse refs/remotes/origin/main)
	assert_equal "$main_remote_sha" "$main_remote_after"
}

@test "git-rename-branch: optional argument --help shows usage" {
	run git-rename-branch --help
	assert_success
	assert_line -p "Usage: git rename-branch"

	local current_branch
	current_branch=$(git branch --show-current)
	assert_equal "$current_branch" "main"
}

@test "git-rename-branch: optional argument -h shows usage" {
	run git-rename-branch -h
	assert_success
	assert_line -p "Usage: git rename-branch"
}

@test "git-rename-branch: invalid argument combination - missing branch name" {
	run git rename-branch
	assert_failure
	assert_line -p "new branch name required."

	# All branches intact
	run git rev-parse --verify refs/heads/main
	assert_success
	run git rev-parse --verify refs/heads/topic
	assert_success
}

@test "git-rename-branch: invalid argument combination - unknown option" {
	run git rename-branch --invalid-flag
	assert_failure
	assert_line -p "error: unknown option"
}

@test "git-rename-branch: invalid argument combination - too many arguments" {
	run git rename-branch b1 b2 b3
	assert_failure
	assert_line -p "error: too many arguments"
}

@test "git-rename-branch: edge-state - renaming non-existent branch fails" {
	run git rename-branch non-existent-branch new-branch
	assert_failure

	# Unrelated branches intact
	run git rev-parse --verify refs/heads/main
	assert_success
	run git rev-parse --verify refs/heads/topic
	assert_success
}

@test "git-rename-branch: edge-state - renaming to existing branch name fails" {
	run git rename-branch topic main
	assert_failure

	# Existing branches intact
	run git rev-parse --verify refs/heads/main
	assert_success
	run git rev-parse --verify refs/heads/topic
	assert_success
}

