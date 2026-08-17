# Branch workflow

Test work happens on its own branch, named after the branch it came from, created **before** the first file is written.

## The trap in "sub-branch of the parent"

The obvious implementation fails. Git stores refs as files under `.git/refs/heads/`, so a branch named `main` is a **file** at `refs/heads/main`. Creating `main/tests` needs `refs/heads/main` to be a **directory**. It can't be both:

```
$ git switch -c main/tests
fatal: cannot lock ref 'refs/heads/main/tests': 'refs/heads/main' exists;
cannot create 'refs/heads/main/tests'
```

This is a directory/file conflict, and it hits **every** parent branch that already exists — which is all of them. Nesting a new branch directly under an existing branch name is impossible in git.

**So use a non-slash separator.** The parent name still prefixes the branch, which is what makes it sortable, greppable, and obvious in `git branch`:

```
<parent>-test-<slug>
```

| Parent | Test branch |
|---|---|
| `main` | `main-test-20260814-inventory` |
| `develop` | `develop-test-20260814-checkout` |
| `feature/checkout` | `feature/checkout-test-20260814` |

`feature/checkout-test-20260814` works because the path components are `feature` and `checkout-test-20260814` — `checkout` and `checkout-test-...` are different names, so no conflict.

## Creating it

```bash
# 1. Where are we?
PARENT=$(git rev-parse --abbrev-ref HEAD)

# 2. Guard: detached HEAD returns literally "HEAD"
[ "$PARENT" = "HEAD" ] && { echo "Detached HEAD — check out a branch first"; exit 1; }

# 3. Build and validate the name
SLUG="20260814-inventory"                      # date + what's being tested
BRANCH="${PARENT}-test-${SLUG}"
git check-ref-format --branch "$BRANCH" >/dev/null || { echo "Invalid name: $BRANCH"; exit 1; }

# 4. Create and switch
git switch -c "$BRANCH"                        # git checkout -b on older git
```

`git check-ref-format` is the authoritative validator — don't hand-roll the rules. It rejects spaces, `~ ^ : ? * [ \`, `..`, a leading `-`, a trailing `.lock`, consecutive or trailing slashes.

If the parent name contains characters that survive into an invalid combination, sanitise the **slug**, never the parent — mangling the parent breaks the prefix relationship that makes the convention useful.

## Before switching

- **Detached HEAD** → stop and ask. Branching from an unnamed commit produces work nobody can find later.
- **Not a git repo** → say so and proceed without branching rather than running `git init` on someone's directory uninvited.
- **Dirty working tree** → uncommitted changes follow you across `git switch` when there's no conflict, which is usually what you want. When switching *would* conflict, stop and ask rather than stashing silently — a stash you created and didn't mention is work the user can't find.
- **Branch already exists** → don't clobber it. Either switch to it (if resuming the same run) or append a counter. Never `-B`, which resets an existing branch and discards commits.

## Never test directly on the default branch

If `PARENT` is `main` or `master`, branching isn't optional — it's the point. Test scaffolding, fixtures, and result files landing on the default branch is how a repo accumulates junk nobody will delete because nobody's sure what it is.

## What goes on the branch

- Test files — specs, fixtures, factories, config changes.
- `test-results/<date>-<time>/` — the result files and screenshots.
- Nothing else. If a source fix is needed to make a test pass, that's a **separate finding**, reported for a human. Fixing product code on a test branch mixes two decisions into one diff and hides the drift.

**Do the result files get committed?** Default to yes on a test branch — the run record is the deliverable, and it's the reason the branch exists. Add `test-results/` to `.gitignore` only if the team explicitly doesn't want run history in git. Ask once, then follow the answer.

## Committing and pushing

Commit when there's a coherent unit — the case set, then the run. Keep them separate:

```
test: add functional cases for inventory receipt slice
test: record run 2026-08-14 — 4 failures, 2 drifts
```

**Never push without being asked.** The branch exists locally; whether it goes to a remote, and to which remote, is the user's call. This repo currently has **no remote configured**, so a push would fail anyway — worth saying out loud rather than attempting it.

Follow the repo's commit conventions if it has them. No AI or tool attribution in commit messages, trailers, or PR bodies.

## Finishing

State the branch name and what's on it in the final report:

```
Branch:   main-test-20260814-inventory  (from main)
Commits:  2 — 112 cases added, run recorded
Results:  test-results/2026-08-14-1432/
Not pushed — no remote configured.
```

Leave the user on the test branch unless they asked to return. Switching them back without saying so is disorienting, and they may want to inspect what was produced.
