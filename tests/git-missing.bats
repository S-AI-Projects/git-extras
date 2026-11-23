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
	git checkout -b topic
	printf '%s\n' 'T1' > topic.txt
	git add .
	git commit -m T1
	git checkout main
	printf '%s\n' 'M1' > main.txt
	git add .
	git commit -m M1
}

# Print one evidence line into the TAP report.
report() {
	local line
	while IFS= read -r line; do
		printf '# evidence: %s\n' "$line" >&3
	done <<< "$*"
}

# "< <hash> M1" -> "< M1"
without_hashes() {
	printf '%s\n' "$output" | sed -E 's/^([<>]) [0-9a-f]+ /\1 /'
}

@test "git-missing: one branch compares it with the current branch (success)" {
	run git missing topic
	report "args=[topic] (on main) status=$status"
	report "$output"

	assert_success
	[ "$(without_hashes)" = "$(printf '%s\n' '< M1' '> T1')" ]
}

@test "git-missing: two branches compare them with each other (success)" {
	git checkout topic

	run git missing main topic
	report "args=[main topic] (on topic) status=$status"
	report "$output"

	assert_success
	[ "$(without_hashes)" = "$(printf '%s\n' '< M1' '> T1')" ]
}

@test "git-missing: --no-merges is passed to git log and hides merge commits (success)" {
	git checkout -b side
	printf '%s\n' 'S1' > side.txt
	git add .
	git commit -m S1
	git checkout main
	git merge --no-ff -m 'merge side' side

	run git missing topic
	report "args=[topic] status=$status subjects=[$(without_hashes | tr '\n' ' ')]"
	assert_success
	assert_line -p 'merge side'

	run git missing topic --no-merges
	report "args=[topic --no-merges] status=$status subjects=[$(without_hashes | tr '\n' ' ')]"
	assert_success
	refute_line -p 'merge side'
	# commits made in the same second have no fixed order, so compare sorted
	[ "$(without_hashes | sort | tr '\n' ' ')" = '< M1 < S1 > T1 ' ]
}

@test "git-missing: a path after -- limits the comparison (success)" {
	run git missing topic -- topic.txt
	report "args=[topic -- topic.txt] status=$status"
	report "$output"

	assert_success
	[ "$(without_hashes)" = '> T1' ]
}

@test "git-missing: no arguments print usage and fail (edge)" {
	run git missing
	report "args=[] status=$status output=[$output]"

	assert_failure 1
	assert_output -p 'usage: git missing'
}

@test "git-missing: an option without a branch is rejected (edge)" {
	run git missing --no-merges
	report "args=[--no-merges] status=$status output=[$output]"

	assert_failure 1
	assert_output 'error: at least one branch required'
}

@test "git-missing: three branches are rejected (edge)" {
	run git missing main topic extra
	report "args=[main topic extra] status=$status output=[$output]"

	# more than two branches falls into the same error as zero branches
	assert_failure 1
	assert_output 'error: at least one branch required'
}

@test "git-missing: an unknown branch fails with git's error (edge)" {
	run git missing no-such-branch
	report "args=[no-such-branch] status=$status output=[$output]"

	assert_failure 128
	assert_output -p 'no-such-branch'
}
