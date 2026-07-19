import re
import sys
from pathlib import Path
from typing import NoReturn

from magnetizer.content import IMAGE_EXTENSIONS, _IMAGE_EXT_RE, special_page_image_pattern

_MD_PATTERN = re.compile(r'^([1-9]\d*)\.md$')
_IMAGE_PATTERN = re.compile(rf'^([1-9]\d*)-image-(\d{{2}})\.({_IMAGE_EXT_RE})$')
_BASE_RESERVED_SLUGS = {"index", "archive"}
_INDEX_PAGE_SLUG_PATTERN = re.compile(r'^index-\d+$')


def _error(msg) -> NoReturn:
    print(f"\033[31mERROR\033[0m: {msg}", file=sys.stderr)
    sys.exit(1)


def validate_config(config):
    if not config.get("site_url"):
        _error("'site_url' is required in config.yaml — set it to the absolute base URL of your site, e.g. https://example.github.io")
    reserved = _BASE_RESERVED_SLUGS | set(config.get("special_pages", []))
    for slug in config.get("categories", {}):
        if slug in reserved or _INDEX_PAGE_SLUG_PATTERN.match(slug) or slug.isdigit():
            _error(f"category slug '{slug}' in config.yaml is reserved and would overwrite a generated page — choose a different slug")


def validate_project(cwd):
    cwd = Path(cwd)
    for name in ("content", "dist", "templates", "resources"):
        if not (cwd / name).is_dir():
            _error(f"required directory '{name}/' not found in {cwd}")
    if not (cwd / "config.yaml").is_file():
        _error(f"required file 'config.yaml' not found in {cwd}")
    if not (cwd / "templates" / "index.html").is_file():
        _error("required template 'templates/index.html' not found — create it with MAGNETIZER_METADATA and MAGNETIZER_CONTENT placeholders")


def validate_content(content_dir, config=None):
    content_dir = Path(content_dir)
    files = [f.name for f in content_dir.iterdir() if not f.name.startswith('.')]

    special_pages = (config or {}).get("special_pages", [])
    for name in special_pages:
        if f"{name}.md" not in files:
            _error(f"special page '{name}' is configured in config.yaml but '{name}.md' was not found in content/")

    special_md_names = {f"{name}.md" for name in special_pages}
    special_image_patterns = [special_page_image_pattern(name) for name in special_pages]

    md_ids = set()
    image_ids = set()
    image_numbers_by_post: dict[int, set[int]] = {}

    for name in files:
        if name in special_md_names:
            continue
        if any(pattern.match(name) for pattern in special_image_patterns):
            continue
        if name.endswith('.md'):
            m = _MD_PATTERN.match(name)
            if not m:
                _error(f"invalid markdown filename '{name}' in content/ (expected {{post-id}}.md with no leading zeros)")
            md_ids.add(int(m.group(1)))
        elif re.search(r'-image-', name) or any(name.endswith(f'.{ext}') for ext in IMAGE_EXTENSIONS) or name.endswith('.gif'):
            m = _IMAGE_PATTERN.match(name)
            if not m:
                _error(f"invalid image filename '{name}' in content/")
            post_id, image_num = int(m.group(1)), int(m.group(2))
            image_ids.add(post_id)
            image_numbers_by_post.setdefault(post_id, set()).add(image_num)
        else:
            _error(f"unrecognised file '{name}' in content/")

    if not md_ids:
        _error("no .md files found in content/")

    for img_id in image_ids:
        if img_id not in md_ids:
            orphans = [n for n in files if (m := _IMAGE_PATTERN.match(n)) and int(m.group(1)) == img_id]
            _error(f"image file '{orphans[0]}' has no matching {img_id}.md in content/")

    for post_id, numbers in image_numbers_by_post.items():
        expected = set(range(1, len(numbers) + 1))
        if numbers != expected:
            missing = min(expected - numbers)
            _error(f"post {post_id} has a gap in image numbering — image {missing:02d} is missing (image files must be numbered sequentially starting at 01 with no gaps)")
