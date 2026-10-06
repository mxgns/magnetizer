#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from magnetizer.pull import pull


def main():
    parser = argparse.ArgumentParser(
        prog="pull.py",
        description=(
            "Fast-forward the current project's entire source from origin main -- "
            "e.g. to catch up on a post CI ingested from the iPad, or on template/"
            "CSS/config changes pushed from elsewhere. Never merges: refuses with "
            "an error, making no changes, if local and origin have diverged."
        ),
    )
    parser.parse_args()

    try:
        pulled = pull(Path.cwd())
    except RuntimeError as e:
        print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    if pulled:
        print(f"Pulled {pulled} commit{'s' if pulled != 1 else ''}.")
    else:
        print("Already up to date.")


if __name__ == "__main__":
    main()
