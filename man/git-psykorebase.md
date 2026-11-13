git-psykorebase(1) -- Rebase a branch with a merge commit
=========================================================

## SYNOPSIS

`git psykorebase` [-h|--help]  
`git psykorebase` &lt;target_branch&gt; [&lt;feature_branch&gt;] [--no-ff]  
`git psykorebase` --continue

## DESCRIPTION

Rebase the `feature_branch` on top of the `target_branch`, the
`feature_branch` defaults to the current one.

## OPTIONS

  `-h, --help`
  Show usage information.

  `--no-ff`
  Force a commit message even if there are no conflicts.

  `-c, --continue`
  Continue the rebase after conflicts have been resolved.

## EXAMPLES

Complete rebase of a feature branch on top of main with merge commit:

  Setup:

    $ git checkout -b feature main
    $ echo "feature change" > feature.txt
    $ git add feature.txt && git commit -m "Add feature"
    $ git checkout main
    $ echo "main change" > main.txt
    $ git add main.txt && git commit -m "Update main"
    $ git checkout feature

  Command:

    $ git psykorebase main --no-ff

  Output:

    Rebasing feature on top of main

  State verification:

    $ git rev-parse --abbrev-ref HEAD
    feature
    $ git log -1 --pretty=%s
    Psycho-rebased branch feature on top of main
    $ test -f feature.txt && test -f main.txt && echo "State verified"
    State verified

Handle conflicts:

    $ git add README.md

Continue rebase:

    $ git psykorebase --continue

## AUTHOR

Written by Rémy Hubscher &lt;<hubscher.remy@gmail.com>&gt;

Based on Benoît Bryon &lt;<benoit@marmelune.net>&gt; implementation in
Python.

## REPORTING BUGS

&lt;<https://github.com/tj/git-extras/issues>&gt;

## SEE ALSO

&lt;<https://github.com/tj/git-extras>&gt;

&lt;<https://github.com/benoitbryon/psykorebase>&gt;
