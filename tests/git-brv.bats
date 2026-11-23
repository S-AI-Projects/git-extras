# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

MAN_PAGE="$BATS_TEST_DIRNAME/../man/git-brv.md"

setup_file() {
	test_util.setup_file
	test_util.install_command brv
}

setup() {
	test_util.cd_test
	# never look for a repository above the test directory
	export GIT_CEILING_DIRECTORIES="$BATS_TEST_TMPDIR"
	export TZ=UTC

	git init --bare remote.git
	mkdir my-project
	cd my-project
	test_util.git_init
	for name in A B C; do
		printf '%s\n' "$name" > "file-$name.txt"
		git add .
		GIT_COMMITTER_DATE='2020-01-08T12:00:00Z' git commit -m "$name"
	done
	git checkout -b topic
	printf '%s\n' 'topic work' > topic.txt
	git add .
	GIT_COMMITTER_DATE='2020-01-14T12:00:00Z' git commit -m 'topic work'
	git checkout main
	git remote add origin ../remote.git
	git push -u origin main topic
	cd ..
}

# Print one evidence line into the TAP report.
report() {
	local line
	while IFS= read -r line; do
		printf '# evidence: %s\n' "$line" >&3
	done <<< "$*"
}

# Commit hashes differ on every run.
normalize() {
	sed -E 's/ [0-9a-f]{7,} / HASH /'
}

# The example lines that follow "$ git -C my-project brv" in the manual.
documented_success() {
	awk '
		/^    \$ git -C my-project brv$/ { found = 1; next }
		found && !/^    [0-9]/ { exit }
		found { print substr($0, 5) }
	' "$MAN_PAGE"
}

@test "git-brv: outside a repository it fails with the documented message (edge)" {
	run git brv
	report "pwd=[$PWD] (not a repository) args=[] status=$status output=[$output]"

	assert_failure 128
	assert_output 'Not a git repo!'
	[ ! -e .git ]
	# the manual explains this exact message and exit status
	grep -qF '`Not a git repo!` (exit status 128)' "$MAN_PAGE"
}

@test "git-brv: the corrected call with git -C succeeds as documented (success)" {
	local expected actual
	expected=$(documented_success | normalize)

	run git -C my-project brv
	actual=$(printf '%s\n' "$output" | normalize)
	report "args=[-C my-project brv] status=$status"
	report "documented:"
	report "$expected"
	report "actual:"
	report "$actual"

	assert_success
	[ -n "$expected" ]
	[ "$actual" = "$expected" ]
}

@test "git-brv: lists the newest branch first with its upstream and hash (success)" {
	cd my-project

	run git brv
	report "args=[] status=$status"
	report "$output"

	assert_success
	assert_line -n 0 "2020-01-14 topic origin/topic $(git rev-parse --short topic) topic work"
	assert_line -n 1 "2020-01-08 main  origin/main  $(git rev-parse --short main) C"
}

@test "git-brv: --reverse puts the newest branch last (success)" {
	cd my-project

	run git brv --reverse
	report "args=[--reverse] status=$status"
	report "$output"

	assert_success
	assert_line -n 0 -p '2020-01-08 main'
	assert_line -n 1 -p '2020-01-14 topic'
}

@test "git-brv: git-extras.brv.reverse=true works like --reverse (success)" {
	cd my-project
	git config git-extras.brv.reverse true

	run git brv
	report "config git-extras.brv.reverse=true args=[] status=$status"

	assert_success
	assert_line -n 0 -p '2020-01-08 main'
}

@test "git-brv: the bash version requirement is documented with its message (edge)" {
	local message
	message=$(grep -o 'This script requires bash [0-9.]* or newer' "$BATS_TEST_DIRNAME/../bin/git-brv")
	report "message in bin/git-brv=[$message] running bash=[$BASH_VERSION]"

	[ -n "$message" ]
	grep -qF "\`$message\` (exit status 1)" "$MAN_PAGE"
}
