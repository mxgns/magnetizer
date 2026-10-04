import subprocess

_TIMEOUT = 60


def _run_git(cmd, *, cwd):
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=_TIMEOUT,
        )
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or "").strip()
        raise RuntimeError(f"Git command failed: {' '.join(cmd)}\n{msg}") from e


def _run_git_probe(cmd, *, cwd, valid_returncodes=(0,)):
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=_TIMEOUT,
    )
    if result.returncode not in valid_returncodes:
        raise RuntimeError(
            f"Git command failed: {' '.join(cmd)}\n{(result.stderr or '').strip()}"
        )
    return result


def publish_source(project_dir, message):
    """Stage, commit, and push every change in project_dir to origin main.
    Returns True if something was published, False if there was nothing
    staged to commit."""
    _run_git(["git", "add", "-A"], cwd=project_dir)

    diff = _run_git_probe(
        ["git", "diff", "--cached", "--quiet"],
        cwd=project_dir, valid_returncodes=(0, 1),
    )
    if diff.returncode == 0:
        return False

    _run_git(["git", "commit", "-m", message], cwd=project_dir)
    _run_git(["git", "push", "origin", "main"], cwd=project_dir)
    return True
