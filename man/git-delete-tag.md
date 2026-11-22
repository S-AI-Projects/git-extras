git-delete-tag(1) -- Delete tags
================================

## SYNOPSIS

`git delete-tag` [-h|--help] &lt;tagname&gt;...

## DESCRIPTION

  Deletes local and remote tag named &lt;tagname&gt;.

## OPTIONS

  -h, --help

  Show help message and exit.

  &lt;tagname&gt;

  The name of the tag to delete.
  If multiple tags are provided, then they will all be deleted.

## DIAGNOSTICS

  If no tag name is supplied, `git delete-tag` exits with status 1 and explains that a tag name is required.
  If local tag deletion fails, it exits with status 1 and suggests inspecting tags using `git tag -l`.
  If remote tag deletion fails, it reports a troubleshooting hint to verify remote connectivity and permissions.

## EXAMPLES

    $ git delete-tag 0.0.1
    $ git delete-tag 0.0.1 0.0.2

## AUTHOR

Written by Tj Holowaychuk <tj@vision-media.ca>

## REPORTING BUGS

<https://github.com/tj/git-extras/issues>

## SEE ALSO

<https://github.com/tj/git-extras>
