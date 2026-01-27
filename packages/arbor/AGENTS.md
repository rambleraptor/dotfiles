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
Adds a local Git repository to Arbor's registry.
```bash
arbor import /path/to/repo --name my-project
```

### `create`
Creates a new worktree for a registered project on a specific branch. If the branch doesn't exist, it creates it.
```bash
arbor create my-project feature/cool-thing
```

### `status`
Displays a table of all active worktrees, their associated project, branch, PR number, and current GitHub status.
```bash
arbor status
```

### `cleanup`
Scans all active worktrees and removes those whose PRs have been merged on GitHub.
```bash
arbor cleanup
```

### `config`
Displays the current Arbor configuration, including the worktrees directory and imported projects.
```bash
arbor config
```

## Internal Architecture

### Configuration
- **Global Config**: Stored at `~/.arbor_config.json`. It tracks the `worktrees_dir` and a mapping of project names to their local filesystem paths.
- **Worktree Metadata**: Each worktree has a corresponding JSON file in `{worktrees_dir}/.arbor/{branch_name}.json`, storing specific metadata like the repo name and cached PR info.

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
