import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import typer
from git import Repo
from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()
# Use for human-facing output on commands whose stdout is consumed by the shell
# wrapper (e.g. 'arbor research' prints the worktree path to stdout so the shell
# can cd into it).
err_console = Console(stderr=True)

CONFIG_PATH = Path.home() / ".arbor_config.json"

# Research worktrees are short-lived, detached checkouts used to give LLMs
# context. They live under this subdirectory so they don't clutter the regular
# worktrees, and are auto-expired after RESEARCH_TTL_DAYS.
RESEARCH_SUBDIR = "research"
RESEARCH_TTL_DAYS = 3

# Memorable, throwaway names for ephemeral research worktrees. We pair an
# adjective with a noun (e.g. "brave-otter") so each worktree is easy to refer
# to with 'arbor cd <name>' while still being unique.
_RESEARCH_ADJECTIVES = [
    "brave", "calm", "clever", "swift", "quiet", "bright", "bold", "lush",
    "keen", "spry", "merry", "nimble", "sunny", "gentle", "wily", "amber",
]
_RESEARCH_NOUNS = [
    "otter", "falcon", "maple", "cedar", "heron", "lynx", "willow", "raven",
    "badger", "ferret", "marten", "sparrow", "thistle", "comet", "harbor", "fern",
]

def generate_research_name(worktrees_dir: Path) -> str:
    """Return a memorable name for a research worktree that isn't in use yet."""
    research_dir = worktrees_dir / RESEARCH_SUBDIR
    for _ in range(100):
        name = f"{secrets.choice(_RESEARCH_ADJECTIVES)}-{secrets.choice(_RESEARCH_NOUNS)}"
        if not (research_dir / name).exists():
            return name
    # Astronomically unlikely; fall back to a random suffix to guarantee progress.
    return f"research-{secrets.token_hex(4)}"

class Config(BaseModel):
    worktrees_dir: Path
    projects: dict[str, Path] = Field(default_factory=dict)

class WorktreeInfo(BaseModel):
    name: str
    repo_name: str
    branch: str
    pr_number: Optional[int] = None
    pr_status: Optional[str] = "None"
    # "work" (a normal branch worktree) or "research" (short-lived, detached).
    kind: str = "work"
    # ISO-8601 UTC timestamp, set for research worktrees to drive TTL cleanup.
    created_at: Optional[str] = None

def get_config() -> Optional[Config]:
    if not CONFIG_PATH.exists():
        return None
    return Config.model_validate_json(CONFIG_PATH.read_text())

def save_config(config: Config):
    CONFIG_PATH.write_text(config.model_dump_json(indent=2))

def get_arbor_dir(worktrees_dir: Path) -> Path:
    arbor_dir = worktrees_dir / ".arbor"
    arbor_dir.mkdir(parents=True, exist_ok=True)
    return arbor_dir

def get_worktree_file(worktrees_dir: Path, name: str) -> Path:
    file_path = get_arbor_dir(worktrees_dir) / f"{name}.json"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    return file_path

def find_project_by_path(config: Config, path: Path) -> Optional[str]:
    target = path.resolve()
    for name, p in config.projects.items():
        if p.resolve() == target:
            return name
    return None

def get_git_info(path: Path):
    try:
        # Get absolute path to the git common directory (main repo .git)
        res = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, check=True
        )
        common_dir_str = res.stdout.strip()
        common_dir = Path(common_dir_str)
        if not common_dir.is_absolute():
            common_dir = (path / common_dir).resolve()
        else:
            common_dir = common_dir.resolve()
        
        # Get absolute path to the current worktree's top level
        res = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        toplevel = Path(res.stdout.strip()).resolve()
        
        return common_dir, toplevel
    except subprocess.CalledProcessError:
        return None, None

def is_git_dirty(path: Path) -> bool:
    res = subprocess.run(
        ["git", "-C", str(path), "status", "--porcelain"],
        capture_output=True, text=True, check=True
    )
    return bool(res.stdout.strip())

def _create_worktree(config: Config, repo_name: str, branch: str, repo_path: Path):
    worktree_path = config.worktrees_dir / branch
    if worktree_path.exists():
        console.print(f"[red]Worktree directory {worktree_path} already exists.[/red]")
        raise typer.Exit(1)

    console.print(f"Creating worktree for [blue]{repo_name}[/blue] on branch [yellow]{branch}[/yellow]...")
    
    try:
        # Check if branch exists
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--verify", branch],
            capture_output=True,
            text=True
        )
        
        cmd = ["git", "-C", str(repo_path), "worktree", "add", str(worktree_path)]
        if result.returncode != 0:
            console.print(f"Branch [yellow]{branch}[/yellow] does not exist. Creating it.")
            cmd.append("-b")
        
        cmd.append(branch)
        
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        
        # Save metadata
        info = WorktreeInfo(name=branch, repo_name=repo_name, branch=branch)
        get_worktree_file(config.worktrees_dir, branch).write_text(info.model_dump_json(indent=2))
        
        console.print(f"[green]Worktree created at {worktree_path}[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to create worktree: {e.stderr}[/red]")
        raise typer.Exit(1)

@app.command()
def init(worktrees_dir: str):
    """Initialize arbor with a worktrees directory."""
    config = Config(
        worktrees_dir=Path(worktrees_dir).expanduser().resolve()
    )
    config.worktrees_dir.mkdir(parents=True, exist_ok=True)
    save_config(config)
    console.print(f"[green]Arbor initialized![/green]")
    console.print(f"Worktrees: {config.worktrees_dir}")

@app.command("import")
def import_command(
    path: Optional[str] = typer.Argument(None, help="Path to the repository or worktree"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Name for the project (if importing a repository)")
):
    """Import a git repository or worktree into arbor."""
    config = get_config()
    if not config:
        console.print("[red]Arbor not initialized. Run 'arbor init' first.[/red]")
        raise typer.Exit(1)

    target_path = Path(path or ".").expanduser().resolve()
    common_dir, toplevel = get_git_info(target_path)
    
    if not common_dir:
        console.print(f"[red]Path {target_path} does not appear to be a git repository.[/red]")
        raise typer.Exit(1)

    # The main repo is the parent of the common .git directory
    main_repo_path = common_dir.parent
    
    if main_repo_path == toplevel:
        # It's a main repository, import as project
        
        if is_git_dirty(toplevel):
            console.print("[red]Repo has uncommitted changes. Please commit or stash them first.[/red]")
            raise typer.Exit(1)

        repo_name = name or toplevel.name
        config.projects[repo_name] = toplevel
        save_config(config)
        console.print(f"[green]Imported project [bold]{repo_name}[/bold] from {toplevel}[/green]")
        
        # Check current branch and convert to worktree if applicable
        res = subprocess.run(
            ["git", "-C", str(toplevel), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True
        )
        current_branch = res.stdout.strip()
        
        if current_branch != "HEAD":
            console.print(f"Converting current branch [yellow]{current_branch}[/yellow] into a worktree...")
            subprocess.run(["git", "-C", str(toplevel), "checkout", "--detach"], check=True)
            try:
                _create_worktree(config, repo_name, current_branch, toplevel)
            except Exception:
                console.print(f"[red]Failed to create worktree for {current_branch}. Restoring checkout...[/red]")
                subprocess.run(["git", "-C", str(toplevel), "checkout", current_branch], check=False)
                raise
            
    else:
        # It's a worktree
        # Verify it's inside the worktrees_dir
        try:
            toplevel.relative_to(config.worktrees_dir)
        except ValueError:
            console.print(f"[red]Worktree {toplevel} must be located inside the configured worktrees directory: {config.worktrees_dir}[/red]")
            raise typer.Exit(1)
            
        repo_name = find_project_by_path(config, main_repo_path)
        if not repo_name:
            console.print(f"[red]Main repository {main_repo_path} is not imported into Arbor.[/red]")
            console.print(f"Please run 'arbor import {main_repo_path}' first to register the project.")
            raise typer.Exit(1)
            
        # Get branch name
        branch = subprocess.run(
            ["git", "-C", str(toplevel), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        
        # We use the relative path from worktrees_dir as the worktree name
        worktree_name = str(toplevel.relative_to(config.worktrees_dir))
        info = WorktreeInfo(name=worktree_name, repo_name=repo_name, branch=branch)
        get_worktree_file(config.worktrees_dir, worktree_name).write_text(info.model_dump_json(indent=2))
        
        console.print(f"[green]Imported worktree [bold]{worktree_name}[/bold] for project [bold]{repo_name}[/bold][/green]")
        console.print(f"Branch: [yellow]{branch}[/yellow]")

@app.command()
def create(repo_name: str, branch: str):
    """Create a new worktree for a repo and branch."""
    config = get_config()
    if not config:
        console.print("[red]Arbor not initialized. Run 'arbor init' first.[/red]")
        raise typer.Exit(1)

    repo_path = config.projects.get(repo_name)
    if not repo_path:
        console.print(f"[red]Repo {repo_name} not found in arbor. Use 'arbor import' to add it.[/red]")
        raise typer.Exit(1)
    
    if not repo_path.exists():
        console.print(f"[red]Repo path {repo_path} for {repo_name} no longer exists.[/red]")
        raise typer.Exit(1)

    _create_worktree(config, repo_name, branch, repo_path)

def _ref_exists(repo_path: Path, ref: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "--verify", "--quiet", ref],
        capture_output=True, text=True
    ).returncode == 0

def get_remote_default_branch(repo_path: Path, remote: str) -> Optional[str]:
    """Return the default branch of a remote as e.g. 'origin/main'."""
    def _read_head() -> Optional[str]:
        res = subprocess.run(
            ["git", "-C", str(repo_path), "symbolic-ref", f"refs/remotes/{remote}/HEAD"],
            capture_output=True, text=True
        )
        if res.returncode == 0:
            return res.stdout.strip().replace("refs/remotes/", "", 1)
        return None

    ref = _read_head()
    if ref:
        return ref
    # The remote HEAD may not be recorded locally yet; ask the remote.
    subprocess.run(
        ["git", "-C", str(repo_path), "remote", "set-head", remote, "-a"],
        capture_output=True, text=True
    )
    return _read_head()

def resolve_research_base(repo_path: Path) -> str:
    """Resolve the base ref for a research worktree.

    Prefers upstream/main, fetching upstream first. Falls back to origin's
    default branch when no upstream remote exists.
    """
    remotes = subprocess.run(
        ["git", "-C", str(repo_path), "remote"],
        capture_output=True, text=True, check=True
    ).stdout.split()

    if "upstream" in remotes:
        err_console.print("Fetching [blue]upstream[/blue]...")
        subprocess.run(["git", "-C", str(repo_path), "fetch", "--quiet", "upstream"], check=True)
        if _ref_exists(repo_path, "upstream/main"):
            return "upstream/main"
        default = get_remote_default_branch(repo_path, "upstream")
        if default and _ref_exists(repo_path, default):
            return default

    if "origin" in remotes:
        err_console.print("Fetching [blue]origin[/blue]...")
        subprocess.run(["git", "-C", str(repo_path), "fetch", "--quiet", "origin"], check=True)
        default = get_remote_default_branch(repo_path, "origin")
        if default and _ref_exists(repo_path, default):
            return default
        for candidate in ("origin/main", "origin/master"):
            if _ref_exists(repo_path, candidate):
                return candidate

    err_console.print("[red]Could not resolve a base ref (no upstream/origin default branch found).[/red]")
    raise typer.Exit(1)

def research_age_days(info: WorktreeInfo) -> Optional[int]:
    if not info.created_at:
        return None
    try:
        created = datetime.fromisoformat(info.created_at)
    except ValueError:
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - created).days

@app.command()
def research(
    repo_name: str,
    pr: Optional[int] = typer.Option(None, "--pr", help="PR number to check out (default: base branch HEAD)"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Name for the research worktree"),
):
    """Create a short-lived research worktree for feeding context to an LLM.

    With --pr, checks out that PR (detached). Otherwise checks out the base
    branch HEAD (upstream/main, falling back to origin's default branch).
    Research worktrees live under '<worktrees>/research/' and are auto-expired
    by 'arbor cleanup' after a few days.
    """
    config = get_config()
    if not config:
        err_console.print("[red]Arbor not initialized. Run 'arbor init' first.[/red]")
        raise typer.Exit(1)

    repo_path = config.projects.get(repo_name)
    if not repo_path:
        err_console.print(f"[red]Repo {repo_name} not found in arbor. Use 'arbor import' to add it.[/red]")
        raise typer.Exit(1)
    if not repo_path.exists():
        err_console.print(f"[red]Repo path {repo_path} for {repo_name} no longer exists.[/red]")
        raise typer.Exit(1)

    if not name:
        # Research worktrees are ephemeral: give each a unique, memorable name
        # rather than reusing a single "base" slot.
        name = generate_research_name(config.worktrees_dir)
        if pr:
            name = f"pr-{pr}-{name}"
    rel_name = f"{RESEARCH_SUBDIR}/{name}"
    worktree_path = config.worktrees_dir / rel_name

    if worktree_path.exists():
        err_console.print(f"[red]Research worktree {worktree_path} already exists.[/red]")
        err_console.print("Remove it first or pass a different [yellow]--name[/yellow].")
        raise typer.Exit(1)

    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if pr is not None:
            err_console.print(f"Creating research worktree for [blue]{repo_name}[/blue] PR [yellow]#{pr}[/yellow]...")
            # Create an empty detached worktree, then let gh fetch + check out the PR.
            subprocess.run(
                ["git", "-C", str(repo_path), "worktree", "add", "--detach", str(worktree_path)],
                check=True, capture_output=True, text=True
            )
            try:
                subprocess.run(
                    ["gh", "pr", "checkout", str(pr), "--detach"],
                    cwd=worktree_path, check=True, capture_output=True, text=True
                )
            except subprocess.CalledProcessError as e:
                subprocess.run(
                    ["git", "-C", str(repo_path), "worktree", "remove", "--force", str(worktree_path)],
                    check=False, capture_output=True, text=True
                )
                err_console.print(f"[red]Failed to check out PR #{pr}: {e.stderr}[/red]")
                raise typer.Exit(1)
            branch_desc = f"PR #{pr}"
        else:
            base = resolve_research_base(repo_path)
            err_console.print(f"Creating research worktree for [blue]{repo_name}[/blue] at [yellow]{base}[/yellow]...")
            subprocess.run(
                ["git", "-C", str(repo_path), "worktree", "add", "--detach", str(worktree_path), base],
                check=True, capture_output=True, text=True
            )
            branch_desc = base
    except subprocess.CalledProcessError as e:
        err_console.print(f"[red]Failed to create research worktree: {e.stderr}[/red]")
        raise typer.Exit(1)

    info = WorktreeInfo(
        name=rel_name,
        repo_name=repo_name,
        branch=branch_desc,
        pr_number=pr,
        kind="research",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    get_worktree_file(config.worktrees_dir, rel_name).write_text(info.model_dump_json(indent=2))

    err_console.print(f"[green]Research worktree created at {worktree_path}[/green]")
    # Print the bare path to stdout so the shell wrapper can cd into it.
    print(worktree_path)

def get_gh_pr_status(repo_path: Path, branch: str) -> tuple[Optional[int], Optional[str]]:
    """Get PR number and status using 'gh' CLI."""
    try:
        # Check if there is a PR for this branch
        result = subprocess.run(
            ["gh", "pr", "view", branch, "--json", "number,state"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data["number"], data["state"]
    except Exception:
        pass
    return None, None

@app.command("cd")
@app.command("c", hidden=True)
def cd_command(name: str):
    """Print the path to a worktree for shell integration."""
    config = get_config()
    if not config:
        print("Arbor not initialized. Run 'arbor init' first.", file=sys.stderr)
        raise typer.Exit(1)

    # Try direct path first
    worktree_path = config.worktrees_dir / name
    if worktree_path.exists() and (worktree_path / ".git").exists():
        print(worktree_path)
        return

    # Try searching metadata
    arbor_dir = get_arbor_dir(config.worktrees_dir)
    # Check if a direct json file exists
    meta_file = arbor_dir / f"{name}.json"
    if meta_file.exists():
        info = WorktreeInfo.model_validate_json(meta_file.read_text())
        print(config.worktrees_dir / info.name)
        return

    # Recursive search
    json_files = list(arbor_dir.glob("**/*.json"))
    for f in json_files:
        # Check if the name matches the stem (e.g. "feature-branch") 
        # or the full relative path name in metadata
        if f.stem == name:
            info = WorktreeInfo.model_validate_json(f.read_text())
            print(config.worktrees_dir / info.name)
            return
        
        info = WorktreeInfo.model_validate_json(f.read_text())
        if info.name == name:
            print(config.worktrees_dir / info.name)
            return

    print(f"Worktree '{name}' not found.", file=sys.stderr)
    raise typer.Exit(1)

@app.command()
def status():
    """Show the status of all worktrees and their PRs."""
    config = get_config()
    if not config:
        console.print("[red]Arbor not initialized. Run 'arbor init' first.[/red]")
        raise typer.Exit(1)

    arbor_dir = get_arbor_dir(config.worktrees_dir)
    json_files = list(arbor_dir.glob("**/*.json"))

    if not json_files:
        console.print("No worktrees found.")
        return

    infos = [(f, WorktreeInfo.model_validate_json(f.read_text())) for f in json_files]
    work = [(f, i) for f, i in infos if i.kind != "research"]
    research = [(f, i) for f, i in infos if i.kind == "research"]

    if work:
        table = Table(title="Arbor Worktrees")
        table.add_column("Worktree", style="cyan")
        table.add_column("Repo", style="magenta")
        table.add_column("Branch", style="green")
        table.add_column("PR", style="blue")
        table.add_column("Status", style="yellow")

        for f, info in work:
            repo_path = config.projects.get(info.repo_name)

            if not repo_path:
                # Maybe the repo was removed from arbor config
                table.add_row(
                    info.name,
                    f"{info.repo_name} (Missing)",
                    info.branch,
                    str(info.pr_number) if info.pr_number else "-",
                    info.pr_status or "None"
                )
                continue

            # Update status from GH
            pr_number, pr_status = get_gh_pr_status(repo_path, info.branch)
            if pr_status:
                info.pr_number = pr_number
                info.pr_status = pr_status
                f.write_text(info.model_dump_json(indent=2))

            table.add_row(
                info.name,
                info.repo_name,
                info.branch,
                str(info.pr_number) if info.pr_number else "-",
                info.pr_status or "None"
            )

        console.print(table)

    if research:
        rtable = Table(title="Research Worktrees")
        rtable.add_column("Worktree", style="cyan")
        rtable.add_column("Repo", style="magenta")
        rtable.add_column("Source", style="green")
        rtable.add_column("Age", style="yellow")

        for f, info in research:
            age = research_age_days(info)
            age_str = "-" if age is None else (f"{age}d" if age else "today")
            rtable.add_row(info.name, info.repo_name, info.branch, age_str)

        console.print(rtable)

def _remove_worktree(repo_path: Path, worktree_path: Path, meta_file: Path, force: bool = False) -> bool:
    cmd = ["git", "-C", str(repo_path), "worktree", "remove", str(worktree_path)]
    if force:
        cmd.append("--force")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        meta_file.unlink()
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to remove worktree {worktree_path.name}: {e.stderr}[/red]")
        return False

@app.command()
def cleanup(
    research_ttl: int = typer.Option(
        RESEARCH_TTL_DAYS, "--research-ttl",
        help="Remove research worktrees older than this many days."
    ),
):
    """Delete merged worktrees and expired research worktrees."""
    config = get_config()
    if not config:
        console.print("[red]Arbor not initialized. Run 'arbor init' first.[/red]")
        raise typer.Exit(1)

    arbor_dir = get_arbor_dir(config.worktrees_dir)
    json_files = list(arbor_dir.glob("**/*.json"))

    cleaned = 0
    for f in json_files:
        info = WorktreeInfo.model_validate_json(f.read_text())
        repo_path = config.projects.get(info.repo_name)

        if not repo_path:
            console.print(f"[yellow]Skipping {info.name}: Repo {info.repo_name} not found in config.[/yellow]")
            continue

        worktree_path = config.worktrees_dir / info.name

        if info.kind == "research":
            age = research_age_days(info)
            if age is not None and age >= research_ttl:
                console.print(f"Cleaning up expired research worktree: [blue]{info.name}[/blue] ({age}d old)")
                # Research worktrees are detached and disposable; force removal.
                if _remove_worktree(repo_path, worktree_path, f, force=True):
                    cleaned += 1
            continue

        _, pr_status = get_gh_pr_status(repo_path, info.branch)

        # Use updated status if available, otherwise use cached
        current_status = pr_status or info.pr_status

        if current_status and current_status.upper() == "MERGED":
            console.print(f"Cleaning up merged worktree: [blue]{info.name}[/blue]")
            if _remove_worktree(repo_path, worktree_path, f):
                cleaned += 1

    if cleaned == 0:
        console.print("Nothing to clean up.")
    else:
        console.print(f"[green]Cleaned up {cleaned} worktrees.[/green]")

@app.command()
def config():
    """Show current configuration."""
    cfg = get_config()
    if not cfg:
        console.print("[red]Arbor not initialized. Run 'arbor init' first.[/red]")
        return
    console.print(f"Worktrees: [blue]{cfg.worktrees_dir}[/blue]")
    console.print("\n[bold]Projects:[/bold]")
    if not cfg.projects:
        console.print("  No projects imported yet.")
    else:
        for name, path in cfg.projects.items():
            console.print(f"  [green]{name}[/green]: {path}")

if __name__ == "__main__":
    app()
