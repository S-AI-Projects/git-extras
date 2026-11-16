# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command delete-submodule
	test_util.install_command root
}

setup() {
	test_util.cd_test
	test_util.git_init
	printf '%s\n' "Initial" > init.txt
	git add .
	git commit -m "Initial commit"
}

@test "git-delete-submodule without arguments fails and displays error" {
	run git delete-submodule
	assert_failure
	assert_equal "$status" 1
	assert_line -p "Submodule required"
}

@test "git-delete-submodule fails when .gitmodules file not found" {
	run git delete-submodule non_existent
	assert_failure
	assert_equal "$status" 2
	assert_line -p ".gitmodules file not found"
}

@test "git-delete-submodule fails when submodule not registered in .gitmodules" {
	touch .gitmodules
	git add .gitmodules
	git commit -m "Add empty .gitmodules"

	run git delete-submodule unregistered
	assert_failure
	assert_equal "$status" 3
	assert_line -p "Submodule not found"
}

@test "git-delete-submodule successfully deletes an existing submodule" {
	local sub_repo="$BATS_TEST_TMPDIR/sub_repo"
	mkdir -p "$sub_repo"
	git -C "$sub_repo" init --initial-branch main
	git -C "$sub_repo" config user.name "Sub User"
	git -C "$sub_repo" config user.email "sub@example.com"
	printf '%s\n' "submodule content" > "$sub_repo/sub.txt"
	git -C "$sub_repo" add .
	git -C "$sub_repo" commit -m "Sub initial commit"

	git -c protocol.file.allow=always submodule add "$sub_repo" my_sub
	git commit -m "Add submodule my_sub"

	[ -d "my_sub" ]
	[ -f ".gitmodules" ]

	run git delete-submodule my_sub
	assert_success
	assert_line -p "Successfully deleted my_sub."

	[ ! -d "my_sub" ]
	[ ! -f ".gitmodules" ]
}
