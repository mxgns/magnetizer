import html
import re
import sys
from dataclasses import dataclass
from datetime import date as _date
from typing import NoReturn
import markdown as _markdown


IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "svg")
_IMAGE_EXT_RE = "|".join(IMAGE_EXTENSIONS)


def special_page_image_pattern(name):
    return re.compile(rf'^{re.escape(name)}-image-(\d{{2}})\.({_IMAGE_EXT_RE})$')

_ALLOWED_FRONTMATTER_KEYS = frozenset({'date', 'title', 'name', 'images', 'favourite', 'category', 'draft', 'ai_assisted', 'noindex'})
_MARKDOWN_EXTENSIONS = ['pymdownx.mark', 'smarty', 'magnetizer.containers']

_IMAGE_TOKEN_BLOCK_RE = re.compile(r'^\{\{\s*image\s+(\d+)\s*\}\}$')
_IMAGE_TOKEN_LOOSE_RE = re.compile(r'\{\{\s*image\s+\d+\s*\}\}')


def _error(msg) -> NoReturn:
    print(f"\033[31mERROR\033[0m: {msg}", file=sys.stderr)
    sys.exit(1)


@dataclass
class Image:
    filename: str
    alt: str = ""


@dataclass
class Post:
    id: int | str
    date: str | None
    date_uk: str | None
    title: str | None
    url: str
    body_html: str
    images: list
    excerpt_html: str | None = None
    name: str | None = None
    post_type: str | None = None
    is_favourite: bool = False
    is_draft: bool = False
    is_ai_assisted: bool = False
    is_noindex: bool = False
    category: str | None = None
    char_count: int = 0
    inline_image_filenames: frozenset = frozenset()
    excerpt_inline_image_filenames: frozenset = frozenset()


def resized_filename(filename):
    if filename.lower().endswith('.svg'):
        return filename
    stem, _, ext = filename.rpartition('.')
    return f"{stem}-resized.{ext}"


def _plain_text(rendered_html):
    text = re.sub(r'<[^>]+>', '', rendered_html)
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def _parse_frontmatter(text):
    parts = text.split('---')
    if len(parts) < 3:
        return {}, text.strip()
    fm = {}
    lines = parts[1].splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        key, sep, value = line.partition(':')
        if sep:
            key = key.strip()
            value = value.strip()
            if not value:
                items = []
                i += 1
                while i < len(lines) and lines[i].strip().startswith('- '):
                    items.append(lines[i].strip()[2:])
                    i += 1
                fm[key] = items
                continue
            else:
                fm[key] = value
        i += 1
    body = '---'.join(parts[2:]).strip()
    return fm, body


def _format_date_uk(date_str):
    d = _date.fromisoformat(date_str)
    return f"{d.day} {d.strftime('%B %Y')}"


def _substitute_image_tokens(body, images, post_id):
    blocks = body.split('\n\n')
    used_filenames = set()

    for i, block in enumerate(blocks):
        m = _IMAGE_TOKEN_BLOCK_RE.match(block.strip())
        if not m:
            continue
        n = int(m.group(1))
        if not (1 <= n <= len(images)):
            _error(f"post {post_id} references image {n} via {{{{ image {n} }}}}, but only {len(images)} image(s) exist for this post")
        image = images[n - 1]
        used_filenames.add(image.filename)
        alt = html.escape(image.alt, quote=True)
        blocks[i] = f'<figure><img src="{resized_filename(image.filename)}" alt="{alt}"></figure>'

    new_body = '\n\n'.join(blocks)
    if _IMAGE_TOKEN_LOOSE_RE.search(new_body):
        _error(f"post {post_id} uses {{{{ image N }}}} inline with other text — it must be on its own line, separated by blank lines from surrounding content")

    return new_body, used_filenames


def parse_post(md_text, post_id, image_filenames):
    fm, body = _parse_frontmatter(md_text)

    for key in fm:
        if key not in _ALLOWED_FRONTMATTER_KEYS:
            print(f"Warning: Post {post_id} has unknown frontmatter key: '{key}'")

    date_str = fm.get('date') or None
    title = fm.get('title') or None
    name = fm.get('name') or None
    alt_texts = fm.get('images') or []
    favourite_raw = fm.get('favourite', 'false')
    is_favourite = isinstance(favourite_raw, str) and favourite_raw.lower() == 'true'
    draft_raw = fm.get('draft', 'false')
    is_draft = isinstance(draft_raw, str) and draft_raw.lower() == 'true'
    ai_assisted_raw = fm.get('ai_assisted', 'false')
    is_ai_assisted = isinstance(ai_assisted_raw, str) and ai_assisted_raw.lower() == 'true'
    noindex_raw = fm.get('noindex', 'false')
    is_noindex = isinstance(noindex_raw, str) and noindex_raw.lower() == 'true'
    category_raw = fm.get('category', '')
    category = (category_raw.lower().strip() if isinstance(category_raw, str) else '') or None

    sorted_filenames = sorted(
        image_filenames,
        key=lambda f: int(re.search(r'-image-(\d+)', f).group(1)),  # type: ignore[union-attr]
    )

    images = [
        Image(filename=f, alt=str(alt_texts[i]) if i < len(alt_texts) else "")
        for i, f in enumerate(sorted_filenames)
    ]

    more_parts = body.split('<!-- more -->', 1)
    if len(more_parts) == 2:
        part0, excerpt_inline_image_filenames = _substitute_image_tokens(more_parts[0], images, post_id)
        part1, used1 = _substitute_image_tokens(more_parts[1], images, post_id)
        inline_image_filenames = excerpt_inline_image_filenames | used1
        body_html = _markdown.markdown(part0 + '\n\n' + part1, extensions=_MARKDOWN_EXTENSIONS)
        excerpt_html = _markdown.markdown(part0.strip(), extensions=_MARKDOWN_EXTENSIONS)
    else:
        body, inline_image_filenames = _substitute_image_tokens(body, images, post_id)
        excerpt_inline_image_filenames = inline_image_filenames
        body_html = _markdown.markdown(body, extensions=_MARKDOWN_EXTENSIONS) if body else ''
        excerpt_html = None

    char_count = len(_plain_text(body_html))

    top_level_image_count = len(images) - len(inline_image_filenames)
    has_content = char_count > 0
    has_any_image = len(images) > 0
    if title:
        post_type = "full"
    elif top_level_image_count > 0:
        post_type = "image"
    elif has_content or has_any_image:
        post_type = "note"
    else:
        # No title, no images (top-level or inline), no content — the caller
        # decides what to do with this (see the build's invalid-post error).
        post_type = None

    return Post(
        id=post_id,
        date=date_str,
        date_uk=_format_date_uk(date_str) if date_str else None,
        title=title,
        url=f"{post_id}.html",
        body_html=body_html,
        images=images,
        excerpt_html=excerpt_html,
        name=name,
        post_type=post_type,
        is_favourite=is_favourite,
        is_draft=is_draft,
        is_ai_assisted=is_ai_assisted,
        is_noindex=is_noindex,
        category=category,
        char_count=char_count,
        inline_image_filenames=frozenset(inline_image_filenames),
        excerpt_inline_image_filenames=frozenset(excerpt_inline_image_filenames),
    )
