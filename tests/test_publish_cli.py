"""CLI integration tests for publish.py"""

import subprocess
import sys
from pathlib import Path

from conftest import MINIMAL_MD, make_project

SCRIPT = Path(__file__).parent.parent / "publish.py"


def run_publish(args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def make_published_project(tmp_path):
    """A buildable project, already a git repo with an initial commit pushed
    to a local bare 'remote', so push doesn't need network access."""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)

    project = tmp_path / "project"
    project.mkdir()
    make_project(project, posts={1: MINIMAL_MD})
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
    (project / ".gitignore").write_text("dist/\nmanifest.json\n")
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=project, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Initial commit"], cwd=project, check=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=project, check=True)
    return project, remote


def remote_log(remote):
    result = subprocess.run(
        ["git", "log", "main", "--format=%s"], cwd=remote,
        capture_output=True, text=True, check=True,
    )
    return result.stdout.splitlines()


class TestHelp:

    def test_help_exits_zero(self, tmp_path):
        assert run_publish(["--help"], cwd=tmp_path).returncode == 0


class TestPublishWithChanges:

    def test_new_post_is_pushed(self, tmp_path):
        project, remote = make_published_project(tmp_path)
        (project / "content" / "2.md").write_text(MINIMAL_MD)

        result = run_publish(["Add post 2"], cwd=project)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Add post 2" in remote_log(remote)

    def test_default_message_used_when_none_given(self, tmp_path):
        project, remote = make_published_project(tmp_path)
        (project / "content" / "2.md").write_text(MINIMAL_MD)

        result = run_publish([], cwd=project)

        assert result.returncode == 0, result.stdout + result.stderr
        assert any(msg.startswith("Update ") for msg in remote_log(remote))

    def test_builds_before_publishing(self, tmp_path):
        project, remote = make_published_project(tmp_path)
        (project / "content" / "2.md").write_text(MINIMAL_MD)

        run_publish(["Add post 2"], cwd=project)

        assert (project / "dist" / "2.html").exists()


class TestPublishNoChanges:

    def test_prints_nothing_to_publish(self, tmp_path):
        project, remote = make_published_project(tmp_path)

        result = run_publish([], cwd=project)

        assert result.returncode == 0
        assert "Nothing to publish" in result.stdout

    def test_no_new_commit_pushed(self, tmp_path):
        project, remote = make_published_project(tmp_path)
        before = remote_log(remote)

        run_publish([], cwd=project)

        assert remote_log(remote) == before


class TestBuildFailureAbortsPublish:

    def test_invalid_content_is_not_published(self, tmp_path):
        project, remote = make_published_project(tmp_path)
        before = remote_log(remote)
        # An orphan image with no matching post .md fails validate_content.
        (project / "content" / "99-image-01.jpg").write_bytes(b"not a real image")

        result = run_publish(["Should not land"], cwd=project)

        assert result.returncode == 1
        assert "Build failed" in result.stderr
        assert remote_log(remote) == before

    def test_working_tree_left_uncommitted_on_build_failure(self, tmp_path):
        project, remote = make_published_project(tmp_path)
        (project / "content" / "99-image-01.jpg").write_bytes(b"not a real image")

        result = run_publish(["Should not land"], cwd=project)

        assert result.returncode == 1
        assert "Build failed" in result.stderr

        status = subprocess.run(
            ["git", "status", "--short"], cwd=project,
            capture_output=True, text=True, check=True,
        )
        assert "99-image-01.jpg" in status.stdout
