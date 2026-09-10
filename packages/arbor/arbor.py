import fcntl
import json
import re
import secrets
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, NamedTuple, Optional

import typer
from git import Repo
from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()
# Use for human-facing output on commands whose stdout is consumed by a caller
# (e.g. 'arbor research' prints the worktree path to stdout so the shell wrapper
# can cd into it, and 'arbor status --json' prints a JSON document).
err_console = Console(stderr=True)
_stdout_console = console

CONFIG_PATH = Path.home() / ".arbor_config.json"

# When JSON mode is on, stdout carries exactly one JSON document and every
# human-facing message moves to stderr, so an agent can parse stdout without
# stripping Rich formatting.
JSON_MODE = False

# Mutating commands take an exclusive lock: 'git fetch' and 'git worktree add'
# both write to the shared main repo, so parallel agents creating worktrees at
# the same moment can otherwise corrupt each other's view of the remotes.
LOCK_TIMEOUT_SECONDS = 120

# PR lookups are network-bound, so we run them concurrently. Each call also gets
# a timeout so one hung request can't stall the whole table.
PR_LOOKUP_WORKERS = 8
GH_TIMEOUT_SECONDS = 30

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

def set_json_mode(enabled: bool) -> None:
    """Reserve stdout for the JSON payload by moving human output to stderr."""
    global JSON_MODE, console
    JSON_MODE = enabled
    console = err_console if enabled else _stdout_console

def emit(payload: dict[str, Any]) -> None:
    """Write the machine-readable result to stdout, when asked for."""
    if JSON_MODE:
        print(json.dumps(payload, indent=2, default=str))

def fail(message: str, code: str = "error") -> typer.Exit:
    """Report an error and return the exception to raise.

    Errors always go to stderr, even in plain mode: several commands put a path
    or a JSON document on stdout, and a caller reading that stream must never
    pick up an error message as if it were the result.
    """
    if JSON_MODE:
        print(json.dumps({"ok": False, "error": message, "code": code}, indent=2))
    else:
        err_console.print(f"[red]{message}[/red]")
    return typer.Exit(1)

@contextmanager
def arbor_lock(worktrees_dir: Path, timeout: int = LOCK_TIMEOUT_SECONDS):
    """Hold an exclusive lock across worktree mutations.

    Creating a worktree fetches and writes refs in the shared main repo, so
    parallel agents have to take turns. Read-only commands ('status', 'cd')
    never take this lock, so a long fan-out can still be inspected while it runs.
    """
    lock_path = get_arbor_dir(worktrees_dir) / "lock"
    deadline = time.monotonic() + timeout
    with open(lock_path, "w") as handle:
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise fail(
                        f"Timed out after {timeout}s waiting for the arbor lock at {lock_path}.",
                        "lock_timeout",
                    )
                time.sleep(0.2)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)

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
    # Free-form note describing what this worktree is for, so a session that
    # fanned out several of them can tell them apart later.
    task: Optional[str] = None
    # Who asked for this worktree - typically an agent or session identifier.
    owner: Optional[str] = None

def get_config() -> Optional[Config]:
    if not CONFIG_PATH.exists():
        return None
    return Config.model_validate_json(CONFIG_PATH.read_text())

def require_config() -> Config:
    config = get_config()
    if not config:
        raise fail("Arbor not initialized. Run 'arbor init' first.", "not_initialized")
    return config

def require_project(config: Config, repo_name: str) -> Path:
    repo_path = config.projects.get(repo_name)
    if not repo_path:
        raise fail(
            f"Repo {repo_name} not found in arbor. Use 'arbor import' to add it.",
            "unknown_project",
        )
    if not repo_path.exists():
        raise fail(
            f"Repo path {repo_path} for {repo_name} no longer exists.",
            "missing_repo_path",
        )
    return repo_path

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

def _create_worktree(
    config: Config,
    repo_name: str,
    branch: str,
    repo_path: Path,
    base: Optional[str] = None,
    task: Optional[str] = None,
    owner: Optional[str] = None,
) -> tuple[Path, WorktreeInfo]:
    """Add a worktree for 'branch' and record its metadata.

    'base' is the start point for a branch that doesn't exist yet. An existing
    branch is checked out where it already is, so a base is meaningless there.
    """
    worktree_path = config.worktrees_dir / branch
    if worktree_path.exists():
        raise fail(f"Worktree directory {worktree_path} already exists.", "worktree_exists")

    err_console.print(f"Creating worktree for [blue]{repo_name}[/blue] on branch [yellow]{branch}[/yellow]...")

    try:
        # Check if branch exists
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--verify", branch],
            capture_output=True,
            text=True
        )

        cmd = ["git", "-C", str(repo_path), "worktree", "add", str(worktree_path)]
        if result.returncode != 0:
            where = f" from [blue]{base}[/blue]" if base else ""
            err_console.print(f"Branch [yellow]{branch}[/yellow] does not exist. Creating it{where}.")
            cmd += ["-b", branch]
            if base:
                cmd.append(base)
        else:
            cmd.append(branch)

        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )

        # Save metadata
        info = WorktreeInfo(
            name=branch, repo_name=repo_name, branch=branch, task=task, owner=owner
        )
        get_worktree_file(config.worktrees_dir, branch).write_text(info.model_dump_json(indent=2))

        err_console.print(f"[green]Worktree created at {worktree_path}[/green]")
        return worktree_path, info
    except subprocess.CalledProcessError as e:
        raise fail(f"Failed to create worktree: {e.stderr}", "worktree_add_failed")

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
    config = require_config()

    target_path = Path(path or ".").expanduser().resolve()
    common_dir, toplevel = get_git_info(target_path)
    
    if not common_dir:
        raise fail(f"Path {target_path} does not appear to be a git repository.", "not_a_repo")

    # The main repo is the parent of the common .git directory
    main_repo_path = common_dir.parent
    
    if main_repo_path == toplevel:
        # It's a main repository, import as project
        
        if is_git_dirty(toplevel):
            raise fail(
                "Repo has uncommitted changes. Please commit or stash them first.",
                "dirty_repo",
            )

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
            raise fail(
                f"Worktree {toplevel} must be located inside the configured worktrees "
                f"directory: {config.worktrees_dir}",
                "outside_worktrees_dir",
            )
            
        repo_name = find_project_by_path(config, main_repo_path)
        if not repo_name:
            raise fail(
                f"Main repository {main_repo_path} is not imported into Arbor. "
                f"Run 'arbor import {main_repo_path}' first to register the project.",
                "unknown_project",
            )
            
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
def create(
    repo_name: str,
    branch: str,
    base: Optional[str] = typer.Option(
        None, "--base",
        help="Ref to branch from. Defaults to the upstream main branch."
    ),
    no_fetch: bool = typer.Option(
        False, "--no-fetch",
        help="Resolve the base from local refs instead of fetching first."
    ),
    task: Optional[str] = typer.Option(
        None, "--task", help="What this worktree is for; recorded in metadata."
    ),
    owner: Optional[str] = typer.Option(
        None, "--owner", help="Who owns this worktree, e.g. an agent or session id."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON on stdout."),
):
    """Create a new worktree for a repo and branch, branched from main.

    The worktree path is printed to stdout so a caller can act on it directly;
    everything else goes to stderr.
    """
    set_json_mode(json_out)
    config = require_config()
    repo_path = require_project(config, repo_name)

    with arbor_lock(config.worktrees_dir):
        start_point = base or resolve_base_ref(repo_path, fetch=not no_fetch)
        worktree_path, info = _create_worktree(
            config, repo_name, branch, repo_path, base=start_point, task=task, owner=owner
        )

    if json_out:
        emit({
            "ok": True,
            "name": info.name,
            "path": str(worktree_path),
            "repo": repo_name,
            "branch": branch,
            "base": start_point,
            "task": task,
            "owner": owner,
        })
    else:
        print(worktree_path)

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

def find_base_ref(repo_path: Path, fetch: bool = True) -> Optional[str]:
    """Resolve the ref that new worktrees should start from: the main branch.

    Prefers upstream/main, fetching upstream first so that every worktree cut
    during a fan-out starts from the same fresh commit rather than from whatever
    the main repo's HEAD happens to be. Falls back to origin's default branch
    when the repo has no upstream remote, and returns None when neither yields
    one.
    """
    remotes = subprocess.run(
        ["git", "-C", str(repo_path), "remote"],
        capture_output=True, text=True, check=True
    ).stdout.split()

    if "upstream" in remotes:
        if fetch:
            err_console.print("Fetching [blue]upstream[/blue]...")
            subprocess.run(["git", "-C", str(repo_path), "fetch", "--quiet", "upstream"], check=True)
        if _ref_exists(repo_path, "upstream/main"):
            return "upstream/main"
        default = get_remote_default_branch(repo_path, "upstream")
        if default and _ref_exists(repo_path, default):
            return default

    if "origin" in remotes:
        if fetch:
            err_console.print("Fetching [blue]origin[/blue]...")
            subprocess.run(["git", "-C", str(repo_path), "fetch", "--quiet", "origin"], check=True)
        default = get_remote_default_branch(repo_path, "origin")
        if default and _ref_exists(repo_path, default):
            return default
        for candidate in ("origin/main", "origin/master"):
            if _ref_exists(repo_path, candidate):
                return candidate

    return None

def resolve_base_ref(repo_path: Path, fetch: bool = True) -> str:
    """find_base_ref, but a missing base branch is a hard error."""
    base = find_base_ref(repo_path, fetch=fetch)
    if not base:
        raise fail(
            f"Could not resolve a base ref for {repo_path} "
            "(no upstream/origin default branch found).",
            "no_base_ref",
        )
    return base

def base_branch_name(base_ref: str) -> str:
    """Strip the remote prefix from a base ref: 'upstream/main' -> 'main'."""
    return base_ref.split("/", 1)[1] if "/" in base_ref else base_ref

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
    task: Optional[str] = typer.Option(
        None, "--task", help="What this worktree is for; recorded in metadata."
    ),
    owner: Optional[str] = typer.Option(
        None, "--owner", help="Who owns this worktree, e.g. an agent or session id."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON on stdout."),
):
    """Create a short-lived research worktree for feeding context to an LLM.

    With --pr, checks out that PR (detached). Otherwise checks out the base
    branch HEAD (upstream/main, falling back to origin's default branch).
    Research worktrees live under '<worktrees>/research/' and are auto-expired
    by 'arbor cleanup' after a few days.
    """
    set_json_mode(json_out)
    config = require_config()
    repo_path = require_project(config, repo_name)

    if not name:
        # Research worktrees are ephemeral: give each a unique, memorable name
        # rather than reusing a single "base" slot.
        name = generate_research_name(config.worktrees_dir)
        if pr:
            name = f"pr-{pr}-{name}"
    rel_name = f"{RESEARCH_SUBDIR}/{name}"
    worktree_path = config.worktrees_dir / rel_name

    if worktree_path.exists():
        raise fail(
            f"Research worktree {worktree_path} already exists. "
            "Remove it first or pass a different --name.",
            "worktree_exists",
        )

    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    with arbor_lock(config.worktrees_dir):
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
                    raise fail(f"Failed to check out PR #{pr}: {e.stderr}", "pr_checkout_failed")
                branch_desc = f"PR #{pr}"
            else:
                base = resolve_base_ref(repo_path)
                err_console.print(f"Creating research worktree for [blue]{repo_name}[/blue] at [yellow]{base}[/yellow]...")
                subprocess.run(
                    ["git", "-C", str(repo_path), "worktree", "add", "--detach", str(worktree_path), base],
                    check=True, capture_output=True, text=True
                )
                branch_desc = base
        except subprocess.CalledProcessError as e:
            raise fail(f"Failed to create research worktree: {e.stderr}", "worktree_add_failed")

    info = WorktreeInfo(
        name=rel_name,
        repo_name=repo_name,
        branch=branch_desc,
        pr_number=pr,
        kind="research",
        created_at=datetime.now(timezone.utc).isoformat(),
        task=task,
        owner=owner,
    )
    get_worktree_file(config.worktrees_dir, rel_name).write_text(info.model_dump_json(indent=2))

    err_console.print(f"[green]Research worktree created at {worktree_path}[/green]")
    if json_out:
        emit({
            "ok": True,
            "name": rel_name,
            "path": str(worktree_path),
            "repo": repo_name,
            "source": branch_desc,
            "pr_number": pr,
            "kind": "research",
            "task": task,
            "owner": owner,
        })
    else:
        # Print the bare path to stdout so the shell wrapper can cd into it.
        print(worktree_path)

class PRLookup(NamedTuple):
    """Outcome of a PR lookup: found, absent, or failed.

    These are three distinct states, not two: a PR was found (number/state
    set), there is genuinely no PR (all fields None), or the lookup itself
    failed (error set). Collapsing the third into the second hides broken 'gh'
    auth and makes 'cleanup' silently do nothing, so callers must branch on
    'error' before reading 'state'.
    """
    number: Optional[int] = None
    state: Optional[str] = None
    error: Optional[str] = None


_GITHUB_REMOTE_RE = re.compile(
    r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/\s]+?)(?:\.git)?/?$"
)


def parse_github_remote(repo_path: Path, remote: str) -> Optional[tuple[str, str]]:
    """Return (owner, repo) for a remote pointing at GitHub, else None."""
    res = subprocess.run(
        ["git", "-C", str(repo_path), "remote", "get-url", remote],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        return None
    match = _GITHUB_REMOTE_RE.search(res.stdout.strip())
    return (match.group("owner"), match.group("repo")) if match else None


@lru_cache(maxsize=None)
def get_origin_owner(repo_path: Path) -> Optional[str]:
    """GitHub owner of the 'origin' remote, used to disambiguate PR matches."""
    parsed = parse_github_remote(repo_path, "origin")
    return parsed[0] if parsed else None


def _pick_pr(prs: list[dict], owner: Optional[str]) -> dict:
    """Choose the most relevant PR when a head branch name matches several."""
    def rank(pr: dict):
        head_owner = (pr.get("headRepositoryOwner") or {}).get("login")
        return (
            owner is not None and head_owner == owner,
            (pr.get("state") or "").upper() == "OPEN",
            pr.get("number") or 0,
        )
    return max(prs, key=rank)


def get_gh_pr_status(repo_path: Path, branch: str) -> PRLookup:
    """Look up the PR for a branch using the 'gh' CLI.

    Uses 'gh pr list --head', not 'gh pr view <branch>': in a fork workflow the
    PR head is '<fork-owner>:<branch>' on the upstream repo, which 'pr view'
    does not resolve. '--state all' is required to see MERGED/CLOSED PRs.
    """
    try:
        result = subprocess.run(
            [
                "gh", "pr", "list", "--head", branch, "--state", "all",
                "--json", "number,state,headRepositoryOwner", "--limit", "10",
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return PRLookup(error="gh CLI not found")
    except subprocess.TimeoutExpired:
        return PRLookup(error=f"gh timed out after {GH_TIMEOUT_SECONDS}s")

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        return PRLookup(error=detail[0] if detail else f"gh exited {result.returncode}")

    try:
        prs = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return PRLookup(error="could not parse gh output")

    if not prs:
        return PRLookup()

    pr = _pick_pr(prs, get_origin_owner(repo_path))
    return PRLookup(number=pr.get("number"), state=pr.get("state"))


def lookup_prs(jobs: dict[Path, tuple[Path, str]]) -> dict[Path, PRLookup]:
    """Resolve PR status for many worktrees at once, keyed by metadata file."""
    if not jobs:
        return {}

    keys = list(jobs)
    with err_console.status(f"Checking {len(keys)} branches on GitHub..."):
        with ThreadPoolExecutor(max_workers=PR_LOOKUP_WORKERS) as pool:
            results = pool.map(lambda k: get_gh_pr_status(*jobs[k]), keys)
            return dict(zip(keys, results))


def apply_lookup(info: WorktreeInfo, lookup: PRLookup, meta_file: Path) -> None:
    """Persist a successful lookup, writing only when something changed."""
    if lookup.error:
        return
    if info.pr_number == lookup.number and info.pr_status == lookup.state:
        return
    info.pr_number = lookup.number
    info.pr_status = lookup.state
    meta_file.write_text(info.model_dump_json(indent=2))

class ResolvedWorktree(NamedTuple):
    path: Path
    # Both are None for a directory that exists under the worktrees root but has
    # no arbor metadata - 'cd' still resolves those, commands that need a branch
    # or a repo don't.
    info: Optional[WorktreeInfo] = None
    meta_file: Optional[Path] = None


def resolve_worktree(config: Config, name: str) -> Optional[ResolvedWorktree]:
    """Find a worktree by short name, relative path, or metadata name."""
    # Try direct path first
    worktree_path = config.worktrees_dir / name
    arbor_dir = get_arbor_dir(config.worktrees_dir)
    meta_file = arbor_dir / f"{name}.json"

    if worktree_path.exists() and (worktree_path / ".git").exists():
        if meta_file.exists():
            info = WorktreeInfo.model_validate_json(meta_file.read_text())
            return ResolvedWorktree(worktree_path, info, meta_file)
        return ResolvedWorktree(worktree_path)

    # Check if a direct json file exists
    if meta_file.exists():
        info = WorktreeInfo.model_validate_json(meta_file.read_text())
        return ResolvedWorktree(config.worktrees_dir / info.name, info, meta_file)

    # Recursive search: match either the file stem (e.g. "feature-branch") or
    # the full relative path recorded in the metadata.
    for f in sorted(arbor_dir.glob("**/*.json")):
        info = WorktreeInfo.model_validate_json(f.read_text())
        if f.stem == name or info.name == name:
            return ResolvedWorktree(config.worktrees_dir / info.name, info, f)

    return None


def require_worktree(config: Config, name: str) -> ResolvedWorktree:
    found = resolve_worktree(config, name)
    if not found:
        raise fail(f"Worktree '{name}' not found.", "unknown_worktree")
    return found


@app.command("cd")
@app.command("c", hidden=True)
def cd_command(name: str):
    """Print the path to a worktree for shell integration."""
    config = get_config()
    if not config:
        print("Arbor not initialized. Run 'arbor init' first.", file=sys.stderr)
        raise typer.Exit(1)

    found = resolve_worktree(config, name)
    if not found:
        print(f"Worktree '{name}' not found.", file=sys.stderr)
        raise typer.Exit(1)
    print(found.path)


@app.command(
    "exec",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def exec_command(ctx: typer.Context, name: str):
    """Run a command inside a worktree: arbor exec <name> -- <cmd>...

    Lets a caller act on a worktree by name without first resolving its path,
    and exits with the command's own exit code.
    """
    config = require_config()
    found = require_worktree(config, name)

    argv = list(ctx.args)
    if not argv:
        raise fail("No command given. Usage: arbor exec <name> -- <cmd>...", "no_command")

    if not found.path.exists():
        raise fail(f"Worktree directory {found.path} does not exist.", "missing_worktree_dir")

    try:
        # stdio is inherited so output streams through unchanged.
        result = subprocess.run(argv, cwd=found.path)
    except FileNotFoundError:
        raise fail(f"Command not found: {argv[0]}", "command_not_found")
    raise typer.Exit(result.returncode)

class GitState(NamedTuple):
    """Local state of a worktree, relative to the ref it was branched from."""
    exists: bool = True
    dirty: Optional[bool] = None
    ahead: Optional[int] = None
    behind: Optional[int] = None
    head: Optional[str] = None


def get_git_state(worktree_path: Path, base_ref: Optional[str]) -> GitState:
    if not worktree_path.exists():
        return GitState(exists=False)

    head = subprocess.run(
        ["git", "-C", str(worktree_path), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True
    )
    dirty = subprocess.run(
        ["git", "-C", str(worktree_path), "status", "--porcelain"],
        capture_output=True, text=True
    )

    ahead = behind = None
    if base_ref:
        counts = subprocess.run(
            ["git", "-C", str(worktree_path), "rev-list", "--left-right", "--count",
             f"{base_ref}...HEAD"],
            capture_output=True, text=True
        )
        if counts.returncode == 0:
            parts = counts.stdout.split()
            if len(parts) == 2:
                behind, ahead = int(parts[0]), int(parts[1])

    return GitState(
        exists=True,
        dirty=bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
        ahead=ahead,
        behind=behind,
        head=head.stdout.strip() if head.returncode == 0 else None,
    )


def collect_git_states(
    config: Config, infos: list[tuple[Path, WorktreeInfo]]
) -> dict[Path, GitState]:
    """Read local git state for many worktrees at once, keyed by metadata file.

    Base refs are resolved without fetching: 'status' is a read-only command
    that agents poll, so it must stay fast and work offline.
    """
    bases: dict[str, Optional[str]] = {}
    for _, info in infos:
        if info.repo_name in bases:
            continue
        repo_path = config.projects.get(info.repo_name)
        try:
            bases[info.repo_name] = find_base_ref(repo_path, fetch=False) if repo_path else None
        except subprocess.CalledProcessError:
            # A project whose checkout has gone missing still gets a row.
            bases[info.repo_name] = None

    def state_for(item):
        _, info = item
        return get_git_state(config.worktrees_dir / info.name, bases[info.repo_name])

    with ThreadPoolExecutor(max_workers=PR_LOOKUP_WORKERS) as pool:
        states = pool.map(state_for, infos)
        return {f: state for (f, _), state in zip(infos, states)}


@app.command()
def status(
    repo: Optional[str] = typer.Option(
        None, "--repo", help="Only show worktrees belonging to this project."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Show cached PR status without calling 'gh'."
    ),
    json_out: bool = typer.Option(
        False, "--json",
        help="Emit JSON on stdout, including local git state for each worktree."
    ),
):
    """Show the status of all worktrees and their PRs."""
    set_json_mode(json_out)
    config = require_config()

    arbor_dir = get_arbor_dir(config.worktrees_dir)
    json_files = sorted(arbor_dir.glob("**/*.json"))

    infos = [(f, WorktreeInfo.model_validate_json(f.read_text())) for f in json_files]
    if repo:
        infos = [(f, i) for f, i in infos if i.repo_name == repo]

    if not infos:
        if json_out:
            emit({"ok": True, "worktrees_dir": str(config.worktrees_dir), "worktrees": []})
        else:
            console.print("No worktrees found.")
        return

    work = [(f, i) for f, i in infos if i.kind != "research"]
    research = [(f, i) for f, i in infos if i.kind == "research"]

    jobs = {}
    if not offline:
        jobs = {
            f: (config.projects[i.repo_name], i.branch)
            for f, i in work
            if i.repo_name in config.projects
        }
    lookups = lookup_prs(jobs)

    for f, info in work:
        lookup = lookups.get(f)
        if lookup:
            apply_lookup(info, lookup, f)

    if json_out:
        states = collect_git_states(config, infos)
        emit({
            "ok": True,
            "worktrees_dir": str(config.worktrees_dir),
            "worktrees": [
                {
                    "name": info.name,
                    "path": str(config.worktrees_dir / info.name),
                    "repo": info.repo_name,
                    "repo_path": str(config.projects.get(info.repo_name) or ""),
                    "branch": info.branch,
                    "kind": info.kind,
                    "task": info.task,
                    "owner": info.owner,
                    "created_at": info.created_at,
                    "pr_number": info.pr_number,
                    "pr_status": info.pr_status,
                    "pr_lookup_error": (lookups.get(f).error if lookups.get(f) else None),
                    "git": states[f]._asdict(),
                }
                for f, info in infos
            ],
        })
        return

    if work:
        table = Table(title="Arbor Worktrees")
        table.add_column("Worktree", style="cyan")
        table.add_column("Repo", style="magenta")
        table.add_column("Branch", style="green")
        table.add_column("PR", style="blue")
        table.add_column("Status", style="yellow")

        failures = []
        for f, info in work:
            if info.repo_name not in config.projects:
                # Maybe the repo was removed from arbor config
                repo_label = f"{info.repo_name} (Missing)"
            else:
                repo_label = info.repo_name

            lookup = lookups.get(f)
            if lookup and lookup.error:
                # Don't pass a failed lookup off as "no PR" - say so out loud.
                failures.append((info.name, lookup.error))
                pr_cell, status_cell = "?", "[red]lookup failed[/red]"
            else:
                pr_cell = str(info.pr_number) if info.pr_number else "-"
                status_cell = info.pr_status or "None"

            table.add_row(info.name, repo_label, info.branch, pr_cell, status_cell)

        console.print(table)

        for name, error in failures:
            console.print(f"[yellow]PR lookup failed for {name}: {error}[/yellow]")

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
    repo: Optional[str] = typer.Option(
        None, "--repo", help="Only consider worktrees belonging to this project."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Report what would be removed without removing it."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON on stdout."),
):
    """Delete merged worktrees and expired research worktrees."""
    set_json_mode(json_out)
    config = require_config()

    arbor_dir = get_arbor_dir(config.worktrees_dir)
    json_files = sorted(arbor_dir.glob("**/*.json"))

    removed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    jobs = {}
    work = []
    for f in json_files:
        info = WorktreeInfo.model_validate_json(f.read_text())
        if repo and info.repo_name != repo:
            continue
        repo_path = config.projects.get(info.repo_name)

        if not repo_path:
            console.print(f"[yellow]Skipping {info.name}: Repo {info.repo_name} not found in config.[/yellow]")
            skipped.append({"name": info.name, "reason": f"repo {info.repo_name} not in config"})
            continue

        worktree_path = config.worktrees_dir / info.name

        if info.kind == "research":
            age = research_age_days(info)
            if age is not None and age >= research_ttl:
                console.print(f"Cleaning up expired research worktree: [blue]{info.name}[/blue] ({age}d old)")
                # Research worktrees are detached and disposable; force removal.
                if dry_run or _remove_worktree(repo_path, worktree_path, f, force=True):
                    removed.append({"name": info.name, "reason": f"research worktree {age}d old"})
            continue

        work.append((f, info, repo_path, worktree_path))
        jobs[f] = (repo_path, info.branch)

    lookups = lookup_prs(jobs)

    for f, info, repo_path, worktree_path in work:
        lookup = lookups[f]
        if lookup.error:
            # Removing a worktree is destructive, so never act on a stale cached
            # status when we couldn't confirm it against GitHub.
            console.print(f"[yellow]Skipping {info.name}: PR lookup failed ({lookup.error}).[/yellow]")
            skipped.append({"name": info.name, "reason": f"PR lookup failed: {lookup.error}"})
            continue

        apply_lookup(info, lookup, f)

        if lookup.state and lookup.state.upper() == "MERGED":
            console.print(f"Cleaning up merged worktree: [blue]{info.name}[/blue]")
            if dry_run or _remove_worktree(repo_path, worktree_path, f):
                removed.append({"name": info.name, "reason": f"PR #{info.pr_number} merged"})

    if not removed:
        console.print("Nothing to clean up.")
    else:
        verb = "Would clean up" if dry_run else "Cleaned up"
        console.print(f"[green]{verb} {len(removed)} worktrees.[/green]")

    emit({"ok": True, "dry_run": dry_run, "removed": removed, "skipped": skipped})

_PR_URL_RE = re.compile(r"https://github\.com/\S+/pull/(?P<number>\d+)")


def count_commits(worktree_path: Path, base_ref: str) -> Optional[int]:
    """Commits on this worktree's HEAD that aren't in base_ref."""
    res = subprocess.run(
        ["git", "-C", str(worktree_path), "rev-list", "--count", f"{base_ref}..HEAD"],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        return None
    return int(res.stdout.strip() or 0)


@app.command()
def pr(
    name: str,
    title: Optional[str] = typer.Option(None, "--title", "-t", help="PR title."),
    body: str = typer.Option("", "--body", "-b", help="PR body."),
    body_file: Optional[str] = typer.Option(
        None, "--body-file", "-F", help="Read the PR body from a file."
    ),
    fill: bool = typer.Option(
        False, "--fill", help="Take the title and body from the branch's commits."
    ),
    draft: bool = typer.Option(False, "--draft", "-d", help="Open the PR as a draft."),
    base: Optional[str] = typer.Option(
        None, "--base", help="Branch to merge into. Defaults to the upstream main branch."
    ),
    allow_dirty: bool = typer.Option(
        False, "--allow-dirty", help="Push even though the worktree has uncommitted changes."
    ),
    force: bool = typer.Option(
        False, "--force", help="Force-push the branch (with lease)."
    ),
    no_fetch: bool = typer.Option(
        False, "--no-fetch",
        help="Resolve the base branch from local refs instead of fetching first."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON on stdout."),
):
    """Push a worktree's branch and open a pull request for it.

    Handles the fork workflow explicitly - push to origin, target upstream, head
    as '<fork-owner>:<branch>' - so 'gh' never has to prompt for a repo. Safe to
    re-run: if the branch already has a PR, it reports that one instead of
    opening a second. The PR URL is printed to stdout.
    """
    set_json_mode(json_out)
    config = require_config()
    found = require_worktree(config, name)

    if not found.info:
        raise fail(f"Worktree '{name}' has no arbor metadata to read a branch from.", "no_metadata")
    info = found.info
    if info.kind == "research":
        raise fail(
            f"'{info.name}' is a research worktree: it's a detached checkout with no branch to push.",
            "research_worktree",
        )

    repo_path = require_project(config, info.repo_name)

    if not allow_dirty and is_git_dirty(found.path):
        raise fail(
            f"Worktree {found.path} has uncommitted changes. Commit them first, "
            "or pass --allow-dirty to push without them.",
            "dirty_worktree",
        )

    base_ref = base or resolve_base_ref(repo_path, fetch=not no_fetch)
    base_branch = base_branch_name(base_ref)

    ahead = count_commits(found.path, base_ref)
    if ahead == 0:
        raise fail(
            f"Branch {info.branch} has no commits on top of {base_ref}; nothing to open a PR for.",
            "no_commits",
        )
    if ahead is None:
        err_console.print(
            f"[yellow]Could not count commits against {base_ref}; "
            "opening the PR without that check.[/yellow]"
        )

    # Re-running after a partial failure must not open a duplicate PR.
    existing = get_gh_pr_status(repo_path, info.branch)
    if existing.number and (existing.state or "").upper() == "OPEN":
        err_console.print(
            f"[yellow]PR #{existing.number} is already open for {info.branch}.[/yellow]"
        )
        apply_lookup(info, existing, found.meta_file)
        url = f"https://github.com/{'/'.join(_pr_target(repo_path))}/pull/{existing.number}"
        if json_out:
            emit({"ok": True, "name": info.name, "pr_number": existing.number,
                  "url": url, "branch": info.branch, "created": False})
        else:
            print(url)
        return

    if not fill and not title:
        raise fail(
            "Pass --title (and optionally --body), or --fill to take both from the "
            "branch's commits. Without one of them 'gh' would open an editor.",
            "missing_title",
        )

    err_console.print(f"Pushing [yellow]{info.branch}[/yellow] to [blue]origin[/blue]...")
    push_cmd = ["git", "-C", str(found.path), "push", "--set-upstream"]
    if force:
        push_cmd.append("--force-with-lease")
    push_cmd += ["origin", info.branch]
    push = subprocess.run(push_cmd, capture_output=True, text=True)
    if push.returncode != 0:
        raise fail(f"Failed to push {info.branch}: {push.stderr.strip()}", "push_failed")

    owner, repo = _pr_target(repo_path)
    origin_owner = get_origin_owner(repo_path)
    # On a fork, the PR head has to name the fork's owner; on a direct clone the
    # bare branch name is what 'gh' expects.
    head = f"{origin_owner}:{info.branch}" if origin_owner and origin_owner != owner else info.branch

    cmd = [
        "gh", "pr", "create",
        "--repo", f"{owner}/{repo}",
        "--base", base_branch,
        "--head", head,
    ]
    if fill:
        cmd.append("--fill")
    else:
        cmd += ["--title", title]
        if body_file:
            # gh runs in the worktree, so resolve the path against the caller's cwd.
            cmd += ["--body-file", str(Path(body_file).expanduser().resolve())]
        else:
            cmd += ["--body", body]
    if draft:
        cmd.append("--draft")

    err_console.print(f"Opening a PR against [blue]{owner}/{repo}[/blue] ([yellow]{base_branch}[/yellow])...")
    try:
        result = subprocess.run(
            cmd, cwd=found.path, capture_output=True, text=True, timeout=GH_TIMEOUT_SECONDS
        )
    except FileNotFoundError:
        raise fail("gh CLI not found.", "gh_missing")
    except subprocess.TimeoutExpired:
        raise fail(f"gh timed out after {GH_TIMEOUT_SECONDS}s.", "gh_timeout")

    if result.returncode != 0:
        raise fail(
            f"Failed to create PR: {(result.stderr or result.stdout).strip()}",
            "pr_create_failed",
        )

    match = _PR_URL_RE.search(result.stdout)
    if not match:
        raise fail(
            f"PR created but its URL could not be parsed from gh output: {result.stdout.strip()}",
            "pr_url_unparsed",
        )
    url = match.group(0)
    number = int(match.group("number"))

    info.pr_number = number
    info.pr_status = "OPEN"
    found.meta_file.write_text(info.model_dump_json(indent=2))

    err_console.print(f"[green]Opened PR #{number}[/green]")
    if json_out:
        emit({"ok": True, "name": info.name, "pr_number": number, "url": url,
              "branch": info.branch, "base": base_branch, "head": head, "created": True})
    else:
        print(url)


def _pr_target(repo_path: Path) -> tuple[str, str]:
    """The GitHub repo a PR should be opened against: upstream, else origin."""
    for remote in ("upstream", "origin"):
        parsed = parse_github_remote(repo_path, remote)
        if parsed:
            return parsed
    raise fail(
        f"No GitHub remote found on {repo_path}; expected 'upstream' or 'origin'.",
        "no_github_remote",
    )


@app.command()
def config(
    json_out: bool = typer.Option(False, "--json", help="Emit JSON on stdout."),
):
    """Show current configuration."""
    set_json_mode(json_out)
    cfg = require_config()

    if json_out:
        emit({
            "ok": True,
            "worktrees_dir": str(cfg.worktrees_dir),
            "projects": {name: str(path) for name, path in cfg.projects.items()},
        })
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
