from magnetizer.git_utils import _run_git


def _current_branch(project_dir):
    result = _run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_dir)
    branch = result.stdout.strip()
    return "detached HEAD" if branch == "HEAD" else branch


def _commit_count(cmd, *, cwd):
    return int(_run_git(cmd, cwd=cwd).stdout.strip())


def pull(project_dir):
    """Fast-forward the local project's own source from origin main. Returns
    the number of commits pulled (0 if there was nothing to pull). Raises
    RuntimeError -- making no changes -- if not on main, if local and origin
    have diverged, or on any other git failure (e.g. a fast-forward blocked
    by conflicting uncommitted local changes)."""
    branch = _current_branch(project_dir)
    if branch != "main":
        raise RuntimeError(
            f"Refusing to pull on branch '{branch}' — pull.py only fast-forwards "
            f"from origin main. Switch to main first."
        )

    _run_git(["git", "fetch", "origin", "main"], cwd=project_dir)

    behind = _commit_count(["git", "rev-list", "--count", "HEAD..origin/main"], cwd=project_dir)
    ahead = _commit_count(["git", "rev-list", "--count", "origin/main..HEAD"], cwd=project_dir)

    if behind == 0:
        return 0

    if ahead > 0:
        raise RuntimeError(
            f"Local main and origin/main have diverged ({ahead} commit(s) local, "
            f"{behind} commit(s) origin) — pull.py only fast-forwards, it never "
            f"merges. Resolve manually (e.g. 'git rebase origin/main')."
        )

    _run_git(["git", "merge", "--ff-only", "origin/main"], cwd=project_dir)
    return behind
