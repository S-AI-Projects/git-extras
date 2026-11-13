# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file

	PATH="$BATS_TEST_DIRNAME/bin:$PATH"
}

setup() {
	test_util.cd_test

	test_util.git_init
	touch ./tracked
	git add ./tracked
	git commit -m 'Commit A'

	git checkout -b topic
	echo 'change B' > ./tracked
	git commit -am 'Commit B'

	echo 'change C' > ./tracked
	git commit -am 'Commit C'

	git checkout main

	# Local bare remote with spaces in its path
	spaced_remote_dir="$BATS_TEST_TMPDIR/spaced remote dir/remote.git"
	mkdir -p "$(dirname "$spaced_remote_dir")"
	git init --bare --initial-branch main "$spaced_remote_dir"
	git push "$spaced_remote_dir" topic:refs/pull/42/head
	git push "$spaced_remote_dir" topic:refs/pull/42/merge

	git remote add origin "$spaced_remote_dir"
}

@test "preserves quoted remote path containing spaces and does not expand wildcards" {
	touch "unrelated_1.txt" "unrelated_2.txt"
	mkdir -p "refs/heads/pr"
	touch "refs/heads/pr/unrelated_glob_file"

	run git pr 42 "$spaced_remote_dir"
	assert_success

	run git rev-parse --abbrev-ref HEAD
	assert_output 'pr/42'

	run git config --local --get branch.pr/42.remote
	assert_output "$spaced_remote_dir"

	run git config --local --get branch.pr/42.merge
	assert_output 'refs/pull/42/head'

	# Wildcard argument preserves boundaries and does not affect unrelated files
	run git pr "invalid*wildcard*arg"
	assert_failure
	assert_output "invalid*wildcard*arg doesn't match the pr id pattern."

	[ -f "unrelated_1.txt" ]
	[ -f "unrelated_2.txt" ]
	[ -f "refs/heads/pr/unrelated_glob_file" ]

	# Switch back to main before cleaning pr/* branches
	git checkout main
	run git pr clean
	assert_success
	[ -f "refs/heads/pr/unrelated_glob_file" ]
}
