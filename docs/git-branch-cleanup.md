# Git branch cleanup

`gb` fetches from `origin`, cleans up eligible local branches, and synchronizes
the requested branch. `gw` calls `gb` before creating or opening a worktree.
These commands require Git 2.36 or newer for unambiguous worktree paths.

## What cleanup preserves

Automatic cleanup leaves registered worktrees and their files in place,
including clean, dirty, locked, and missing worktrees. It also keeps branches
involved in a rebase or bisect, the current branch, `main`, and the requested
target branch. `gb` refuses to switch to a branch registered in another
worktree. Use that checkout or remove it explicitly with `gw rm`. Switching
and fast-forwarding refuse to overwrite ignored local files.

`gw` preserves missing registrations. Restore the checkout or explicitly run
`git worktree prune` before recreating a missing worktree.

## When a branch can be pruned

A branch must have a deleted upstream and no registered worktree. Cleanup
then requires one of these proofs against the fetched `origin/main`:

- The branch tip is an ancestor of `origin/main`.
- The branch's complete change from its unique merge base exactly matches
  one non-merge commit on `origin/main` after that base. This recognizes
  squash merges by comparing paths, file modes, and full old and new object
  IDs. Whitespace and binary differences remain significant.

Empty squash comparisons, ambiguous history, and failed Git commands leave
the branch in place. Shallow history cannot establish squash equivalence. Conflict
resolutions, main changing the same files before the squash, and changes
spread across multiple commits may also prevent a match. Kept branches produce one summary per run.

Cleanup proofs examine original Git objects, bypassing replacement objects
and legacy grafts. Normal switching and syncing retain Git's partial-clone
fetch behavior. A failed proof leaves the branch in place.

`gb` disables automatic Git maintenance for its commands so a fetch cannot
silently expire old worktree registrations.

## Restore a pruned branch

Every pruned branch retains its original tip under:

```text
refs/gb/pruned/<branch>/<original-tip>
```

Creating that recovery ref and deleting the branch happen in one Git
transaction. Changes to the branch tip or `origin/main` abort the transaction.
An existing recovery ref must point directly to the same commit. Cleanup
never expires these refs, so the original history survives reflog expiration
and garbage collection.

Each successful prune prints a complete `git branch` command to restore the
branch. To find saved refs later:

```sh
git for-each-ref --format='%(refname) %(objectname)' refs/gb/pruned/
```

Copy the desired ref into `git branch <branch-name> <recovery-ref>`. The
restored branch has its original tip, tree, and commit history, without
inheriting the deleted upstream. Cleanup removes obsolete branch configuration
after pruning.

Recovery refs protect committed history within this local repository. Git
views using `--all` include that history. `gb` explicitly fetches branch heads
into `refs/remotes/origin/`, overriding configured fetch mappings for this
command. It does not fetch or prune tags or notes. Local branches and recovery
refs stay outside the fetch destinations.

Worktree use is checked before pruning. A checkout or rebase starting after
that check can still require restoring the branch reference. The recovery
ref retains its original tip and cleanup leaves worktree files in place.

## Verification

Run the CLI tests with:

```sh
python3 -m unittest discover -s tests -p 'test_g[wb].py'
```

The tests create disposable repositories and local bare remotes. They verify
normal and squash merges, exact restoration after garbage collection, local
commits and file differences, worktree preservation, interrupted Git
operations (including stacked rebase updates), transaction failures, concurrent
branch updates, ignored-file collisions, submodule changes, and partial clones.
