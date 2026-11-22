git-local-commits(1) -- List local commits
=======================================

## SYNOPSIS

`git local-commits` [-h|--help] [<args>]

## DESCRIPTION

  Lists commits in the local branch that have not been pushed to the remote tracked branch.
  This requires that HEAD points to a branch which is tracking another branch.

## OPTIONS

  -h, --help

  Show help message and exit.

  <args>

  All arguments passed to `git local-commits` will be passed directly to `git log`.

## EXAMPLES

    $ git local-commits --graph

## AUTHOR

Written by Michael Komitee <mkomitee@gmail.com>

## REPORTING BUGS

<https://github.com/tj/git-extras/issues>

## SEE ALSO

<https://github.com/tj/git-extras>
