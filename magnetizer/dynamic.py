"""Shortcode-style dynamic values for markdown pages: {{ post_count }}, {{ today }}, etc."""

import re
from datetime import date as _date
from html import escape as _escape

from magnetizer.content import _plain_text

SCALAR_NAMES = {"post_count", "word_count", "image_count", "today"}
BLOCK_NAMES = {"ai_post_list"}
KNOWN_NAMES = SCALAR_NAMES | BLOCK_NAMES

_SHORTCODE_RE = re.compile(r'\{\{\s*([a-z][a-z0-9_]*)\s*\}\}')
_PROTECTED_RE = re.compile(
    r'<pre\b.*?</pre>|<code\b.*?</code>|<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->',
    re.DOTALL | re.IGNORECASE,
)
_ATTR_RE = r'''\s+[a-zA-Z_:][-a-zA-Z0-9_:.]*(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?'''
# A bare `<[^>]+>` split ends the match at the first `>`, even one quoted inside an
# attribute value (e.g. `<a title="x > y">`), silently exposing the tail of that
# attribute as expandable text. Require well-formed attribute syntax instead, so a
# quoted `>` can never be mistaken for the tag's real closing bracket.
_TAG_RE = re.compile(rf'(</?[a-zA-Z][a-zA-Z0-9:-]*(?:{_ATTR_RE})*\s*/?>)')
_P_OPEN_RE = re.compile(r'^<p(\s[^>]*)?>$', re.IGNORECASE)
_P_CLOSE_RE = re.compile(r'^</p>$', re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r'\x00(\d+)\x00')


def format_int(n: int) -> str:
    return f"{n:,}"


def wrap_scalar(name: str, formatted: str) -> str:
    return f'<span class="{name.replace("_", "-")}">{formatted}</span>'


def format_today(build_date) -> str:
    return f"{build_date.day}/{build_date.month}/{build_date:%y}"


def render_ai_post_list(published_posts) -> str:
    matching = [p for p in published_posts if p.is_ai_assisted]
    if not matching:
        return '<ul class="ai-post-list"><li>(none)</li></ul>'
    # Special pages carry a string id (their name) rather than an int post id, so a
    # plain (date, id) key would raise when sorting a mix of the two — group by
    # id-type first (only ever compared within the same type) as a tie-break.
    matching.sort(
        key=lambda p: (p.date or "", 1, p.id) if isinstance(p.id, int) else (p.date or "", 0, p.id),
        reverse=True,
    )
    items = "".join(
        f'<li><a href="{_escape(p.url, quote=True)}">{_escape(p.title or "")}</a></li>'
        for p in matching
    )
    return f'<ul class="ai-post-list">{items}</ul>'


def compute_base_values(published_posts, build_date, warn, ai_post_list_candidates=None) -> dict:
    # ai_post_list is the one dynamic value that also draws on special pages (an
    # about/now/etc. page can be ai_assisted too) — every other value stays scoped
    # to published posts only, per the post-inclusion rules.
    if ai_post_list_candidates is None:
        ai_post_list_candidates = published_posts
    post_count = len(published_posts)
    image_count = sum(len(p.images) for p in published_posts)
    return {
        "post_count": wrap_scalar("post_count", format_int(post_count)),
        "image_count": wrap_scalar("image_count", format_int(image_count)),
        "today": wrap_scalar("today", format_today(build_date)),
        "ai_post_list": render_ai_post_list(ai_post_list_candidates),
    }


def compute_word_count(published_posts, base_values) -> int:
    values = {**base_values, "word_count": ""}
    total = 0
    for post in published_posts:
        expanded, _ = expand_shortcodes(post.body_html, values, f"{post.id}.md", None)
        text = _plain_text(expanded)
        if text:
            total += len(text.split())
    return total


def _protect(html_fragment):
    protected = []

    def _store(m):
        protected.append(m.group(0))
        return f'\x00{len(protected) - 1}\x00'

    return _PROTECTED_RE.sub(_store, html_fragment), protected


def _restore(html_fragment, protected):
    return _PLACEHOLDER_RE.sub(lambda m: protected[int(m.group(1))], html_fragment)


def expand_shortcodes(html_fragment, values, source_name, warn):
    if warn is None:
        def warn(msg):
            pass

    working, protected = _protect(html_fragment)
    tokens = _TAG_RE.split(working)
    used_names = set()

    def _protect_one(text):
        protected.append(text)
        return f'\x00{len(protected) - 1}\x00'

    # Phase 1: block shortcode as sole content of its own <p>...</p>
    i = 0
    while i <= len(tokens) - 3:
        if (
            _P_OPEN_RE.match(tokens[i])
            and _P_CLOSE_RE.match(tokens[i + 2])
        ):
            m = re.fullmatch(r'\{\{\s*([a-z][a-z0-9_]*)\s*\}\}', tokens[i + 1].strip())
            if m and m.group(1) in BLOCK_NAMES:
                name = m.group(1)
                used_names.add(name)
                replacement = _protect_one(values[name])
                tokens[i:i + 3] = [replacement]
                i += 1
                continue
        i += 1

    # Phase 2: scalars + leftover unknown/inline-block handling
    def _callback(m):
        name = m.group(1)
        if name in SCALAR_NAMES:
            used_names.add(name)
            return values[name]
        if name in BLOCK_NAMES:
            warn(f"Shortcode {{{{ {name} }}}} used inline — must be the sole content of its paragraph")
            return m.group(0)
        warn(f"Unknown shortcode: {{{{ {name} }}}}")
        return m.group(0)

    for idx in range(0, len(tokens), 2):
        tokens[idx] = _SHORTCODE_RE.sub(_callback, tokens[idx])

    joined = "".join(tokens)
    return _restore(joined, protected), used_names
