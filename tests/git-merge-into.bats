# shellcheck shell=bash

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command merge-into
}

setup() {
	test_util.cd_test
	test_util.git_init
	printf '%s\n' "Initial" > init.txt
	git add init.txt
	git commit -m "Initial commit"
}

@test "git-merge-into -h displays usage screen" {
	run git merge-into -h
	assert_success
	assert_line -p "Usage: git merge-into"
}

@test "git-merge-into without arguments fails with usage" {
	run git merge-into
	assert_failure
	assert_equal "$status" 1
	assert_line -p "Usage: git merge-into"
}

@test "git-merge-into merges current branch into destination and returns to current" {
	git checkout -b feature
	echo "Feature work" > feature.txt
	git add feature.txt
	git commit -m "Feature commit"

	run git merge-into main
	assert_success

	run git rev-parse --abbrev-ref HEAD
	assert_output "feature"

	run git log main --oneline -n 1
	assert_line -p "Feature commit"
}

@test "git-merge-into merges explicit src branch into dest branch" {
	git checkout -b branch_a
	echo "A" > a.txt
	git add a.txt
	git commit -m "Commit A"

	git checkout -b branch_b
	echo "B" > b.txt
	git add b.txt
	git commit -m "Commit B"

	run git merge-into branch_a main
	assert_success

	run git rev-parse --abbrev-ref HEAD
	assert_output "branch_b"

	run git log main --oneline -n 1
	assert_line -p "Commit A"
}

@test "git-merge-into with --ff-only fast-forwards destination branch" {
	git checkout -b feature_ff
	echo "Fast forward" > ff.txt
	git add ff.txt
	git commit -m "Fast forward commit"

	run git merge-into main --ff-only
	assert_success

	run git rev-parse --abbrev-ref HEAD
	assert_output "feature_ff"

	run git log main --oneline -n 1
	assert_line -p "Fast forward commit"
}

@test "git-merge-into with --ff-only fails on non-fast-forward divergence" {
	git checkout -b topic
	echo "Topic commit" > topic.txt
	git add topic.txt
	git commit -m "Topic commit"

	git checkout main
	echo "Main diverged" > main_div.txt
	git add main_div.txt
	git commit -m "Main diverged commit"

	git checkout topic
	run git merge-into main --ff-only
	assert_failure
	assert_equal "$status" 1

	run git rev-parse --abbrev-ref HEAD
	assert_output "topic"

	run git log main --oneline -n 1
	refute_line -p "Topic commit"
}

@test "git-merge-into automatically stashes and pops uncommitted modifications" {
	git checkout -b stashed_branch
	echo "clean commit" > clean.txt
	git add clean.txt
	git commit -m "clean commit"

	echo "uncommitted change" > uncommitted.txt

	run git merge-into main --ff-only
	assert_success
	assert_line -p "Local modifications detected, stashing"

	run git status --porcelain
	assert_line -p "uncommitted.txt"
}
