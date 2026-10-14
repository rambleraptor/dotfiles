# Arbor CLI Agent Guide

Arbor is a specialized CLI tool for managing Git worktrees and tracking their associated GitHub Pull Request statuses. It's designed to streamline a workflow where each feature or PR lives in its own dedicated worktree, isolated from the main repository.

## Design Goals

- **No Git Pollution**: Arbor-related metadata is stored exclusively in the root of the worktrees directory (in a `.arbor` folder) and the user's home directory. No Arbor files are ever stored within the project worktrees themselves, ensuring they can never be accidentally committed to Git.
- **Project Isolation**: Manage multiple repositories (projects) from a single worktree root.
- **GitHub Integration**: Automatically tracks PR numbers and states (OPEN, MERGED, CLOSED) using the `gh` CLI.
- **Automated Cleanup**: Safely removes worktrees associated with merged PRs.

## Capabilities

- **Worktree Management**: Create and delete Git worktrees with ease.
- **Status Tracking**: Unified view of PR status across multiple projects and worktrees.
- **Cleanup**: Bulk removal of stale worktrees.

## Commands

### `init`
Initializes Arbor by setting the root directory where all worktrees will be created.
```bash
arbor init ~/worktrees
```

### `import`
Adds a local Git repository to Arbor's registry. If the repo has a feature
branch checked out, that branch is moved into its own worktree and the repo is
left detached; the main branch is left where it is.
```bash
arbor import /path/to/repo --name my-project
```

### `create`
Creates a new worktree for a registered project on a specific branch, branched
from the project's main branch. If the branch doesn't exist, it creates it.
An existing branch is checked out as-is: a local branch is used directly, a
branch that only exists on `origin`/`upstream` is tracked, and a branch checked
out in the main repo is moved into the worktree (the main repo is detached).
If the branch already has a worktree in the worktrees dir, that path is
returned instead of failing.
The worktree path is printed to stdout; everything else goes to stderr.
```bash
arbor create my-project feature/cool-thing
WT=$(arbor create my-project fix-the-thing)   # capture the path directly
```
Pass a comma-separated list of projects to make a multi-repo group: one
worktree per repo, all on the same branch, under a shared folder named after
the branch. The group folder's path is printed; `--json` lists each member.
If any repo fails, the worktrees (and newly created branches) already made for
the group are rolled back, so you get all of them or none.
```bash
arbor create api,web feature/cool-thing
# ~/worktrees/feature/cool-thing/api  and  ~/worktrees/feature/cool-thing/web
```
Members are addressed as `<branch>/<repo>` (`arbor pr feature/cool-thing/api`);
the bare group name resolves to the folder (`arbor cd`, `arbor exec`). A short
name matching more than one worktree is an `ambiguous_worktree` error.
The base is resolved fresh every time (fetch `upstream`, prefer `upstream/main`,
fall back to origin's default branch), so several branches cut for independent
PRs all start from the same current commit instead of stacking on each other.
Override with `--base <ref>`, or skip the fetch with `--no-fetch`.

### `pr`
Pushes a worktree's branch and opens a pull request for it.
```bash
arbor pr fix-the-thing --title "Fix the thing" --body "Closes #123"
arbor pr fix-the-thing --fill --draft
```
The fork workflow is spelled out explicitly — push to `origin`, target
`upstream`, head as `<fork-owner>:<branch>` — so `gh` never stops to ask which
repo to use. It refuses to run on a dirty worktree or a branch with no commits,
and re-running after a failure reports the existing PR rather than opening a
second one. The PR URL is printed to stdout.

### `exec`
Runs a command inside a worktree, addressed by name, and exits with that
command's exit code.
```bash
arbor exec fix-the-thing -- pytest tests/
```

### `status`
Displays a table of all active worktrees, their associated project, branch, PR
number, and current GitHub status. `--repo <name>` narrows it to one project,
which also makes it much faster.
```bash
arbor status
arbor status --repo my-project --offline
```

### `cleanup`
Scans all active worktrees and removes those whose PRs have been merged on
GitHub, plus research worktrees past their TTL. A multi-repo group is only
removed once every member's PR is merged, and then the whole group goes.
`--dry-run` reports without removing.
```bash
arbor cleanup
```

### `config`
Displays the current Arbor configuration, including the worktrees directory and
imported projects.
```bash
arbor config
```

## Machine-readable output

`create`, `research`, `status`, `cleanup`, `config` and `pr` all take `--json`.
In JSON mode stdout carries exactly one JSON document and every human-facing
message moves to stderr, so the output can be parsed without stripping terminal
formatting. Errors are reported the same way — `{"ok": false, "error": ...,
"code": ...}` on stdout, exit code 1 — with a stable `code` to branch on
(`unknown_project`, `worktree_exists`, `branch_checked_out`, `dirty_worktree`, `no_commits`,
`missing_title`, `no_base_ref`, `lock_timeout`, ...).

`arbor status --json` additionally reports each worktree's local git state
(`dirty`, `ahead`, `behind`, `head`) alongside its PR, computed live rather than
cached, so a session can tell at a glance which of its worktrees still have
uncommitted or unpushed work.

Worktrees can be tagged at creation with `--task "what this is for"` and
`--owner <agent-or-session-id>`; both come back in `status --json`, which is how
a session that fanned out several worktrees tells them apart later.

## Running several worktrees at once

Arbor is built to have several worktrees in flight against one repository. The
shape of a fan-out:

```bash
WT=$(arbor create my-project fix-a --task "fix the retry bug" --owner agent-1)
# ... work in $WT, commit ...
arbor pr fix-a --title "Fix the retry bug"
arbor status --repo my-project --json     # collect results
```

Each branch is cut from the same freshly fetched main branch, so the PRs stay
independent. Commands that mutate git state (`create`, `research`) take an
exclusive lock in `{worktrees_dir}/.arbor/lock`, because `git fetch` and
`git worktree add` both write to the shared main repo; read-only commands
(`status`, `cd`) never take it, so a fan-out can be inspected while it runs.

## Internal Architecture

### Configuration
- **Global Config**: Stored at `~/.arbor_config.json`. It tracks the `worktrees_dir` and a mapping of project names to their local filesystem paths.
- **Worktree Metadata**: Each worktree has a corresponding JSON file in `{worktrees_dir}/.arbor/{branch_name}.json`, storing specific metadata like the repo name and cached PR info. Group members live at `.arbor/{branch_name}/{repo}.json` with `group` set to the branch name.

### Dependencies
- **Typer**: CLI framework.
- **Pydantic**: Data validation and serialization for configuration.
- **Rich**: Terminal formatting and tables.
- **Git CLI**: Required for worktree operations.
- **GitHub CLI (`gh`)**: Required for PR status tracking.

## Usage for AI Agents
When working with this codebase, remember:
1. Arbor relies on the `gh` CLI being authenticated for status updates.
2. Worktree names are derived from branch names.
3. The `worktrees_dir` is the source of truth for "active" worktrees tracked by Arbor.
4. Prefer `--json` over parsing the Rich tables, and address worktrees by name
   (`arbor exec`, `arbor pr`) rather than reconstructing paths.
