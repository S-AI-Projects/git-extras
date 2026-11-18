# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
}

setup() {
	test_util.cd_test

	test_util.git_init
	git commit --allow-empty -m "Initial commit"
	git branch A
	git branch B
	git checkout A
	printf '%s\n' 'a' > tmpfile
	git add .
	git commit -m A
	git checkout B
	printf '%s\n' 'b' > tmpfile
	git add .
	git commit -m B
	git status
}

repo_state() {
	python3 - <<'PY'
import json
import pathlib
import subprocess

def git(*args):
    return subprocess.run(["git", *args], text=True, capture_output=True, check=False)

gitdir = pathlib.Path(git("rev-parse", "--git-dir").stdout.strip())
print(json.dumps({
    "head": git("rev-parse", "HEAD").stdout.strip(),
    "status": git("status", "--porcelain").stdout.splitlines(),
    "operation_markers": sorted(path.name for path in gitdir.glob("*_HEAD")),
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
        "name": "explicit git-dir abort with no active operation is a safe failure",
        "argv": ["git", "--git-dir", ".git", "abort"],
        "exit_status": int(status),
        "before": json.loads(before),
        "after": json.loads(after),
        "output": output,
    }) + "\n")
PY
}

@test "explicit git-dir abort with no active operation is a safe failure" {
	local before after
	before="$(repo_state)"
	run git --git-dir .git abort
	after="$(repo_state)"
	record_scenario "$status" "$before" "$after" "$output"
	assert_failure 1
	assert_output --partial 'No active operation found; nothing to abort or continue'
	assert_equal "$(repo_state)" "$before"
}

@test "works with cherry pick" {
	run git cherry-pick A
	assert_failure

	run git status
	assert_line -p 'You are currently cherry-picking commit'
	assert_line -p 'Unmerged paths:'
	assert_success

	run git abort
	assert_success

	run git status
	assert_line -p 'nothing to commit, working tree clean'
	assert_success
}

@test "works with merge" {
	run git merge A
	assert_failure

	run git status
	assert_line -p 'You have unmerged paths'
	assert_line -p 'Unmerged paths:'
	assert_success

	run git abort
	assert_success

	run git status
	assert_line -p 'nothing to commit, working tree clean'
	assert_success
}

@test "works with rebase" {
	run git rebase A
	assert_failure

	run git status
	assert_line -p 'You are currently rebasing branch'
	assert_line -p 'Unmerged paths:'
	assert_success

	run git abort
	assert_success

	run git status
	assert_line -p 'nothing to commit, working tree clean'
	assert_success
}

@test "works with revert" {
	run git revert A
	assert_failure

	run git status
	assert_line -p 'You are currently reverting commit'
	assert_line -p 'Unmerged paths:'
	assert_success

	run git abort
	assert_success

	run git status
	assert_line -p 'nothing to commit, working tree clean'
	assert_success
}
