#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/test_util.sh"

setup_file() {
	test_util.setup_file
	test_util.install_command psykorebase
}

setup() {
	test_util.cd_test
	test_util.git_init
	echo "initial" > initial.txt
	git add initial.txt
	git commit -m "Initial commit"
}

@test "executes documented usage example with setup, command, output and state verification" {
	# Documented Setup:
	git checkout -b feature main
	echo "feature change" > feature.txt
	git add feature.txt && git commit -m "Add feature"
	git checkout main
	echo "main change" > main.txt
	git add main.txt && git commit -m "Update main"
	git checkout feature

	# Documented Command:
	run git psykorebase main --no-ff
	assert_success
	assert_line -p "Rebasing feature on top of main"

	# Documented State verification:
	run git rev-parse --abbrev-ref HEAD
	assert_output "feature"

	run git log -1 --pretty=%s
	assert_output "Psycho-rebased branch feature on top of main"

	[ -f feature.txt ]
	[ -f main.txt ]
	[ -f initial.txt ]
}

@test "rebases secondary branch on primary branch with fast-forward by default" {
	git checkout -b topic main
	echo "topic change" > topic.txt
	git add topic.txt && git commit -m "Topic commit"

	run git psykorebase main
	assert_success
	assert_line -p "Rebasing topic on top of main"

	run git rev-parse --abbrev-ref HEAD
	assert_output "topic"

	[ -f topic.txt ]
}

@test "explicit target and feature branch arguments: git psykorebase <target> <feature>" {
	git checkout -b topic main
	echo "topic commit" > topic.txt
	git add topic.txt && git commit -m "Topic commit"

	git checkout main
	echo "main commit" > main.txt
	git add main.txt && git commit -m "Main commit"

	run git psykorebase main topic --no-ff
	assert_success
	assert_line -p "Rebasing topic on top of main"

	run git rev-parse --abbrev-ref HEAD
	assert_output "topic"

	run git log -1 --pretty=%s
	assert_output "Psycho-rebased branch topic on top of main"

	[ -f topic.txt ]
	[ -f main.txt ]
}

@test "handles merge conflicts and resumes with --continue" {
	git checkout -b feature main
	echo "feature line" > conflict.txt
	git add conflict.txt && git commit -m "Feature commit"

	git checkout main
	echo "main line" > conflict.txt
	git add conflict.txt && git commit -m "Main commit"

	git checkout feature
	run git psykorebase main --no-ff
	assert_failure 1
	assert_line -p "Rebasing feature on top of main"
	assert_line -p "Resolve the conflict and run git psykorebase --continue."

	# Intermediate state
	run git rev-parse --abbrev-ref HEAD
	assert_output "feature-rebased-on-top-of-main"

	# Resolve conflict and continue
	echo "resolved conflict" > conflict.txt
	git add conflict.txt

	GIT_EDITOR=cat run git psykorebase --continue
	assert_success
	assert_line -p "Continuing rebasing of feature on top of main"

	# Final state
	run git rev-parse --abbrev-ref HEAD
	assert_output "feature"

	run git log -1 --pretty=%s
	assert_output "Psycho-rebased branch feature on top of main"

	[ -f conflict.txt ]
}

@test "--continue fails when not in a psykorebase branch" {
	run git psykorebase --continue
	assert_failure 30
	assert_line -p "Couldn't continue rebasing on main"
}

@test "missing target branch argument fails with exit 10" {
	run git psykorebase
	assert_failure 10
	assert_line -p "USAGE: git psykorebase PRIMARY_BRANCH"
}

@test "too many arguments fails with exit 20" {
	run git psykorebase branch1 branch2 branch3 extra
	assert_failure 20
	assert_line -p "USAGE: git psykorebase PRIMARY_BRANCH"
}

@test "-h and --help display usage and exit 0" {
	run git psykorebase -h
	assert_success
	assert_line -p "USAGE: git psykorebase PRIMARY_BRANCH"

	run git-psykorebase --help
	assert_success
	assert_line -p "USAGE: git psykorebase PRIMARY_BRANCH"
}
