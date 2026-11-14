git-squash(1) -- squash N last changes up to a ref'ed commit
=============================================

## SYNOPSIS

`git squash` [--squash-msg] &lt;source-branch|commit-ref&gt; [&lt;commit-message&gt;]

## DESCRIPTION

  Squash the N last changes in the current branch, where N is the range of commits from the given ref up to HEAD.

## OPTIONS

  `--squash-msg`

  Create a commit using the concatenated messages from the commits being
  squashed. This option must precede the source and cannot be combined with
  `&lt;commit-message&gt;`.

  &lt;source-branch|commit-ref&gt;

  Required. A branch is squash-merged into the current branch. A commit
  reference on the current branch can instead be given to squash the commits
  after that reference up to `HEAD`.

  &lt;commit-message&gt;

  If commit-message is given, commit the squashed result, otherwise the squash remains just added to the index and is not committed.

  If the source is omitted, the command exits with an error. Unknown options
  and extra positional arguments are rejected. Without `&lt;commit-message&gt;` or
  `--squash-msg`, the squash is staged and `HEAD` is unchanged.

## EXAMPLES

    # squash changes and follow up with separate commit step
    $ git squash my-other-branch
    Updating a2740f5..533b19c
    Fast-forward
    Squash commit -- not updating HEAD
     my-changed-file | 1 +
     1 file changed, 1 insertion(+)
    $ git commit -m "New commit without a real merge"

    # squash and commit with given message
    $ git squash HEAD~3 "Commit message"

    # squash and commit and concatenate all messages
    $ git squash --squash-msg @~3

## AUTHOR

Written by Jesús Espino &lt;<jespinog@gmail.com>&gt;

## REPORTING BUGS

&lt;<https://github.com/tj/git-extras/issues>&gt;

## SEE ALSO

&lt;<https://github.com/tj/git-extras>&gt;
