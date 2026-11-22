# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command release
}

setup() {
	test_util.cd_test
	test_util.git_init

	# Set up a local bare remote as origin
	bare_remote="$BATS_TEST_TMPDIR/bare.git"
	git init --bare --initial-branch main "$bare_remote"
	git remote add origin "$bare_remote"

	printf '%s\n' 'Commit A' > fileA.txt
	git add fileA.txt
	git commit -m "Commit A"

	printf '%s\n' 'Commit B' > fileB.txt
	git add fileB.txt
	git commit -m "Commit B"

	git switch -c topic
	printf '%s\n' 'Commit C' > fileC.txt
	git add fileC.txt
	git commit -m "Commit C"

	git switch main
	git push -u origin main
	git push origin topic
}

@test "git-release: minimum accepted argument list releases with tagname" {
	local before_head
	before_head=$(git rev-parse HEAD)

	run git release 0.1.0
	assert_success
	assert_line -p "... releasing 0.1.0"
	assert_line -p "... complete"

	# Release commit was created with default message
	run git log -1 --format=%s
	assert_output "Release 0.1.0"

	# Annotated tag was created
	run git tag -l 0.1.0
	assert_output "0.1.0"

	# Tag was pushed to origin
	run git ls-remote origin refs/tags/0.1.0
	assert_line -p "refs/tags/0.1.0"
}

@test "git-release: optional argument -m sets custom commit message" {
	run git release 0.2.0 -m "Custom release 0.2.0 message"
	assert_success
	assert_line -p "... releasing 0.2.0"
	assert_line -p "... complete"

	run git log -1 --format=%s
	assert_output "Custom release 0.2.0 message"

	run git tag -l 0.2.0
	assert_output "0.2.0"
}

@test "git-release: optional argument --no-empty-commit skips empty commit" {
	local before_head
	before_head=$(git rev-parse HEAD)

	run git release 0.3.0 --no-empty-commit
	assert_success
	assert_line -p "... releasing 0.3.0"
	assert_line -p "... complete"

	# No extra empty commit created
	run git rev-parse HEAD
	assert_output "$before_head"

	run git tag -l 0.3.0
	assert_output "0.3.0"
}

@test "git-release: documented invalid combination -s and -u is rejected" {
	local before_head
	before_head=$(git rev-parse HEAD)

	run git release -s -u mykey 0.4.0
	assert_failure
	assert_line -p "Please use '-s' OR '-u'"

	# Repository state unchanged
	run git rev-parse HEAD
	assert_output "$before_head"

	run git tag -l 0.4.0
	assert_output ""
}

@test "git-release: missing tag argument is rejected" {
	local before_head
	before_head=$(git rev-parse HEAD)

	run git release
	assert_failure
	assert_line -p "tag required"

	run git rev-parse HEAD
	assert_output "$before_head"
}
