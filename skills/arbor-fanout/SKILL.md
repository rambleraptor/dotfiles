---
name: arbor-fanout
description: Run several pieces of work against one repository at the same time using arbor worktrees - opening multiple independent PRs, or answering multiple questions about a codebase in parallel. Use when a request contains several separable changes to one repo, asks for more than one PR, or asks several questions that each need their own checkout.
---

# arbor-fanout

Several pieces of work against one repository, each in its own worktree, at the
same time. Two shapes: independent PRs (write) and independent questions
(read). See the `arbor` skill for the full CLI contract.

## Deciding to fan out

Fan out when the pieces are genuinely independent — separate bugs, separate
files, separate questions. Do not fan out work that has to land in order, or
where one piece needs to see another's result; that is one worktree, sequential.

Prefer arbor over a throwaway worktree when the output is a PR to track for
days. For a question answered and forgotten within the session, a plain
subagent reading the existing checkout is cheaper.

## Multiple PRs

```bash
# One worktree per change. Each branches from the same freshly fetched main,
# so the PRs stay independent instead of stacking.
WT_A=$(arbor create my-project fix-retry --task "fix the retry backoff")
WT_B=$(arbor create my-project fix-parser --task "fix the header parser")
```

Then dispatch one subagent per worktree. Subagents inherit the parent's working
directory, so each prompt must carry the absolute path and say to stay inside
it:

> Work only in `<WT_A>`. Use absolute paths or `git -C <WT_A>`; do not rely on
> `cd` persisting. Make the change, run the tests, and commit. Do not push and
> do not open a PR.

Have agents commit but not open PRs — collect first, then open them yourself so
titles stay consistent and a half-finished branch never becomes a PR:

```bash
arbor status --repo my-project --json     # check dirty/ahead before opening
arbor pr fix-retry --title "Fix the retry backoff"
arbor pr fix-parser --title "Fix the header parser"
```

`arbor pr` refuses a dirty worktree or a branch with no commits, and reports an
existing PR rather than opening a second, so a partial failure is safe to retry.

## Multiple questions

```bash
arbor research my-project --task "how does auth token refresh work"
arbor research my-project --task "where is retry backoff configured"
```

Each prints a detached checkout path. Give one to each subagent with the
question, and ask for the answer plus the `file:line` citations backing it.
These expire on their own; `arbor cleanup` collects them.

## Collecting

```bash
arbor status --repo my-project --json
```

Gives every worktree with its `task`, `owner`, PR number and state, and live
git state (`dirty`, `ahead`, `behind`). Report per worktree what landed, what
is still dirty, and what was left undone — never assume a dispatched agent
finished just because it returned.

## Pitfalls

- Don't reuse one worktree for two agents. Concurrent edits in one checkout
  corrupt each other silently.
- Don't let agents rebase or force-push during a fan-out; branches already share
  a base.
- Tag every worktree with `--task` at creation. Without it, `arbor status` shows
  a list of branch names with no way to tell which question each answered.
