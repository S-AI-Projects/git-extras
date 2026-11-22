# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command ignore-io
}

mock_env() {
	local mock_bin="$BATS_TEST_TMPDIR/mock_bin"
	mkdir -p "$mock_bin"

	# Mock curl to return fixtures without internet access
	cat << 'EOF' > "$mock_bin/curl"
#!/usr/bin/env bash
url=""
for arg; do
    case "$arg" in
        http*) url="$arg" ;;
    esac
done
case "$url" in
    *Python.gitignore)
        printf '# Python\n*.py[cod]\n__pycache__/\n'
        ;;
    *Vim.gitignore)
        printf '# Vim\n[._]*.s[a-w][a-z]\n*.un~\n'
        ;;
    *Node.gitignore)
        printf '# Node\nnode_modules/\nnpm-debug.log\n'
        ;;
    *)
        exit 22
        ;;
esac
EOF
	chmod +x "$mock_bin/curl"
	PATH="$mock_bin:$PATH"

	# Seed gi_list cache so check_list_exist does not contact GitHub
	export XDG_CACHE_HOME="$BATS_TEST_TMPDIR/cache"
	mkdir -p "$XDG_CACHE_HOME/git-extras"
	printf '%s\n' "C" "Global/Vim" "Node" "Python" "Rust" > "$XDG_CACHE_HOME/git-extras/gi_list"
}

setup() {
	test_util.cd_test
	test_util.git_init
	mock_env
}

@test "git-ignore-io: displays usage with -h and --help" {
	run git ignore-io -h
	assert_success
	assert_line -p "Usage:"

	run git-ignore-io --help
	assert_success
	assert_line -p "Usage:"
}

@test "git-ignore-io: --replace creates or overwrites .gitignore with template" {
	printf '%s\n' 'legacy content' > .gitignore

	run git ignore-io --replace Python
	assert_success

	assert [ -f .gitignore ]
	run cat .gitignore
	assert_line -p "*.py[cod]"
	assert_line -p "__pycache__/"
	refute_line -p "legacy content"

	# Ensure no leftover temporary files
	run ls -A .gitignore.tmp.*
	assert_failure
}

@test "git-ignore-io: --append appends template to existing .gitignore" {
	printf '%s\n' 'existing content' > .gitignore

	run git ignore-io --append Vim
	assert_success

	run cat .gitignore
	assert_line -p "existing content"
	assert_line -p "[._]*.s[a-w][a-z]"
}

@test "git-ignore-io: --list-alphabetically prints types in alphabetical order" {
	run git ignore-io --list-alphabetically
	assert_success
	assert_line -p "Python"
	assert_line -p "Global/Vim"
}

@test "git-ignore-io: --list-in-table prints types in columns" {
	run git ignore-io --list-in-table
	assert_success
	assert_line -p "Python"
}

@test "git-ignore-io: fails with documented error when template is not found" {
	run git ignore-io NonexistentTemplate
	assert_failure
	assert_line -p "Template not found: NonexistentTemplate"
}

@test "git-ignore-io: fails when --replace or --append is called with no types" {
	run git ignore-io --replace
	assert_failure
	assert_line -p "There should be at least one type"

	run git ignore-io --append
	assert_failure
	assert_line -p "There should be at least one type"
}
