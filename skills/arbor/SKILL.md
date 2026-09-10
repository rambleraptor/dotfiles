---
name: arbor
description: Use arbor to manage git worktrees and their pull requests - create a worktree branched from main, run commands in it, open a PR from it, check what is in flight, and clean up merged work. Use whenever a task involves working on a branch in isolation, opening a PR, or asking what worktrees/PRs are currently open.
---

# arbor

`arbor` manages a worktree per branch outside the main checkout, and tracks the
pull request each one belongs to. Every command that a caller needs to parse
takes `--json`.

Reach for it when work should happen on its own branch — anything headed for a
PR, or anything that shouldn't disturb the current checkout.

## The contract

- `--json` puts exactly one JSON document on stdout; all human output moves to
  stderr. Parse stdout, never the tables.
- Errors are `{"ok": false, "error": "...", "code": "..."}` on stdout with exit
  code 1. Branch on `code`, not on message text.
- Address worktrees by name. Don't rebuild paths by hand.

## Commands

```bash
# Create a worktree, branched from the freshly fetched main branch.
# The path goes to stdout, so it can be captured directly.
WT=$(arbor create <project> <branch> --task "what this is for")

# Run a command inside a worktree, by name. Exits with the command's own code.
arbor exec <branch> -- pytest tests/

# Push the branch and open a PR. Handles the fork workflow (push origin,
# target upstream, head as <fork-owner>:<branch>) so gh never prompts.
arbor pr <branch> --title "..." --body "..."
arbor pr <branch> --fill --draft

# What is in flight, with live git state (dirty/ahead/behind) per worktree.
arbor status --repo <project> --json

# A throwaway detached checkout for reading code, expired automatically.
arbor research <project>
arbor research <project> --pr 1234

# Remove worktrees whose PRs merged, plus expired research checkouts.
arbor cleanup --dry-run
```

`arbor config --json` lists the registered projects; project names are what
`create`, `status --repo` and `cleanup --repo` expect.

## Things worth knowing

- `create` always branches from the project's main branch, fetched fresh, so
  branches cut for independent PRs never stack on each other. `--base <ref>`
  overrides; `--no-fetch` skips the network.
- `pr` is safe to re-run. If the branch already has an open PR it reports that
  one instead of opening a second. It refuses on a dirty worktree or a branch
  with no commits, so commit before calling it.
- `status --json` reports `ahead`/`behind` against the base branch. A large
  `behind` means the branch needs a rebase before it will review cleanly.
- Reading `status` for every project is slow (it hits GitHub once per branch).
  Pass `--repo`, and `--offline` when cached PR state is good enough.
- `create` and `research` serialize on a lock, because both write to the shared
  main repo. Concurrent callers wait rather than corrupting each other.

For several worktrees in flight at once, use the `arbor-fanout` skill.
