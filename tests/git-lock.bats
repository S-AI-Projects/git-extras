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

@test "git-lock: locks a tracked file (success)" {
	local before after
	before=$(git ls-files -v file-A.txt)

	run git lock file-A.txt
	after=$(git ls-files -v file-A.txt)
	report "args=[file-A.txt] status=$status output=[$output]"
	report "before=[$before] after=[$after]"

	# output
	assert_output ''
	# exit status
	assert_success
	# repository state
	[ "$before" = 'H file-A.txt' ]
	[ "$after" = 'S file-A.txt' ]
	# a file that was not named must stay unlocked
	[ "$(git ls-files -v file-B.txt)" = 'H file-B.txt' ]
}

@test "git-lock: local changes to a locked file are hidden from git status (success)" {
	git lock file-A.txt
	printf '%s\n' 'local change' >> file-A.txt

	run git status --porcelain
	report "args=[status --porcelain] status=$status output=[$output]"

	assert_success
	assert_output ''
	[ "$(cat file-A.txt)" = "$(printf '%s\n' A 'local change')" ]
}

@test "git-lock: no filename prints an error and exits 1 (edge)" {
	local before after
	before=$(git ls-files -v)

	run git lock
	after=$(git ls-files -v)
	report "args=[] status=$status output=[$output]"
	report "index unchanged: $([ "$before" = "$after" ] && echo yes || echo no)"

	assert_output 'filename required.'
	assert_failure 1
	[ "$before" = "$after" ]
}

@test "git-lock: an empty filename is treated like a missing one (edge)" {
	run git lock ''
	report "args=[''] status=$status output=[$output]"

	assert_output 'filename required.'
	assert_failure 1
}

@test "git-lock: a file git does not track is rejected (edge)" {
	local before after
	before=$(git ls-files -v)

	run git lock missing.txt
	after=$(git ls-files -v)
	report "args=[missing.txt] status=$status output=[$output]"

	assert_output -p 'Unable to mark file missing.txt'
	assert_failure 128
	[ "$before" = "$after" ]
	[ ! -e missing.txt ]
}
