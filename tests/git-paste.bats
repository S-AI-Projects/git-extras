# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command paste
}

mock_pastebinit() {
	local mock_bin="$BATS_FILE_TMPDIR/mock_bin"
	mkdir -p "$mock_bin"
	cat << EOF > "$mock_bin/pastebinit"
#!/usr/bin/env bash
printf "%s\n" "\$@" > "$BATS_FILE_TMPDIR/pastebinit_args.txt"
cat > "$BATS_FILE_TMPDIR/pastebinit_stdin.txt"
printf "https://pastebin.example.com/mock-paste\n"
EOF
	chmod +x "$mock_bin/pastebinit"
	PATH="$mock_bin:$PATH"
}

unmock_pastebinit() {
	PATH="${PATH//$BATS_FILE_TMPDIR\/mock_bin:/}"
	rm -rf "$BATS_FILE_TMPDIR/mock_bin"
}

setup() {
	test_util.cd_test
	test_util.git_init

	# Base commit A
	mkdir -p "dir with spaces"
	printf '%s\n' 'base space 1' > "dir with spaces/file with spaces 1.txt"
	printf '%s\n' 'base space 2' > "dir with spaces/file with spaces 2.txt"
	printf '%s\n' 'unrelated root' > "unrelated_file.txt"
	printf '%s\n' 'wildcard root' > "file_wildcard_target.txt"
	git add -A
	git commit -m "Commit A"

	# Commit B: modify file with spaces
	printf '%s\n' 'modified space 1' > "dir with spaces/file with spaces 1.txt"
	git commit -am "Commit B"

	# Commit C on topic branch
	git switch -c topic
	printf '%s\n' 'topic modification' > "unrelated_file.txt"
	git commit -am "Commit C"

	git switch main
}

@test "git-paste: preserves quoted path arguments containing spaces" {
	mock_pastebinit
	local before_unrelated
	before_unrelated=$(git hash-object "unrelated_file.txt")

	run git paste -1 HEAD -- "dir with spaces/file with spaces 1.txt"
	assert_success
	assert_line -p "https://pastebin.example.com/mock-paste"

	run cat "$BATS_FILE_TMPDIR/pastebinit_args.txt"
	assert_line "-f"
	assert_line "diff"

	run cat "$BATS_FILE_TMPDIR/pastebinit_stdin.txt"
	assert_line -p "dir with spaces/file with spaces 1.txt"
	refute_line -p "unrelated_file.txt"

	# Unrelated file remains untouched
	assert_equal "$(git hash-object unrelated_file.txt)" "$before_unrelated"
	assert_equal "$(git status --porcelain)" ""
	unmock_pastebinit
}

@test "git-paste: preserves wildcard arguments and does not affect unrelated files" {
	mock_pastebinit
	local before_unrelated before_wildcard
	before_unrelated=$(git hash-object "unrelated_file.txt")
	before_wildcard=$(git hash-object "file_wildcard_target.txt")

	run git paste -1 HEAD -- "dir with spaces/*.txt"
	assert_success
	assert_line -p "https://pastebin.example.com/mock-paste"

	run cat "$BATS_FILE_TMPDIR/pastebinit_stdin.txt"
	assert_line -p "dir with spaces/file with spaces 1.txt"
	refute_line -p "unrelated_file.txt"
	refute_line -p "file_wildcard_target.txt"

	# Unrelated files and shell state remain unaffected
	assert_equal "$(git hash-object unrelated_file.txt)" "$before_unrelated"
	assert_equal "$(git hash-object file_wildcard_target.txt)" "$before_wildcard"
	assert_equal "$(git status --porcelain)" ""
	unmock_pastebinit
}

@test "git-paste: supports -h and --help without requiring pastebinit" {
	unmock_pastebinit

	run git paste -h
	assert_success
	assert_line -p "usage: git paste"

	run git-paste --help
	assert_success
	assert_line -p "usage: git paste"
}

@test "git-paste: fails with documented error when pastebinit is missing" {
	unmock_pastebinit

	run git paste -1
	assert_failure
	assert_line -p "To run 'git paste', you need to install pastebinit in your system"
}

@test "git-paste: fails on invalid git format-patch argument" {
	mock_pastebinit

	run git paste nonexistent_ref_12345
	assert_failure

	# Working tree and repository state remain unchanged
	assert_equal "$(git status --porcelain)" ""
	unmock_pastebinit
}
