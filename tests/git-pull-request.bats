# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command pull-request
}

setup() {
	test_util.cd_test
	# a token from the developer's own shell must not leak into the test
	unset GITHUB_TOKEN

	# Stub curl, first on PATH: it records its arguments instead of calling
	# the GitHub API.
	CURL_LOG="$BATS_TEST_TMPDIR/curl.log"
	export CURL_LOG
	mkdir stub
	cat > stub/curl <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$CURL_LOG"
printf '%s\n' '{"html_url": "https://github.com/owner/proj/pull/1"}'
EOF
	chmod +x stub/curl
	PATH="$BATS_TEST_TMPDIR/stub:$PATH"

	# Pushes go to a local bare repository; fetch URL looks like GitHub.
	git init --bare remote.git
	mkdir repo
	cd repo
	test_util.git_init
	for name in A B C; do
		printf '%s\n' "$name" > "file-$name.txt"
		git add .
		git commit -m "$name"
	done
	git checkout -b topic
	printf '%s\n' 'topic work' > topic.txt
	git add .
	git commit -m 'topic work'
	git remote add origin https://github.com/owner/proj.git
	git config remote.origin.pushurl "$BATS_TEST_TMPDIR/remote.git"
}

# Print one evidence line into the TAP report.
report() {
	local line
	while IFS= read -r line; do
		printf '# evidence: %s\n' "$line" >&3
	done <<< "$*"
}

# Run git pull-request, feeding the four prompt answers on stdin:
# answers <title> <body> <base> <2fa code> [git pull-request args...]
answers() {
	local input
	input=$(printf '%s\n' "$1" "$2" "$3" "$4")
	shift 4
	run bash -c 'printf "%s\n" "$1" | git pull-request "${@:2}"' _ "$input" "$@"
}

remote_branches() {
	git --git-dir="$BATS_TEST_TMPDIR/remote.git" for-each-ref --format='%(refname:short)' refs/heads | tr '\n' ' '
}

@test "git-pull-request: pushes the branch and posts the pull request (success)" {
	export GITHUB_TOKEN=test-token

	answers 'My title' 'My body' '' ''
	report "args=[] answers=[My title|My body||] status=$status"
	report "remote branches after=[$(remote_branches)]"
	report "curl arguments:"
	report "$(cat "$CURL_LOG")"

	assert_success
	assert_line 'no upstream found, push to origin as default'
	assert_line -p "create pull-request for owner/proj 'topic'"
	assert_output -p 'base [main]:'
	[ "$(remote_branches)" = 'topic ' ]
	grep -qxF 'https://api.github.com/repos/owner/proj/pulls' "$CURL_LOG"
	grep -qxF 'Authorization: token test-token' "$CURL_LOG"
	grep -qxF '  "title": "My title",' "$CURL_LOG"
	grep -qxF '  "body": "My body",' "$CURL_LOG"
	grep -qxF '  "head": "topic",' "$CURL_LOG"
	grep -qxF '  "base": "main"' "$CURL_LOG"
}

@test "git-pull-request: an answered base is used as given (success)" {
	export GITHUB_TOKEN=test-token

	answers 'T' 'B' 'release' ''
	report "answers=[T|B|release|] status=$status"

	assert_success
	grep -qxF '  "base": "release"' "$CURL_LOG"
}

@test "git-pull-request: an empty base answer uses git-extras.default-branch (success)" {
	export GITHUB_TOKEN=test-token
	git config git-extras.default-branch develop

	answers 'T' 'B' '' ''
	report "config git-extras.default-branch=develop answers=[T|B||] status=$status"
	report "prompt shown: $(grep -o 'base \[[^]]*\]' <<< "$output")"

	assert_success
	assert_output -p 'base [develop]:'
	grep -qxF '  "base": "develop"' "$CURL_LOG"
}

@test "git-pull-request: the branch argument picks the head branch (success)" {
	export GITHUB_TOKEN=test-token
	git checkout main

	answers 'T' 'B' '' '' topic
	report "args=[topic] (on main) status=$status"

	assert_success
	grep -qxF '  "head": "topic",' "$CURL_LOG"
	[ "$(remote_branches)" = 'topic ' ]
}

@test "git-pull-request: the token can come from git config (success)" {
	git config git-extras.github-personal-access-token config-token

	answers 'T' 'B' '' ''
	report "GITHUB_TOKEN unset, config token set, status=$status"

	assert_success
	grep -qxF 'Authorization: token config-token' "$CURL_LOG"
}

@test "git-pull-request: an ssh remote URL gives the same project name (success)" {
	export GITHUB_TOKEN=test-token
	git config remote.origin.url git@github.com:owner/proj.git

	answers 'T' 'B' '' ''
	report "remote url=git@github.com:owner/proj.git status=$status"

	assert_success
	grep -qxF 'https://api.github.com/repos/owner/proj/pulls' "$CURL_LOG"
}

@test "git-pull-request: double quotes in the title are escaped in the JSON (success)" {
	export GITHUB_TOKEN=test-token

	answers 'say "hi"' 'B' '' ''
	report "answers=[say \"hi\"|B||] status=$status"

	assert_success
	grep -qxF '  "title": "say \"hi\"",' "$CURL_LOG"
}

@test "git-pull-request: no token stops before pushing or calling the API (edge)" {
	answers 'T' 'B' '' ''
	report "GITHUB_TOKEN unset, no config token, status=$status output=[$output]"
	report "remote branches after=[$(remote_branches)]"

	assert_failure 1
	assert_output 'GITHUB_TOKEN or git config git-extras.github-personal-access-token required'
	[ "$(remote_branches)" = '' ]
	[ ! -e "$CURL_LOG" ]
}

@test "git-pull-request: a local upstream (.) is rejected (edge)" {
	export GITHUB_TOKEN=test-token
	git config branch.topic.remote .

	answers 'T' 'B' '' ''
	report "branch.topic.remote=. status=$status output=[$output]"

	assert_failure 1
	assert_output 'the upstream should be a remote branch.'
	[ "$(remote_branches)" = '' ]
	[ ! -e "$CURL_LOG" ]
}

@test "git-pull-request: a failed push stops before calling the API (edge)" {
	export GITHUB_TOKEN=test-token
	git config remote.origin.pushurl "$BATS_TEST_TMPDIR/does-not-exist.git"

	answers 'T' 'B' '' ''
	report "pushurl points to a missing repository, status=$status"
	report "last line=[${lines[${#lines[@]}-1]}]"

	assert_failure 1
	assert_line 'failed to push topic'
	[ ! -e "$CURL_LOG" ]
}
