# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	PATH="$BATS_TEST_DIRNAME/bin:$PATH"
}

setup() {
	test_util.cd_test

	test_util.git_init
	touch ./tracked
	git add ./tracked
	git commit -m 'Initial commit'

	# Local bare "remote" standing in for a real GitLab/Forgejo instance,
	# with a merge-requests ref and a pull ref pointing at the same commit.
	remote_dir="$BATS_TEST_TMPDIR/remote.git"
	git init --bare --initial-branch main "$remote_dir"
	git push "$remote_dir" HEAD:refs/merge-requests/51/head
	git push "$remote_dir" HEAD:refs/pull/51/head

	git remote add origin "$remote_dir"
}

@test "checks out a merge request by numeric id" {
	run git mr 51
	assert_success
	assert_output --partial "refs/merge-requests/51/head"

	run git rev-parse --abbrev-ref HEAD
	assert_output 'mr/51'

	run git config --get branch.mr/51.merge
	assert_output 'refs/merge-requests/51/head'
}

@test "checks out a merge request by numeric id and explicit remote" {
	run git mr 51 "$remote_dir"
	assert_success
	assert_output --partial "refs/merge-requests/51/head"

	run git rev-parse --abbrev-ref HEAD
	assert_output 'mr/51'
}

@test "checks out a GitLab merge request by URL" {
	git config --local url."$remote_dir".insteadOf "https://gitlab.com/owner/repository.git"

	run git mr "https://gitlab.com/owner/repository/merge_requests/51"
	assert_success
	assert_output --partial "refs/merge-requests/51/head"

	run git rev-parse --abbrev-ref HEAD
	assert_output 'mr/51'

	run git config --get branch.mr/51.merge
	assert_output 'refs/merge-requests/51/head'

	run git config --get branch.mr/51.remote
	assert_output 'https://gitlab.com/owner/repository.git'
}

@test "checks out a Forgejo/Codeberg pull request by URL" {
	git config --local url."$remote_dir".insteadOf "https://codeberg.org/owner/repository.git"

	run git mr "https://codeberg.org/owner/repository/pulls/51"
	assert_success
	assert_output --partial "refs/pull/51/head"

	run git rev-parse --abbrev-ref HEAD
	assert_output 'mr/51'

	run git config --get branch.mr/51.merge
	assert_output 'refs/pull/51/head'

	run git config --get branch.mr/51.remote
	assert_output 'https://codeberg.org/owner/repository.git'
}

@test "displays usage synopsis with -h or --help" {
	run git-mr -h
	assert_success
	assert_output --partial "Usage: git mr"

	run git-mr --help
	assert_success
	assert_output --partial "Usage: git mr"
}

@test "fails when argument is missing" {
	run git mr
	assert_failure 1
	assert_output --partial "mr number or URL required. See --help for usage."
}

@test "fails when merge request reference does not exist on remote" {
	run git mr 999
	assert_failure
	run git rev-parse --verify refs/heads/mr/999
	assert_failure
}

@test "cleans up local mr branches" {
	run git mr 51
	assert_success

	git checkout main
	run git rev-parse --verify refs/heads/mr/51
	assert_success

	run git mr clean
	assert_success

	run git rev-parse --verify refs/heads/mr/51
	assert_failure
}
