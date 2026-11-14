# shellcheck shell=bash

load test_util.sh

setup_file() {
	test_util.setup_file
	test_util.install_command gh-pages
}

setup() {
	test_util.cd_test

	# Create isolated bare remote directory simulating GitHub host
	mkdir -p "$BATS_TEST_TMPDIR/remotes/testuser"
	git init --bare "$BATS_TEST_TMPDIR/remotes/testuser/testrepo.git" >/dev/null

	# Create isolated working repository with commits A, B, C and branches main & topic
	mkdir -p "$BATS_TEST_TMPDIR/workrepo"
	cd "$BATS_TEST_TMPDIR/workrepo"
	test_util.git_init

	echo "A" > file.txt
	git add file.txt
	git commit -m "A" >/dev/null

	echo "B" >> file.txt
	git add file.txt
	git commit -m "B" >/dev/null

	git checkout -b topic >/dev/null 2>&1
	echo "C" >> file.txt
	git add file.txt
	git commit -m "C" >/dev/null

	git checkout main >/dev/null 2>&1
}

@test "git-gh-pages creates gh-pages branch and pushes to isolated bare remote" {
	export GIT_GH_PAGES_REMOTE_BASE="$BATS_TEST_TMPDIR/remotes"

	run git gh-pages testuser testrepo
	assert_success
	assert_output --partial "setting up gh-pages"
	assert_output --partial "Complete"

	# Verify local branch, index.html, and bare remote state
	run git branch --show-current
	assert_output "gh-pages"

	[ -f index.html ]
	run cat index.html
	assert_output "My Page"

	run git --git-dir="$BATS_TEST_TMPDIR/remotes/testuser/testrepo.git" rev-parse --verify refs/heads/gh-pages
	assert_success
}

@test "git-gh-pages fails cleanly when required arguments or remote target are missing" {
	# Case 1: Empty interactive input (missing username/repository)
	run bash -c 'printf "\n\n" | git gh-pages'
	assert_failure
	assert_output --partial "Error: GitHub username and repository name are required."

	# Case 2: Missing target bare repository on remote base
	export GIT_GH_PAGES_REMOTE_BASE="$BATS_TEST_TMPDIR/remotes"
	run git gh-pages testuser nonexistent-repo
	assert_failure
}
