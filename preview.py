#!/usr/bin/env python3
import argparse
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from magnetizer.config import load_config
from magnetizer.manifest import load_manifest
from magnetizer.preview import last_edited_md, make_server, page_for_md
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

    cwd = Path.cwd()
    # Before building: the build rewrites manifest.json, erasing what changed.
    edited_md = None
    if (cwd / "content").is_dir():
        edited_md = last_edited_md(cwd / "content", load_manifest(cwd / "manifest.json"))

    try:
        build_ok = run_build(_BUILD_SCRIPT, cwd, args=build_args)
    except RuntimeError as e:
        print(f"  {e}", file=sys.stderr)
        sys.exit(1)
    if not build_ok:
        print("Build failed — not serving.", file=sys.stderr)
        sys.exit(1)

    try:
        server = make_server(cwd / "dist", port=args.port)
    except OSError as e:
        print(f"  Can't serve on port {args.port}: {e.strerror}", file=sys.stderr)
        sys.exit(1)

    url = f"http://localhost:{server.server_address[1]}/"
    if edited_md:
        page = page_for_md(edited_md, load_config(cwd / "config.yaml"))
        if (cwd / "dist" / page).is_file():
            url += page
    print(f"Serving at {url} (Ctrl+C to stop)", flush=True)
    if not args.no_open:
        # In a thread: with a text-mode browser, webbrowser.open blocks until
        # the browser exits, which would stop serve_forever from ever starting.
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
