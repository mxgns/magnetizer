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


def publish(dist_dir, timestamp):
    _run_git(["git", "add", "."], cwd=dist_dir)

    diff = _run_git_probe(
        ["git", "diff", "--cached", "--quiet"],
        cwd=dist_dir, valid_returncodes=(0, 1),
    )
    has_staged = diff.returncode == 1

    if has_staged:
        _run_git(["git", "commit", "-m", f"Build {timestamp}"], cwd=dist_dir)
        _run_git(["git", "push", "origin", "main"], cwd=dist_dir)
        return

    ahead = _run_git_probe(
        ["git", "rev-list", "origin/main..HEAD", "--count"],
        cwd=dist_dir,
    )
    if ahead.stdout.strip() != "0":
        _run_git(["git", "push", "origin", "main"], cwd=dist_dir)
        return

    print("Nothing to publish — no changes since last build.")
