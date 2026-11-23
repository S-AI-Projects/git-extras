# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	# git filter-branch otherwise prints a long warning and sleeps
	export FILTER_BRANCH_SQUELCH_WARNING=1
}

setup() {
	test_util.cd_test

	test_util.git_init
	for name in A B C; do
		printf '%s\n' "$name" > "file-$name.txt"
		git add .
		git commit -m "$name"
	done
	git branch topic
	git tag v1 HEAD~1
	GIT_AUTHOR_NAME='Old Name' GIT_AUTHOR_EMAIL='old@example.com' \
		GIT_COMMITTER_NAME='Old Name' GIT_COMMITTER_EMAIL='old@example.com' \
		git commit --allow-empty -m D
}

# Print one evidence line into the TAP report.
report() {
	local line
	while IFS= read -r line; do
		printf '# evidence: %s\n' "$line" >&3
	done <<< "$*"
}

# One line per commit on main: message, author, committer, tree.
history() {
	git log --format='%s|%an <%ae>|%cn <%ce>|%T' main
}

identity_of() {
	git log --format='%s|%an <%ae>|%cn <%ce>' main | grep "^$1|" | cut -d '|' -f 2-
}

trees() {
	git log --format='%s %T' main
}

ref_names() {
	git for-each-ref --format='%(refname:short)' refs/heads refs/tags | tr '\n' ' '
}

@test "git-reauthor: --old-email with --correct-email rewrites only the matching identity (success)" {
	local before after
	before=$(history)
	local trees_before
	trees_before=$(trees)

	run git reauthor --old-email old@example.com --correct-email new@example.com
	after=$(history)
	report "args=[--old-email old@example.com --correct-email new@example.com] status=$status"
	report "before:"
	report "$before"
	report "after:"
	report "$after"

	assert_success
	# intended change: D now has the new email, the old name is kept
	[ "$(identity_of D)" = 'Old Name <new@example.com>|Old Name <new@example.com>' ]
	# unrelated state: A, B and C keep their identity
	[ "$(identity_of A)" = 'Name <name@example.com>|Name <name@example.com>' ]
	[ "$(identity_of C)" = 'Name <name@example.com>|Name <name@example.com>' ]
	# unrelated state: messages and file trees are identical
	[ "$(trees)" = "$trees_before" ]
	# unrelated state: branches and tags are all still there
	[ "$(ref_names)" = 'main topic v1 ' ]
	[ "$(git log --format=%s -1 v1)" = 'B' ]
}

@test "git-reauthor: --use-config takes the name and email from git config (success)" {
	run git reauthor --old-email old@example.com --use-config
	report "args=[--old-email old@example.com --use-config] status=$status"
	report "D after: $(identity_of D)"

	assert_success
	[ "$(identity_of D)" = 'Name <name@example.com>|Name <name@example.com>' ]
	[ "$(identity_of B)" = 'Name <name@example.com>|Name <name@example.com>' ]
}

@test "git-reauthor: --type author leaves the committer identity unchanged (success)" {
	run git reauthor --old-email old@example.com --correct-name 'New Name' --type author
	report "args=[--old-email old@example.com --correct-name 'New Name' --type author] status=$status"
	report "D after: $(identity_of D)"

	assert_success
	[ "$(identity_of D)" = 'New Name <old@example.com>|Old Name <old@example.com>' ]
}

@test "git-reauthor: no target prints an error and leaves history alone (edge)" {
	local head_before
	head_before=$(git rev-parse HEAD)

	run git reauthor --correct-email new@example.com
	report "args=[--correct-email new@example.com] status=$status"
	report "first output line=[${lines[0]}]"
	report "HEAD before=[$head_before] after=[$(git rev-parse HEAD)]"

	assert_failure 1
	assert_line 'error: missing target of the rewrite'
	[ "$(git rev-parse HEAD)" = "$head_before" ]
}

@test "git-reauthor: --all together with --old-email is rejected as ambiguous (edge)" {
	local head_before
	head_before=$(git rev-parse HEAD)

	run git reauthor --all --old-email old@example.com --correct-email new@example.com
	report "args=[--all --old-email old@example.com --correct-email new@example.com] status=$status"

	assert_failure 1
	assert_line 'error: ambiguous target of the rewrite'
	[ "$(git rev-parse HEAD)" = "$head_before" ]
}

@test "git-reauthor: an empty --correct-name is not allowed (edge)" {
	local head_before
	head_before=$(git rev-parse HEAD)

	run git reauthor --all --correct-name ''
	report "args=[--all --correct-name ''] status=$status"

	assert_failure 1
	assert_line 'error: empty name is not allowed'
	[ "$(git rev-parse HEAD)" = "$head_before" ]
}

@test "git-reauthor: an unknown --type is rejected (edge)" {
	run git reauthor --all --correct-email new@example.com --type bogus
	report "args=[--all --correct-email new@example.com --type bogus] status=$status"

	assert_failure 1
	assert_line "error: invalid type 'bogus'"
}
