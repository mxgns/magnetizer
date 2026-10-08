"""Tests for magnetizer/git_utils.py — shared git-subprocess helpers used by
pull.py and source_publisher.py (see issue #66)."""

import subprocess
import pytest
from unittest.mock import MagicMock, patch
from magnetizer.git_utils import _run_git, _run_git_probe

_CMD = ["git", "status"]


# ---------------------------------------------------------------------------
# _run_git — success
# ---------------------------------------------------------------------------

class TestRunGitSuccess:

    def test_returns_completed_process(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="output\n")
            result = _run_git(_CMD, cwd=tmp_path)
        assert result.stdout == "output\n"

    def test_runs_in_given_cwd(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _run_git(_CMD, cwd=tmp_path)
        assert mock_run.call_args.kwargs.get("cwd") == tmp_path

    def test_specifies_a_timeout(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _run_git(_CMD, cwd=tmp_path)
        assert mock_run.call_args.kwargs.get("timeout") is not None


# ---------------------------------------------------------------------------
# _run_git — failure handling
# ---------------------------------------------------------------------------

class TestRunGitFailure:

    def test_called_process_error_raises_runtime_error(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run",
                   side_effect=subprocess.CalledProcessError(1, _CMD, stderr="fatal: bad")):
            with pytest.raises(RuntimeError, match="bad"):
                _run_git(_CMD, cwd=tmp_path)

    def test_timeout_expired_raises_runtime_error(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd=_CMD, timeout=60)):
            with pytest.raises(RuntimeError, match="timed out"):
                _run_git(_CMD, cwd=tmp_path)

    def test_missing_git_binary_raises_runtime_error(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run",
                   side_effect=FileNotFoundError("git not found")):
            with pytest.raises(RuntimeError, match="git"):
                _run_git(_CMD, cwd=tmp_path)


# ---------------------------------------------------------------------------
# _run_git_probe
# ---------------------------------------------------------------------------

class TestRunGitProbe:

    def test_returns_result_on_expected_returncode(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok\n")
            result = _run_git_probe(_CMD, cwd=tmp_path)
        assert result.stdout == "ok\n"

    def test_accepts_custom_valid_returncodes(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = _run_git_probe(_CMD, cwd=tmp_path, valid_returncodes=(0, 1))
        assert result.returncode == 1

    def test_raises_runtime_error_outside_valid_returncodes(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stderr="fatal: not a git repository")
            with pytest.raises(RuntimeError, match="not a git repository"):
                _run_git_probe(_CMD, cwd=tmp_path)

    def test_specifies_a_timeout(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _run_git_probe(_CMD, cwd=tmp_path)
        assert mock_run.call_args.kwargs.get("timeout") is not None
