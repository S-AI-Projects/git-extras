#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command info
}

setup() {
	test_util.cd_test
	test_util.git_init
	echo "init" > file.txt
	git add file.txt
	git commit -m "Initial commit"
}

@test "git-info outputs repository information" {
	run git info
	assert_success
	assert_line -p "## Remote URLs:"
	assert_line -p "## Remote Branches:"
	assert_line -p "## Local Branches:"
	assert_line -p "## Most Recent Commit:"
	assert_line -p "## Configuration (.git/config):"
}

@test "git-info --no-config suppresses configuration section" {
	run git info --no-config
	assert_success
	assert_line -p "## Remote URLs:"
	assert_line -p "## Local Branches:"
	assert_line -p "## Most Recent Commit:"
	refute_line -p "## Configuration (.git/config):"
}

@test "git-info --color and -c work cleanly" {
	run git info --color
	assert_success
	assert_line -p "## Local Branches:"

	run git info -c
	assert_success
	assert_line -p "## Local Branches:"
}

@test "git-info reaches failure branch with failing config-grep fixture and recovers with --no-config" {
	git config git-extras.info.config-grep "grep-nonexistent-command"

	# Failing invocation reaching the failure branch
	run git info
	assert_failure 1
	assert_line -p "git-info: failed to execute git-extras.info.config-grep: 'grep-nonexistent-command'"
	assert_line -p "Troubleshooting: verify the command in 'git config git-extras.info.config-grep' or use '--no-config'."

	# Corrected invocation succeeding afterwards
	run git info --no-config
	assert_success
	refute_line -p "## Configuration (.git/config):"
}

@test "git-info reaches failure branch with failing log fixture and recovers when config is fixed" {
	git config git-extras.info.log "git log --nonexistent-flag-xyz"

	# Failing invocation reaching the failure branch
	run git info
	assert_failure 1
	assert_line -p "git-info: failed to execute git-extras.info.log: 'git log --nonexistent-flag-xyz'"
	assert_line -p "Troubleshooting: verify the command in 'git config git-extras.info.log'."

	# Corrected invocation succeeding afterwards
	git config --unset git-extras.info.log
	run git info
	assert_success
	assert_line -p "## Most Recent Commit:"
}

@test "git-info unknown option fails with diagnostic and recovers with valid invocation" {
	# Failing invocation
	run git info --unknown-flag
	assert_failure 1
	assert_line -p "git-info: unknown option '--unknown-flag'"
	assert_line -p "Troubleshooting: run 'git info -h' or refer to 'git info --help' for valid options."

	# Corrected invocation
	run git info --color
	assert_success
}

@test "git-info -h and --help show usage and exit 0" {
	run git info -h
	assert_success
	assert_line -p "Usage: git info [-c|--color] [--no-config]"

	run git-info --help
	assert_success
	assert_line -p "Usage: git info [-c|--color] [--no-config]"
}
