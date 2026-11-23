# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command sed
}

setup() {
	test_util.cd_test

	# A stub sed, first on PATH. It logs every call and imitates either
	# GNU sed (SED_MODE=gnu) or BSD/macOS sed (SED_MODE=bsd), so the test
	# does not depend on which sed the machine has. The edit itself is done
	# by the real sed reading stdin, which works the same everywhere.
	REAL_SED=$(command -v sed)
	SED_LOG="$BATS_TEST_TMPDIR/sed.log"
	SED_MODE=gnu
	export REAL_SED SED_LOG SED_MODE
	# keep the scratch file git-sed creates with mktemp inside this test
	export TMPDIR="$BATS_TEST_TMPDIR"
	mkdir stub
	cat > stub/sed <<'EOF'
#!/usr/bin/env bash
printf '[%s] ' "$@" >> "$SED_LOG"
printf '\n' >> "$SED_LOG"
[ "$1" = '-i' ] || exec "$REAL_SED" "$@"
shift
if [ "$SED_MODE" = bsd ]; then
	# BSD sed: -i always takes a backup suffix as the next argument
	[ -z "$1" ] || exit 1
	shift
elif [ -z "$1" ]; then
	# GNU sed would read '' as the script and the expression as a file
	exit 2
fi
expr=$1
shift
for file in "$@"; do
	"$REAL_SED" "$expr" < "$file" > "$file.stub-tmp" || exit 1
	cat "$file.stub-tmp" > "$file"
	rm "$file.stub-tmp"
done
EOF
	chmod +x stub/sed
	PATH="$BATS_TEST_TMPDIR/stub:$PATH"

	mkdir repo
	cd repo
	test_util.git_init
	for name in A B C; do
		printf '%s\n' "$name" > "file-$name.txt"
		git add .
		git commit -m "$name"
	done
	git branch topic
	printf '%s\n' 'hello world hello' > greeting.txt
	git add .
	git commit -m 'add greeting'
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

@test "git-sed: replaces the first match per line with GNU sed (success)" {
	local count_before
	count_before=$(commit_count)

	run git sed hello bye
	report "args=[hello] [bye] SED_MODE=gnu status=$status"
	report "file after=[$(cat greeting.txt)]"
	report "sed calls:"
	report "$(cat "$SED_LOG")"

	assert_success
	[ "$(cat greeting.txt)" = 'bye world hello' ]
	# no commit without -c, the change is left in the working tree
	[ "$(commit_count)" = "$count_before" ]
	[ "$(git status --porcelain)" = ' M greeting.txt' ]
	# GNU form: sed -i <expression> <file>
	grep -qxF '[-i] [s/hello/bye/] [greeting.txt] ' "$SED_LOG"
	# the feature probe ran on a scratch file inside this test's directory
	grep -q "^\[-i\] \[s/hello/world/\] \[$BATS_TEST_TMPDIR/" "$SED_LOG"
	# the user's global git config was not touched
	[ ! -e "$GIT_CONFIG_GLOBAL" ]
}

@test "git-sed: falls back to sed -i '' when GNU sed -i is missing (success)" {
	SED_MODE=bsd

	run git sed hello bye
	report "args=[hello] [bye] SED_MODE=bsd status=$status"
	report "file after=[$(cat greeting.txt)]"
	report "sed calls:"
	report "$(cat "$SED_LOG")"

	assert_success
	[ "$(cat greeting.txt)" = 'bye world hello' ]
	# BSD form: sed -i '' <expression> <file>
	grep -qxF '[-i] [] [s/hello/bye/] [greeting.txt] ' "$SED_LOG"
}

@test "git-sed: -f g replaces every match on the line (success)" {
	run git sed -f g hello bye
	report "args=[-f] [g] [hello] [bye] status=$status file after=[$(cat greeting.txt)]"

	assert_success
	[ "$(cat greeting.txt)" = 'bye world bye' ]
}

@test "git-sed: -c commits the replacement (success)" {
	local count_before
	count_before=$(commit_count)

	run git sed -c hello bye
	report "args=[-c] [hello] [bye] status=$status"
	report "commits before=$count_before after=$(commit_count)"
	report "last commit subject=[$(git log -1 --format=%s)]"

	assert_success
	[ "$(commit_count)" = "$((count_before + 1))" ]
	[ "$(git log -1 --format=%s)" = 'replace hello with bye' ]
	[ "$(git status --porcelain)" = '' ]
}

@test "git-sed: a slash in the pattern picks another separator (success)" {
	printf '%s\n' 'path a/b' > path.txt
	git add path.txt
	git commit -m 'add path'

	run git sed 'a/b' 'c/d'
	report "args=[a/b] [c/d] status=$status file after=[$(cat path.txt)]"
	report "sed calls:"
	report "$(cat "$SED_LOG")"

	assert_success
	[ "$(cat path.txt)" = 'path c/d' ]
	grep -qxF '[-i] [s a/b c/d ] [path.txt] ' "$SED_LOG"
}

@test "git-sed: -c with uncommitted changes refuses to run (edge)" {
	printf '%s\n' 'dirty' >> file-A.txt
	local count_before
	count_before=$(commit_count)

	run git sed -c hello bye
	report "args=[-c] [hello] [bye] status=$status"
	report "output=[$output]"

	assert_failure 1
	assert_line 'you need to commit your changes before running with --commit'
	[ "$(cat greeting.txt)" = 'hello world hello' ]
	[ "$(commit_count)" = "$count_before" ]
}

@test "git-sed: -f without a value prints usage and fails (edge)" {
	run git sed -f
	report "args=[-f] status=$status last line=[${lines[${#lines[@]}-1]}]"

	assert_failure 1
	assert_line -n 0 -p 'usage: git sed'
	assert_line 'missing argument for -f'
}

@test "git-sed: an unknown flag prints usage and fails (edge)" {
	run git sed --porcelain hello bye
	report "args=[--porcelain] [hello] [bye] status=$status last line=[${lines[${#lines[@]}-1]}]"

	assert_failure 1
	assert_line 'unknown flag: --porcelain'
	[ "$(cat greeting.txt)" = 'hello world hello' ]
}

@test "git-sed: --help prints usage and changes nothing (edge)" {
	# "git sed --help" is intercepted by git itself (it opens the manual),
	# so the script's own --help branch is called directly.
	run git-sed --help
	report "args=[--help] status=$status first line=[${lines[0]}]"

	assert_success
	assert_line -n 0 -p 'usage: git sed'
	[ "$(git status --porcelain)" = '' ]
	[ ! -e "$SED_LOG" ]
}
