# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command unlock
	test_util.install_command lock
}

setup() {
	test_util.cd_test
	test_util.git_init

	# Create files with spaces and wildcard characters, plus unrelated files
	printf '%s\n' 'spaces content' > "file with spaces.txt"
	printf '%s\n' 'wildcard star content' > "file*with*star.txt"
	printf '%s\n' 'unrelated candidate content' > "fileXwithYstar.txt"
	printf '%s\n' 'another space content' > "another space file.txt"
	printf '%s\n' 'regular content' > "regular.txt"

	git add -A
	git commit -m "initial commit with spaces and wildcard files"

	# Lock the files using git update-index --skip-worktree
	git update-index --skip-worktree "file with spaces.txt"
	git update-index --skip-worktree "file*with*star.txt"
	git update-index --skip-worktree "fileXwithYstar.txt"
	git update-index --skip-worktree "another space file.txt"
}

@test "git-unlock: unlock file with path containing spaces" {
	# Verify it is locked initially
	run git ls-files -v
	assert_line "S file with spaces.txt"

	run git unlock "file with spaces.txt"
	assert_success

	# Verify target file is unlocked (marked H)
	run git ls-files -v
	assert_line "H file with spaces.txt"

	# Verify unrelated files remain locked (marked S)
	assert_line "S file*with*star.txt"
	assert_line "S fileXwithYstar.txt"
	assert_line "S another space file.txt"
}

@test "git-unlock: unlock file with wildcard in filename without affecting unrelated files" {
	# Verify both target and candidate are locked initially
	run git ls-files -v
	assert_line "S file*with*star.txt"
	assert_line "S fileXwithYstar.txt"

	# Unlock literal file containing wildcard character
	run git unlock 'file*with*star.txt'
	assert_success

	# Intended change: file*with*star.txt is unlocked
	run git ls-files -v
	assert_line "H file*with*star.txt"

	# Unrelated state unchanged: fileXwithYstar.txt must remain locked
	assert_line "S fileXwithYstar.txt"
	assert_line "S file with spaces.txt"
}

@test "git-unlock: unlock multiple files preserving quoted argument boundaries" {
	run git unlock "file with spaces.txt" "another space file.txt"
	assert_success

	run git ls-files -v
	assert_line "H file with spaces.txt"
	assert_line "H another space file.txt"
	assert_line "S file*with*star.txt"
	assert_line "S fileXwithYstar.txt"
}

@test "git-unlock: optional argument --help shows usage" {
	run git-unlock --help
	assert_success
	assert_line -p "Usage: git unlock"

	# Locked state unchanged
	run git ls-files -v
	assert_line "S file with spaces.txt"
}

@test "git-unlock: optional argument -h shows usage" {
	run git-unlock -h
	assert_success
	assert_line -p "Usage: git unlock"
}

@test "git-unlock: invalid argument combination - missing filename" {
	run git unlock
	assert_failure
	assert_line -p "filename required."

	# All locked files remain locked
	run git ls-files -v
	assert_line "S file with spaces.txt"
	assert_line "S file*with*star.txt"
}

@test "git-unlock: edge-state - non-existent file fails and leaves state intact" {
	run git unlock "non existent file.txt"
	assert_failure

	# Existing locked files remain locked
	run git ls-files -v
	assert_line "S file with spaces.txt"
	assert_line "S file*with*star.txt"
}

