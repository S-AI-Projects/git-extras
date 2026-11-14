git-gh-pages(1) -- Create the GitHub Pages branch
=================================================

## SYNOPSIS

`git gh-pages` [&lt;username&gt; &lt;repository&gt;]

## DESCRIPTION

  Create the GitHub Pages branch (`gh-pages`) with an initial dummy `index.html` file and push it to `origin`. If `<username>` and `<repository>` are not supplied as positional arguments, the command prompts for them interactively.

## OPTIONS

  &lt;username&gt;

  Your GitHub account username.

  &lt;repository&gt;

  The name of the target GitHub repository.

## EXAMPLES

    $ git gh-pages myuser myrepository
    setting up gh-pages
    -------------------
    [gh-pages 94f4b26] Initial commit
     1 file changed, 1 insertion(+)
     create mode 100644 index.html
    To https://github.com/myuser/myrepository.git
     * [new branch]      gh-pages -> gh-pages
    Branch 'gh-pages' set up to track remote branch 'gh-pages' from 'origin'.
    Complete
    -------------------
    You can find your last changes in the stash!
    $


## AUTHOR

Written by Jesús Espino &lt;<jespinog@gmail.com>&gt;

## REPORTING BUGS

&lt;<https://github.com/tj/git-extras/issues>&gt;

## SEE ALSO

&lt;<https://github.com/tj/git-extras>&gt;
