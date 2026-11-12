# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
}

setup() {
	test_util.cd_test
	git config --global --remove-section bulkworkspaces 2>/dev/null || true

	mkdir -p "$BATS_TEST_TMPDIR/ws/repo1"
	git -C "$BATS_TEST_TMPDIR/ws/repo1" init --initial-branch main
	git -C "$BATS_TEST_TMPDIR/ws/repo1" config user.name 'Name'
	git -C "$BATS_TEST_TMPDIR/ws/repo1" config user.email 'name@example.com'
	echo "a" > "$BATS_TEST_TMPDIR/ws/repo1/file.txt"
	git -C "$BATS_TEST_TMPDIR/ws/repo1" add file.txt
	git -C "$BATS_TEST_TMPDIR/ws/repo1" commit -m "A"

	mkdir -p "$BATS_TEST_TMPDIR/ws/.hidden/repo_hidden"
	git -C "$BATS_TEST_TMPDIR/ws/.hidden/repo_hidden" init --initial-branch main

	mkdir -p "$BATS_TEST_TMPDIR/external/repo_sym"
	git -C "$BATS_TEST_TMPDIR/external/repo_sym" init --initial-branch main
	ln -s "$BATS_TEST_TMPDIR/external/repo_sym" "$BATS_TEST_TMPDIR/ws/sym_repo"
}

@test "addworkspace registers and listall displays workspace" {
	run git bulk --addworkspace testws "$BATS_TEST_TMPDIR/ws"
	assert_success

	run git bulk --listall
	assert_success
	assert_output "bulkworkspaces.testws $BATS_TEST_TMPDIR/ws"
}

@test "no-follow-hidden skips repositories under hidden directories" {
	git bulk --addworkspace testws "$BATS_TEST_TMPDIR/ws"
	run git bulk --no-follow-hidden --no-follow-symlinks -w testws status --short
	assert_success
	assert_output --partial "repo1"
	refute_output --partial "repo_hidden"
}

@test "no-follow-symlinks skips symlinked repositories" {
	git bulk --addworkspace testws "$BATS_TEST_TMPDIR/ws"
	run git bulk --no-follow-symlinks -w testws status --short
	assert_success
	refute_output --partial "sym_repo"
}

@test "quiet suppresses workspace banner output" {
	git bulk --addworkspace testws "$BATS_TEST_TMPDIR/ws"
	run git bulk --quiet --no-follow-hidden --no-follow-symlinks -w testws status --short
	assert_success
	refute_output --partial "Executing bulk operation in workspace"
}

@test "unknown workspace fails with error" {
	run git bulk -w nonexistent status
	assert_failure
	assert_output --partial "unknown workspace name: nonexistent"
}
