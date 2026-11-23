git-brv(1) -- List branches sorted by their last commit date
========================================================

## SYNOPSIS

`git brv` [-r|--reverse]

## DESCRIPTION

  Pretty listing of branches sorted by the date of their last commit.

## OPTIONS

  -r | --reverse

  Reverses the output to put the most recent branch at the bottom of the list. This is useful when there are large amount of branches as the most recent branch is shown just above the next prompt. This can be configured as the default by setting `git-extras.brv.reverse` to true in your git options.

## EXAMPLES

  Simply run `git brv`

    $ git brv
    2020-01-14 adds-git-brv fork/adds-git-brv 1ca0d76 Fixes #700: Adds git-brv
    2020-01-08 master       origin/master     265b03e Merge pull request #816 from spacewander/git-sed-pathspec

  To display the rows in reverse order: `git brv --reverse`

    $ git brv --reverse
    2020-01-08 master       origin/master     265b03e Merge pull request #816 from spacewander/git-sed-pathspec
    2020-01-14 adds-git-brv fork/adds-git-brv 1ca0d76 Fixes #700: Adds git-brv

## TROUBLESHOOTING

  `Not a git repo!` (exit status 128)

  `git brv` was run outside a Git repository, so there are no branches to list. Change into a repository first, or point Git at one with `git -C`:

    $ git brv
    Not a git repo!
    $ git -C my-project brv
    2020-01-14 topic origin/topic 1ca0d76 topic work
    2020-01-08 main  origin/main  265b03e C

  `This script requires bash 4.2 or newer` (exit status 1)

  The `bash` found first in your `PATH` is older than 4.2 (macOS ships bash 3.2). Install a newer bash, for example with `brew install bash`, and make sure it comes first in `PATH`.

## AUTHOR

Written by Øsse &lt;<https://github.com/Osse>&gt;

## REPORTING BUGS

&lt;<https://github.com/tj/git-extras/issues>&gt;

## SEE ALSO

&lt;<https://github.com/tj/git-extras>&gt;
