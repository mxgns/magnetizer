import subprocess

_TIMEOUT = 120


def run_pagefind_index(dist_dir):
    try:
        subprocess.run(
            ["npx", "--yes", "pagefind", "--site", str(dist_dir)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=_TIMEOUT,
        )
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or "").strip()
        raise RuntimeError(f"Pagefind indexing failed:\n{msg}") from e
    except FileNotFoundError as e:
        raise RuntimeError(f"Pagefind indexing failed: {e}") from e
