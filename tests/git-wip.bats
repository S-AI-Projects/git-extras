# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
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
}

# Print one evidence line into the TAP report.
report() {
	local line
	while IFS= read -r line; do
		printf '# evidence: %s\n' "$line" >&3
	done <<< "$*"
}

commit_count() {
	git rev-list --count HEAD
}

# Files changed by the last commit, as "<status> <path>" lines.
last_commit_files() {
	git show --name-status --format= HEAD | tr '\t' ' '
}

@test "git-wip: commits new, changed and deleted files as WIP (success)" {
	printf '%s\n' 'new' > new.txt
	printf '%s\n' 'changed' >> file-A.txt
	rm file-B.txt
	local before
	before=$(git status --porcelain)

	run git wip
	report "args=[] status=$status"
	report "status before:"
	report "$before"
	report "last commit files:"
	report "$(last_commit_files)"

	assert_success
	[ "$(git log -1 --format=%s)" = 'WIP' ]
	[ "$(git status --porcelain)" = '' ]
	[ "$(last_commit_files)" = "$(printf '%s\n' 'M file-A.txt' 'D file-B.txt' 'A new.txt')" ]
}

@test "git-wip: a brand-new untracked file is included in the WIP commit (success)" {
	printf '%s\n' 'only new' > untracked.txt

	run git wip
	report "args=[] status=$status last commit files=[$(last_commit_files)]"

	# This is the regression check: without "git add --all" the untracked
	# file is left out and "git commit --all" finds nothing to commit.
	assert_success
	[ "$(last_commit_files)" = 'A untracked.txt' ]
	[ "$(git status --porcelain)" = '' ]
}

@test "git-wip: a clean working tree fails and adds no commit (edge)" {
	local count_before
	count_before=$(commit_count)

	run git wip
	report "args=[] status=$status output=[$output]"
	report "commits before=$count_before after=$(commit_count)"

	assert_failure 1
	assert_output -p 'nothing to commit, working tree clean'
	[ "$(commit_count)" = "$count_before" ]
}

@test "git-wip: ignored files are not committed (edge)" {
	printf '%s\n' '*.log' > .gitignore
	printf '%s\n' 'noise' > debug.log

	run git wip
	report "args=[] status=$status last commit files=[$(last_commit_files)]"

	assert_success
	[ "$(last_commit_files)" = 'A .gitignore' ]
	[ -e debug.log ]
	[ -z "$(git ls-files debug.log)" ]
}
