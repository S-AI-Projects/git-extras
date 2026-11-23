# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
}

setup() {
	test_util.cd_test

	git init --bare remote.git
	mkdir repo
	cd repo
	test_util.git_init
	for name in A B C; do
		printf '%s\n' "$name" > "file-$name.txt"
		git add .
		git commit -m "$name"
	done
	git branch topic
	git branch feature
	git remote add origin ../remote.git
	git push -u origin main topic feature
}

# Print one evidence line into the TAP report.
report() {
	local line
	while IFS= read -r line; do
		printf '# evidence: %s\n' "$line" >&3
	done <<< "$*"
}

local_branches() {
	git for-each-ref --format='%(refname:short)' refs/heads | tr '\n' ' '
}

remote_branches() {
	git ls-remote --heads origin | sed 's|.*refs/heads/||' | tr '\n' ' '
}

@test "git-delete-branch: one branch deletes it locally and on the remote (success)" {
	local before_local before_remote after_local after_remote
	before_local=$(local_branches)
	before_remote=$(remote_branches)

	run git delete-branch topic
	after_local=$(local_branches)
	after_remote=$(remote_branches)
	report "args=[topic] status=$status"
	report "local before=[$before_local] after=[$after_local]"
	report "remote before=[$before_remote] after=[$after_remote]"

	assert_success
	[ "$before_local" = 'feature main topic ' ]
	[ "$after_local" = 'feature main ' ]
	[ "$before_remote" = 'feature main topic ' ]
	[ "$after_remote" = 'feature main ' ]
}

@test "git-delete-branch: several branches are all deleted (success)" {
	run git delete-branch topic feature
	report "args=[topic feature] status=$status"
	report "local after=[$(local_branches)] remote after=[$(remote_branches)]"

	assert_success
	[ "$(local_branches)" = 'main ' ]
	[ "$(remote_branches)" = 'main ' ]
}

@test "git-delete-branch: no branch prints an error and changes nothing (edge)" {
	local before_local before_remote
	before_local=$(local_branches)
	before_remote=$(remote_branches)

	run git delete-branch
	report "args=[] status=$status output=[$output]"
	report "local after=[$(local_branches)] remote after=[$(remote_branches)]"

	assert_failure 1
	assert_output 'branch required.'
	[ "$(local_branches)" = "$before_local" ]
	[ "$(remote_branches)" = "$before_remote" ]
}

@test "git-delete-branch: a checked-out branch is kept locally but still deleted on the remote (edge)" {
	git checkout topic

	run git delete-branch topic
	report "args=[topic] (checked out) status=$status"
	report "local after=[$(local_branches)] remote after=[$(remote_branches)]"

	# documented: local deletion fails if the branch is checked out
	assert_success
	assert_output --regexp "[Cc]annot delete branch 'topic'"
	[ "$(local_branches)" = 'feature main topic ' ]
	# the remote branch is removed anyway
	[ "$(remote_branches)" = 'feature main ' ]
}

@test "git-delete-branch: an unknown branch is reported and the others are untouched (edge)" {
	run git delete-branch no-such-branch
	report "args=[no-such-branch] status=$status output=[$output]"

	assert_success
	assert_output -p "branch 'no-such-branch' not found"
	[ "$(local_branches)" = 'feature main topic ' ]
	[ "$(remote_branches)" = 'feature main topic ' ]
}
