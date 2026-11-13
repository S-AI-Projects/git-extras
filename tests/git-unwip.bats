#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command undo
	test_util.install_command unwip
}

setup() {
	test_util.cd_test
	test_util.git_init
	echo "initial" > file.txt
	git add file.txt
	git commit -m "Initial commit"
}

@test "git-unwip successfully unwips a commit with exact message 'WIP'" {
	echo "wip work" >> file.txt
	git add file.txt
	git commit -m "WIP"

	run git unwip
	assert_success

	run git log -1 --pretty=%s
	assert_output "Initial commit"

	grep -q "wip work" file.txt
}

@test "git-unwip handles WIP commit with leading or trailing whitespace" {
	echo "whitespace wip" >> file.txt
	git add file.txt
	git commit -m "  WIP  "

	run git unwip
	assert_success

	run git log -1 --pretty=%s
	assert_output "Initial commit"

	grep -q "whitespace wip" file.txt
}

@test "git-unwip rejects commit that is not a WIP commit" {
	echo "non-wip change" >> file.txt
	git add file.txt
	git commit -m "Regular commit"

	run git unwip
	assert_failure 1
	assert_line -p "Last commit is not a WIP commit, so it will not be unWIP-ed."

	run git log -1 --pretty=%s
	assert_output "Regular commit"
}

@test "git-unwip rejects commit that only contains WIP as a substring" {
	echo "substring change" >> file.txt
	git add file.txt
	git commit -m "WIP: partial feature"

	run git unwip
	assert_failure 1
	assert_line -p "Last commit is not a WIP commit, so it will not be unWIP-ed."

	run git log -1 --pretty=%s
	assert_output "WIP: partial feature"
}

@test "git-unwip rejects positional arguments with diagnostic and exit 1" {
	run git unwip extra_arg
	assert_failure 1
	assert_line -p "git-unwip: unexpected argument 'extra_arg'"
	assert_line -p "Usage: git unwip [-h|--help]"
}

@test "git-unwip -h and --help display usage and exit 0" {
	run git unwip -h
	assert_success
	assert_line -p "Usage: git unwip [-h|--help]"

	run git-unwip --help
	assert_success
	assert_line -p "Usage: git unwip [-h|--help]"
}
