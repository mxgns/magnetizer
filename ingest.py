#!/usr/bin/env python3
import argparse
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from magnetizer.config import load_config
from magnetizer.inbox import (
    build_post_markdown,
    cleanup_inbox_sources,
    commit_staged_files,
    is_draft_filename,
    output_image_filename,
    process_image,
    scan_inbox,
)
from magnetizer.post import get_next_post_id
from magnetizer.validate import validate_content


def main():
    parser = argparse.ArgumentParser(
        prog="ingest.py",
        description=(
            "Turn inbox/'s dropped files into a numbered post in content/. "
            "inbox/ holds the files for exactly one post as loose files, no subfolders."
        ),
    )
    parser.add_argument("--inbox", default="inbox", metavar="DIRECTORY", help="Inbox directory (default: inbox).")
    parser.add_argument("--content", default="content", metavar="DIRECTORY", help="Content directory (default: content).")
    parser.add_argument("--max-edge", type=int, default=2000, metavar="N", help="Maximum long edge in pixels (default: 2000).")
    parser.add_argument("--quality", type=int, default=90, metavar="N", help="JPEG/PNG save quality (default: 90).")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be created without changing anything.")
    args = parser.parse_args()

    inbox_dir = Path.cwd() / args.inbox
    content_dir = Path.cwd() / args.content

    if not inbox_dir.is_dir():
        print(f"Error: inbox directory '{inbox_dir}' could not be found.", file=sys.stderr)
        sys.exit(1)
    if not content_dir.is_dir():
        print(f"Error: content directory '{content_dir}' could not be found.", file=sys.stderr)
        sys.exit(1)

    md_file, images = scan_inbox(inbox_dir)
    if md_file is None and not images:
        print("Nothing to ingest.")
        return

    post_id = get_next_post_id(content_dir)
    is_draft = is_draft_filename(md_file)
    skeleton_today = date.today().isoformat()
    config = load_config(Path.cwd() / "config.yaml")

    with tempfile.TemporaryDirectory() as staging:
        staging_dir = Path(staging)

        for i, src in enumerate(images, start=1):
            dest = staging_dir / output_image_filename(post_id, i, src)
            process_image(src, dest, args.max_edge, args.quality)

        markdown = build_post_markdown(md_file, skeleton_today, is_draft, len(images), config["default_category"])
        (staging_dir / f"{post_id}.md").write_text(markdown, encoding='utf-8')

        with tempfile.TemporaryDirectory() as merged:
            merged_dir = Path(merged)
            for f in content_dir.iterdir():
                if not f.name.startswith('.'):
                    (merged_dir / f.name).symlink_to(f)
            for f in staging_dir.iterdir():
                (merged_dir / f.name).symlink_to(f)

            validate_content(merged_dir, config)

        if args.dry_run:
            print(f"Would create post {post_id}.")
            return

        commit_staged_files(staging_dir, content_dir)

    cleanup_inbox_sources(md_file, images)

    print(f"Post {post_id} created.")


if __name__ == "__main__":
    main()
