# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

MAN_PAGE="$BATS_TEST_DIRNAME/../man/git-squash.md"
EXAMPLE_TITLE='# complete example: squash the last two commits into one and check the result'

setup_file() {
	test_util.setup_file
	test_util.install_command squash
}

setup() {
	test_util.cd_test

	export GIT_AUTHOR_NAME='Name' GIT_AUTHOR_EMAIL='name@example.com'
	export GIT_COMMITTER_NAME='Name' GIT_COMMITTER_EMAIL='name@example.com'
}

# Print one evidence line into the TAP report.
report() {
	local line
	while IFS= read -r line; do
		printf '# evidence: %s\n' "$line" >&3
	done <<< "$*"
}

# Print the lines of the documented example, without the 4-space indent.
documented_example() {
	awk -v title="    $EXAMPLE_TITLE" '
		$0 == title { found = 1; next }
		found && !/^    / { exit }
		found { print substr($0, 5) }
	' "$MAN_PAGE"
}

# Commit hashes differ on every run.
normalize() {
	sed -E 's/^\[([^ ]+) [0-9a-f]{7,}\]/[\1 HASH]/'
}

make_abc_repo() {
	git init -q -b main repo
	cd repo
	for name in A B C; do
		printf '%s\n' "$name" > "file-$name.txt"
		git add .
		git commit -q -m "$name"
	done
	git branch topic
}

@test "git-squash: the complete example in man/git-squash.md runs as documented (success)" {
	local example script expected actual
	example=$(documented_example)
	report "example taken from man/git-squash.md:"
	report "$example"
	[ -n "$example" ]

	# Turn the example into a script: each "$ command" line is printed as a
	# marker and then run; every other line is the output it should give.
	script=$(printf '%s\n' "$example" | awk -v q="'" '
		/^\$ / {
			cmd = substr($0, 3)
			quoted = cmd
			gsub(q, q "\\" q q, quoted)
			print "printf \"%s\\n\" " q "$ " quoted q
			print cmd " 2>&1"
		}
	')
	expected=$(printf '%s\n' "$example" | normalize)

	run bash -c "set -e; $script"
	actual=$(printf '%s\n' "$output" | normalize)
	report "status=$status"
	report "actual run:"
	report "$actual"

	assert_success
	[ "$(grep -c '^\$ ' <<< "$expected")" -eq 7 ]
	[ "$actual" = "$expected" ]
}

@test "git-squash: --squash-msg joins the squashed messages (success)" {
	make_abc_repo

	run git squash --squash-msg HEAD~2
	report "args=[--squash-msg] [HEAD~2] status=$status"
	report "new message=[$(git log -1 --format=%B | tr '\n' '|')]"

	assert_success
	[ "$(git log --format=%s | tr '\n' ' ')" = 'B A ' ]
	[ "$(git log -1 --format=%B)" = "$(printf '%s\n\n%s' B C)" ]
}

@test "git-squash: a branch without a message is staged but not committed (success)" {
	make_abc_repo
	git checkout -q topic
	printf '%s\n' 'D' > file-D.txt
	git add .
	git commit -q -m D
	git checkout -q main
	local head_before
	head_before=$(git rev-parse HEAD)

	run git squash topic
	report "args=[topic] status=$status"
	report "HEAD unchanged: $([ "$(git rev-parse HEAD)" = "$head_before" ] && echo yes || echo no)"
	report "staged=[$(git diff --cached --name-only)]"

	assert_success
	[ "$(git rev-parse HEAD)" = "$head_before" ]
	[ "$(git diff --cached --name-only)" = 'file-D.txt' ]
}

@test "git-squash: --squash-msg together with a message is rejected (edge)" {
	make_abc_repo
	local head_before
	head_before=$(git rev-parse HEAD)

	run git squash --squash-msg HEAD~2 'my message'
	report "args=[--squash-msg] [HEAD~2] ['my message'] status=$status output=[$output]"

	assert_failure 1
	assert_output 'When commit message is given, --squash-msg is not allowed.'
	[ "$(git rev-parse HEAD)" = "$head_before" ]
}

@test "git-squash: an unknown ref is rejected (edge)" {
	make_abc_repo
	local head_before
	head_before=$(git rev-parse HEAD)

	run git squash no-such-ref 'my message'
	report "args=[no-such-ref] ['my message'] status=$status output=[$output]"

	assert_failure 1
	assert_output 'Source branch or commit reference required.'
	[ "$(git rev-parse HEAD)" = "$head_before" ]
}

@test "git-squash: no arguments are rejected (edge)" {
	make_abc_repo

	run git squash
	report "args=[] status=$status output=[$output]"

	assert_failure 1
	assert_output 'Source branch or commit reference required.'
}
