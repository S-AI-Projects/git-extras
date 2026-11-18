#!/usr/bin/env bats
# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command sed
}

setup() {
	test_util.cd_test
	test_util.git_init
	git config --local user.name Example
	git config --local user.email example@example.com
	printf 'hello hello\n' > note.txt
	git add note.txt
	git commit -q -m 'Add note'
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
    "status": git("status", "--porcelain").stdout.splitlines(),
    "staged_diff": git("diff", "--cached", "--numstat").stdout.splitlines(),
    "file": open("note.txt", encoding="utf-8").read(),
}))
PY
}

record_scenario() {
	local status="$1" before="$2" after="$3" output="$4"
	[[ -n "${R13_SCENARIO_LOG:-}" ]] || return 0
	python3 - "$R13_SCENARIO_LOG" "$status" "$before" "$after" "$output" <<'PY'
import json
import sys

path, status, before, after, output = sys.argv[1:]
with open(path, "a", encoding="utf-8") as stream:
    stream.write(json.dumps({
        "name": "documented git-sed example replaces text and verifies the working tree",
        "argv": ["git-sed", "-f", "g", "hello", "goodbye", "--", "note.txt"],
        "exit_status": int(status),
        "before": json.loads(before),
        "after": json.loads(after),
        "output": output,
    }) + "\n")
PY
}

@test "executes the documented git-sed example and verifies its state" {
	before="$(repo_state)"
	run git-sed -f g hello goodbye -- note.txt
	after="$(repo_state)"
	record_scenario "$status" "$before" "$after" "$output"

	assert_success
	assert_output ''
	assert_equal "$(cat note.txt)" 'goodbye goodbye'
	assert_equal "$(git diff --numstat -- note.txt)" $'1\t1\tnote.txt'
	assert_equal "$(git status --porcelain)" ' M note.txt'
	assert_equal "$(git diff --cached --numstat)" ''
	assert_equal "$(git rev-parse HEAD)" "$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["head"])' "$before")"
}
