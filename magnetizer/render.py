import re
from collections import Counter
from datetime import date as _date
from html import escape as _escape, unescape as _unescape

from magnetizer.content import resized_filename as _resized_filename

_DEFAULT_AI_DISCLOSURE_TEXT = 'The contents of this post have been entirely or partially created using AI.'


def _render_ai_disclosure(ai_disclosure_html):
    text = ai_disclosure_html or _DEFAULT_AI_DISCLOSURE_TEXT
    return (
        '<div class="container container-brown ai-disclosure">'
        f'<p>{text}</p>'
        '</div>'
    )


def index_page_url(page_num):
    return "index.html" if page_num == 1 else f"index-{page_num}.html"


def category_page_url(slug, page_num):
    return f"{slug}.html" if page_num == 1 else f"{slug}-{page_num}.html"


def microblog_page_url(page_num):
    return "microblog.html" if page_num == 1 else f"microblog-{page_num}.html"


def render_article(post, on_index_page, categories=None, ai_disclosure_html=None):
    article_class = "multiple-posts" if on_index_page else "single-post"
    if post.is_micro:
        article_class += " micro-post"
    if not post.title:
        aria = f' aria-label="Post {post.id} ({post.date_uk})"' if post.date_uk else f' aria-label="Post {post.id}"'
    else:
        aria = ''
    parts = [f'<article id="post-{post.id}" class="{article_class}"{aria}>']

    top_images = [image for image in post.images if image.filename not in post.inline_image_filenames]

    if top_images:
        parts.append('<div class="post-images">')
        images_to_show = top_images[:2] if on_index_page else top_images
        for image in images_to_show:
            resized = _resized_filename(image.filename)
            alt = f' alt="{_escape(image.alt, quote=True)}"'
            if on_index_page:
                parts.append(f'<figure><a href="{post.url}"><img src="{resized}"{alt}></a></figure>')
            else:
                parts.append(f'<figure><img src="{resized}"{alt}></figure>')
        parts.append('</div>')

    if post.title:
        if on_index_page:
            parts.append(f'<h2><a href="{post.url}">{_escape(post.title)}</a></h2>')
        else:
            parts.append(f'<h1>{_escape(post.title)}</h1>')

    hidden_top = max(0, len(top_images) - 2) if on_index_page else 0

    ai_banner = _render_ai_disclosure(ai_disclosure_html) if post.is_ai_assisted else ''

    if on_index_page and post.excerpt_html is not None and not post.is_micro:
        hidden_inline = len(post.inline_image_filenames) - len(post.excerpt_inline_image_filenames)
        hidden = hidden_top + hidden_inline
        if hidden > 0:
            read_more_label = f'Read more (+{hidden} photo{"s" if hidden != 1 else ""})'
        else:
            read_more_label = 'Read more'
        parts.append(f'<div class="post-body">{ai_banner}{post.excerpt_html}<a href="{post.url}" class="read-more">{read_more_label}</a></div>')
    else:
        parts.append(f'<div class="post-body">{ai_banner}{post.body_html}</div>')

    if on_index_page and post.excerpt_html is None and hidden_top > 0:
        label = f'{hidden_top} more photo{"s" if hidden_top != 1 else ""}'
        parts.append(f'<a href="{post.url}" class="more-photos">{label}</a>')

    if post.date:
        if on_index_page:
            date_content = f'<a href="{post.url}">{post.date_uk}</a>'
        else:
            date_content = post.date_uk
        footer_parts = [f'<time datetime="{post.date}">{date_content}</time>']
        if post.is_micro:
            footer_parts.append('<a href="microblog.html" class="microblog">Microblog</a>')
        if post.category and categories and post.category in categories:
            display_name = _escape(categories[post.category])
            footer_parts.append(f'<a href="{post.category}.html" class="category">{display_name}</a>')
        parts.append(f'<footer>{"".join(footer_parts)}</footer>')

    parts.append('</article>')
    return '\n'.join(parts)


def render_post_page_content(post, index_page_url, newer_url=None, older_url=None, back_url=None, categories=None, ai_disclosure_html=None):
    article = render_article(post, on_index_page=False, categories=categories, ai_disclosure_html=ai_disclosure_html)
    back_url = back_url or f"{index_page_url}#post-{post.id}"

    parts = [f'<main>\n{article}\n</main>']

    if newer_url or older_url:
        nav_items = []
        if newer_url:
            nav_items.append(f'<li class="newer"><a href="{newer_url}">Newer post</a></li>')
        if older_url:
            nav_items.append(f'<li class="older"><a href="{older_url}">Older post</a></li>')
        parts.append(f'<nav><ul>{"".join(nav_items)}</ul></nav>')

    parts.append(f'<nav><a href="{back_url}">Back to homepage</a></nav>')
    return '\n'.join(parts)


def render_index_page_content(posts, page_num, total_pages, categories=None, ai_disclosure_html=None):
    articles = '\n'.join(render_article(p, on_index_page=True, categories=categories, ai_disclosure_html=ai_disclosure_html) for p in posts)
    content = f'<main>\n{articles}\n</main>'

    if total_pages > 1:
        nav_items = []
        if page_num > 1:
            prev_url = index_page_url(page_num - 1)
            nav_items.append(f'<li class="newer"><a href="{prev_url}">Newer posts</a></li>')
        if page_num < total_pages:
            next_url = index_page_url(page_num + 1)
            nav_items.append(f'<li class="older"><a href="{next_url}">Older posts</a></li>')
        content += f'\n<nav><ul>{"".join(nav_items)}</ul></nav>'

    return content


def render_category_page_content(posts, category_name, category_slug, page_num, total_pages, categories=None, ai_disclosure_html=None):
    articles = '\n'.join(render_article(p, on_index_page=True, categories=categories, ai_disclosure_html=ai_disclosure_html) for p in posts)
    content = f'<main>\n<h1>{_escape(category_name)}</h1>\n{articles}\n</main>'

    if total_pages > 1:
        nav_items = []
        if page_num > 1:
            prev_url = category_page_url(category_slug, page_num - 1)
            nav_items.append(f'<li class="newer"><a href="{prev_url}">Newer posts</a></li>')
        if page_num < total_pages:
            next_url = category_page_url(category_slug, page_num + 1)
            nav_items.append(f'<li class="older"><a href="{next_url}">Older posts</a></li>')
        content += f'\n<nav><ul>{"".join(nav_items)}</ul></nav>'

    content += '\n<nav><a href="index.html">Back to homepage</a></nav>'
    return content


def render_microblog_page_content(posts, page_num, total_pages, categories=None, ai_disclosure_html=None):
    articles = '\n'.join(render_article(p, on_index_page=True, categories=categories, ai_disclosure_html=ai_disclosure_html) for p in posts)
    content = f'<main>\n<h1>Microblog</h1>\n{articles}\n</main>'

    if total_pages > 1:
        nav_items = []
        if page_num > 1:
            prev_url = microblog_page_url(page_num - 1)
            nav_items.append(f'<li class="newer"><a href="{prev_url}">Newer posts</a></li>')
        if page_num < total_pages:
            next_url = microblog_page_url(page_num + 1)
            nav_items.append(f'<li class="older"><a href="{next_url}">Older posts</a></li>')
        content += f'\n<nav><ul>{"".join(nav_items)}</ul></nav>'

    content += '\n<nav><a href="index.html">Back to homepage</a></nav>'
    return content


def _nav_item_class(href):
    stem = href.rsplit('.', 1)[0]
    slug = re.sub(r'[^a-z0-9]+', '-', stem.lower()).strip('-')
    return f'nav-{slug}'


def render_navigation(navigation, current_filename=None):
    if not navigation:
        return ''
    items = []
    for href, label in navigation.items():
        classes = _nav_item_class(href)
        current_attr = ''
        if href == current_filename:
            classes += ' current'
            current_attr = ' aria-current="page"'
        items.append(f'<li><a href="{_escape(href, quote=True)}" class="{classes}"{current_attr}>{_escape(label)}</a></li>')
    return f'<ul>{"".join(items)}</ul>'


def render_page_title(site_name, post_title, page_num, index_title=None, post_id=None):
    if page_num is not None:
        if page_num == 1:
            return f"{site_name} - {index_title}" if index_title else site_name
        return f"{site_name} - Page {page_num}"
    if post_title:
        return f"{post_title} - {site_name}"
    if post_id is not None:
        return f"Post {post_id} - {site_name}"
    return site_name


def render_metadata(title, canonical=None, meta_description=None, is_noindex=False):
    lines = [f'<title>{title}</title>']
    if meta_description:
        lines.append(f'<meta name="description" content="{_escape(meta_description, quote=True)}">')
    if canonical is not None:
        lines.append(f'<link rel="canonical" href="{canonical}">')
    if is_noindex:
        lines.append('<meta name="robots" content="noindex">')
    return '\n'.join(lines)


def render_template(template_html, title, content, canonical=None, meta_description=None, navigation='', is_noindex=False):
    metadata = render_metadata(title, canonical=canonical, meta_description=meta_description, is_noindex=is_noindex)
    html = template_html.replace('MAGNETIZER_METADATA', metadata)
    html = html.replace('MAGNETIZER_NAVIGATION', navigation)
    html = html.replace('MAGNETIZER_CONTENT', content)
    return html


def canonical_url(site_url, filename):
    base = site_url.rstrip("/")
    if filename == "index.html":
        return base + "/"
    return f"{base}/{filename}"


def _archive_description(post):
    if post.title:
        return _escape(post.title)
    if post.body_html:
        m = re.search(r'<p\b[^>]*>(.*?)</p>', post.body_html, re.DOTALL | re.IGNORECASE)
        if m:
            text = _unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
            if text:
                if len(text) <= 36:
                    return _escape(text)
                truncated = text[:36].rsplit(' ', 1)[0]
                return _escape(truncated) + '…'
    return 'Untitled'


def _archive_item_class(post):
    if post.is_micro:
        cls = "micro-post"
    elif post.images and post.title:
        cls = "mixed-post"
    elif post.images:
        cls = "photo-post"
    else:
        cls = "text-post"
    if post.is_favourite:
        cls += " favourite"
    return cls


def render_archive_page_content(posts, categories=None):
    blog_posts = [p for p in posts if p.date and not p.is_micro]

    months = {}
    for post in blog_posts:
        d = _date.fromisoformat(post.date)
        key = (d.year, d.month)
        months.setdefault(key, []).append(post)

    micro_count = sum(1 for p in posts if p.is_micro)

    parts = ['<main>', '<h1>Archive</h1>']
    has_sections = False

    if categories:
        used_slugs = {p.category for p in posts if p.category}
        category_items = [(slug, name) for slug, name in categories.items() if slug in used_slugs]
        if category_items:
            category_counts = Counter(p.category for p in posts if p.category)
            category_items.sort(key=lambda item: category_counts.get(item[0], 0), reverse=True)
            parts.append('<h2>Categories</h2>')
            parts.append('<ul>')
            for slug, name in category_items:
                count = category_counts.get(slug, 0)
                parts.append(f'<li><a href="{slug}.html">{_escape(name)}</a> ({count})</li>')
            parts.append('</ul>')
            has_sections = True

    if micro_count:
        parts.append('<h2>Microblog</h2>')
        parts.append('<ul>')
        parts.append('<li><a href="microblog.html">All microblog posts</a></li>')
        parts.append('</ul>')
        has_sections = True

    if has_sections:
        parts.append('<h2>Blog Posts</h2>')

    for year, month in sorted(months.keys(), reverse=True):
        label = _date(year, month, 1).strftime('%B %Y')
        parts.append('<section>')
        parts.append(f'<h2>{label}</h2>')
        parts.append('<ul>')
        for post in months[(year, month)]:
            day = str(_date.fromisoformat(post.date).day)
            item_class = _archive_item_class(post)
            parts.append(f'<li class="{item_class}"><span class="day">{day}</span><a href="{post.url}">{_archive_description(post)}</a></li>')
        parts.append('</ul>')
        parts.append('</section>')
    parts.append('</main>')
    parts.append('<nav><a href="index.html">Back to homepage</a></nav>')

    return '\n'.join(parts)
