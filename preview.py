#!/usr/bin/env python3
import argparse
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from magnetizer.preview import make_server
from magnetizer.source_publisher import run_build

_BUILD_SCRIPT = Path(__file__).parent / "build.py"


def main():
    parser = argparse.ArgumentParser(
        prog="preview.py",
        description=(
            "Build the project with build.py, then serve ./dist on localhost and open "
            "it in a browser. Any option not listed below (e.g. --flush, --refresh, "
            "--resources, --verbose) is passed straight through to build.py. "
            "Press Ctrl+C to stop."
        ),
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port to serve on (default: 8000; 0 picks a free one).",
    )
    parser.add_argument(
        "--no-open", action="store_true",
        help="Don't open the site in a browser.",
    )
    args, build_args = parser.parse_known_args()

    try:
        build_ok = run_build(_BUILD_SCRIPT, Path.cwd(), args=build_args)
    except RuntimeError as e:
        print(f"  {e}", file=sys.stderr)
        sys.exit(1)
    if not build_ok:
        print("Build failed — not serving.", file=sys.stderr)
        sys.exit(1)

    try:
        server = make_server(Path.cwd() / "dist", port=args.port)
    except OSError as e:
        print(f"  Can't serve on port {args.port}: {e.strerror}", file=sys.stderr)
        sys.exit(1)

    url = f"http://localhost:{server.server_address[1]}/"
    print(f"Serving at {url} (Ctrl+C to stop)", flush=True)
    if not args.no_open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
