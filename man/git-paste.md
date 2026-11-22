git-paste(1) -- Send patches to pastebin for chat conversations
===============================================================

## SYNOPSIS

`git paste` [-h|--help] [&lt;git format-patch options&gt;]

## DESCRIPTION

  Send patches to pastebin for chat conversations using pastebinit.
  The syntax highlighting will be set to 'diff'.

## OPTIONS

  -h, --help

  Display help message.

  &lt;git format-patch options&gt;

  All options are passed directly to `git format-patch`.
  Given no arguments, `git paste` passes `@{u}` to `git format-patch`.
  Positional arguments and options containing spaces or wildcard characters are preserved and passed directly to `git format-patch` without word-splitting or premature shell expansion.

## CONFIGURATION

  The pastebinit software chooses the most appropriate pastebin site
  for your operating system and the [pastebinit documentation](https://manpages.debian.org/pastebinit)
  contains details of how to configure it to use a different site.

## EXAMPLES

 Pastebin the patches between the current branch and its upstream:

    $ git paste
    $ git paste @{u}

 Pastebin the latest commit:

    $ git paste -1

 Pastebin the latest three commits:

    $ git paste -3

 Pastebin changes for files matching a path containing spaces and wildcards:

    $ git paste -1 HEAD -- "dir with spaces/*.txt"

## AUTHOR

Written by Paul Wise &lt;<pabs3@bonedaddy.net>&gt;

## REPORTING BUGS

&lt;<https://github.com/tj/git-extras/issues>&gt;

## SEE ALSO

&lt;<https://github.com/tj/git-extras>&gt;
