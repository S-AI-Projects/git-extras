git-delete-submodule(1) -- Delete submodules
============================================

## SYNOPSIS

`git delete-submodule` [--force] &lt;path&gt;

## DESCRIPTION

  Deletes a git submodule located at &lt;path&gt;, cleaning up `.gitmodules`, git configuration, and working tree files.

## OPTIONS

  --force

  Do not abort on intermediate failures, allowing cleanup after a previous failure.

  &lt;path&gt;

  The path of the submodule to delete.

## EXAMPLES

    $ git delete-submodule lib/foo
    $ git delete-submodule --force lib/foo

## AUTHOR

Written by Jonhnny Weslley &lt;<jw@jonhnnyweslley.net>&gt;

## REPORTING BUGS

&lt;<https://github.com/tj/git-extras/issues>&gt;

## SEE ALSO

&lt;<https://github.com/tj/git-extras>&gt;
