# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command delete-tag
}

setup() {
	test_util.cd_test
	test_util.git_init

	# Setup bare remote and initial commit
	mkdir -p "$BATS_TEST_TMPDIR/upstream.git"
	git init --bare "$BATS_TEST_TMPDIR/upstream.git"
	git remote add origin "$BATS_TEST_TMPDIR/upstream.git"

	printf '%s\n' "initial commit" > file.txt
	git add file.txt
	git commit -m "Initial commit"
	git push -u origin main
}

@test "fails when invoked without arguments and provides diagnostic hint" {
	run git delete-tag
	assert_failure
	assert_output -p "Error: Tag name required"
	assert_output -p "Hint: Use 'git tag -l'"
}

@test "fails when tag does not exist and provides troubleshooting hint" {
	run git delete-tag nonexistent-tag
	assert_failure
	assert_output -p "Hint: Tag deletion failed. Run 'git tag -l'"
}

@test "succeeds with corrected invocation deleting single tag locally and remotely" {
	git tag v1.0.0
	git push origin v1.0.0

	run git tag -l
	assert_output -p "v1.0.0"

	# Corrected invocation succeeds
	run git delete-tag v1.0.0
	assert_success
	assert_output -p "Deleted tag 'v1.0.0'"

	# Verify local deletion
	run git tag -l
	refute_output -p "v1.0.0"

	# Verify remote deletion
	run git ls-remote --tags origin refs/tags/v1.0.0
	assert_success
	refute_output -p "refs/tags/v1.0.0"
}

@test "succeeds deleting multiple tags locally and remotely" {
	git tag v1.0.1
	git tag v1.0.2
	git push origin v1.0.1 v1.0.2

	run git delete-tag v1.0.1 v1.0.2
	assert_success
	assert_output -p "Deleted tag 'v1.0.1'"
	assert_output -p "Deleted tag 'v1.0.2'"

	run git tag -l
	refute_output -p "v1.0.1"
	refute_output -p "v1.0.2"
}

@test "displays usage when invoked with -h or --help" {
	run git delete-tag -h
	assert_success
	assert_output -p "Usage: git delete-tag <tagname>..."

	run git-delete-tag --help
	assert_success
	assert_output -p "Usage: git delete-tag <tagname>..."
}
