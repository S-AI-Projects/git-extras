# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command sync
}

setup() {
	test_util.cd_test
	test_util.git_init

	# Setup local bare remote origin
	local bare_dir="$BATS_TEST_TMPDIR/bare_origin.git"
	git init --bare "$bare_dir"
	git remote add origin "$bare_dir"

	# Commit A and Commit B
	printf '%s\n' 'Commit A' > fileA.txt
	git add fileA.txt
	git commit -m "Commit A"

	printf '%s\n' 'Commit B' > fileB.txt
	git add fileB.txt
	git commit -m "Commit B"

	# Push main to origin and set upstream tracking
	git push -u origin main
}

@test "git-sync: sync with upstream using --force (hard reset and clean untracked)" {
	# Create a diverged local commit and an untracked file
	printf '%s\n' 'Local commit' > file_local.txt
	git add file_local.txt
	git commit -m "Local commit"
	printf '%s\n' 'Untracked data' > untracked.txt

	local upstream_sha
	upstream_sha=$(git rev-parse refs/remotes/origin/main)

	run git sync --force
	assert_success

	# Verify HEAD was reset to upstream
	local current_sha
	current_sha=$(git rev-parse HEAD)
	assert_equal "$current_sha" "$upstream_sha"

	# Verify untracked file was cleaned
	assert_file_not_exists untracked.txt
	assert_file_not_exists file_local.txt
}

@test "git-sync: sync with --soft preserves untracked files" {
	printf '%s\n' 'Local commit' > file_local.txt
	git add file_local.txt
	git commit -m "Local commit"
	printf '%s\n' 'Keep untracked data' > untracked.txt

	local upstream_sha
	upstream_sha=$(git rev-parse refs/remotes/origin/main)

	run git sync --soft --force
	assert_success

	# HEAD was reset
	local current_sha
	current_sha=$(git rev-parse HEAD)
	assert_equal "$current_sha" "$upstream_sha"

	# Untracked file is preserved
	assert_file_exists untracked.txt
}

@test "git-sync: sync with explicit remote and branch arguments" {
	printf '%s\n' 'Local commit' > file_local.txt
	git add file_local.txt
	git commit -m "Local commit"

	local remote_sha
	remote_sha=$(git rev-parse refs/remotes/origin/main)

	run git sync -f origin main
	assert_success

	local current_sha
	current_sha=$(git rev-parse HEAD)
	assert_equal "$current_sha" "$remote_sha"
}

@test "git-sync: interactive confirmation prompt accepted" {
	printf '%s\n' 'Local unpushed commit' > file_local.txt
	git add file_local.txt
	git commit -m "Local unpushed commit"

	local upstream_sha
	upstream_sha=$(git rev-parse refs/remotes/origin/main)

	run bash -c "echo 'y' | git sync origin main"
	assert_success

	local current_sha
	current_sha=$(git rev-parse HEAD)
	assert_equal "$current_sha" "$upstream_sha"
}

@test "git-sync: interactive confirmation prompt declined cancels sync" {
	printf '%s\n' 'Local unpushed commit' > file_local.txt
	git add file_local.txt
	git commit -m "Local unpushed commit"

	local local_sha
	local_sha=$(git rev-parse HEAD)

	run bash -c "echo 'n' | git sync origin main"
	assert_success
	assert_line -p "Canceled."

	# State remains unchanged
	local current_sha
	current_sha=$(git rev-parse HEAD)
	assert_equal "$current_sha" "$local_sha"
	assert_file_exists file_local.txt
}

@test "git-sync: optional argument --help shows usage" {
	run git-sync --help
	assert_success
	assert_line -p "Usage:"
	assert_line -p "git sync"
}

@test "git-sync: optional argument -h shows usage" {
	run git-sync -h
	assert_success
	assert_line -p "Usage:"
}

@test "git-sync: error when local branch has no upstream information" {
	# Create a branch without upstream tracking
	git checkout -b orphan-branch
	run git sync -f
	assert_failure
	assert_line -p "There is no upstream information of local branch."
}

@test "git-sync: error when too few arguments supplied" {
	run git sync origin
	assert_failure
	assert_line -p "Error: too few arguments."
}

@test "git-sync: error when too many arguments supplied" {
	run git sync origin main extra-arg
	assert_failure
	assert_line -p "Error: too many arguments."
}

