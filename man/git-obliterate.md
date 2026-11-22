git-obliterate(1) -- rewrite past commits to remove some files
===============================

## SYNOPSIS

git obliterate &lt;files...&gt; [-- &lt;rev-list options...&gt;]

## DESCRIPTION

Completely remove some files from the repository, including past commits and tags. 
WARNING! This command will rewrite the history similar to `git rebase`(though it affects more). The rewritten history will have different object names for all the objects and will not converge with the original branch. So **avoid using it on commits that you shared**.
And it will mess up stash, so **don't have stash when you run `git obliterate`**.

## OPTIONS

  &lt;files...&gt;

  One or more files to remove from the repository history. At least one file is required; if omitted, the command terminates with `file required.` and exits with status 1.

  -- &lt;rev-list options...&gt;

  Optional rev-list options to restrict the range of commits affected (such as `feature ^origin` or `abcdefg..1234567`), separated from the file list by `--`. Run `git help rev-list` to see acceptable options. When omitted, all commits on all refs (`--all`) are rewritten.

  -h, --help

  Show usage information.

## EXAMPLES

  Complete removal of a secret file from repository history:

  Setup:

    $ git init --quiet --initial-branch=main repo && cd repo
    $ git config user.name "Example"
    $ git config user.email "example@example.com"
    $ echo "safe content" > safe.txt
    $ echo "secret content" > secret.txt
    $ git add safe.txt secret.txt && git commit -q -m "Initial commit with secret"
    $ echo "updated safe content" >> safe.txt
    $ git commit -q -am "Update safe file"

  Command:

    $ git obliterate secret.txt

  Output:

    Ref 'refs/heads/main' was rewritten

  State verification:

    $ git log -- secret.txt
    # (no output: secret.txt is removed from history)
    $ ls secret.txt 2>/dev/null || echo "not found"
    not found
    $ git ls-files
    safe.txt

  Remove .secret from the repository:

    $ git obliterate .secret

  Remove .secret from commits between origin and feature:

    $ git obliterate .secret -- feature ^origin

  Remove .secret from commit abcdefg to commit 1234567

    $ git obliterate .secret -- abcdefg..1234567

## AUTHOR

Written by &lt;<brianloveswords@gmail.com>&gt;

## REPORTING BUG

&lt;<https://github.com/tj/git-extras/issues>&gt;

## SEE ALSO

&lt;<https://github.com/tj/git-extras>&gt;
