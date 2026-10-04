"""Tests for magnetizer/mtimes.py — restore_mtimes()"""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from magnetizer.mtimes import restore_mtimes


def _init_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    return tmp_path


def _commit(repo_dir, message, timestamp):
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = f"{timestamp} +0000"
    env["GIT_COMMITTER_DATE"] = f"{timestamp} +0000"
    subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo_dir, check=True, env=env)


class TestRestoreMtimes:

    def test_restores_mtime_to_commit_time(self, tmp_path):
        _init_repo(tmp_path)
        (tmp_path / "content").mkdir()
        (tmp_path / "content" / "1.md").write_text("a")
        _commit(tmp_path, "add 1.md", 1_700_000_000)

        os.utime(tmp_path / "content" / "1.md", (2_000_000_000, 2_000_000_000))
        restore_mtimes(tmp_path, ["content"])

        assert int((tmp_path / "content" / "1.md").stat().st_mtime) == 1_700_000_000

    def test_different_files_get_their_own_commit_time(self, tmp_path):
        _init_repo(tmp_path)
        (tmp_path / "content").mkdir()
        (tmp_path / "content" / "1.md").write_text("a")
        _commit(tmp_path, "add 1.md", 1_700_000_000)
        (tmp_path / "content" / "2.md").write_text("b")
        _commit(tmp_path, "add 2.md", 1_800_000_000)

        restore_mtimes(tmp_path, ["content"])

        assert int((tmp_path / "content" / "1.md").stat().st_mtime) == 1_700_000_000
        assert int((tmp_path / "content" / "2.md").stat().st_mtime) == 1_800_000_000

    def test_uses_most_recent_commit_when_file_changed_again(self, tmp_path):
        _init_repo(tmp_path)
        (tmp_path / "content").mkdir()
        (tmp_path / "content" / "1.md").write_text("a")
        _commit(tmp_path, "add 1.md", 1_700_000_000)
        (tmp_path / "content" / "1.md").write_text("a, edited")
        _commit(tmp_path, "edit 1.md", 1_900_000_000)

        restore_mtimes(tmp_path, ["content"])

        assert int((tmp_path / "content" / "1.md").stat().st_mtime) == 1_900_000_000

    def test_untracked_file_is_left_untouched(self, tmp_path):
        _init_repo(tmp_path)
        (tmp_path / "content").mkdir()
        (tmp_path / "content" / "1.md").write_text("a")
        _commit(tmp_path, "add 1.md", 1_700_000_000)
        (tmp_path / "content" / "2.md").write_text("new, uncommitted")
        os.utime(tmp_path / "content" / "2.md", (1_234_567_890, 1_234_567_890))

        restore_mtimes(tmp_path, ["content"])

        assert int((tmp_path / "content" / "2.md").stat().st_mtime) == 1_234_567_890

    def test_files_outside_given_directories_are_untouched(self, tmp_path):
        _init_repo(tmp_path)
        (tmp_path / "content").mkdir()
        (tmp_path / "other").mkdir()
        (tmp_path / "content" / "1.md").write_text("a")
        (tmp_path / "other" / "x.txt").write_text("b")
        _commit(tmp_path, "add both", 1_700_000_000)
        os.utime(tmp_path / "other" / "x.txt", (1_234_567_890, 1_234_567_890))

        restore_mtimes(tmp_path, ["content"])

        assert int((tmp_path / "other" / "x.txt").stat().st_mtime) == 1_234_567_890

    def test_returns_count_of_restored_files(self, tmp_path):
        _init_repo(tmp_path)
        (tmp_path / "content").mkdir()
        (tmp_path / "content" / "1.md").write_text("a")
        (tmp_path / "content" / "2.md").write_text("b")
        _commit(tmp_path, "add both", 1_700_000_000)

        assert restore_mtimes(tmp_path, ["content"]) == 2

    def test_multiple_directories(self, tmp_path):
        _init_repo(tmp_path)
        (tmp_path / "content").mkdir()
        (tmp_path / "resources").mkdir()
        (tmp_path / "content" / "1.md").write_text("a")
        (tmp_path / "resources" / "style.css").write_text("body{}")
        _commit(tmp_path, "add both", 1_700_000_000)

        assert restore_mtimes(tmp_path, ["content", "resources"]) == 2

    def test_missing_directory_is_skipped_without_error(self, tmp_path):
        _init_repo(tmp_path)
        (tmp_path / "content").mkdir()
        (tmp_path / "content" / "1.md").write_text("a")
        _commit(tmp_path, "add 1.md", 1_700_000_000)

        assert restore_mtimes(tmp_path, ["content", "resources"]) == 1

    def test_single_git_log_invocation_regardless_of_file_count(self, tmp_path):
        _init_repo(tmp_path)
        (tmp_path / "content").mkdir()
        for i in range(1, 6):
            (tmp_path / "content" / f"{i}.md").write_text(str(i))
        _commit(tmp_path, "add five files", 1_700_000_000)

        with patch("magnetizer.mtimes.subprocess.run", wraps=subprocess.run) as mock_run:
            restore_mtimes(tmp_path, ["content"])

        git_log_calls = [c for c in mock_run.call_args_list if c.args[0][:2] == ["git", "log"]]
        assert len(git_log_calls) == 1
