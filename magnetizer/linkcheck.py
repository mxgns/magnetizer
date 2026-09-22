import html
from pathlib import Path
from urllib.parse import urlsplit

from magnetizer.content import _A_TAG_RE, _HREF_ATTR_RE, _is_external_href

_NON_PAGE_SCHEMES = {'mailto', 'tel', 'sms', 'javascript'}


def _internal_target(href, site_url):
    """The dist/-relative path an internal href resolves to, or None if it's
    external, a same-page fragment/query with no path, or a non-navigable
    scheme (mailto:, tel:, ...). Decodes HTML entities first, since
    Python-Markdown's <email@example.com> autolink syntax obfuscates the
    mailto: href character-by-character as &#nn; anti-spam entities."""
    decoded = html.unescape(href)
    split = urlsplit(decoded)
    if split.scheme in _NON_PAGE_SCHEMES:
        return None
    if _is_external_href(decoded, site_url):
        return None
    if not split.path:
        return None
    return 'index.html' if split.path == '/' else split.path.lstrip('/')


def _dist_files(dist_dir):
    """Every regular file under dist_dir, as a dist-relative posix path.
    Dotted directories (dist/.git, the published site's own repo) are
    excluded -- nothing in content/ should be linking into them."""
    return {
        p.relative_to(dist_dir).as_posix()
        for p in dist_dir.rglob('*')
        if p.is_file() and not any(part.startswith('.') for part in p.relative_to(dist_dir).parts)
    }


def check_internal_links(dist_dir, site_url):
    """Scan every page in dist_dir for internal links whose target doesn't
    exist in dist_dir, returning (filename, message) warnings in the same
    shape as the rest of the build's warnings list. Runs over the whole
    tree rather than just this run's changed pages, since a link can break
    because the page it points to was deleted elsewhere."""
    dist_dir = Path(dist_dir)
    existing = _dist_files(dist_dir)

    warnings = []
    for html_path in sorted(dist_dir.glob('*.html')):
        html_text = html_path.read_text()
        reported = set()
        for attrs_match in _A_TAG_RE.finditer(html_text):
            href_match = _HREF_ATTR_RE.search(attrs_match.group(1))
            if not href_match:
                continue
            href = href_match.group(2)
            target = _internal_target(href, site_url)
            if target is None or target in existing or href in reported:
                continue
            reported.add(href)
            warnings.append((html_path.name, f"Broken internal link: '{href}'"))
    return warnings
