"""CLI integration tests for pull.py"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "pull.py"


def run_pull(args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def make_clone_with_remote(tmp_path):
    """A plain git repo (no magnetizer project structure needed -- pull.py
    only ever touches git plumbing) cloned from a local bare 'remote', so
    pulling doesn't need network access."""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(remote)], check=True)

    seed = tmp_path / "seed"
    seed.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=seed, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=seed, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=seed, check=True)
    (seed / "README.md").write_text("baseline")
    subprocess.run(["git", "add", "-A"], cwd=seed, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Initial commit"], cwd=seed, check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=seed, check=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=seed, check=True)

    local = tmp_path / "local"
    subprocess.run(["git", "clone", "-q", str(remote), str(local)], check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=local, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=local, check=True)
    return local, remote, seed


def push_from_elsewhere(remote, seed, filename, content):
    """Simulate CI's ingest-and-push step landing a new commit on origin/main
    that the local checkout doesn't have yet."""
    path = seed / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    subprocess.run(["git", "add", "-A"], cwd=seed, check=True)
    subprocess.run(["git", "commit", "-q", "-m", f"Ingest {filename}"], cwd=seed, check=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=seed, check=True)


class TestHelp:

    def test_help_exits_zero(self, tmp_path):
        assert run_pull(["--help"], cwd=tmp_path).returncode == 0


class TestFastForward:

    def test_new_remote_commit_is_pulled(self, tmp_path):
        local, remote, seed = make_clone_with_remote(tmp_path)
        push_from_elsewhere(remote, seed, "content/113.md", "---\ndate: 2026-10-06\n---\n")

        result = run_pull([], cwd=local)

        assert result.returncode == 0, result.stdout + result.stderr
        assert (local / "content" / "113.md").exists()

    def test_reports_commits_pulled(self, tmp_path):
        local, remote, seed = make_clone_with_remote(tmp_path)
        push_from_elsewhere(remote, seed, "content/113.md", "x")

        result = run_pull([], cwd=local)

        assert "1" in result.stdout


class TestAlreadyUpToDate:

    def test_prints_up_to_date(self, tmp_path):
        local, remote, seed = make_clone_with_remote(tmp_path)

        result = run_pull([], cwd=local)

        assert result.returncode == 0
        assert "up to date" in result.stdout.lower()

    def test_no_changes_made(self, tmp_path):
        local, remote, seed = make_clone_with_remote(tmp_path)
        before = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=local, capture_output=True, text=True, check=True,
        ).stdout

        run_pull([], cwd=local)

        after = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=local, capture_output=True, text=True, check=True,
        ).stdout
        assert before == after


class TestDiverged:

    def test_exits_nonzero_and_leaves_local_commit_intact(self, tmp_path):
        local, remote, seed = make_clone_with_remote(tmp_path)
        push_from_elsewhere(remote, seed, "content/113.md", "x")

        (local / "content").mkdir()
        (local / "content" / "114.md").write_text("y")
        subprocess.run(["git", "add", "-A"], cwd=local, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "Local post 114"], cwd=local, check=True)

        result = run_pull([], cwd=local)

        assert result.returncode != 0
        assert (local / "content" / "114.md").exists()
        assert not (local / "content" / "113.md").exists()


class TestNotOnMain:

    def test_exits_nonzero_on_other_branch(self, tmp_path):
        local, remote, seed = make_clone_with_remote(tmp_path)
        subprocess.run(["git", "checkout", "-q", "-b", "feature/x"], cwd=local, check=True)

        result = run_pull([], cwd=local)

        assert result.returncode != 0
        assert "feature/x" in result.stderr
