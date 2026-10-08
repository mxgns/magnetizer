import subprocess

_TIMEOUT = 60


def _run_git(cmd, *, cwd):
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=_TIMEOUT,
        )
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or "").strip()
        raise RuntimeError(f"Git command failed: {' '.join(cmd)}\n{msg}") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Git command timed out after {_TIMEOUT}s: {' '.join(cmd)}") from e
    except FileNotFoundError as e:
        raise RuntimeError(f"git executable not found: {e}") from e


def _run_git_probe(cmd, *, cwd, valid_returncodes=(0,)):
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=_TIMEOUT,
    )
    if result.returncode not in valid_returncodes:
        raise RuntimeError(
            f"Git command failed: {' '.join(cmd)}\n{(result.stderr or '').strip()}"
        )
    return result
