import html as _html
import re

from magnetizer.content import resized_filename as _resized_filename
from magnetizer.render import post_display_text

_SCRIPT_TAG_RE = re.compile(r'<script\b[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL)


def _strip_scripts(html_str):
    return _SCRIPT_TAG_RE.sub('', html_str)


def _rfc3339(date_str, post_id):
    h = (post_id // 3600) % 24
    m = (post_id // 60) % 60
    s = post_id % 60
    return f"{date_str}T{h:02d}:{m:02d}:{s:02d}Z"


def render_feed(posts, config):
    site_url = config["site_url"].rstrip('/')
    site_name = _html.escape(config["site_name"])
    feed_url = f"{site_url}/feed.xml"
    dated_posts = [p for p in posts if p.date]
    most_recent_date = _rfc3339(dated_posts[0].date, dated_posts[0].id) if dated_posts else ""
    dated_posts = dated_posts[:config.get("feed_max_posts", 30)]

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f'  <title>{site_name}</title>',
        f'  <link href="{site_url}" />',
        f'  <link rel="self" href="{feed_url}" />',
        f'  <id>{site_url}/</id>',
        f'  <updated>{most_recent_date}</updated>',
        f'  <author><name>{site_name}</name></author>',
    ]

    for post in dated_posts:
        post_url = f"{site_url}/{post.url}"
        tracked_url = f"{post_url}?src=atom"
        title = _html.escape(post_display_text(post))
        images_html = ''.join(
            f'<figure><img src="{site_url}/{_resized_filename(img.filename)}"'
            f' alt="{_html.escape(img.alt, quote=True)}"></figure>'
            for img in post.images
        )
        if post.excerpt_html is not None:
            body_content = (
                f'{_strip_scripts(post.excerpt_html)}'
                f'<p><a href="{tracked_url}" class="read-more">Read more</a></p>'
            )
        else:
            body_content = _strip_scripts(post.body_html)
        lines += [
            '  <entry>',
            f'    <title>{title}</title>',
            f'    <link href="{tracked_url}" />',
            f'    <id>{post_url}</id>',
            f'    <updated>{_rfc3339(post.date, post.id)}</updated>',
            f'    <content type="html"><![CDATA[{images_html}{body_content}]]></content>',
            '  </entry>',
        ]

    lines.append('</feed>')
    return '\n'.join(lines)
