def render_sitemap(pages, config):
    site_url = config["site_url"].rstrip('/')
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url_path, lastmod in pages:
        lines.append('  <url>')
        lines.append(f'    <loc>{site_url}/{url_path}</loc>')
        if lastmod:
            lines.append(f'    <lastmod>{lastmod}</lastmod>')
        lines.append('  </url>')
    lines.append('</urlset>')
    return '\n'.join(lines)


def render_robots_txt(config, disallowed_paths=()):
    site_url = config["site_url"].rstrip('/')
    disallow_lines = "".join(f"Disallow: /{path}\n" for path in disallowed_paths)
    return f"User-agent: *\nAllow: /\n{disallow_lines}\nSitemap: {site_url}/sitemap.xml\n"
