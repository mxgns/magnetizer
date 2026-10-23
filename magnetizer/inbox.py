import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import NoReturn
from zoneinfo import ZoneInfo

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
_ALT_TEXT_MIN_WORDS = 2


def _humanize_filename(stem: str) -> str | None:
    """Turn a source image's filename stem into alt text, or None if it looks
    like a camera/screenshot default rather than something a human typed on
    purpose. A deliberately-named file ("The Mona Lisa in a crowded room") is
    almost always several real words; every default naming scheme (IMG_1234,
    DSC_0001, PXL_20231004_123456789, Screenshot_2023-10-04, ...) is a single
    word plus digits/separators -- requiring >=2 words rejects those without
    needing a prefix blocklist to keep up to date. Only '_' is folded into a
    space (a pure filename-safe space substitute); '-' is left alone since it
    can be meaningful grammar ("well-known", "state-of-the-art")."""
    normalized = re.sub(r'_+', ' ', stem).strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    if len(re.findall(r'[A-Za-z]+', normalized)) < _ALT_TEXT_MIN_WORDS:
        return None
    return normalized


def _error(msg) -> NoReturn:
    print(f"\033[31mERROR\033[0m: {msg}", file=sys.stderr)
    sys.exit(1)


def today_in_london(now: datetime | None = None) -> str:
    """Today's date in Europe/London -- used for a supplied .md's missing
    date, so ingest.py gives the same answer regardless of the system/CI
    runner's own local timezone."""
    if now is None:
        return datetime.now(ZoneInfo('Europe/London')).date().isoformat()
    return now.astimezone(ZoneInfo('Europe/London')).date().isoformat()


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


def build_post_markdown(md_file: Path | None, skeleton_today: str, is_draft: bool, source_images: list, default_category: str = "") -> str:
    """Build the post's markdown. If a .md was supplied its body and existing
    frontmatter are kept, with date/draft/images/category normalised in --
    its missing-date default uses Europe/London (today_in_london()),
    independent of the system/CI runner's own local timezone. Otherwise a
    fresh skeleton is generated, dated skeleton_today (matching
    new-post.py's own date.today()). Any image frontmatter entry this adds
    (new skeleton, or padding past what's already listed) uses the source
    file's own name as alt text when it looks deliberately chosen -- see
    _humanize_filename -- falling back to the generic "Image N" otherwise.
    An image already listed in a supplied .md is never touched."""
    image_count = len(source_images)

    if md_file is None:
        image_alts = [_humanize_filename(src.stem) for src in source_images]
        return build_markdown(skeleton_today, None, image_count, default_category, image_alts)

    fm, body = _parse_frontmatter(md_file.read_text(encoding='utf-8'))
    order = list(fm.keys())

    if 'date' not in fm:
        fm['date'] = today_in_london()
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
            fm['images'] = images + [
                _humanize_filename(source_images[i - 1].stem) or f"Image {i}"
                for i in range(len(images) + 1, image_count + 1)
            ]
        elif len(images) > image_count:
            print(f"Warning: '{md_file.name}' lists {len(images)} image(s) in frontmatter, but only {image_count} image file(s) were supplied.")

    if 'category' not in fm:
        fm['category'] = default_category
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


def commit_staged_files(staging_dir: Path, content_dir: Path) -> None:
    """Move every staged file into content_dir. All-or-nothing: if any move
    fails partway through, whatever was already moved is rolled back so
    content_dir ends up exactly as it started."""
    moved = []
    try:
        for f in sorted(staging_dir.iterdir()):
            dest = content_dir / f.name
            shutil.move(str(f), str(dest))
            moved.append(dest)
    except Exception:
        for dest in moved:
            dest.unlink()
        raise


def cleanup_inbox_sources(md_file: Path | None, images: list) -> None:
    """Delete inbox/'s processed source files. Best-effort: by the time this
    runs the post is already committed to content/, so one file failing to
    delete is a warning, not a reason to report the whole run as failed."""
    for f in ([md_file] if md_file is not None else []) + list(images):
        try:
            f.unlink()
        except OSError as e:
            print(f"Warning: could not remove processed source '{f.name}' from inbox/: {e}", file=sys.stderr)
