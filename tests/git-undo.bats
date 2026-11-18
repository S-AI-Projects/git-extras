#!/usr/bin/env bats
# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command undo
}

setup() {
	test_util.cd_test
	test_util.git_init

	printf '%s\n' 'A' > a.txt
	git add a.txt
	git commit -m 'A'
	git switch -c topic
	printf '%s\n' 'B' >> a.txt
	git add a.txt
	git commit -m 'B'
	printf '%s\n' 'C' >> a.txt
	git add a.txt
	git commit -m 'C'
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
    "main_ref": git("rev-parse", "refs/heads/main").stdout.strip(),
    "topic_ref": git("rev-parse", "refs/heads/topic").stdout.strip(),
    "status": git("status", "--porcelain").stdout.splitlines(),
    "files": {"a.txt": open("a.txt", encoding="utf-8").read()},
    "user_name": git("config", "--local", "--get", "user.name").stdout.strip(),
    "user_email": git("config", "--local", "--get", "user.email").stdout.strip(),
}))
PY
}

record_scenario() {
	local name="$1" argv="$2" status="$3" before="$4" after="$5" output="$6"
	[[ -n "${R13_SCENARIO_LOG:-}" ]] || return 0
	python3 - "$R13_SCENARIO_LOG" "$name" "$argv" "$status" "$before" "$after" "$output" <<'PY'
import json
import sys

path, name, argv, status, before, after, output = sys.argv[1:]
with open(path, "a", encoding="utf-8") as stream:
    stream.write(json.dumps({
        "name": name,
        "argv": json.loads(argv),
        "exit_status": int(status),
        "before": json.loads(before),
        "after": json.loads(after),
        "output": output,
    }) + "\n")
PY
}

@test "undo removes one latest commit using only temporary repository config" {
	before="$(repo_state)"
	run git-undo
	after="$(repo_state)"
	record_scenario "$BATS_TEST_DESCRIPTION" '["git-undo"]' "$status" "$before" "$after" "$output"

	assert_success
	assert_equal "$(git log -1 --format=%s)" 'B'
	assert_equal "$(git rev-parse refs/heads/main)" "$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["main_ref"])' "$before")"
	assert_equal "$(cat a.txt)" $'A\nB\nC'
	assert_equal "$(git status --porcelain)" 'M  a.txt'
	assert_equal "$(git config --local --get user.name)" 'Name'
	assert_equal "$(git config --local --get user.email)" 'name@example.com'
}

@test "reports a missing git executable without changing the repository" {
	before="$(repo_state)"
	no_git="$BATS_TEST_TMPDIR/.git/no-git-bin"
	mkdir -p "$no_git"
	if missing_output="$(/usr/bin/env "PATH=$no_git" /bin/bash "$BATS_TEST_DIRNAME/../bin/git-undo" 2>&1)"; then
		missing_status=0
	else
		missing_status=$?
	fi
	after="$(repo_state)"
	record_scenario "$BATS_TEST_DESCRIPTION" "[\"/bin/bash\", \"$BATS_TEST_DIRNAME/../bin/git-undo\"]" "$missing_status" "$before" "$after" "$missing_output"

	assert_equal "$missing_status" 127
	assert_equal "$missing_output" 'git undo: git executable not found on PATH'
	assert_equal "$after" "$before"
}
