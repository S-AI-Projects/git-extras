git-contrib(1) -- Show user's contributions
===========================================

## SYNOPSIS

`git contrib` &lt;username&gt;|&lt;email&gt; [-- &lt;path&gt;...]

## DESCRIPTION

  Output a user's contributions to a project, based on the author name or email.
  Returns multiple entries if there are more than one match.
  Optionally limits contributions to the specified paths when preceded by `--`.

## OPTIONS

  &lt;username&gt;

  The name or email of the user who owns the contributions. Supports wildcards and multi-word names with spaces.

  [-- &lt;path&gt;...]

  Optional path(s) to restrict contributions to, preserving quoted arguments and paths containing spaces.

## EXAMPLES

    Searching with a username

    $ git contrib visionmedia
    visionmedia (18):
      Export STATUS_CODES
      Moved help msg to node-repl
      Added multiple arg support for sys.puts(), print(), etc.
      Fix stack output on socket error
      ...

    Searching with a partial email

    $ git contrib tj@
    visionmedia (18):
      Export STATUS_CODES
      Moved help msg to node-repl
      Added multiple arg support for sys.puts(), print(), etc.
      Fix stack output on socket error
      ...


## AUTHOR

Written by Tj Holowaychuk &lt;<tj@vision-media.ca>&gt;

## REPORTING BUGS

&lt;<https://github.com/tj/git-extras/issues>&gt;

## SEE ALSO

&lt;<https://github.com/tj/git-extras>&gt;
