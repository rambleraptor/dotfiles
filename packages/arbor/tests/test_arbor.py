import json
import os
import shutil
import subprocess
from pathlib import Path
import pytest
from typer.testing import CliRunner

# We need to import the app and CONFIG_PATH from arbor
# Since it's in the parent directory, we might need to adjust sys.path or use relative import
import sys
sys.path.append(str(Path(__file__).parent.parent))
from arbor import app, CONFIG_PATH, Config

runner = CliRunner()

@pytest.fixture
def temp_arbor_env(tmp_path, monkeypatch):
    config_file = tmp_path / ".arbor_config.json"
    worktrees_dir = tmp_path / "worktrees"
    worktrees_dir.mkdir()
    
    # Set dummy git identity for CI
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Arbor Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Arbor Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")

    # Monkeypatch CONFIG_PATH in the arbor module
    import arbor
    monkeypatch.setattr(arbor, "CONFIG_PATH", config_file)
    
    return {
        "config_file": config_file,
        "worktrees_dir": worktrees_dir,
        "tmp_path": tmp_path
    }

def test_init(temp_arbor_env):
    worktrees_dir = temp_arbor_env["worktrees_dir"]
    result = runner.invoke(app, ["init", str(worktrees_dir)])
    assert result.exit_code == 0
    assert "Arbor initialized!" in result.stdout
    
    assert temp_arbor_env["config_file"].exists()
    config = Config.model_validate_json(temp_arbor_env["config_file"].read_text())
    assert config.worktrees_dir.resolve() == worktrees_dir.resolve()

def test_import_project(temp_arbor_env):
    # Init first
    runner.invoke(app, ["init", str(temp_arbor_env["worktrees_dir"])])
    
    # Create a dummy git repo
    repo_path = temp_arbor_env["tmp_path"] / "my-repo"
    repo_path.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True)
    (repo_path / "README.md").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo_path, check=True)
    
    result = runner.invoke(app, ["import", str(repo_path), "--name", "test-repo"])
    assert result.exit_code == 0
    assert "Imported project test-repo" in result.stdout
    
    config = Config.model_validate_json(temp_arbor_env["config_file"].read_text())
    assert "test-repo" in config.projects
    assert Path(config.projects["test-repo"]).resolve() == repo_path.resolve()

def test_cd_command(temp_arbor_env):
    worktrees_dir = temp_arbor_env["worktrees_dir"]
    runner.invoke(app, ["init", str(worktrees_dir)])
    
    # Create a mock worktree directory
    wt_name = "feature-1"
    wt_path = worktrees_dir / wt_name
    wt_path.mkdir()
    (wt_path / ".git").write_text("gitdir: /somewhere") # mock gitdir
    
    # Test cd
    result = runner.invoke(app, ["cd", wt_name])
    assert result.exit_code == 0
    assert result.stdout.strip() == str(wt_path.resolve())

def test_cd_command_alias(temp_arbor_env):
    worktrees_dir = temp_arbor_env["worktrees_dir"]
    runner.invoke(app, ["init", str(worktrees_dir)])
    
    wt_name = "feature-alias"
    wt_path = worktrees_dir / wt_name
    wt_path.mkdir()
    (wt_path / ".git").write_text("gitdir: /somewhere")
    
    result = runner.invoke(app, ["c", wt_name])
    assert result.exit_code == 0
    assert result.stdout.strip() == str(wt_path.resolve())

def test_import_worktree(temp_arbor_env):
    worktrees_dir = temp_arbor_env["worktrees_dir"]
    runner.invoke(app, ["init", str(worktrees_dir)])
    
    # Create main repo
    repo_path = temp_arbor_env["tmp_path"] / "main-repo"
    repo_path.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True)
    (repo_path / "file.txt").write_text("data")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "commit"], cwd=repo_path, check=True)
    
    # Import project
    runner.invoke(app, ["import", str(repo_path), "--name", "my-project"])
    
    # Create worktree
    wt_path = worktrees_dir / "my-worktree"
    subprocess.run(["git", "worktree", "add", str(wt_path), "-b", "my-branch"], cwd=repo_path, check=True)
    
    # Import worktree
    result = runner.invoke(app, ["import", str(wt_path)])
    assert result.exit_code == 0
    assert "Imported worktree my-worktree" in result.stdout
    
    # Verify metadata
    arbor_dir = worktrees_dir / ".arbor"
    assert (arbor_dir / "my-worktree.json").exists()
    
    # Test cd with metadata
    result = runner.invoke(app, ["cd", "my-worktree"])
    assert result.exit_code == 0
    assert result.stdout.strip() == str(wt_path.resolve())

def test_import_dirty_repo_fails(temp_arbor_env):
    runner.invoke(app, ["init", str(temp_arbor_env["worktrees_dir"])])
    
    repo_path = temp_arbor_env["tmp_path"] / "dirty-repo"
    repo_path.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True)
    (repo_path / "file.txt").write_text("v1")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_path, check=True)
    
    # Make dirty
    (repo_path / "file.txt").write_text("v2")
    
    result = runner.invoke(app, ["import", str(repo_path)])
    assert result.exit_code == 1
    assert "Repo has uncommitted changes" in result.stdout

def test_import_converts_branch_to_worktree(temp_arbor_env):
    worktrees_dir = temp_arbor_env["worktrees_dir"]
    runner.invoke(app, ["init", str(worktrees_dir)])
    
    repo_path = temp_arbor_env["tmp_path"] / "branch-repo"
    repo_path.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True)
    (repo_path / "file.txt").write_text("v1")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_path, check=True)
    
    # Create feature branch
    subprocess.run(["git", "checkout", "-b", "feature-x"], cwd=repo_path, check=True)
    
    result = runner.invoke(app, ["import", str(repo_path), "--name", "my-proj"])
    assert result.exit_code == 0
    assert "Converting current branch feature-x into a worktree" in result.stdout
    assert "Imported project my-proj" in result.stdout
    
    # Verify worktree created
    wt_path = worktrees_dir / "feature-x"
    assert wt_path.exists()
    assert (wt_path / "file.txt").exists()
    
    # Verify main repo is detached
    res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path, capture_output=True, text=True)
    assert res.stdout.strip() == "HEAD"

def _make_repo_with_upstream(tmp_path, name="work-repo"):
    """Create a repo with an 'upstream' remote that has a 'main' branch."""
    upstream = tmp_path / f"{name}-upstream.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(upstream)], check=True)

    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True)
    (repo / "file.txt").write_text("v1")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)
    subprocess.run(["git", "remote", "add", "upstream", str(upstream)], cwd=repo, check=True)
    subprocess.run(["git", "push", "upstream", "main"], cwd=repo, check=True)
    return repo

def test_research_base(temp_arbor_env):
    worktrees_dir = temp_arbor_env["worktrees_dir"]
    runner.invoke(app, ["init", str(worktrees_dir)])

    repo = _make_repo_with_upstream(temp_arbor_env["tmp_path"])
    runner.invoke(app, ["import", str(repo), "--name", "proj"])

    result = runner.invoke(app, ["research", "proj"])
    assert result.exit_code == 0, result.stdout

    # The bare worktree path is printed to stdout so the shell wrapper can cd in
    wt = Path(result.stdout.strip())
    assert wt.exists()
    assert (wt / "file.txt").exists()

    # It lives under the research/ subdirectory with a generated (non-"base") name
    assert wt.parent == (worktrees_dir / "research").resolve()
    name = wt.name
    assert name != "base"

    # Metadata is marked as research with a timestamp
    meta = worktrees_dir / ".arbor" / "research" / f"{name}.json"
    assert meta.exists()
    info = json.loads(meta.read_text())
    assert info["kind"] == "research"
    assert info["created_at"]
    assert info["branch"] == "upstream/main"

    # It's a detached checkout (no owned branch)
    res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=wt, capture_output=True, text=True)
    assert res.stdout.strip() == "HEAD"

    # cd resolves by short name
    result = runner.invoke(app, ["cd", name])
    assert result.exit_code == 0
    assert result.stdout.strip() == str(wt.resolve())

def test_research_unique_names(temp_arbor_env):
    worktrees_dir = temp_arbor_env["worktrees_dir"]
    runner.invoke(app, ["init", str(worktrees_dir)])

    repo = _make_repo_with_upstream(temp_arbor_env["tmp_path"])
    runner.invoke(app, ["import", str(repo), "--name", "proj"])

    # Two un-named research worktrees should coexist with distinct names.
    r1 = runner.invoke(app, ["research", "proj"])
    r2 = runner.invoke(app, ["research", "proj"])
    assert r1.exit_code == 0, r1.stdout
    assert r2.exit_code == 0, r2.stdout

    p1 = Path(r1.stdout.strip())
    p2 = Path(r2.stdout.strip())
    assert p1 != p2
    assert p1.exists() and p2.exists()

def test_research_falls_back_to_origin(temp_arbor_env):
    worktrees_dir = temp_arbor_env["worktrees_dir"]
    runner.invoke(app, ["init", str(worktrees_dir)])

    # No upstream remote: build a repo whose only remote is 'origin'
    origin = temp_arbor_env["tmp_path"] / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True)
    repo = temp_arbor_env["tmp_path"] / "origin-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True)
    (repo / "file.txt").write_text("v1")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)
    subprocess.run(["git", "remote", "add", "origin", str(origin)], cwd=repo, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True)

    runner.invoke(app, ["import", str(repo), "--name", "proj"])
    result = runner.invoke(app, ["research", "proj"])
    assert result.exit_code == 0, result.stdout

    name = Path(result.stdout.strip()).name
    info = json.loads((worktrees_dir / ".arbor" / "research" / f"{name}.json").read_text())
    assert info["branch"] == "origin/main"

def test_research_cleanup_ttl(temp_arbor_env):
    from datetime import datetime, timezone, timedelta

    worktrees_dir = temp_arbor_env["worktrees_dir"]
    runner.invoke(app, ["init", str(worktrees_dir)])

    repo = _make_repo_with_upstream(temp_arbor_env["tmp_path"])
    runner.invoke(app, ["import", str(repo), "--name", "proj"])
    res = runner.invoke(app, ["research", "proj"])

    wt = Path(res.stdout.strip())
    meta = worktrees_dir / ".arbor" / "research" / f"{wt.name}.json"

    # Fresh research worktree survives cleanup
    result = runner.invoke(app, ["cleanup"])
    assert result.exit_code == 0
    assert wt.exists()

    # Backdate it past the TTL -> cleanup removes it
    info = json.loads(meta.read_text())
    info["created_at"] = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    meta.write_text(json.dumps(info))

    result = runner.invoke(app, ["cleanup"])
    assert result.exit_code == 0
    assert "expired research worktree" in result.stdout
    assert not wt.exists()
    assert not meta.exists()


# --- PR lookup ---------------------------------------------------------------
#
# A fake 'gh' on PATH lets us pin down the fork-workflow behaviour that broke PR
# tracking: 'gh pr view <branch>' finds nothing when the PR head lives on a fork,
# while 'gh pr list --head <branch> --state all' finds it.

FAKE_GH = '''#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
log = os.environ.get("FAKE_GH_LOG")
if log:
    with open(log, "a") as fh:
        fh.write(" ".join(args) + "\\n")

if os.environ.get("FAKE_GH_MODE") == "fail":
    sys.stderr.write("could not determine what repo to use\\n")
    sys.exit(1)

if args[:2] == ["pr", "view"]:
    sys.stderr.write('no pull requests found for branch "%s"\\n' % args[2])
    sys.exit(1)

if args[:2] == ["pr", "list"]:
    head = args[args.index("--head") + 1]
    print(json.dumps(json.loads(os.environ.get("FAKE_GH_PRS", "{}")).get(head, [])))
    sys.exit(0)

sys.exit(1)
'''


@pytest.fixture
def fake_gh(tmp_path, monkeypatch):
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    log = tmp_path / "gh.log"

    def configure(prs=None, mode=None):
        monkeypatch.setenv("FAKE_GH_PRS", json.dumps(prs or {}))
        monkeypatch.setenv("FAKE_GH_MODE", mode or "ok")
        monkeypatch.setenv("FAKE_GH_LOG", str(log))

    configure()
    configure.log = log
    return configure


def _fork_repo(tmp_path, name="fork-repo"):
    """A repo whose 'origin' is a fork and 'upstream' is the canonical repo."""
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True)
    (repo / "file.txt").write_text("v1")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:me/proj.git"], cwd=repo, check=True
    )
    subprocess.run(
        ["git", "remote", "add", "upstream", "git@github.com:apache/proj.git"], cwd=repo, check=True
    )
    return repo


def _setup_worktree(temp_arbor_env, fake_gh, branch="feature-pr"):
    worktrees_dir = temp_arbor_env["worktrees_dir"]
    runner.invoke(app, ["init", str(worktrees_dir)])
    repo = _fork_repo(temp_arbor_env["tmp_path"])
    runner.invoke(app, ["import", str(repo), "--name", "proj"])
    runner.invoke(app, ["create", "proj", branch])
    return repo, worktrees_dir / branch, worktrees_dir / ".arbor" / f"{branch}.json"


def test_status_finds_pr_on_fork(temp_arbor_env, fake_gh):
    repo, wt, meta = _setup_worktree(temp_arbor_env, fake_gh)
    fake_gh(prs={"feature-pr": [{"number": 42, "state": "OPEN", "headRepositoryOwner": {"login": "me"}}]})

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "42" in result.stdout
    assert "OPEN" in result.stdout

    info = json.loads(meta.read_text())
    assert info["pr_number"] == 42
    assert info["pr_status"] == "OPEN"

    # It must query by head branch across all states, not 'gh pr view'.
    calls = fake_gh.log.read_text()
    assert "pr list --head feature-pr --state all" in calls
    assert "pr view" not in calls


def test_status_reports_lookup_failure(temp_arbor_env, fake_gh):
    repo, wt, meta = _setup_worktree(temp_arbor_env, fake_gh)
    fake_gh(mode="fail")

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    # A broken lookup must not masquerade as "no PR".
    assert "lookup failed" in result.stdout
    assert "could not determine what repo to use" in result.stdout


def test_status_offline_skips_gh(temp_arbor_env, fake_gh):
    repo, wt, meta = _setup_worktree(temp_arbor_env, fake_gh)
    fake_gh(prs={"feature-pr": [{"number": 7, "state": "OPEN", "headRepositoryOwner": {"login": "me"}}]})

    result = runner.invoke(app, ["status", "--offline"])
    assert result.exit_code == 0
    assert not fake_gh.log.exists()


def test_status_prefers_pr_from_origin_owner(temp_arbor_env, fake_gh):
    repo, wt, meta = _setup_worktree(temp_arbor_env, fake_gh)
    fake_gh(prs={"feature-pr": [
        {"number": 10, "state": "OPEN", "headRepositoryOwner": {"login": "someone-else"}},
        {"number": 11, "state": "OPEN", "headRepositoryOwner": {"login": "me"}},
    ]})

    runner.invoke(app, ["status"])
    assert json.loads(meta.read_text())["pr_number"] == 11


def test_cleanup_removes_merged_worktree(temp_arbor_env, fake_gh):
    repo, wt, meta = _setup_worktree(temp_arbor_env, fake_gh)
    fake_gh(prs={"feature-pr": [{"number": 42, "state": "MERGED", "headRepositoryOwner": {"login": "me"}}]})

    result = runner.invoke(app, ["cleanup"])
    assert result.exit_code == 0
    assert "Cleaning up merged worktree" in result.stdout
    assert not wt.exists()
    assert not meta.exists()


def test_cleanup_skips_when_lookup_fails(temp_arbor_env, fake_gh):
    repo, wt, meta = _setup_worktree(temp_arbor_env, fake_gh)

    # Even with a cached MERGED status, an unverifiable lookup must not delete.
    info = json.loads(meta.read_text())
    info["pr_status"] = "MERGED"
    meta.write_text(json.dumps(info))

    fake_gh(mode="fail")
    result = runner.invoke(app, ["cleanup"])
    assert result.exit_code == 0
    assert "PR lookup failed" in result.stdout
    assert wt.exists()
    assert meta.exists()


def test_cleanup_keeps_open_pr_worktree(temp_arbor_env, fake_gh):
    repo, wt, meta = _setup_worktree(temp_arbor_env, fake_gh)
    fake_gh(prs={"feature-pr": [{"number": 42, "state": "OPEN", "headRepositoryOwner": {"login": "me"}}]})

    result = runner.invoke(app, ["cleanup"])
    assert result.exit_code == 0
    assert wt.exists()
    assert json.loads(meta.read_text())["pr_status"] == "OPEN"
