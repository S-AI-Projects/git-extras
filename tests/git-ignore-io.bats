#!/usr/bin/env bats
# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command ignore-io
}

setup() {
	test_util.cd_test
	test_util.git_init
	export XDG_CACHE_HOME="$BATS_FILE_TMPDIR/xdg-cache"
	mkdir -p "$XDG_CACHE_HOME/git-extras"
	printf 'Vim\nPython\n' > "$XDG_CACHE_HOME/git-extras/gi_list"
	printf 'keep-me\n' > .gitignore
	git add .gitignore
	git commit -q -m 'Add existing ignore rules'

	local mock_bin="$BATS_FILE_TMPDIR/mock-bin"
	mkdir -p "$mock_bin"
	cat > "$mock_bin/curl" <<'MOCK'
#!/usr/bin/env bash
case "$*" in
  *Vim.gitignore)
    printf '# Vim rules\n*.swp\n'
    ;;
  *)
    echo "Unexpected curl request: $*" >&2
    exit 22
    ;;
esac
MOCK
	chmod +x "$mock_bin/curl"
	PATH="$mock_bin:$PATH"
}

repo_state() {
	python3 - <<'PY'
import glob
import json
import pathlib
import subprocess

def git(*args):
    return subprocess.run(["git", *args], text=True, capture_output=True, check=False)

path = pathlib.Path(".gitignore")
print(json.dumps({
    "head": git("rev-parse", "HEAD").stdout.strip(),
    "status": git("status", "--porcelain").stdout.splitlines(),
    "gitignore_exists": path.exists(),
    "gitignore": path.read_text(encoding="utf-8") if path.exists() else None,
    "temporary_files": sorted(glob.glob(".gitignore.tmp.*")),
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

@test "diagnoses an unknown template and succeeds with the corrected name" {
	local before after
	before="$(repo_state)"
	run git-ignore-io --replace Vmi
	after="$(repo_state)"
	record_scenario "unknown template is rejected without changing the file" '["git-ignore-io", "--replace", "Vmi"]' "$status" "$before" "$after" "$output"
	assert_failure 1
	assert_output --partial 'Template not found: Vmi. Use --list-alphabetically to see available templates.'
	assert_equal "$(cat .gitignore)" 'keep-me'
	assert_equal "$(git status --porcelain)" ''
	assert_equal "$(find . -maxdepth 1 -name '.gitignore.tmp.*' -print)" ''

	before="$(repo_state)"
	run git-ignore-io --replace Vim
	after="$(repo_state)"
	record_scenario "listed template succeeds after correcting the name" '["git-ignore-io", "--replace", "Vim"]' "$status" "$before" "$after" "$output"
	assert_success
	assert_output ''
	assert_equal "$(cat .gitignore)" $'# Vim rules\n*.swp'
	assert_equal "$(git status --porcelain)" ' M .gitignore'
	assert_equal "$(find . -maxdepth 1 -name '.gitignore.tmp.*' -print)" ''
	assert_equal "$(git rev-parse HEAD)" "$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["head"])' "$before")"
}
