# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
}

setup() {
	test_util.cd_test

	test_util.git_init
	printf '%s\n' 'hello' > tracked.txt
	git add tracked.txt
	git commit -m 'Initial commit'

	# never created: neither dry-run nor declined interactive should touch it
	git remote add fake "$BATS_TEST_TMPDIR/never-created"

	printf '%s\n' 'world' >> tracked.txt
}

@test "dry-run previews the sync without changing anything" {
	run git scp -n fake
	assert_success
	assert_line -p 'tracked.txt'
	assert_line -p 'DRY RUN'

	run git status --short
	assert_line -p 'M tracked.txt'

	run test -e "$BATS_TEST_TMPDIR/never-created"
	assert_failure
}

@test "interactive mode aborts without syncing when declined" {
	run bash -c 'echo n | git scp -i fake'
	assert_success
	assert_line -p 'Aborted, nothing synced.'

	run git status --short
	assert_line -p 'M tracked.txt'

	run test -e "$BATS_TEST_TMPDIR/never-created"
	assert_failure
}

@test "documented usage example: copy unstaged changes with verbose output and state verification" {
	local staging_dir="$BATS_TEST_TMPDIR/staging"
	git remote add staging "$staging_dir"

	run git scp --verbose staging
	assert_success
	assert_line -p 'diff --git a/tracked.txt b/tracked.txt'
	assert_line -p '+world'
	assert_line -p "Pushing to staging ($staging_dir)"
	assert_line -p 'tracked.txt'

	# State verification: target exists and contains both lines
	assert [ -f "$staging_dir/tracked.txt" ]
	assert_equal "$(cat "$staging_dir/tracked.txt")" "$(cat tracked.txt)"
}

@test "git-scp: fails when remote does not exist in git config" {
	run git scp nonexistent_remote
	assert_failure
	assert_line -p "Remote nonexistent_remote does not exist in your git config"
}

@test "git-scp: sanitization config get-all executes without error" {
	git config --add extras.scp.sanitize dos2unix
	run git config --get-all extras.scp.sanitize
	assert_success
	assert_output "dos2unix"
}
