git-lock(1) -- Lock a file excluded from version control
========================================================

## SYNOPSIS

`git lock` &lt;filename&gt;

## DESCRIPTION

  Mark a tracked local file with `--skip-worktree` in the Git index so local modifications to it are ignored by version control until unlocked. Requires a non-empty `<filename>` argument referring to a tracked file.

## OPTIONS

  &lt;filename&gt;

  The name of the tracked file to lock.

## EXAMPLES

    $ git lock config/database.yml

## AUTHOR

Written by Julio Napuri &lt;<julionc@gmail.com>&gt;

## REPORTING BUGS

&lt;<https://github.com/tj/git-extras/issues>&gt;

## SEE ALSO

&lt;<https://github.com/tj/git-extras>&gt;
