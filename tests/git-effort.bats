#!/usr/bin/env bats
# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command effort
}

setup() {
	test_util.cd_test
	test_util.git_init

	mkdir -p 'dir with spaces'
	printf '%s\n' 'special path' > 'dir with spaces/name[*].txt'
	printf '%s\n' 'matching shell glob' > 'dir with spaces/name*.txt'
	printf '%s\n' 'unrelated' > unrelated.txt
	git add .
	git commit -m 'A: add effort fixtures'

	git switch -c topic
	printf '%s\n' 'topic file' > topic.txt
	git add topic.txt
	git commit -m 'B: add topic file'
	printf '%s\n' 'later' >> unrelated.txt
	git add unrelated.txt
	git commit -m 'C: update unrelated file'

	REAL_GIT="$(command -v git)"
	GIT_LOG_ARGS="$BATS_TEST_TMPDIR/.git/git-log-argv.jsonl"
	export REAL_GIT GIT_LOG_ARGS
	stub_bin="$BATS_TEST_TMPDIR/.git/git-stub-bin"
	mkdir -p "$stub_bin"
	cat > "$stub_bin/git" <<'SH'
#!/usr/bin/env bash
if [[ "$1" == log ]]; then
	python3 - "$GIT_LOG_ARGS" "$@" <<'PY'
import json
import sys
with open(sys.argv[1], "a", encoding="utf-8") as stream:
    stream.write(json.dumps(sys.argv[2:]) + "\n")
PY
fi
exec "$REAL_GIT" "$@"
SH
	chmod +x "$stub_bin/git"
	PATH="$stub_bin:$PATH"
	export PATH TERM=dumb
}

repo_state() {
	python3 - <<'PY'
import json
import pathlib
import subprocess

def git(*args):
    return subprocess.run(["git", *args], text=True, capture_output=True, check=False)

files = {str(path): path.read_text(encoding="utf-8") for path in pathlib.Path(".").rglob("*.txt") if ".git" not in path.parts}
print(json.dumps({
    "branch": git("branch", "--show-current").stdout.strip(),
    "head": git("rev-parse", "HEAD").stdout.strip(),
    "status": git("status", "--porcelain").stdout.splitlines(),
    "files": files,
}))
PY
}

record_scenario() {
	local name="$1" argv="$2" status="$3" before="$4" after="$5" output="$6" git_log_args="$7"
	[[ -n "${R13_SCENARIO_LOG:-}" ]] || return 0
	python3 - "$R13_SCENARIO_LOG" "$name" "$argv" "$status" "$before" "$after" "$output" "$git_log_args" <<'PY'
import json
import sys

path, name, argv, status, before, after, output, git_log_args = sys.argv[1:]
with open(path, "a", encoding="utf-8") as stream:
    stream.write(json.dumps({
        "name": name,
        "argv": json.loads(argv),
        "exit_status": int(status),
        "before": json.loads(before),
        "after": json.loads(after),
        "output": output,
        "git_log_argv": [json.loads(line) for line in git_log_args.splitlines()],
    }) + "\n")
PY
}

@test "passes one quoted path containing spaces and a wildcard as one argument" {
	before="$(repo_state)"
	path='dir with spaces/name[*].txt'
	run git-effort "$path"
	after="$(repo_state)"
	git_log_args="$(cat "$GIT_LOG_ARGS")"
	record_scenario "$BATS_TEST_DESCRIPTION" "[\"git-effort\", \"$path\"]" "$status" "$before" "$after" "$output" "$git_log_args"

	assert_success
	assert_output --partial "$path"
	assert_equal "$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])[-1])' "$git_log_args")" "$path"
	assert_equal "$after" "$before"
	assert_equal "$(git status --porcelain)" ''
}

@test "enumerates special filenames without shell glob expansion" {
	before="$(repo_state)"
	run git-effort
	after="$(repo_state)"
	git_log_args="$(cat "$GIT_LOG_ARGS")"
	record_scenario "$BATS_TEST_DESCRIPTION" '["git-effort"]' "$status" "$before" "$after" "$output" "$git_log_args"

	assert_success
	assert_output --partial 'dir with spaces/name[*].txt'
	assert_equal "$(git status --porcelain)" ''
	assert_equal "$after" "$before"
	assert_equal "$(python3 -c 'import json,sys; print(json.dumps(sorted(json.loads(x)[-1] for x in sys.argv[1].splitlines())))' "$git_log_args")" '["dir with spaces/name*.txt", "dir with spaces/name[*].txt", "topic.txt", "unrelated.txt"]'
}
