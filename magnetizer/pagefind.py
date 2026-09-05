import subprocess

_TIMEOUT = 120

# Pinned so a bare `npx pagefind` can't silently resolve a newer release
# mid-project and change the generated index's format/behaviour between
# builds. Bump deliberately, alongside a changelog entry, when upgrading.
_PAGEFIND_VERSION = "1.5.2"


def run_pagefind_index(dist_dir):
    try:
        subprocess.run(
            ["npx", "--yes", f"pagefind@{_PAGEFIND_VERSION}", "--site", str(dist_dir)],
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
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Pagefind indexing failed: timed out after {e.timeout}s") from e
