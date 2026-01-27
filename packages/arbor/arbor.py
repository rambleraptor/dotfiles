import json
import os
import subprocess
from pathlib import Path
from typing import List, Optional

import typer
from git import Repo
from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()

CONFIG_PATH = Path.home() / ".arbor_config.json"

class Config(BaseModel):
    worktrees_dir: Path
    projects: dict[str, Path] = Field(default_factory=dict)

class WorktreeInfo(BaseModel):
    name: str
    repo_name: str
    branch: str
    pr_number: Optional[int] = None
    pr_status: Optional[str] = "None"

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
    return get_arbor_dir(worktrees_dir) / f"{name}.json"

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
def import_project(path: str, name: Optional[str] = None):
    """Import a git repository into arbor."""
    config = get_config()
    if not config:
        console.print("[red]Arbor not initialized. Run 'arbor init' first.[/red]")
        raise typer.Exit(1)

    repo_path = Path(path).expanduser().resolve()
    if not (repo_path / ".git").exists():
        console.print(f"[red]Path {repo_path} does not appear to be a git repository.[/red]")
        raise typer.Exit(1)

    repo_name = name or repo_path.name
    config.projects[repo_name] = repo_path
    save_config(config)
    console.print(f"[green]Imported {repo_name} from {repo_path}[/green]")

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

@app.command()
def status():
    """Show the status of all worktrees and their PRs."""
    config = get_config()
    if not config:
        console.print("[red]Arbor not initialized. Run 'arbor init' first.[/red]")
        raise typer.Exit(1)

    arbor_dir = get_arbor_dir(config.worktrees_dir)
    json_files = list(arbor_dir.glob("*.json"))
    
    if not json_files:
        console.print("No worktrees found.")
        return

    table = Table(title="Arbor Worktrees")
    table.add_column("Worktree", style="cyan")
    table.add_column("Repo", style="magenta")
    table.add_column("Branch", style="green")
    table.add_column("PR", style="blue")
    table.add_column("Status", style="yellow")

    for f in json_files:
        info = WorktreeInfo.model_validate_json(f.read_text())
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

@app.command()
def cleanup():
    """Delete worktrees where PRs have been merged."""
    config = get_config()
    if not config:
        console.print("[red]Arbor not initialized. Run 'arbor init' first.[/red]")
        raise typer.Exit(1)

    arbor_dir = get_arbor_dir(config.worktrees_dir)
    json_files = list(arbor_dir.glob("*.json"))
    
    cleaned = 0
    for f in json_files:
        info = WorktreeInfo.model_validate_json(f.read_text())
        repo_path = config.projects.get(info.repo_name)
        
        if not repo_path:
            console.print(f"[yellow]Skipping {info.name}: Repo {info.repo_name} not found in config.[/yellow]")
            continue
            
        _, pr_status = get_gh_pr_status(repo_path, info.branch)
        
        # Use updated status if available, otherwise use cached
        current_status = pr_status or info.pr_status
        
        if current_status and current_status.upper() == "MERGED":
            console.print(f"Cleaning up merged worktree: [blue]{info.name}[/blue]")
            worktree_path = config.worktrees_dir / info.name
            
            try:
                # Remove worktree
                subprocess.run(
                    ["git", "-C", str(repo_path), "worktree", "remove", str(worktree_path)],
                    check=True,
                    capture_output=True,
                    text=True
                )
                # Remove metadata file
                f.unlink()
                cleaned += 1
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Failed to remove worktree {info.name}: {e.stderr}[/red]")

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
