# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command fork
}

setup() {
	test_util.cd_test
}

@test "git-fork -h displays usage screen" {
	run git fork -h
	assert_success
	assert_line -p "Usage: git fork"
}

@test "git-fork without args outside repo fails with repo required error" {
	run git fork
	assert_failure
	assert_equal "$status" 1
	assert_line -p "github repo needs to be specified as an argument"
}

@test "git-fork with empty username aborts" {
	run bash -c 'printf "\n" | git fork owner/repo'
	assert_failure
	assert_equal "$status" 1
	assert_line -p "git username required"
}

@test "git-fork without token aborts" {
	run bash -c '
		unset GITHUB_TOKEN
		git config --global --unset-all git-extras.github-personal-access-token || true
		printf "myuser\n" | git fork owner/repo
	'
	assert_failure
	assert_equal "$status" 1
	assert_line -p "GITHUB_TOKEN, or git config git-extras.github-personal-access-token required"
}

@test "git-fork with failing API call aborts with fork failed" {
	local mock_bin="$BATS_TEST_TMPDIR/mock_bin"
	mkdir -p "$mock_bin"
	cat << 'EOF' > "$mock_bin/curl"
#!/usr/bin/env bash
exit 1
EOF
	chmod +x "$mock_bin/curl"

	run bash -c "
		export PATH=\"$mock_bin:\$PATH\"
		export GITHUB_TOKEN=\"dummy_token\"
		printf \"myuser\n\" | git fork owner/repo
	"
	assert_failure
	assert_equal "$status" 1
	assert_line -p "fork failed"
}

@test "git-fork in existing repo renames origin to upstream and adds fork origin" {
	local remotes_dir="$BATS_TEST_TMPDIR/remotes_exist"
	mkdir -p "$remotes_dir/owner/repo.git" "$remotes_dir/myuser/repo.git"
	git init --bare --initial-branch main "$remotes_dir/owner/repo.git"
	git init --bare --initial-branch main "$remotes_dir/myuser/repo.git"

	local seed_dir="$BATS_TEST_TMPDIR/seed_exist"
	git clone "$remotes_dir/owner/repo.git" "$seed_dir"
	pushd "$seed_dir" > /dev/null
	test_util.git_init
	echo "content" > file.txt
	git add file.txt
	git commit -m "commit on main"
	git push origin main
	git push "$remotes_dir/myuser/repo.git" main
	popd > /dev/null

	local local_repo="$BATS_TEST_TMPDIR/local_work"
	git clone "$remotes_dir/owner/repo.git" "$local_repo"
	pushd "$local_repo" > /dev/null

	local mock_bin="$BATS_TEST_TMPDIR/mock_bin_ok"
	mkdir -p "$mock_bin"
	cat << 'EOF' > "$mock_bin/curl"
#!/usr/bin/env bash
exit 0
EOF
	chmod +x "$mock_bin/curl"

	run bash -c "
		export PATH=\"$mock_bin:\$PATH\"
		export GITHUB_TOKEN=\"dummy_token\"
		export GIT_REMOTE_PREFIX=\"$remotes_dir/\"
		printf \"myuser\nn\n\" | git fork
	"
	assert_success

	run git remote get-url upstream
	assert_success
	assert_line -p "$remotes_dir/owner/repo.git"

	run git remote get-url origin
	assert_success
	assert_line -p "$remotes_dir/myuser/repo.git"

	popd > /dev/null
}

@test "git-fork with repo url clones fork and sets up upstream" {
	local remotes_dir="$BATS_TEST_TMPDIR/remotes_clone"
	mkdir -p "$remotes_dir/owner/clonerepo.git" "$remotes_dir/myuser/clonerepo.git"
	git init --bare --initial-branch main "$remotes_dir/owner/clonerepo.git"
	git init --bare --initial-branch main "$remotes_dir/myuser/clonerepo.git"

	local seed_dir="$BATS_TEST_TMPDIR/seed_clone"
	git clone "$remotes_dir/owner/clonerepo.git" "$seed_dir"
	pushd "$seed_dir" > /dev/null
	test_util.git_init
	echo "content" > file.txt
	git add file.txt
	git commit -m "initial commit"
	git push origin main
	git push "$remotes_dir/myuser/clonerepo.git" main
	popd > /dev/null

	local work_dir="$BATS_TEST_TMPDIR/work_clone"
	mkdir -p "$work_dir"
	pushd "$work_dir" > /dev/null

	local mock_bin="$BATS_TEST_TMPDIR/mock_bin_ok2"
	mkdir -p "$mock_bin"
	cat << 'EOF' > "$mock_bin/curl"
#!/usr/bin/env bash
exit 0
EOF
	chmod +x "$mock_bin/curl"

	run bash -c "
		export PATH=\"$mock_bin:\$PATH\"
		export GITHUB_TOKEN=\"dummy_token\"
		export GIT_REMOTE_PREFIX=\"$remotes_dir/\"
		printf \"myuser\nn\n\" | git fork owner/clonerepo
	"
	assert_success

	cd clonerepo
	run git remote get-url origin
	assert_success
	assert_line -p "$remotes_dir/myuser/clonerepo.git"

	run git remote get-url upstream
	assert_success
	assert_line -p "$remotes_dir/owner/clonerepo.git"

	popd > /dev/null
}
