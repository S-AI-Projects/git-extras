# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command extras
}

mock_curl() {
	local mock_bin="$BATS_FILE_TMPDIR/mock_bin"
	mkdir -p "$mock_bin"
	cat << 'EOF' > "$mock_bin/curl"
#!/usr/bin/env bash
printf "%s\n" "$@" > "$BATS_FILE_TMPDIR/curl_args.txt"
printf "echo 'mock install successful'\n"
EOF
	chmod +x "$mock_bin/curl"
	PATH="$mock_bin:$PATH"
}

unmock_curl() {
	PATH="${PATH//$BATS_FILE_TMPDIR\/mock_bin:/}"
	rm -rf "$BATS_FILE_TMPDIR/mock_bin"
}

setup() {
	test_util.cd_test
	test_util.git_init
}

@test "git-extras: -v and --version display version number" {
	run git extras -v
	assert_success
	assert_line -p "7.6.0-dev"

	run git extras --version
	assert_success
	assert_line -p "7.6.0-dev"
}

@test "git-extras: -h and --help display usage information" {
	run git extras -h
	assert_success
	assert_line -p "Usage: git extras"

	run git-extras --help
	assert_success
	assert_line -p "Usage: git extras"
}

@test "git-extras: respects local config with --add git-extras.default-branch" {
	git config --add git-extras.default-branch custom-feature
	source "$BATS_TEST_DIRNAME/../helper/git-extra-utility"
	run git_extra_default_branch
	assert_success
	assert_output "custom-feature"
}

@test "git-extras: update succeeds with stubbed curl dependency" {
	mock_curl

	run git extras update
	assert_success
	assert_line -p "mock install successful"
	assert_line -p "... updated git-extras"

	run cat "$BATS_FILE_TMPDIR/curl_args.txt"
	assert_line "-s"

	unmock_curl
}

@test "git-extras: update fails with documented error when curl is missing" {
	unmock_curl
	local isolate_bin="$BATS_FILE_TMPDIR/isolate_bin"
	mkdir -p "$isolate_bin"
	ln -sf "$(command -v bash)" "$isolate_bin/bash"
	ln -sf "$(command -v git)" "$isolate_bin/git"
	ln -sf "$(command -v uname)" "$isolate_bin/uname"
	ln -sf "$BATS_FILE_TMPDIR/bin/git-extras" "$isolate_bin/git-extras"

	PATH="$isolate_bin" run "$isolate_bin/git-extras" update
	assert_failure
	assert_line -p "curl is required to update git-extras"

	rm -rf "$isolate_bin"
}
