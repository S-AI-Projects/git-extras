#!/usr/bin/env bats

load ./test_util.sh

setup() {
  mkdir -p "$BATS_TEST_TMPDIR/repo"
  cd "$BATS_TEST_TMPDIR/repo"
  git init
  git config user.name "Test User"
  git config user.email "test@example.com"
  echo "test" > file.txt
  git add file.txt
  git commit -m "initial commit"
}

@test "git-locked: minimum accepted arguments (no args)" {
  run "$BATS_TEST_DIRNAME/../bin/git-locked"
  [ "$status" -eq 0 ]
}

@test "git-locked: optional argument handling (--help)" {
  run "$BATS_TEST_DIRNAME/../bin/git-locked" --help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage:" ]]
}

@test "git-locked: invalid argument combination" {
  run "$BATS_TEST_DIRNAME/../bin/git-locked" --invalid-flag-xyz
  [ "$status" -ne 0 ]
}
 