#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from magnetizer.source_publisher import publish_source, run_build

_BUILD_SCRIPT = Path(__file__).parent / "build.py"


def main():
    parser = argparse.ArgumentParser(
        prog="publish.py",
        description=(
            "Build the project locally as a sanity check, then commit and push any "
            "changes in the current directory to origin main. Distinct from "
            "'build.py --push', which publishes dist/ (the generated output) to the "
            "Pages repo -- this publishes the project's own source."
        ),
    )
    parser.add_argument(
        "message",
        nargs="?",
        metavar="MESSAGE",
        help="Commit message (default: 'Update {timestamp}').",
    )
    args = parser.parse_args()

    try:
        build_ok = run_build(_BUILD_SCRIPT, Path.cwd())
    except RuntimeError as e:
        print(f"  {e}", file=sys.stderr)
        sys.exit(1)
    if not build_ok:
        print("Build failed — not publishing.", file=sys.stderr)
        sys.exit(1)

    message = args.message or f"Update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        published = publish_source(Path.cwd(), message)
    except RuntimeError as e:
        print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    if published:
        print(f"Published: {message}")
    else:
        print("Nothing to publish — no changes to commit.")


if __name__ == "__main__":
    main()
