git-fork(1) -- Fork a repo on github
====================================

## SYNOPSIS

`git fork` [-h|--help] [&lt;github-repo-url&gt;]

## DESCRIPTION

  If a github repo url is given, fork the repo. Like clone but forks first.

  1. forks the repo on github
  2. clones the repo into the current dir
  3. adds the original repo as a remote called `upstream`

  If a url is not given and the current dir is a github repo, fork the repo.

  1. forks the current repo
  2. rename the `origin` remote repo to `upstream`
  3. adds the forked repo as a remote called `origin`

  Remotes will use ssh if you have it configured with GitHub, if not, https will be used.

  Create a fork of a project on GitHub via command line.
  
  A personal access token is required for making the API call to create a fork in GitHub. [API Documentation here](https://docs.github.com/en/rest/reference/repos#forks)
  
  Make sure the personal access token has the right `OAuth` scopes for the repo(s)
  
  Use `GITHUB_TOKEN` environment variable, or `git config --global --add git-extras.github-personal-access-token <your-personal-access-token>`
  
  If using multiple accounts, override the global value in the specific repo using `git config git-extras.github-personal-access-token <other-acc-personal-access-token>`

  The GitHub API base URL defaults to `https://api.github.com`, but can be overridden with the `GITHUB_API_URL` environment variable for testing or enterprise GitHub installations. The remote URL prefix defaults to `git@github.com:` or `https://github.com/`, but can be overridden with `GIT_REMOTE_PREFIX`.

## OPTIONS

  -h, --help

  Show help message and exit.

  &lt;github-repo-url&gt;

  The GitHub repository URL (HTTPS or SSH) or `owner/repo` shorthand to fork.

## EXAMPLE

  Fork expect.js:

    $ git fork https://github.com/LearnBoost/expect.js

  or just:

    $ git fork LearnBoost/expect.js

  Then:

    $ ..<forks into your github profile and clones repo locally to expect.js dir>...

    $ cd expect.js && git remote -v

      origin          git@github.com:<user>/expect.js (fetch)
      origin          git@github.com:<user>/expect.js (push)
      upstream        git@github.com:LearnBoost/expect.js (fetch)
      upstream        git@github.com:LearnBoost/expect.js (push)

  If the current dir is a clone of expect.js, this has the same effect:

    $ git fork


## AUTHOR

Written by Andrew Griffiths &lt;<mail@andrewgriffithsonline.com>&gt;

## REPORTING BUGS

&lt;<https://github.com/tj/git-extras/issues>&gt;

## SEE ALSO

&lt;<https://github.com/tj/git-extras>&gt;
