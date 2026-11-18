#!/usr/bin/env bats
# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command guilt
}

setup() {
	test_util.cd_test
	test_util.git_init

	git config --local user.name Alice
	git config --local user.email alice@example.com
	for i in {1..50}; do printf 'Alice line %02d\n' "$i"; done > contributions.txt
	git add contributions.txt
	GIT_AUTHOR_DATE='2020-01-01T00:00:00+0000' GIT_COMMITTER_DATE='2020-01-01T00:00:00+0000' git commit -m A
	base="$(git rev-parse HEAD)"

	git switch -c topic
	git config --local user.name Bob
	git config --local user.email bob@example.com
	for i in {1..50}; do printf 'Bob line %02d\n' "$i"; done > contributions.txt
	git add contributions.txt
	GIT_AUTHOR_DATE='2020-01-02T00:00:00+0000' GIT_COMMITTER_DATE='2020-01-02T00:00:00+0000' git commit -m B
	head_commit="$(git rev-parse HEAD)"
}

repo_state() {
	python3 - <<'PY'
import json
import subprocess

def git(*args):
    return subprocess.run(["git", *args], text=True, capture_output=True, check=False)

print(json.dumps({
    "branch": git("branch", "--show-current").stdout.strip(),
    "head": git("rev-parse", "HEAD").stdout.strip(),
    "base_ref": git("rev-parse", "refs/heads/main").stdout.strip(),
    "topic_ref": git("rev-parse", "refs/heads/topic").stdout.strip(),
    "status": git("status", "--porcelain").stdout.splitlines(),
    "file": open("contributions.txt", encoding="utf-8").read(),
}))
PY
}

record_scenario() {
	local name="$1" status="$2" before="$3" after="$4" output="$5"
	shift 5
	[[ -n "${R13_SCENARIO_LOG:-}" ]] || return 0
	python3 - "$R13_SCENARIO_LOG" "$name" "$status" "$before" "$after" "$output" "$@" <<'PY'
import json
import sys

path, name, status, before, after, output, *argv = sys.argv[1:]
with open(path, "a", encoding="utf-8") as stream:
    stream.write(json.dumps({
        "name": name,
        "argv": argv,
        "exit_status": int(status),
        "before": json.loads(before),
        "after": json.loads(after),
        "output": output,
    }) + "\n")
PY
}

@test "characterizes positive and negative contribution bars at the 50-line boundary" {
	before="$(repo_state)"
	run git-guilt "$base" "$head_commit"
	after="$(repo_state)"
	record_scenario "$BATS_TEST_DESCRIPTION" "$status" "$before" "$after" "$output" git-guilt "$base" "$head_commit"

	assert_failure 1
	plus_bar="$(printf '%46s' '' | tr ' ' '+')"
	minus_bar="$(printf '%45s' '' | tr ' ' '-')"
	expected="$(printf '%-29s %s(50)\n%-29s %s(-50)' Bob "$plus_bar" Alice "$minus_bar")"
	plain_output="$(printf '%s' "$output" | sed -E $'s/\033\\[[0-9;]*m//g')"
	assert_equal "$plain_output" "$expected"
	assert_equal "$after" "$before"
}

@test "characterizes email labeling without changing contribution counts" {
	before="$(repo_state)"
	run git-guilt --email "$base" "$head_commit"
	after="$(repo_state)"
	record_scenario "$BATS_TEST_DESCRIPTION" "$status" "$before" "$after" "$output" git-guilt --email "$base" "$head_commit"

	assert_failure 1
	plus_bar="$(printf '%46s' '' | tr ' ' '+')"
	minus_bar="$(printf '%45s' '' | tr ' ' '-')"
	expected="$(printf '%-29s %s(50)\n%-29s %s(-50)' bob@example.com "$plus_bar" alice@example.com "$minus_bar")"
	plain_output="$(printf '%s' "$output" | sed -E $'s/\033\\[[0-9;]*m//g')"
	assert_equal "$plain_output" "$expected"
	assert_equal "$after" "$before"
}
