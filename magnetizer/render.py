import re
from collections import Counter
from datetime import date as _date, timedelta as _timedelta
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


def notes_page_url(page_num):
    return "notes.html" if page_num == 1 else f"notes-{page_num}.html"


def gallery_page_url(page_num):
    return "gallery.html" if page_num == 1 else f"gallery-{page_num}.html"


_POST_TYPE_CLASS = {"full": "full-post", "image": "image-post", "note": "note"}


def post_display_text(post):
    """The post's title, falling back to its `name`, falling back to a
    generated label based on top-level image count (inline images excluded).
    Used for the post heading and the page meta title."""
    if post.title:
        return post.title
    if post.name:
        return post.name
    return _generated_post_label(post)


def _generated_post_label(post):
    top_level_count = len(post.images) - len(post.inline_image_filenames)
    if top_level_count == 0:
        kind = "Note"
    elif top_level_count == 1:
        kind = "Photo"
    else:
        kind = "Photos"
    return f"{kind} posted {post.date_uk}" if post.date_uk else kind


def _render_comments_section(comments):
    count = len(comments)
    heading = f'{count} comment{"s" if count != 1 else ""}'
    parts = ['<section class="comments" id="comments">', f'<h2>{heading}</h2>']
    for comment in comments:
        parts.append('<article class="comment">')
        initial = _escape(comment.author_initial, quote=True)
        parts.append(f'<div class="avatar author-{comment.author_slug}" data-initial="{initial}" aria-hidden="true"></div>')
        parts.append(f'<h4 class="author author-{comment.author_slug}">{_escape(comment.author)}</h4>')
        parts.append(f'<time datetime="{comment.date}">{comment.date_uk}</time>')
        parts.append(comment.body_html)
        parts.append('</article>')
    parts.append('</section>')
    return '\n'.join(parts)


def _link_inline_images(html_content, post):
    """Wrap each inline (in-body) image's <figure> in a link to the post,
    mirroring how top-strip images link through on index/category pages."""
    for image in post.images:
        if image.filename not in post.inline_image_filenames:
            continue
        resized = _resized_filename(image.filename)
        pattern = re.compile(r'<figure><img src="' + re.escape(resized) + r'"([^>]*)></figure>')
        html_content = pattern.sub(
            lambda m, resized=resized: f'<figure><a href="{post.url}"><img src="{resized}"{m.group(1)}></a></figure>',
            html_content,
        )
    return html_content


def render_article(post, on_index_page, categories=None, ai_disclosure_html=None, images_per_post=2):
    article_class = "multiple-posts" if on_index_page else "single-post"
    if post.post_type in _POST_TYPE_CLASS:
        article_class += f" {_POST_TYPE_CLASS[post.post_type]}"
    parts = [f'<article id="post-{post.id}" class="{article_class}">']

    top_images = [image for image in post.images if image.filename not in post.inline_image_filenames]
    images_to_show = top_images[:images_per_post] if on_index_page else top_images

    if images_to_show:
        parts.append('<div class="post-images">')
        for image in images_to_show:
            resized = _resized_filename(image.filename)
            alt = f' alt="{_escape(image.alt, quote=True)}"'
            if on_index_page:
                parts.append(f'<figure><a href="{post.url}"><img src="{resized}"{alt}></a></figure>')
            else:
                parts.append(f'<figure><img src="{resized}"{alt}></figure>')
        parts.append('</div>')

    if post.is_ai_assisted:
        parts.append(_render_ai_disclosure(ai_disclosure_html))

    heading_text = _escape(post_display_text(post))
    if on_index_page:
        parts.append(f'<h2><a href="{post.url}">{heading_text}</a></h2>')
    else:
        parts.append(f'<h1>{heading_text}</h1>')

    hidden_top = max(0, len(top_images) - images_per_post) if on_index_page else 0

    if on_index_page and post.excerpt_html is not None and post.post_type != "note":
        hidden_inline = len(post.inline_image_filenames) - len(post.excerpt_inline_image_filenames)
        hidden = hidden_top + hidden_inline
        if hidden > 0:
            read_more_label = f'Read more (+{hidden} photo{"s" if hidden != 1 else ""})'
        else:
            read_more_label = 'Read more'
        excerpt_html = _link_inline_images(post.excerpt_html, post)
        parts.append(f'<div class="post-body">{excerpt_html}<a href="{post.url}" class="read-more">{read_more_label}</a></div>')
    else:
        body_html = _link_inline_images(post.body_html, post) if on_index_page else post.body_html
        parts.append(f'<div class="post-body">{body_html}</div>')

    if on_index_page and post.excerpt_html is None and hidden_top > 0:
        label = f'{hidden_top} more photo{"s" if hidden_top != 1 else ""}'
        parts.append(f'<a href="{post.url}" class="more-photos">{label}</a>')

    if post.date:
        if on_index_page:
            date_content = f'<a href="{post.url}">{post.date_uk}</a>'
        else:
            date_content = post.date_uk
        footer_parts = [f'<time datetime="{post.date}">{date_content}</time>']
        if post.post_type == "note":
            footer_parts.append('<a href="notes.html" class="notes">Short note</a>')
        if post.category and categories and post.category in categories:
            display_name = _escape(categories[post.category])
            footer_parts.append(f'<a href="{post.category}.html" class="category">{display_name}</a>')
        if on_index_page and post.comments:
            count = len(post.comments)
            label = f'{count} comment{"s" if count != 1 else ""}'
            footer_parts.append(f'<a href="{post.url}#comments" class="comments">{label}</a>')
        parts.append(f'<footer>{"".join(footer_parts)}</footer>')

    if not on_index_page and post.comments:
        parts.append(_render_comments_section(post.comments))

    parts.append('</article>')
    return '\n'.join(parts)


def render_post_page_content(post, newer_url=None, older_url=None, categories=None, ai_disclosure_html=None):
    article = render_article(post, on_index_page=False, categories=categories, ai_disclosure_html=ai_disclosure_html)

    parts = [f'<main>\n{article}\n</main>']

    if newer_url or older_url:
        nav_items = []
        if newer_url:
            nav_items.append(f'<li class="newer"><a href="{newer_url}">Newer post</a></li>')
        if older_url:
            nav_items.append(f'<li class="older"><a href="{older_url}">Older post</a></li>')
        parts.append(f'<nav><ul>{"".join(nav_items)}</ul></nav>')

    parts.append('<nav><a href="index.html">Blog home</a></nav>')
    return '\n'.join(parts)


def render_index_page_content(posts, page_num, total_pages, categories=None, ai_disclosure_html=None, images_per_post=2):
    articles = '\n'.join(render_article(p, on_index_page=True, categories=categories, ai_disclosure_html=ai_disclosure_html, images_per_post=images_per_post) for p in posts)
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


def render_category_page_content(posts, category_name, category_slug, page_num, total_pages, categories=None, ai_disclosure_html=None, images_per_post=2):
    articles = '\n'.join(render_article(p, on_index_page=True, categories=categories, ai_disclosure_html=ai_disclosure_html, images_per_post=images_per_post) for p in posts)
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

    content += '\n<nav><a href="index.html">Blog home</a></nav>'
    return content


def render_notes_page_content(posts, page_num, total_pages, categories=None, ai_disclosure_html=None, images_per_post=2):
    articles = '\n'.join(render_article(p, on_index_page=True, categories=categories, ai_disclosure_html=ai_disclosure_html, images_per_post=images_per_post) for p in posts)
    content = f'<main>\n<h1>Short notes</h1>\n{articles}\n</main>'

    if total_pages > 1:
        nav_items = []
        if page_num > 1:
            prev_url = notes_page_url(page_num - 1)
            nav_items.append(f'<li class="newer"><a href="{prev_url}">Newer posts</a></li>')
        if page_num < total_pages:
            next_url = notes_page_url(page_num + 1)
            nav_items.append(f'<li class="older"><a href="{next_url}">Older posts</a></li>')
        content += f'\n<nav><ul>{"".join(nav_items)}</ul></nav>'

    content += '\n<nav><a href="index.html">Blog home</a></nav>'
    return content


def render_gallery_page_content(photos, page_num, total_pages):
    items = []
    for photo in photos:
        alt = _escape(photo["alt"], quote=True)
        items.append(
            f'<li class="gallery-item" data-post="{photo["post_id"]}">'
            f'<a href="{photo["post_url"]}" data-full="{photo["full"]}">'
            f'<img src="{photo["thumb"]}" alt="{alt}" width="{photo["width"]}" height="{photo["height"]}" loading="lazy">'
            f'</a></li>'
        )
    content = (
        f'<main>\n<h1>Photo archive</h1>\n'
        f'<p>These are all the photos from my blog posts.</p>\n'
        f'<ul id="gallery">\n{"".join(items)}\n</ul>\n</main>'
    )

    if total_pages > 1:
        nav_items = []
        if page_num > 1:
            prev_url = gallery_page_url(page_num - 1)
            nav_items.append(f'<li class="newer"><a href="{prev_url}">Newer photos</a></li>')
        if page_num < total_pages:
            next_url = gallery_page_url(page_num + 1)
            nav_items.append(f'<li class="older"><a href="{next_url}" class="load-more">Older photos</a></li>')
        content += f'\n<nav><ul>{"".join(nav_items)}</ul></nav>'

    content += '\n<nav><a href="index.html">Blog home</a></nav>'
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


def render_page_title(site_name, post_title, page_num, index_title=None):
    if page_num is not None:
        if page_num == 1:
            return f"{site_name} - {index_title}" if index_title else site_name
        return f"{site_name} - Page {page_num}"
    if post_title:
        return f"{post_title} - {site_name}"
    return site_name


def render_metadata(title, canonical=None, meta_description=None, is_noindex=False):
    lines = [f'<title>{_escape(title)}</title>']
    if meta_description:
        lines.append(f'<meta name="description" content="{_escape(meta_description, quote=True)}">')
    if canonical is not None:
        lines.append(f'<link rel="canonical" href="{_escape(canonical, quote=True)}">')
    if is_noindex:
        lines.append('<meta name="robots" content="noindex">')
    return '\n'.join(lines)


def render_template(template_html, title, content, canonical=None, meta_description=None, navigation='', is_noindex=False, page_id=''):
    metadata = render_metadata(title, canonical=canonical, meta_description=meta_description, is_noindex=is_noindex)
    html = template_html.replace('MAGNETIZER_METADATA', metadata)
    html = html.replace('MAGNETIZER_NAVIGATION', navigation)
    html = html.replace('MAGNETIZER_CONTENT', content)
    html = html.replace('MAGNETIZER_PAGE_ID', page_id)
    return html


def canonical_url(site_url, filename):
    base = site_url.rstrip("/")
    if filename == "index.html":
        return base + "/"
    return f"{base}/{filename}"


def archive_display_text(post):
    """The archive's title-fallback chain (title -> name -> first-paragraph
    excerpt, truncated to 40 chars at a word boundary -> generated label) as
    plain, unescaped text — for non-HTML consumers such as posts.json."""
    if post.title:
        return post.title
    if post.name:
        return post.name
    if post.body_html:
        m = re.search(r'<p\b[^>]*>(.*?)</p>', post.body_html, re.DOTALL | re.IGNORECASE)
        if m:
            text = _unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
            if text:
                if len(text) <= 40:
                    return text
                truncated = text[:40].rsplit(' ', 1)[0]
                return truncated + '…'
    return _generated_post_label(post)


def _archive_description(post):
    return _escape(archive_display_text(post))


def _archive_item_class(post):
    cls = _POST_TYPE_CLASS.get(post.post_type, "")
    if post.is_favourite:
        cls = f"{cls} favourite" if cls else "favourite"
    return cls


_CALENDAR_DAYS_PER_COLUMN = 10
_CALENDAR_COLUMNS = 37
_CALENDAR_DAYS = _CALENDAR_COLUMNS * _CALENDAR_DAYS_PER_COLUMN


def _calendar_window(build_date):
    """The 370-day window ending exactly on build_date, split into 37 columns
    of 10 days each -- so build_date is always the grid's last cell,
    regardless of which day of the week it falls on."""
    return build_date - _timedelta(days=_CALENDAR_DAYS - 1)


def _calendar_month_labels(start_date):
    labels = {}
    seen_months = set()
    for i in range(_CALENDAR_DAYS):
        d = start_date + _timedelta(days=i)
        month_key = (d.year, d.month)
        if month_key in seen_months:
            continue
        if d.day == 1 or i == 0:
            seen_months.add(month_key)
            labels[i // _CALENDAR_DAYS_PER_COLUMN] = d.strftime('%b')
    return labels


def _calendar_day_tooltip(d, day_posts):
    date_str = f"{d.day} {d.strftime('%B')}"
    posts_n = sum(1 for p in day_posts if p.post_type != "note")
    notes_n = sum(1 for p in day_posts if p.post_type == "note")
    counts = []
    if posts_n:
        counts.append(f'{posts_n} post{"" if posts_n == 1 else "s"}')
    if notes_n:
        counts.append(f'{notes_n} note{"" if notes_n == 1 else "s"}')
    return f'{date_str}: {" + ".join(counts)}'


def _posting_streak_weeks(posts, build_date):
    """The number of consecutive ISO calendar weeks, ending with build_date's
    own week, that have at least one post -- Monday-Sunday weeks, so a post
    on Monday of one week and Sunday of the next still counts as two
    consecutive weeks. If build_date's own week has no post yet, it isn't
    counted as broken (the week isn't over) -- the streak is simply measured
    from the most recent week that does have one."""
    weeks_with_posts = {
        _date.fromisoformat(p.date).isocalendar()[:2]
        for p in posts
        if p.date and _date.fromisoformat(p.date) <= build_date
    }
    cursor = build_date
    if cursor.isocalendar()[:2] not in weeks_with_posts:
        cursor -= _timedelta(days=7)
    streak = 0
    while cursor.isocalendar()[:2] in weeks_with_posts:
        streak += 1
        cursor -= _timedelta(days=7)
    return streak


def _render_contribution_calendar(posts, build_date, posts_per_page):
    start_date = _calendar_window(build_date)

    page_num_by_id = {}
    for idx, post in enumerate(posts):
        page_num_by_id[post.id] = idx // posts_per_page + 1

    posts_by_date = {}
    for post in posts:
        if not post.date:
            continue
        posts_by_date.setdefault(post.date, []).append(post)

    posts_in_window = [
        p for date_str, day_posts in posts_by_date.items()
        if start_date <= _date.fromisoformat(date_str) < start_date + _timedelta(days=_CALENDAR_DAYS)
        for p in day_posts
    ]
    post_count = sum(1 for p in posts_in_window if p.post_type != "note")
    note_count = sum(1 for p in posts_in_window if p.post_type == "note")

    month_labels = _calendar_month_labels(start_date)

    streak = _posting_streak_weeks(posts, build_date)
    summary = (
        '<p class="calendar-summary">I have posted '
        f'<strong><span class="calendar-post-count">{post_count}</span> posts</strong> and '
        f'<strong><span class="calendar-note-count">{note_count}</span> notes</strong> so far'
    )
    if streak:
        week_word = "week" if streak == 1 else "weeks"
        summary += (
            ', and have posted every week for the last '
            f'<strong>{streak} {week_word}</strong>'
        )
    summary += '.</p>'

    parts = [
        '<section class="contribution-calendar">',
        '<h2>Publishing calendar</h2>',
        summary,
        '<div class="calendar">',
        '<div class="calendar-months">',
    ]
    for col in range(_CALENDAR_COLUMNS):
        label = month_labels.get(col, '')
        parts.append(f'<span class="calendar-month">{label}</span>')
    parts.append('</div>')

    parts.append('<div class="calendar-columns">')
    for col in range(_CALENDAR_COLUMNS):
        parts.append('<div class="calendar-column">')
        for row in range(_CALENDAR_DAYS_PER_COLUMN):
            d = start_date + _timedelta(days=col * _CALENDAR_DAYS_PER_COLUMN + row)
            day_posts = posts_by_date.get(d.isoformat(), [])
            level = min(len(day_posts), 5)
            if day_posts:
                newest = max(day_posts, key=lambda p: p.id)
                url = f"{index_page_url(page_num_by_id[newest.id])}#post-{newest.id}"
                tooltip = _escape(_calendar_day_tooltip(d, day_posts), quote=True)
                parts.append(f'<a href="{url}" class="calendar-day level-{level}" data-tooltip="{tooltip}" aria-label="{tooltip}"></a>')
            else:
                parts.append(f'<span class="calendar-day level-{level}"></span>')
        parts.append('</div>')
    parts.append('</div>')
    parts.append('</div>')

    parts.append('</section>')
    return '\n'.join(parts)


def render_archive_page_content(posts, categories=None, build_date=None, posts_per_page=12, has_photos=False):
    blog_posts = [p for p in posts if p.date and p.post_type != "note"]

    months = {}
    for post in blog_posts:
        d = _date.fromisoformat(post.date)
        key = (d.year, d.month)
        months.setdefault(key, []).append(post)

    notes_count = sum(1 for p in posts if p.post_type == "note")

    parts = ['<main>', '<h1>Archive</h1>']
    parts.append(_render_contribution_calendar(posts, build_date or _date.today(), posts_per_page))

    category_block = []
    if categories:
        used_slugs = {p.category for p in posts if p.category}
        category_items = [(slug, name) for slug, name in categories.items() if slug in used_slugs]
        if category_items:
            category_counts = Counter(p.category for p in posts if p.category)
            category_items.sort(key=lambda item: category_counts.get(item[0], 0), reverse=True)
            category_block.append('<h2>Categories</h2>')
            category_block.append('<ul>')
            for slug, name in category_items:
                count = category_counts.get(slug, 0)
                category_block.append(f'<li><a href="{slug}.html">{_escape(name)}</a> ({count})</li>')
            category_block.append('</ul>')

    notes_block = []
    if notes_count:
        notes_block = [
            '<h2>Short notes</h2>',
            '<ul>',
            '<li><a href="notes.html">All short notes</a></li>',
            '</ul>',
        ]

    photos_block = []
    if has_photos:
        photos_block = [
            '<h2>Photo archive</h2>',
            '<ul>',
            '<li><a href="gallery.html">All photos</a></li>',
            '</ul>',
        ]

    has_sections = bool(category_block) or bool(notes_block) or bool(photos_block)

    if has_sections:
        parts.append('<div class="archive-columns">')
        if category_block:
            parts.append('<div class="archive-categories">')
            parts.extend(category_block)
            parts.append('</div>')
        if notes_block or photos_block:
            parts.append('<div class="archive-notes">')
            parts.extend(notes_block)
            parts.extend(photos_block)
            parts.append('</div>')
        parts.append('</div>')

    if has_sections:
        parts.append('<h2>Blog Posts</h2>')

    month_blocks = []
    for year, month in sorted(months.keys(), reverse=True):
        label = _date(year, month, 1).strftime('%B %Y')
        month_blocks.append('<section>')
        month_blocks.append(f'<h3>{label}</h3>')
        month_blocks.append('<ul>')
        for post in months[(year, month)]:
            day = str(_date.fromisoformat(post.date).day)
            item_class = _archive_item_class(post)
            month_blocks.append(f'<li class="{item_class}"><span class="day">{day}</span><a href="{post.url}">{_archive_description(post)}</a></li>')
        month_blocks.append('</ul>')
        month_blocks.append('</section>')

    if month_blocks:
        parts.append('<div class="archive-months">')
        parts.extend(month_blocks)
        parts.append('</div>')

    parts.append('</main>')
    parts.append('<nav><a href="index.html">Blog home</a></nav>')

    return '\n'.join(parts)
