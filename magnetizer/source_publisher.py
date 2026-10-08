import subprocess
import sys

from magnetizer.git_utils import _run_git, _run_git_probe

_BUILD_TIMEOUT = 600  # generous enough for a --flush full rebuild; catches a true hang


def run_build(build_script, cwd):
    """Run build_script as a sanity check before publishing. Returns True on
    success, False on a normal (non-exceptional) build failure. Raises
    RuntimeError if the build hangs past _BUILD_TIMEOUT."""
    try:
        result = subprocess.run(
            [sys.executable, str(build_script)], cwd=cwd, timeout=_BUILD_TIMEOUT,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Build timed out after {_BUILD_TIMEOUT}s") from e
    return result.returncode == 0


def _current_branch(project_dir):
    result = _run_git_probe(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_dir)
    return result.stdout.strip()


def publish_source(project_dir, message):
    """Stage, commit, and push every change in project_dir to origin main.
    Returns True if something was published, False if there was nothing
    staged to commit."""
    branch = _current_branch(project_dir)
    if branch != "main":
        raise RuntimeError(
            f"Refusing to publish from branch '{branch}' — publish_source only "
            f"pushes to origin main, which would silently leave this commit "
            f"unpublished. Switch to main first."
        )

    _run_git(["git", "add", "-A"], cwd=project_dir)
    # dist/ (the Pages clone) and manifest.json are build output, not source.
    # Unstaged defensively, regardless of .gitignore -- if a project ever
    # forgot to ignore dist/, `git add -A` would otherwise stage it as a bare
    # gitlink (a pathspec exclusion on the add itself doesn't work here: git
    # errors out when asked to both add -A and explicitly exclude a path
    # that's already gitignored, which is the normal case).
    _run_git(["git", "reset", "--", "dist", "manifest.json"], cwd=project_dir)

    diff = _run_git_probe(
        ["git", "diff", "--cached", "--quiet"],
        cwd=project_dir, valid_returncodes=(0, 1),
    )
    if diff.returncode == 0:
        return False

    _run_git(["git", "commit", "-m", message], cwd=project_dir)
    _run_git(["git", "push", "origin", "main"], cwd=project_dir)
    return True
