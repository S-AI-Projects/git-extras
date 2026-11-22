git-unlock(1) -- Unlock a file excluded from version control
============================================================

## SYNOPSIS

`git unlock` &lt;filename&gt;

## DESCRIPTION

  Unmark a tracked local file with `--no-skip-worktree` in the Git index so local modifications are tracked again by version control. Requires a non-empty &lt;filename&gt; argument referring to a tracked file. If &lt;filename&gt; is omitted or empty, the command prints an error to stderr and exits with status 1.

## OPTIONS

  &lt;filename&gt;

  The name of the tracked file to unlock.

## EXAMPLES

    $ git unlock config/database.yml

## AUTHOR

Written by Julio Napuri &lt;<julionc@gmail.com>&gt;

## REPORTING BUGS

&lt;<https://github.com/tj/git-extras/issues>&gt;

## SEE ALSO

&lt;<https://github.com/tj/git-extras>&gt;
