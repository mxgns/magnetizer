import os
import subprocess
from pathlib import Path


def _last_commit_times(repo_dir):
    """{relative_path: commit_unix_timestamp} for every path ever committed in
    repo_dir's history, via a single `git log` pass. git log's default order is
    newest-first, so the first commit in which a path is seen while walking is
    the most recent commit that touched it."""
    result = subprocess.run(
        ["git", "log", "--name-only", "--format=%x00%ct"],
        cwd=repo_dir, capture_output=True, text=True, check=True,
    )
    times = {}
    current_time = None
    for line in result.stdout.splitlines():
        if line.startswith("\x00"):
            current_time = int(line[1:])
        elif line and line not in times:
            times[line] = current_time
    return times


def restore_mtimes(repo_dir, directories):
    """Set each tracked file's mtime (and atime) under the given directories to
    the commit time of the most recent commit that touched it. Files that exist
    on disk but have no commit history (not yet committed) are left untouched.
    Returns the number of files restored."""
    repo_dir = Path(repo_dir)
    times = _last_commit_times(repo_dir)
    restored = 0
    for directory in directories:
        base = repo_dir / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(repo_dir).as_posix()
            timestamp = times.get(rel)
            if timestamp is not None:
                os.utime(path, (timestamp, timestamp))
                restored += 1
    return restored
