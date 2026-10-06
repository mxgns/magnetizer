import re
import shutil
import sys
from pathlib import Path
from typing import NoReturn

import pillow_heif
from PIL import Image

from magnetizer.content import _parse_frontmatter
from magnetizer.image import fix_orientation_and_strip_exif
from magnetizer.post import build_markdown

pillow_heif.register_heif_opener()

SOURCE_IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "svg", "heic", "heif")
_SOURCE_IMAGE_EXT_RE = "|".join(SOURCE_IMAGE_EXTENSIONS)
_HEIF_EXTENSIONS = {"heic", "heif"}

_NATURAL_KEY_RE = re.compile(r'(\d+)')


def _error(msg) -> NoReturn:
    print(f"\033[31mERROR\033[0m: {msg}", file=sys.stderr)
    sys.exit(1)


def natural_key(name: str):
    parts = _NATURAL_KEY_RE.split(name)
    return [int(p) if p.isdigit() else p for p in parts]


def scan_inbox(inbox_dir: Path):
    """Validate inbox/'s contents and return (md_file_or_None, images_sorted).

    inbox/ holds the files for exactly one post, as loose files -- no
    subfolders. Dotfiles are ignored."""
    entries = [f for f in Path(inbox_dir).iterdir() if not f.name.startswith('.')]
    if not entries:
        return None, []

    md_files = [f for f in entries if f.suffix.lower() == '.md']
    if len(md_files) > 1:
        _error(f"inbox/ has {len(md_files)} .md files ({', '.join(f.name for f in md_files)}) -- at most one is allowed")

    others = [f for f in entries if f not in md_files]
    for f in others:
        if f.suffix.lower().lstrip('.') not in SOURCE_IMAGE_EXTENSIONS:
            _error(f"unsupported file in inbox/: '{f.name}' (recognised image extensions: {', '.join(SOURCE_IMAGE_EXTENSIONS)})")

    images = sorted(others, key=lambda f: natural_key(f.name))
    md_file = md_files[0] if md_files else None

    if not images and md_file is None:
        _error("inbox/ has no images and no .md file")

    return md_file, images


def process_image(src: Path, dest: Path, max_edge: int, quality: int) -> None:
    """Process one source image into dest: raster images get EXIF orientation
    baked in, metadata stripped, and are downscaled (never upscaled); SVGs
    are copied as-is."""
    if src.suffix.lower().lstrip('.') == 'svg':
        shutil.copy2(src, dest)
        return

    img = Image.open(src)
    img = fix_orientation_and_strip_exif(img)
    w, h = img.size
    long_edge = max(w, h)
    if long_edge > max_edge:
        scale = max_edge / long_edge
        img = img.resize((round(w * scale), round(h * scale)), Image.Resampling.LANCZOS)
    img.save(dest, quality=quality, optimize=True)


def output_image_filename(post_id: int, index: int, src: Path) -> str:
    ext = src.suffix.lower().lstrip('.')
    if ext in _HEIF_EXTENSIONS:
        ext = 'jpg'
    return f"{post_id}-image-{index:02d}.{ext}"


def is_draft_filename(md_file: Path | None) -> bool:
    return md_file is not None and md_file.name.startswith('_')


def build_post_markdown(md_file: Path | None, today: str, is_draft: bool, image_count: int) -> str:
    """Build the post's markdown. If a .md was supplied its body and existing
    frontmatter are kept, with date/draft/images/category normalised in;
    otherwise a fresh skeleton is generated."""
    if md_file is None:
        return build_markdown(today, None, image_count)

    fm, body = _parse_frontmatter(md_file.read_text())
    order = list(fm.keys())

    if 'date' not in fm:
        fm['date'] = today
        order.append('date')

    if is_draft:
        if 'draft' not in fm:
            order.append('draft')
        fm['draft'] = 'true'

    if image_count > 0 or 'images' in fm:
        images = fm.get('images', [])
        if len(images) < image_count:
            if 'images' not in fm:
                order.append('images')
            fm['images'] = images + [f"Image {i}" for i in range(len(images) + 1, image_count + 1)]
        elif len(images) > image_count:
            print(f"Warning: '{md_file.name}' lists {len(images)} image(s) in frontmatter, but only {image_count} image file(s) were supplied.")

    if 'category' not in fm:
        fm['category'] = ''
        order.append('category')

    lines = ['---']
    for key in order:
        value = fm[key]
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {item}" for item in value)
        else:
            lines.append(f"{key}: {value}")
    lines.append('---')
    lines.append('')
    if body:
        lines.append(body)
        lines.append('')
    return '\n'.join(lines)
