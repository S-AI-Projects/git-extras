# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command local-commits
}

setup() {
	test_util.cd_test
	test_util.git_init

	# Setup bare remote and push initial commit
	mkdir -p "$BATS_TEST_TMPDIR/upstream.git"
	git init --bare "$BATS_TEST_TMPDIR/upstream.git"
	git remote add origin "$BATS_TEST_TMPDIR/upstream.git"

	printf '%s\n' "upstream content" > file.txt
	git add file.txt
	git commit -m "Commit A (upstream)"
	git push -u origin main
}

@test "lists unpushed local commits and rejects mutant without upstream range" {
	# Add local commits not pushed to origin/main
	printf '%s\n' "local change 1" > file1.txt
	git add file1.txt
	git commit -m "Commit B (local 1)"

	printf '%s\n' "local change 2" > file2.txt
	git add file2.txt
	git commit -m "Commit C (local 2)"

	run git local-commits
	assert_success
	assert_output -p "Commit B (local 1)"
	assert_output -p "Commit C (local 2)"
	# Verify that upstream commit A is excluded (rejects mutant running git log "$@")
	refute_output -p "Commit A (upstream)"
}

@test "forwards positional arguments and flags to git log" {
	printf '%s\n' "local change 1" > file1.txt
	git add file1.txt
	git commit -m "Commit B (local 1)"

	printf '%s\n' "local change 2" > file2.txt
	git add file2.txt
	git commit -m "Commit C (local 2)"

	# Option flag forwarding: --oneline
	run git local-commits --oneline
	assert_success
	assert_output -p "Commit B (local 1)"
	assert_output -p "Commit C (local 2)"
	refute_output -p "Author:"

	# Pathspec filtering
	run git local-commits --oneline -- file1.txt
	assert_success
	assert_output -p "Commit B (local 1)"
	refute_output -p "Commit C (local 2)"
}

@test "displays usage when invoked with -h or --help" {
	run git local-commits -h
	assert_success
	assert_output -p "Usage: git local-commits [<git log options>]"

	run git-local-commits --help
	assert_success
	assert_output -p "Usage: git local-commits [<git log options>]"
}

@test "fails cleanly when branch has no configured upstream" {
	git checkout -b untracked-branch
	printf '%s\n' "untracked change" > untracked.txt
	git add untracked.txt
	git commit -m "Untracked commit"

	run git local-commits
	assert_failure
	assert_output -p "fatal: no upstream configured for branch 'untracked-branch'"
}
