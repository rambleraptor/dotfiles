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

def test_gemini_sidecar_context(temp_arbor_env):
    worktrees_dir = temp_arbor_env["worktrees_dir"]
    runner.invoke(app, ["init", str(worktrees_dir)])
    
    repo_path = temp_arbor_env["tmp_path"] / "gemini-repo"
    repo_path.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True)
    (repo_path / "file.txt").write_text("v1")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_path, check=True)
    
    runner.invoke(app, ["import", str(repo_path), "--name", "my-gemini-proj"])
    runner.invoke(app, ["create", "my-gemini-proj", "feature-gemini"])
    
    wt_path = worktrees_dir / "feature-gemini"
    assert wt_path.exists()
    
    # Check symlink
    gemini_link = wt_path / "GEMINI.md"
    assert gemini_link.is_symlink()
    
    # Check shadow file
    shadow_path = worktrees_dir / ".arbor" / "contexts" / "my-gemini-proj" / "feature-gemini" / "GEMINI.md"
    assert shadow_path.exists()
    assert gemini_link.resolve() == shadow_path.resolve()
    
    # Check git exclude
    res = subprocess.run(["git", "-C", str(repo_path), "rev-parse", "--git-common-dir"], capture_output=True, text=True)
    common_dir = (repo_path / res.stdout.strip()).resolve()
    exclude_file = common_dir / "info" / "exclude"
    assert "GEMINI.md" in exclude_file.read_text()
