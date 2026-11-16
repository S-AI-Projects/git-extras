git-show-merged-branches(1) -- Show merged branches
===================================================

## SYNOPSIS

`git show-merged-branches` [&lt;commit&gt;]

## DESCRIPTION

  Show branches merged in to current HEAD (or specified commit), excluding the default branch.

## OPTIONS

  &lt;commit&gt;

  Optional commit or branch to check merged branches into. Defaults to HEAD.

## EXAMPLES

    $ git show-merged-branches
    $ git show-merged-branches main

## AUTHOR

Written by Paul Schreiber &lt;<paulschreiber@gmail.com>&gt;

## REPORTING BUGS

&lt;<https://github.com/tj/git-extras/issues>&gt;

## SEE ALSO

&lt;<https://github.com/tj/git-extras>&gt;
