git-abort(1) -- Abort current git operation
================================

## SYNOPSIS

`git abort`

## DESCRIPTION

  Abort current git revert, rebase, merge or cherry-pick process.

## OPTIONS

  There are no options, it just aborts current operation.

## EXAMPLES

  `git abort`

## TROUBLESHOOTING

If no merge, rebase, revert, or cherry-pick is active, `git abort` exits with
status 1 and reports that there is nothing to abort. The repository state is
left unchanged. Start or continue the intended Git operation before retrying.

## AUTHOR

Written by Przemek Kitszel &lt;<pkitszel@gmail.com>&gt;

## REPORTING BUGS

&lt;<https://github.com/tj/git-extras/issues>&gt;

## SEE ALSO

&lt;<https://github.com/tj/git-extras>&gt;
