# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
}

setup() {
	test_util.cd_test

	# the repository path contains spaces
	mkdir 'dir with spaces'
	cd 'dir with spaces'
	test_util.git_init
	for name in A B C; do
		printf '%s\n' "$name" > "file $name.txt"
		git add .
		git commit -m "$name"
	done
	git branch topic
	printf '%s\n' 'D' > 'file D.txt'
	git add .
	git commit -m D

	# Untracked decoy files. If the wildcard argument were expanded by a
	# shell, either before the call or inside the script, it would turn into
	# one of these names and the output would change.
	touch 'topic' 'topic..HEAD' 'tofu'
}

# Print one evidence line into the TAP report.
report() {
	local line
	while IFS= read -r line; do
		printf '# evidence: %s\n' "$line" >&3
	done <<< "$*"
}

subjects() {
	printf '%s\n' "$output" | sed 's/^[0-9a-f]* Name - //' | tr '\n' ' '
}

workdir_state() {
	git status --porcelain
	ls -a
}

@test "git-commits-since: a quoted date with a space is one argument (success)" {
	run git commits-since 'last week'
	report "pwd=[$PWD]"
	report "args=['last week'] status=$status subjects=[$(subjects)]"

	assert_success
	[ "$(subjects)" = 'D C B A ' ]
}

@test "git-commits-since: the same date as two words gives the same result (success)" {
	run git commits-since last week
	report "args=[last] [week] status=$status subjects=[$(subjects)]"

	assert_success
	[ "$(subjects)" = 'D C B A ' ]
}

@test "git-commits-since: --ref lists the commits after that ref (success)" {
	run git commits-since --ref topic
	report "args=[--ref] [topic] status=$status subjects=[$(subjects)]"

	assert_success
	[ "$(subjects)" = 'D ' ]
}

@test "git-commits-since: a wildcard in --ref reaches git unexpanded (edge)" {
	local before after
	before=$(workdir_state)

	run git commits-since --ref 'to*'
	after=$(workdir_state)
	report "args=[--ref] ['to*'] status=$status output=[$output]"
	report "decoy files: $(ls topic topic..HEAD tofu | tr '\n' ' ')"
	report "working tree unchanged: $([ "$before" = "$after" ] && echo yes || echo no)"

	# 'to*..HEAD' is passed to git as one literal word: git finds no such
	# ref or file, so nothing is listed. Had it been expanded to the decoy
	# 'topic..HEAD' (or 'topic'), commit D would appear.
	assert_success
	assert_output ''
	[ "$before" = "$after" ]
}

@test "git-commits-since: --ref without a value is rejected (edge)" {
	run git commits-since --ref
	report "args=[--ref] status=$status output=[$output]"

	assert_failure 1
	assert_output 'error: option --ref requires an argument'
}

@test "git-commits-since: an empty quoted --ref value is rejected (edge)" {
	run git commits-since --ref ''
	report "args=[--ref] [''] status=$status output=[$output]"

	assert_failure 1
	assert_output 'error: option --ref requires an argument'
}

@test "git-commits-since: --ref together with a date is rejected (edge)" {
	run git commits-since --ref topic 'last week'
	report "args=[--ref] [topic] ['last week'] status=$status output=[$output]"

	assert_failure 1
	assert_output "error: '--ref <ref>' and '<date>' are mutually exclusive"
}
