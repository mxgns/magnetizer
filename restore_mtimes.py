#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from magnetizer.mtimes import restore_mtimes


def main():
    parser = argparse.ArgumentParser(
        prog="restore_mtimes.py",
        description=(
            "Restore each tracked file's mtime, under the given directories, to the "
            "commit time of the most recent commit that touched it. Intended for CI: a "
            "fresh checkout resets every file's mtime to checkout time, which would "
            "otherwise make the sitemap's <lastmod> say 'just now' for every post."
        ),
    )
    parser.add_argument(
        "directories",
        nargs="*",
        default=["content", "resources"],
        metavar="DIRECTORY",
        help="Directories to restore mtimes under (default: content resources).",
    )
    args = parser.parse_args()

    count = restore_mtimes(Path.cwd(), args.directories)
    print(f"Restored mtimes for {count} file{'s' if count != 1 else ''}.")


if __name__ == "__main__":
    main()
