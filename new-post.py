#!/usr/bin/env python3
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from magnetizer.content import IMAGE_EXTENSIONS
from magnetizer.post import build_markdown, copy_images, get_next_post_id

IMAGE_EXTS = {f".{ext}" for ext in IMAGE_EXTENSIONS}


def main():
    parser = argparse.ArgumentParser(
        prog="new-post.py",
        description="Create a new post in the current directory.",
    )
    parser.add_argument(
        "--latest-images",
        type=int,
        metavar="N",
        dest="latest_images",
        help="Use the N most recently modified images from DIRECTORY instead of listing images explicitly.",
    )
    parser.add_argument("args", nargs="*", metavar="IMAGES/TITLE")
    parsed = parser.parse_args()

    content_dir = Path.cwd() / "content"
    if not content_dir.is_dir():
        print("Error: no content/ directory found in the current directory.", file=sys.stderr)
        sys.exit(1)

    if parsed.latest_images is not None:
        if parsed.latest_images < 0:
            parser.error("--latest-images requires a non-negative N")
        if not parsed.args:
            print("Error: --latest-images requires a DIRECTORY argument.", file=sys.stderr)
            sys.exit(1)
        directory = Path(parsed.args[0])
        title = parsed.args[1] if len(parsed.args) > 1 else None
        if not directory.is_dir():
            print(f"Error: directory {directory} could not be found.", file=sys.stderr)
            sys.exit(1)
        try:
            candidates = [f for f in directory.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS]
        except OSError as e:
            print(f"Error: could not read directory {directory}: {e.strerror}.", file=sys.stderr)
            sys.exit(1)
        if len(candidates) < parsed.latest_images:
            print(
                f"Error: found {len(candidates)} image(s) in {directory}, "
                f"but --latest-images {parsed.latest_images} was requested.",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        except OSError as e:
            print(f"Error: could not read images in {directory}: {e.strerror}.", file=sys.stderr)
            sys.exit(1)
        images = [str(f) for f in candidates[: parsed.latest_images]]
    else:
        images = [a for a in parsed.args if Path(a).suffix.lower() in IMAGE_EXTS]
        non_images = [a for a in parsed.args if Path(a).suffix.lower() not in IMAGE_EXTS]
        title = non_images[0] if non_images else None

    post_id = get_next_post_id(content_dir)
    image_count = copy_images(images, content_dir, post_id)
    (content_dir / f"{post_id}.md").write_text(build_markdown(date.today().isoformat(), title, image_count))
    print(f"Post {post_id} successfully created.")


if __name__ == "__main__":
    main()
