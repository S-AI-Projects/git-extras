#!/usr/bin/env bats
# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
}

setup() {
	test_util.cd_test
	test_util.git_init

	printf '%s\n' 'base value' > tracked.txt
	printf '%s\n' 'keep this' > unrelated.txt
	git add tracked.txt unrelated.txt
	git commit -m 'A: add fixture files'

	git switch -c topic
	printf '%s\n' 'topic change' >> unrelated.txt
	git add unrelated.txt
	git commit -m 'B: update unrelated file on topic'
	git switch main

	printf '%s\n' 'dirty change' >> tracked.txt
	REAL_GIT="$(command -v git)"
	GIT_STUB_PUSH_LOG="$BATS_TEST_TMPDIR/.git/push.log"
	export REAL_GIT GIT_STUB_PUSH_LOG
	stub_bin="$BATS_TEST_TMPDIR/.git/stub-bin"
	mkdir -p "$stub_bin"
	cat > "$stub_bin/git" <<'SH'
#!/usr/bin/env bash
if [[ "$1" == push ]]; then
	printf '%s\n' "$*" >> "$GIT_STUB_PUSH_LOG"
	exit 0
fi
exec "$REAL_GIT" "$@"
SH
	chmod +x "$stub_bin/git"
	PATH="$stub_bin:$PATH"
	export PATH
}

repo_state() {
	python3 - "$GIT_STUB_PUSH_LOG" <<'PY'
import json
import pathlib
import subprocess
import sys

def git(*args):
    return subprocess.run(["git", *args], text=True, capture_output=True, check=False)

files = {}
for name in ("tracked.txt", "unrelated.txt", "index.html"):
    path = pathlib.Path(name)
    files[name] = path.read_text(encoding="utf-8") if path.exists() else None
remote = git("config", "--get", "remote.origin.url")
push_log = pathlib.Path(sys.argv[1])
main_ref = git("rev-parse", "refs/heads/main")
topic_ref = git("rev-parse", "refs/heads/topic")
print(json.dumps({
    "branch": git("branch", "--show-current").stdout.strip(),
    "head": git("rev-parse", "HEAD").stdout.strip(),
    "main_ref": main_ref.stdout.strip(),
    "topic_ref": topic_ref.stdout.strip(),
    "status": git("status", "--porcelain").stdout.splitlines(),
    "stash_list": git("stash", "list").stdout.splitlines(),
    "remote_origin": remote.stdout.strip() if remote.returncode == 0 else None,
    "files": files,
    "push_argv": push_log.read_text(encoding="utf-8").splitlines() if push_log.exists() else [],
}))
PY
}

record_scenario() {
	local status="$1" before="$2" after="$3" output="$4" script="$5"
	[[ -n "${R13_SCENARIO_LOG:-}" ]] || return 0
	python3 - "$R13_SCENARIO_LOG" "$status" "$before" "$after" "$output" "$script" <<'PY'
import json
import sys

path, status, before, after, output, script = sys.argv[1:]
record = {
    "name": "creates gh-pages while preserving the original branch state",
    "argv": [script],
    "stdin": ["sampleuser", "samplerepo"],
    "exit_status": int(status),
    "before": json.loads(before),
    "after": json.loads(after),
    "output": output,
}
with open(path, "a", encoding="utf-8") as stream:
    stream.write(json.dumps(record) + "\n")
PY
}

@test "creates gh-pages while preserving the original branch state" {
	main_ref_before="$(git rev-parse refs/heads/main)"
	topic_ref_before="$(git rev-parse refs/heads/topic)"
	before="$(repo_state)"
	run bash -c "printf '%s\\n' sampleuser samplerepo | '$BATS_TEST_DIRNAME/../bin/git-gh-pages'"
	after="$(repo_state)"
	record_scenario "$status" "$before" "$after" "$output" "$BATS_TEST_DIRNAME/../bin/git-gh-pages"

	assert_success
	assert_output --partial 'setting up gh-pages'
	assert_output --partial 'Complete'
	assert_equal "$(git branch --show-current)" 'gh-pages'
	assert_equal "$(git rev-parse refs/heads/main)" "$main_ref_before"
	assert_equal "$(git rev-parse refs/heads/topic)" "$topic_ref_before"
	assert_equal "$(cat index.html)" 'My Page'
	assert_equal "$(cat unrelated.txt)" 'keep this'
	assert_equal "$(cat tracked.txt)" 'base value'
	assert_equal "$(git config --get remote.origin.url)" 'https://github.com/sampleuser/samplerepo.git'
	assert_equal "$(cat "$GIT_STUB_PUSH_LOG")" 'push -u origin gh-pages'
	assert_equal "$(git status --porcelain)" ''
}
