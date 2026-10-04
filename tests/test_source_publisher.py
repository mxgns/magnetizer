"""Tests for magnetizer/source_publisher.py — publish_source()"""

import pytest
from unittest.mock import MagicMock, patch
from magnetizer.source_publisher import publish_source


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock(has_staged_changes=True):
    def side_effect(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        if cmd == ["git", "diff", "--cached", "--quiet"]:
            m.returncode = 1 if has_staged_changes else 0
        return m
    return side_effect


# ---------------------------------------------------------------------------
# git add
# ---------------------------------------------------------------------------

class TestGitAdd:

    def test_git_add_all_is_called(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert ["git", "add", "-A"] in cmds

    def test_git_add_runs_in_project_dir(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        add_call = next(c for c in mock_run.call_args_list if c.args[0] == ["git", "add", "-A"])
        assert add_call.kwargs.get("cwd") == tmp_path

    def test_git_add_called_before_commit(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert cmds.index(["git", "add", "-A"]) < cmds.index(next(c for c in cmds if c[:2] == ["git", "commit"]))


# ---------------------------------------------------------------------------
# When there are changes — commit + push
# ---------------------------------------------------------------------------

class TestPublishWithChanges:

    def test_git_commit_is_called_with_message(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "Add post 113")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert ["git", "commit", "-m", "Add post 113"] in cmds

    def test_git_push_origin_main_is_called(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert ["git", "push", "origin", "main"] in cmds

    def test_git_push_runs_in_project_dir(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        push_call = next(c for c in mock_run.call_args_list if c.args[0] == ["git", "push", "origin", "main"])
        assert push_call.kwargs.get("cwd") == tmp_path

    def test_push_called_after_commit(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        commit_pos = cmds.index(["git", "commit", "-m", "a message"])
        push_pos = cmds.index(["git", "push", "origin", "main"])
        assert commit_pos < push_pos

    def test_returns_true_when_published(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run", side_effect=make_mock(has_staged_changes=True)):
            assert publish_source(tmp_path, "a message") is True


# ---------------------------------------------------------------------------
# When there are no changes
# ---------------------------------------------------------------------------

class TestPublishNoChanges:

    def test_returns_false_when_nothing_to_commit(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run", side_effect=make_mock(has_staged_changes=False)):
            assert publish_source(tmp_path, "a message") is False

    def test_no_commit_when_no_changes(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run", side_effect=make_mock(has_staged_changes=False)) as mock_run:
            publish_source(tmp_path, "a message")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert not any(c[:2] == ["git", "commit"] for c in cmds)

    def test_no_push_when_no_changes(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run", side_effect=make_mock(has_staged_changes=False)) as mock_run:
            publish_source(tmp_path, "a message")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert ["git", "push", "origin", "main"] not in cmds


# ---------------------------------------------------------------------------
# Git call parameters
# ---------------------------------------------------------------------------

class TestGitCallParameters:

    def test_all_git_calls_specify_timeout(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        for call in mock_run.call_args_list:
            assert call.kwargs.get("timeout") is not None, \
                f"Missing timeout on {call.args[0]}"


# ---------------------------------------------------------------------------
# Git failure handling
# ---------------------------------------------------------------------------

class TestGitFailure:

    def _failing_mock(self, fail_cmd_prefix):
        import subprocess as sp
        def side_effect(cmd, **kwargs):
            if cmd == ["git", "diff", "--cached", "--quiet"]:
                m = MagicMock()
                m.returncode = 1
                return m
            if cmd[:2] == fail_cmd_prefix:
                raise sp.CalledProcessError(1, cmd, stderr="error: push failed")
            return MagicMock(returncode=0)
        return side_effect

    def test_git_push_failure_raises_runtime_error(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run",
                   side_effect=self._failing_mock(["git", "push"])):
            with pytest.raises(RuntimeError):
                publish_source(tmp_path, "a message")

    def test_git_push_failure_message_includes_stderr(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run",
                   side_effect=self._failing_mock(["git", "push"])):
            with pytest.raises(RuntimeError, match="push failed"):
                publish_source(tmp_path, "a message")

    def test_git_commit_failure_raises_runtime_error(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run",
                   side_effect=self._failing_mock(["git", "commit"])):
            with pytest.raises(RuntimeError):
                publish_source(tmp_path, "a message")

    def test_git_diff_probe_error_raises_runtime_error(self, tmp_path):
        def side_effect(cmd, **kwargs):
            if cmd == ["git", "diff", "--cached", "--quiet"]:
                m = MagicMock()
                m.returncode = 128
                m.stderr = "fatal: not a git repository"
                return m
            return MagicMock(returncode=0)
        with patch("magnetizer.source_publisher.subprocess.run", side_effect=side_effect):
            with pytest.raises(RuntimeError, match="not a git repository"):
                publish_source(tmp_path, "a message")
