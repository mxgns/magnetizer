"""CLI integration tests for restore_mtimes.py"""

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "restore_mtimes.py"


def run(args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def _init_repo(repo_dir):
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True)


def _commit(repo_dir, timestamp):
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = f"{timestamp} +0000"
    env["GIT_COMMITTER_DATE"] = f"{timestamp} +0000"
    subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add"], cwd=repo_dir, check=True, env=env)


class TestHelp:

    def test_help_exits_zero(self, tmp_path):
        assert run(["--help"], cwd=tmp_path).returncode == 0


class TestDefaults:

    def test_defaults_to_content_and_resources(self, tmp_path):
        _init_repo(tmp_path)
        (tmp_path / "content").mkdir()
        (tmp_path / "resources").mkdir()
        (tmp_path / "content" / "1.md").write_text("a")
        (tmp_path / "resources" / "style.css").write_text("body{}")
        _commit(tmp_path, 1_700_000_000)

        result = run([], cwd=tmp_path)

        assert result.returncode == 0
        assert int((tmp_path / "content" / "1.md").stat().st_mtime) == 1_700_000_000
        assert int((tmp_path / "resources" / "style.css").stat().st_mtime) == 1_700_000_000

    def test_explicit_directory_argument(self, tmp_path):
        _init_repo(tmp_path)
        (tmp_path / "other").mkdir()
        (tmp_path / "other" / "1.md").write_text("a")
        _commit(tmp_path, 1_700_000_000)

        result = run(["other"], cwd=tmp_path)

        assert result.returncode == 0
        assert int((tmp_path / "other" / "1.md").stat().st_mtime) == 1_700_000_000

    def test_prints_restored_count(self, tmp_path):
        _init_repo(tmp_path)
        (tmp_path / "content").mkdir()
        (tmp_path / "content" / "1.md").write_text("a")
        _commit(tmp_path, 1_700_000_000)

        result = run([], cwd=tmp_path)

        assert "1" in result.stdout
