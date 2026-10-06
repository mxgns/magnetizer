"""Tests for magnetizer/pull.py — pull()"""

import subprocess
import pytest
from unittest.mock import MagicMock, patch
from magnetizer.pull import pull

_FETCH_CMD = ["git", "fetch", "origin", "main"]
_BEHIND_CMD = ["git", "rev-list", "--count", "HEAD..origin/main"]
_AHEAD_CMD = ["git", "rev-list", "--count", "origin/main..HEAD"]
_MERGE_CMD = ["git", "merge", "--ff-only", "origin/main"]
_BRANCH_CMD = ["git", "rev-parse", "--abbrev-ref", "HEAD"]


def make_mock(current_branch="main", behind=0, ahead=0):
    def side_effect(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        if cmd == _BRANCH_CMD:
            m.stdout = f"{current_branch}\n"
        elif cmd == _BEHIND_CMD:
            m.stdout = f"{behind}\n"
        elif cmd == _AHEAD_CMD:
            m.stdout = f"{ahead}\n"
        return m
    return side_effect


# ---------------------------------------------------------------------------
# Branch check
# ---------------------------------------------------------------------------

class TestBranchCheck:

    def test_raises_when_not_on_main(self, tmp_path):
        with patch("magnetizer.pull.subprocess.run",
                   side_effect=make_mock(current_branch="feature/x")):
            with pytest.raises(RuntimeError, match="feature/x"):
                pull(tmp_path)

    def test_no_fetch_when_not_on_main(self, tmp_path):
        with patch("magnetizer.pull.subprocess.run",
                   side_effect=make_mock(current_branch="feature/x")) as mock_run:
            with pytest.raises(RuntimeError):
                pull(tmp_path)
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert _FETCH_CMD not in cmds

    def test_branch_checked_before_fetch(self, tmp_path):
        with patch("magnetizer.pull.subprocess.run", side_effect=make_mock()) as mock_run:
            pull(tmp_path)
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert cmds.index(_BRANCH_CMD) < cmds.index(_FETCH_CMD)


# ---------------------------------------------------------------------------
# Already up to date / nothing to pull
# ---------------------------------------------------------------------------

class TestNothingToPull:

    def test_returns_zero_when_even(self, tmp_path):
        with patch("magnetizer.pull.subprocess.run", side_effect=make_mock(behind=0, ahead=0)):
            assert pull(tmp_path) == 0

    def test_returns_zero_when_purely_ahead(self, tmp_path):
        """Local has unpushed commits, origin has nothing new -- not an error,
        not this tool's concern (that's publish.py's job)."""
        with patch("magnetizer.pull.subprocess.run", side_effect=make_mock(behind=0, ahead=3)):
            assert pull(tmp_path) == 0

    def test_no_merge_when_nothing_to_pull(self, tmp_path):
        with patch("magnetizer.pull.subprocess.run", side_effect=make_mock(behind=0, ahead=3)) as mock_run:
            pull(tmp_path)
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert _MERGE_CMD not in cmds


# ---------------------------------------------------------------------------
# Purely behind -- fast-forward
# ---------------------------------------------------------------------------

class TestFastForward:

    def test_returns_commit_count(self, tmp_path):
        with patch("magnetizer.pull.subprocess.run", side_effect=make_mock(behind=2, ahead=0)):
            assert pull(tmp_path) == 2

    def test_merge_ff_only_is_called(self, tmp_path):
        with patch("magnetizer.pull.subprocess.run", side_effect=make_mock(behind=2, ahead=0)) as mock_run:
            pull(tmp_path)
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert _MERGE_CMD in cmds

    def test_merge_runs_in_project_dir(self, tmp_path):
        with patch("magnetizer.pull.subprocess.run", side_effect=make_mock(behind=2, ahead=0)) as mock_run:
            pull(tmp_path)
        merge_call = next(c for c in mock_run.call_args_list if c.args[0] == _MERGE_CMD)
        assert merge_call.kwargs.get("cwd") == tmp_path

    def test_fetch_called_before_merge(self, tmp_path):
        with patch("magnetizer.pull.subprocess.run", side_effect=make_mock(behind=2, ahead=0)) as mock_run:
            pull(tmp_path)
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert cmds.index(_FETCH_CMD) < cmds.index(_MERGE_CMD)


# ---------------------------------------------------------------------------
# Diverged
# ---------------------------------------------------------------------------

class TestDiverged:

    def test_raises_when_diverged(self, tmp_path):
        with patch("magnetizer.pull.subprocess.run", side_effect=make_mock(behind=3, ahead=2)):
            with pytest.raises(RuntimeError, match="diverged"):
                pull(tmp_path)

    def test_error_names_both_counts(self, tmp_path):
        with patch("magnetizer.pull.subprocess.run", side_effect=make_mock(behind=3, ahead=2)):
            with pytest.raises(RuntimeError, match=r"3.*2|2.*3"):
                pull(tmp_path)

    def test_no_merge_when_diverged(self, tmp_path):
        with patch("magnetizer.pull.subprocess.run", side_effect=make_mock(behind=3, ahead=2)) as mock_run:
            with pytest.raises(RuntimeError):
                pull(tmp_path)
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert _MERGE_CMD not in cmds


# ---------------------------------------------------------------------------
# Git call parameters
# ---------------------------------------------------------------------------

class TestGitCallParameters:

    def test_all_git_calls_specify_timeout(self, tmp_path):
        with patch("magnetizer.pull.subprocess.run", side_effect=make_mock(behind=2, ahead=0)) as mock_run:
            pull(tmp_path)
        for call in mock_run.call_args_list:
            assert call.kwargs.get("timeout") is not None, \
                f"Missing timeout on {call.args[0]}"


# ---------------------------------------------------------------------------
# Git failure handling
# ---------------------------------------------------------------------------

class TestGitFailure:

    def test_fetch_failure_raises_runtime_error(self, tmp_path):
        def side_effect(cmd, **kwargs):
            if cmd == _BRANCH_CMD:
                return MagicMock(returncode=0, stdout="main\n")
            if cmd == _FETCH_CMD:
                raise subprocess.CalledProcessError(1, cmd, stderr="fatal: could not fetch")
            return MagicMock(returncode=0)
        with patch("magnetizer.pull.subprocess.run", side_effect=side_effect):
            with pytest.raises(RuntimeError, match="could not fetch"):
                pull(tmp_path)

    def test_ff_only_merge_failure_raises_runtime_error(self, tmp_path):
        """E.g. uncommitted local changes the fast-forward would overwrite."""
        def side_effect(cmd, **kwargs):
            if cmd == _BRANCH_CMD:
                return MagicMock(returncode=0, stdout="main\n")
            if cmd == _BEHIND_CMD:
                return MagicMock(returncode=0, stdout="1\n")
            if cmd == _AHEAD_CMD:
                return MagicMock(returncode=0, stdout="0\n")
            if cmd == _MERGE_CMD:
                raise subprocess.CalledProcessError(
                    1, cmd, stderr="error: Your local changes would be overwritten by merge"
                )
            return MagicMock(returncode=0)
        with patch("magnetizer.pull.subprocess.run", side_effect=side_effect):
            with pytest.raises(RuntimeError, match="would be overwritten"):
                pull(tmp_path)

    def test_timeout_raises_runtime_error(self, tmp_path):
        """E.g. a slow git fetch over a bad connection."""
        def side_effect(cmd, **kwargs):
            if cmd == _BRANCH_CMD:
                return MagicMock(returncode=0, stdout="main\n")
            if cmd == _FETCH_CMD:
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=60)
            return MagicMock(returncode=0)
        with patch("magnetizer.pull.subprocess.run", side_effect=side_effect):
            with pytest.raises(RuntimeError, match="timed out"):
                pull(tmp_path)

    def test_missing_git_binary_raises_runtime_error(self, tmp_path):
        with patch("magnetizer.pull.subprocess.run",
                   side_effect=FileNotFoundError("git not found")):
            with pytest.raises(RuntimeError, match="git"):
                pull(tmp_path)


# ---------------------------------------------------------------------------
# Detached HEAD
# ---------------------------------------------------------------------------

class TestDetachedHead:

    def test_raises_with_clear_message_not_literal_head(self, tmp_path):
        with patch("magnetizer.pull.subprocess.run", side_effect=make_mock(current_branch="HEAD")):
            with pytest.raises(RuntimeError, match="detached"):
                pull(tmp_path)
