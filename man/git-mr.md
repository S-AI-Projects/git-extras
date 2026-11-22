git-mr(1) -- Checks out a merge request locally
========================================

## SYNOPSIS

`git mr` &lt;number&gt; [&lt;remote&gt;]<br>
`git mr` &lt;url&gt;<br>
`git mr` [-h|--help]<br>
`git mr clean`

## DESCRIPTION

  Fetches merge request head by its number or URL and check it out in a branch
  named with merge request number.

## OPTIONS

  &lt;remote&gt;

  The name of the remote to fetch from. Defaults to `origin`.

  &lt;url&gt;

  GitLab merge request URL in the format
  `https://gitlab.tld/owner/repository/merge_requests/453`, or a
  Forgejo/Codeberg pull request URL in the format
  `https://codeberg.tld/owner/repository/pulls/453`.

  -h | --help

  Show help synopsis and usage options.

## EXAMPLES

This checks out merge request `!51` from remote `origin` to branch `mr/51`.

    $ git mr 51
    From gitlab.com:owner/repository
     * [new ref]         refs/merge-requests/51/head -> mr/51
    Switched to branch 'mr/51'

This checks out pull request `#51` from a Forgejo/Codeberg URL to branch `mr/51`.

    $ git mr https://codeberg.org/owner/repository/pulls/51
    From codeberg.org:owner/repository
     * [new ref]         refs/pull/51/head -> mr/51
    Switched to branch 'mr/51'

To clean up old branches:

    $ git mr clean

    Deleted branch mr/51 (was b96a8c2).

## DIAGNOSTICS & ERRORS

* Missing merge request argument (`mr number or URL required. See --help for usage.`):
  Occurs when `git mr` is run without arguments. Exit status is 1.

* Remote reference or branch not found:
  Occurs when the specified merge request ID does not exist on the remote repository.
  `git fetch` fails and the command exits with non-zero exit status.

## AUTHOR

Written by Étienne BERSAC <bersace03@gmail.com> from git-pr(1).

## REPORTING BUGS

<https://github.com/tj/git-extras/issues>

## SEE ALSO

<https://github.com/tj/git-extras>
