# Arbor Development Context

Arbor is a specialized CLI tool for managing Git worktrees and tracking their associated GitHub Pull Request statuses.

## Core Concepts
- **Worktrees**: Arbor manages a dedicated directory (defaulting to a path set during `init`) where each branch/PR is checked out as a separate Git worktree.
- **Projects**: Local Git repositories that are imported into Arbor. Arbor tracks which worktree belongs to which project.
- **Metadata**: Arbor stores its own metadata about active worktrees in a `.arbor` subdirectory within the worktrees directory. This prevents pollution of the project's own Git state.
- **GitHub Integration**: Uses the `gh` CLI to fetch PR status (OPEN, MERGED, CLOSED).

## File Locations
- **Global Config**: `~/.arbor_config.json` stores the `worktrees_dir` and the map of imported `projects`.
- **Worktree Metadata**: `{worktrees_dir}/.arbor/{branch_name}.json` stores `WorktreeInfo` (JSON) including the repo name, branch, and cached PR details.

## Tech Stack
- **Python**: Core implementation in `arbor.py`.
- **Typer**: CLI interface.
- **Pydantic**: Configuration and metadata validation (v2).
- **Rich**: Terminal formatting and tables.
- **Git/GitHub CLIs**: Relies on external `git` and `gh` commands for operations.

## Key Workflows
- `arbor init <path>`: Sets the root for all managed worktrees.
- `arbor import <path>`: Registers a main repo as a project or an existing worktree as an Arbor-managed one.
- `arbor create <repo> <branch>`: Creates a new worktree in the worktrees root, branched from the freshly fetched main branch, and prints its path to stdout.
- `arbor pr <name>`: Pushes the branch and opens a PR, handling the fork workflow explicitly so `gh` never prompts.
- `arbor exec <name> -- <cmd>`: Runs a command inside a worktree, addressed by name.
- `arbor status`: Refreshes PR status from `gh` and displays a table.
- `arbor cleanup`: Removes worktrees whose PRs have been merged.
- `arbor cd <name>`: Helper for shell integration to jump to a worktree directory.

## Agent-Facing Contract
- `create`, `research`, `status`, `cleanup`, `config` and `pr` accept `--json`: stdout carries exactly one JSON document, all human output moves to stderr, and errors become `{"ok": false, "error": ..., "code": ...}` with exit code 1.
- Worktrees carry optional `task` and `owner` metadata so a session running several at once can tell them apart; `status --json` also reports live git state (`dirty`, `ahead`, `behind`, `head`).
- `create` and `research` serialize on `{worktrees_dir}/.arbor/lock`, since both fetch and write refs in the shared main repo.
