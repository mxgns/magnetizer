"""Tests for magnetizer/source_publisher.py — publish_source()"""

import subprocess
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from magnetizer.source_publisher import publish_source, run_build

_ADD_CMD = ["git", "add", "-A"]
_UNSTAGE_CMD = ["git", "reset", "--", "dist", "manifest.json"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock(has_staged_changes=True, current_branch="main"):
    def side_effect(cmd, **kwargs):
        m = MagicMock()
        m.returncode = 0
        if cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            m.stdout = f"{current_branch}\n"
        elif cmd == ["git", "diff", "--cached", "--quiet"]:
            m.returncode = 1 if has_staged_changes else 0
        return m
    return side_effect


# ---------------------------------------------------------------------------
# Branch check
# ---------------------------------------------------------------------------

class TestBranchCheck:

    def test_raises_when_not_on_main(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run",
                   side_effect=make_mock(current_branch="feature/x")):
            with pytest.raises(RuntimeError, match="feature/x"):
                publish_source(tmp_path, "a message")

    def test_nothing_staged_when_not_on_main(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run",
                   side_effect=make_mock(current_branch="feature/x")) as mock_run:
            with pytest.raises(RuntimeError):
                publish_source(tmp_path, "a message")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert _ADD_CMD not in cmds

    def test_proceeds_when_on_main(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run",
                   side_effect=make_mock(current_branch="main")):
            assert publish_source(tmp_path, "a message") is True

    def test_branch_checked_before_staging(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        branch_pos = cmds.index(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        add_pos = cmds.index(_ADD_CMD)
        assert branch_pos < add_pos


# ---------------------------------------------------------------------------
# git add
# ---------------------------------------------------------------------------

class TestGitAdd:

    def test_git_add_all_is_called(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert _ADD_CMD in cmds

    def test_dist_and_manifest_unstaged_after_add(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert _UNSTAGE_CMD in cmds
        assert cmds.index(_ADD_CMD) < cmds.index(_UNSTAGE_CMD)

    def test_git_add_runs_in_project_dir(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        add_call = next(c for c in mock_run.call_args_list if c.args[0] == _ADD_CMD)
        assert add_call.kwargs.get("cwd") == tmp_path

    def test_git_add_called_before_commit(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert cmds.index(_ADD_CMD) < cmds.index(next(c for c in cmds if c[:2] == ["git", "commit"]))

    def test_dist_and_manifest_never_staged_even_when_untracked_and_unignored(self, tmp_path):
        """Real git, not mocked -- proves the add-then-unstage actually works,
        including against a dist/ that is itself a nested git repo (a gitlink),
        with no .gitignore at all."""
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
        (tmp_path / "README.md").write_text("baseline")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=tmp_path, check=True)

        (tmp_path / "content").mkdir()
        (tmp_path / "content" / "1.md").write_text("x")
        (tmp_path / "manifest.json").write_text("{}")
        dist = tmp_path / "dist"
        subprocess.run(["git", "init", "-q", "-b", "main", str(dist)], check=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=dist, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=dist, check=True)
        (dist / "index.html").write_text("z")
        subprocess.run(["git", "add", "-A"], cwd=dist, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "dist commit"], cwd=dist, check=True)

        remote = tmp_path.parent / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=tmp_path, check=True)

        publish_source(tmp_path, "add content")

        staged = subprocess.run(
            ["git", "show", "--name-only", "--format=", "HEAD"],
            cwd=tmp_path, capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        assert "content/1.md" in staged
        assert "dist" not in staged
        assert "manifest.json" not in staged


# ---------------------------------------------------------------------------
# When there are changes — commit + push
# ---------------------------------------------------------------------------

class TestPublishWithChanges:

    def test_git_commit_is_called_with_message(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "Add post 113")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert ["git", "commit", "-m", "Add post 113"] in cmds

    def test_git_push_origin_main_is_called(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert ["git", "push", "origin", "main"] in cmds

    def test_git_push_runs_in_project_dir(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        push_call = next(c for c in mock_run.call_args_list if c.args[0] == ["git", "push", "origin", "main"])
        assert push_call.kwargs.get("cwd") == tmp_path

    def test_push_called_after_commit(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        commit_pos = cmds.index(["git", "commit", "-m", "a message"])
        push_pos = cmds.index(["git", "push", "origin", "main"])
        assert commit_pos < push_pos

    def test_returns_true_when_published(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run", side_effect=make_mock(has_staged_changes=True)):
            assert publish_source(tmp_path, "a message") is True


# ---------------------------------------------------------------------------
# When there are no changes
# ---------------------------------------------------------------------------

class TestPublishNoChanges:

    def test_returns_false_when_nothing_to_commit(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run", side_effect=make_mock(has_staged_changes=False)):
            assert publish_source(tmp_path, "a message") is False

    def test_no_commit_when_no_changes(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run", side_effect=make_mock(has_staged_changes=False)) as mock_run:
            publish_source(tmp_path, "a message")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert not any(c[:2] == ["git", "commit"] for c in cmds)

    def test_no_push_when_no_changes(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run", side_effect=make_mock(has_staged_changes=False)) as mock_run:
            publish_source(tmp_path, "a message")
        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert ["git", "push", "origin", "main"] not in cmds


# ---------------------------------------------------------------------------
# Git call parameters
# ---------------------------------------------------------------------------

class TestGitCallParameters:

    def test_all_git_calls_specify_timeout(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run", side_effect=make_mock()) as mock_run:
            publish_source(tmp_path, "a message")
        for call in mock_run.call_args_list:
            assert call.kwargs.get("timeout") is not None, \
                f"Missing timeout on {call.args[0]}"


# ---------------------------------------------------------------------------
# Git failure handling
# ---------------------------------------------------------------------------

class TestGitFailure:

    def _failing_mock(self, fail_cmd_prefix):
        def side_effect(cmd, **kwargs):
            if cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                m = MagicMock()
                m.returncode = 0
                m.stdout = "main\n"
                return m
            if cmd == ["git", "diff", "--cached", "--quiet"]:
                m = MagicMock()
                m.returncode = 1
                return m
            if cmd[:2] == fail_cmd_prefix:
                raise subprocess.CalledProcessError(1, cmd, stderr="error: push failed")
            return MagicMock(returncode=0)
        return side_effect

    def test_git_push_failure_raises_runtime_error(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run",
                   side_effect=self._failing_mock(["git", "push"])):
            with pytest.raises(RuntimeError):
                publish_source(tmp_path, "a message")

    def test_git_push_failure_message_includes_stderr(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run",
                   side_effect=self._failing_mock(["git", "push"])):
            with pytest.raises(RuntimeError, match="push failed"):
                publish_source(tmp_path, "a message")

    def test_git_commit_failure_raises_runtime_error(self, tmp_path):
        with patch("magnetizer.git_utils.subprocess.run",
                   side_effect=self._failing_mock(["git", "commit"])):
            with pytest.raises(RuntimeError):
                publish_source(tmp_path, "a message")

    def test_git_diff_probe_error_raises_runtime_error(self, tmp_path):
        def side_effect(cmd, **kwargs):
            if cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                m = MagicMock()
                m.returncode = 0
                m.stdout = "main\n"
                return m
            if cmd == ["git", "diff", "--cached", "--quiet"]:
                m = MagicMock()
                m.returncode = 128
                m.stderr = "fatal: not a git repository"
                return m
            return MagicMock(returncode=0)
        with patch("magnetizer.git_utils.subprocess.run", side_effect=side_effect):
            with pytest.raises(RuntimeError, match="not a git repository"):
                publish_source(tmp_path, "a message")


# ---------------------------------------------------------------------------
# run_build
# ---------------------------------------------------------------------------

class TestRunBuild:

    def test_returns_true_on_success(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert run_build(Path("build.py"), tmp_path) is True

    def test_returns_false_on_nonzero_exit(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert run_build(Path("build.py"), tmp_path) is False

    def test_runs_in_given_cwd(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            run_build(Path("build.py"), tmp_path)
        assert mock_run.call_args.kwargs.get("cwd") == tmp_path

    def test_invokes_build_script_with_current_interpreter(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            run_build(Path("build.py"), tmp_path)
        assert mock_run.call_args.args[0] == [sys.executable, "build.py"]

    def test_specifies_a_timeout(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            run_build(Path("build.py"), tmp_path)
        assert mock_run.call_args.kwargs.get("timeout") is not None

    def test_raises_runtime_error_on_timeout(self, tmp_path):
        with patch("magnetizer.source_publisher.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="build.py", timeout=600)):
            with pytest.raises(RuntimeError, match="timed out"):
                run_build(Path("build.py"), tmp_path)
