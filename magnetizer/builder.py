import re
import shutil
import time
from datetime import date as _date
from datetime import datetime as _datetime
from pathlib import Path

from magnetizer.config import load_config
from magnetizer.content import _IMAGE_EXT_RE, parse_post, special_page_image_pattern
from magnetizer.dynamic import compute_base_values, compute_word_count, expand_shortcodes, format_int, wrap_scalar
from magnetizer.image import resize_image
from magnetizer.manifest import (
    get_changed_post_ids,
    get_changed_resource_filenames,
    load_manifest,
    save_manifest,
    update_page_dynamic_flag,
)
from magnetizer.render import (
    canonical_url,
    category_page_url,
    index_page_url,
    microblog_page_url,
    render_archive_page_content,
    render_category_page_content,
    render_index_page_content,
    render_microblog_page_content,
    render_navigation,
    render_page_title,
    render_post_page_content,
    render_template,
)
from magnetizer.feed import render_feed
from magnetizer.sitemap import render_sitemap, render_robots_txt
from magnetizer.validate import validate_config, validate_content, validate_project

_FLUSH_PRESERVE = {'.git', 'CNAME', '.nojekyll'}


def _lastmod(paths):
    mtimes = [p.stat().st_mtime for p in paths if p.exists()]
    if not mtimes:
        return None
    return _datetime.fromtimestamp(max(mtimes)).strftime('%Y-%m-%d')


def _post_ids_in_content(content_dir):
    ids = set()
    for f in content_dir.iterdir():
        m = re.match(r'^(\d+)', f.name)
        if m:
            ids.add(int(m.group(1)))
    return ids


def _image_filenames_for_post(content_dir, post_id):
    pattern = re.compile(rf'^{post_id}-image-\d{{2}}\.({_IMAGE_EXT_RE})$')
    return sorted(
        f.name for f in content_dir.iterdir() if pattern.match(f.name)
    )


def _load_post(content_dir, post_id, micro_post_max_length=180):
    md_path = content_dir / f"{post_id}.md"
    md_text = md_path.read_text()
    images = _image_filenames_for_post(content_dir, post_id)
    return parse_post(md_text, post_id, images, micro_post_max_length)


def _delete_post_files(dist_dir, post_id):
    for f in list(dist_dir.iterdir()):
        if re.match(rf'^{post_id}[-.]', f.name):
            f.unlink()


def _build_post(post, dist_dir, content_dir, config):
    _delete_post_files(dist_dir, post.id)

    for image in post.images:
        if image.filename.lower().endswith('.svg'):
            shutil.copy2(content_dir / image.filename, dist_dir / image.filename)
        else:
            stem, _, ext = image.filename.rpartition('.')
            resize_image(
                content_dir / image.filename,
                dist_dir / f"{stem}-resized.{ext}",
                max_dimension=config["image_max_dimension"],
                quality=config["image_quality"],
            )


def _neighbor_post_ids(post_id, all_post_ids_sorted_desc):
    if post_id in all_post_ids_sorted_desc:
        pos = all_post_ids_sorted_desc.index(post_id)
        neighbors = []
        if pos > 0:
            neighbors.append(all_post_ids_sorted_desc[pos - 1])
        if pos + 1 < len(all_post_ids_sorted_desc):
            neighbors.append(all_post_ids_sorted_desc[pos + 1])
        return neighbors
    else:
        # Deleted post: find neighbors by value in the remaining list
        newer = next((p for p in all_post_ids_sorted_desc if p > post_id), None)
        older = next((p for p in reversed(all_post_ids_sorted_desc) if p < post_id), None)
        return [p for p in [newer, older] if p is not None]


def _post_index_page_url(post_id, post_ids_sorted_desc, posts_per_page):
    pos = post_ids_sorted_desc.index(post_id)
    page = pos // posts_per_page + 1
    return index_page_url(page)


def _warn_if_missing_category(post, categories):
    if categories and not post.category:
        return "No category"
    return None


def _warn_if_invalid_category(post, categories):
    if categories and post.category and post.category not in categories:
        return f"Unknown category: '{post.category}'"
    return None


def _warn_if_missing_alt_texts(post):
    if post.images and any(not img.alt for img in post.images):
        return "Missing alt text"
    return None


def _warn_if_missing_title(post):
    has_text = bool(post.body_html and post.body_html.strip())
    is_photo_only = bool(post.images) and not has_text
    if not post.is_micro and not is_photo_only and (has_text or post.images) and not post.title:
        return "No title"
    return None


_HIGH_HEADING_PATTERN = re.compile(r'<h([12])[ >]')


def _warn_if_heading_too_high(post):
    levels = sorted({int(m.group(1)) for m in _HIGH_HEADING_PATTERN.finditer(post.body_html)})
    if levels:
        tags = ", ".join(f"<h{level}>" for level in levels)
        return f"High-level headings: {tags}"
    return None


def _adjacent_post_urls(post_id, post_ids_sorted_desc):
    pos = post_ids_sorted_desc.index(post_id)
    newer_url = f"{post_ids_sorted_desc[pos - 1]}.html" if pos > 0 else None
    older_url = f"{post_ids_sorted_desc[pos + 1]}.html" if pos + 1 < len(post_ids_sorted_desc) else None
    return newer_url, older_url


def _write_post_html(post, index_page_url, dist_dir, config, template, newer_url=None, older_url=None, back_url=None, categories=None):
    content_html = render_post_page_content(post, index_page_url, newer_url=newer_url, older_url=older_url, back_url=back_url, categories=categories, ai_disclosure_html=config["ai_disclosure_html"])
    title = render_page_title(config["site_name"], post.title, page_num=None, post_id=post.id)
    filename = f"{post.id}.html"
    html = render_template(template, title=title, content=content_html,
                           canonical=canonical_url(config["site_url"], filename),
                           navigation=render_navigation(config["navigation"], filename),
                           is_noindex=post.is_noindex)
    (dist_dir / filename).write_text(html)


def _write_index_pages(posts_sorted_desc, dist_dir, config, template, categories=None):
    per_page = config["posts_per_page"]
    total = len(posts_sorted_desc)
    total_pages = max(1, (total + per_page - 1) // per_page)

    for page_num in range(1, total_pages + 1):
        slice_ = posts_sorted_desc[(page_num - 1) * per_page: page_num * per_page]
        content_html = render_index_page_content(slice_, page_num, total_pages, categories=categories, ai_disclosure_html=config["ai_disclosure_html"])
        title = render_page_title(config["site_name"], None, page_num=page_num, index_title=config["index_title"])
        filename = index_page_url(page_num)
        html = render_template(template, title=title, content=content_html,
                               canonical=canonical_url(config["site_url"], filename),
                               meta_description=config["index_meta_description"],
                               navigation=render_navigation(config["navigation"], filename))
        (dist_dir / filename).write_text(html)


def _category_pages(posts_sorted_desc, categories, per_page):
    """Yield (slug, display_name, category_posts, total_pages) for each configured
    category with at least one matching post — the single source of truth for
    category pagination, shared by rendering, build logging, and the sitemap."""
    for slug, display_name in categories.items():
        category_posts = [p for p in posts_sorted_desc if p.category == slug]
        if not category_posts:
            continue
        total_pages = max(1, (len(category_posts) + per_page - 1) // per_page)
        yield slug, display_name, category_posts, total_pages


def _write_category_pages(posts_sorted_desc, dist_dir, config, template):
    categories = config["categories"]
    if not categories:
        return
    per_page = config["posts_per_page"]
    for slug, display_name, category_posts, total_pages in _category_pages(posts_sorted_desc, categories, per_page):
        for page_num in range(1, total_pages + 1):
            slice_ = category_posts[(page_num - 1) * per_page: page_num * per_page]
            content_html = render_category_page_content(
                slice_, display_name, slug, page_num, total_pages, categories=categories,
                ai_disclosure_html=config["ai_disclosure_html"]
            )
            title = render_page_title(config["site_name"], display_name, page_num=None)
            filename = category_page_url(slug, page_num)
            html = render_template(template, title=title, content=content_html,
                                   canonical=canonical_url(config["site_url"], filename),
                                   navigation=render_navigation(config["navigation"], filename))
            (dist_dir / filename).write_text(html)


def _write_microblog_pages(posts_sorted_desc, dist_dir, config, template):
    micro_posts = [p for p in posts_sorted_desc if p.is_micro]
    if not micro_posts:
        return
    per_page = config["micro_posts_per_page"]
    total = len(micro_posts)
    total_pages = max(1, (total + per_page - 1) // per_page)
    categories = config["categories"]
    for page_num in range(1, total_pages + 1):
        slice_ = micro_posts[(page_num - 1) * per_page: page_num * per_page]
        content_html = render_microblog_page_content(slice_, page_num, total_pages, categories=categories, ai_disclosure_html=config["ai_disclosure_html"])
        title = render_page_title(config["site_name"], "Microblog", page_num=None)
        filename = microblog_page_url(page_num)
        html = render_template(template, title=title, content=content_html,
                               canonical=canonical_url(config["site_url"], filename),
                               navigation=render_navigation(config["navigation"], filename))
        (dist_dir / filename).write_text(html)


def _special_page_image_filenames(content_dir, name):
    pattern = special_page_image_pattern(name)
    return sorted(f.name for f in content_dir.iterdir() if pattern.match(f.name))


def _load_special_page_post(content_dir, name):
    md_text = (content_dir / f"{name}.md").read_text()
    images = _special_page_image_filenames(content_dir, name)
    return parse_post(md_text, name, images)


def _build_special_page(name, content_dir, dist_dir, config, template, values, warn):
    post = _load_special_page_post(content_dir, name)
    w = _warn_if_heading_too_high(post)

    expanded_body, used_names = expand_shortcodes(post.body_html, values, f"{name}.md", warn)
    post.body_html = expanded_body
    dynamic_flag = bool(used_names)

    for image in post.images:
        if image.filename.lower().endswith('.svg'):
            shutil.copy2(content_dir / image.filename, dist_dir / image.filename)
        else:
            stem, _, ext = image.filename.rpartition('.')
            resize_image(
                content_dir / image.filename,
                dist_dir / f"{stem}-resized.{ext}",
                max_dimension=config["image_max_dimension"],
                quality=config["image_quality"],
            )

    content_html = render_post_page_content(post, "index.html", back_url="index.html", ai_disclosure_html=config["ai_disclosure_html"])
    title = render_page_title(config["site_name"], post.title, page_num=None)
    filename = f"{name}.html"
    html = render_template(template, title=title, content=content_html,
                           canonical=canonical_url(config["site_url"], filename),
                           navigation=render_navigation(config["navigation"], filename),
                           is_noindex=post.is_noindex)
    (dist_dir / filename).write_text(html)
    return w, dynamic_flag


def _special_page_changed(content_dir, manifest, md_name, image_pattern=None):
    relevant = {md_name}
    if image_pattern:
        for f in content_dir.iterdir():
            if image_pattern.match(f.name):
                relevant.add(f.name)
        for name in manifest:
            if image_pattern.match(name):
                relevant.add(name)
    for name in relevant:
        f = content_dir / name
        if f.exists():
            if name not in manifest or manifest[name]["mtime"] != f.stat().st_mtime:
                return True
        elif name in manifest:
            return True
    return False


def _sync_resources(resources_dir, dist_dir, changed_filenames, replace=False):
    src = Path(resources_dir)
    dest = dist_dir / "resources"
    if replace:
        if dest.exists():
            shutil.rmtree(dest)
        if src.exists():
            shutil.copytree(src, dest)
            return sorted(f.name for f in dest.iterdir() if not f.name.startswith('.')), []
        return [], []
    if not dest.exists():
        dest.mkdir()
    copied, deleted = [], []
    for name in sorted(changed_filenames):
        src_file = src / name
        dest_file = dest / name
        if src_file.exists():
            shutil.copy2(src_file, dest_file)
            copied.append(name)
        elif dest_file.exists():
            dest_file.unlink()
            deleted.append(name)
    return copied, deleted


def _flush_dist(dist_dir, manifest_path):
    for item in dist_dir.iterdir():
        if item.name in _FLUSH_PRESERVE:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    if manifest_path.exists():
        manifest_path.unlink()


def _load_content(content_dir, config):
    all_post_ids_sorted_desc = sorted(_post_ids_in_content(content_dir), reverse=True)

    posts_cache = {}
    for pid in all_post_ids_sorted_desc:
        if (content_dir / f"{pid}.md").exists():
            posts_cache[pid] = _load_post(content_dir, pid, config["micro_post_max_length"])

    published_post_ids_sorted_desc = [
        pid for pid in all_post_ids_sorted_desc
        if pid in posts_cache and not posts_cache[pid].is_draft
    ]
    published_posts_sorted_desc = [posts_cache[pid] for pid in published_post_ids_sorted_desc]

    # {{ ai_post_list }} also draws on ai_assisted special pages (e.g. an About page) —
    # every other dynamic value stays scoped to published posts only.
    special_page_posts = [
        _load_special_page_post(content_dir, name)
        for name in config["special_pages"]
        if (content_dir / f"{name}.md").exists()
    ]
    special_page_posts_by_name = {p.id: p for p in special_page_posts}

    return (
        all_post_ids_sorted_desc, posts_cache,
        published_post_ids_sorted_desc, published_posts_sorted_desc,
        special_page_posts, special_page_posts_by_name,
    )


def _compute_dynamic_values(published_posts_sorted_desc, special_page_posts, build_date, warnings):
    base_values = compute_base_values(
        published_posts_sorted_desc, build_date,
        warn=lambda msg: warnings.append(("build", msg)),
        ai_post_list_candidates=published_posts_sorted_desc + special_page_posts,
    )
    total_words = compute_word_count(published_posts_sorted_desc, base_values)
    return {**base_values, "word_count": wrap_scalar("word_count", format_int(total_words))}


def _build_requested_special_page(stem, content_dir, dist_dir, config, template, values, pages_dynamic_updates, warnings, log):
    filename_html = f"{stem}.html"

    def _warn_special(msg):
        warnings.append((filename_html, msg))

    w, dynamic_flag = _build_special_page(stem, content_dir, dist_dir, config, template, values, _warn_special)
    if w:
        warnings.append((filename_html, w))
    log(("UPDATED", filename_html))
    pages_dynamic_updates[filename_html] = {"dynamic": dynamic_flag}


def _determine_full_build_scope(changed_post_ids, content_dir, manifest, prev_pages, config, all_post_ids_sorted_desc, published_post_ids_sorted_desc):
    neighbor_ids = {
        n
        for pid in changed_post_ids
        for n in _neighbor_post_ids(pid, published_post_ids_sorted_desc)
    }
    # Dynamic-flagged pages are only pulled in when something that could have
    # changed their computed values actually changed this build (a post or a
    # special page) — otherwise a build with zero changes anywhere would still
    # needlessly rebuild every dynamic page, every single time.
    any_special_page_changed = any(
        _special_page_changed(content_dir, manifest, f"{name}.md", special_page_image_pattern(name))
        for name in config["special_pages"]
    )
    any_relevant_change = bool(changed_post_ids) or any_special_page_changed
    if any_relevant_change:
        forced_dynamic_ids = {
            pid for pid in all_post_ids_sorted_desc
            if prev_pages.get(f"{pid}.html", {}).get("dynamic")
        }
    else:
        forced_dynamic_ids = set()
    post_ids_to_build = changed_post_ids | neighbor_ids | forced_dynamic_ids
    return post_ids_to_build, any_relevant_change


def _build_changed_posts(post_ids_to_build, changed_post_ids, posts_cache, manifest, published_post_ids_sorted_desc, content_dir, dist_dir, config, template, values, pages_dynamic_updates, deleted_page_filenames, warnings, log):
    created = updated = deleted = 0

    for post_id in post_ids_to_build:
        md_path = content_dir / f"{post_id}.md"
        if not md_path.exists():
            if post_id in changed_post_ids:
                _delete_post_files(dist_dir, post_id)
                deleted += 1
                deleted_page_filenames.add(f"{post_id}.html")
                log(("REMOVED", f"{post_id}.html"))
            continue

        action = "UPDATED" if f"{post_id}.md" in manifest else "CREATED"
        if post_id in changed_post_ids:
            if action == "UPDATED":
                updated += 1
            else:
                created += 1

        post = posts_cache[post_id]
        page_filename = f"{post_id}.html"

        def _warn_post(msg, _page_filename=page_filename):
            warnings.append((_page_filename, msg))

        expanded_body, used_names = expand_shortcodes(post.body_html, values, f"{post_id}.md", _warn_post)
        post.body_html = expanded_body
        if post.excerpt_html is not None:
            # excerpt_html is always rendered from a prefix of the same source text as
            # body_html, so any shortcode issue in it already warned once above — don't
            # warn a second time for the same occurrence.
            expanded_excerpt, _ = expand_shortcodes(post.excerpt_html, values, f"{post_id}.md", None)
            post.excerpt_html = expanded_excerpt
        pages_dynamic_updates[page_filename] = {"dynamic": bool(used_names)}

        post_warnings = [
            w for w in [
                _warn_if_missing_alt_texts(post),
                _warn_if_missing_title(post),
                _warn_if_missing_category(post, config["categories"]),
                _warn_if_invalid_category(post, config["categories"]),
                _warn_if_heading_too_high(post),
            ] if w
        ]
        for msg in post_warnings:
            warnings.append((f"{post_id}.html", msg))
        src_sizes = {img.filename: (content_dir / img.filename).stat().st_size for img in post.images}
        _build_post(post, dist_dir, content_dir, config)
        for image in post.images:
            if not image.filename.lower().endswith('.svg'):
                stem, _, ext = image.filename.rpartition('.')
                resized_name = f"{stem}-resized.{ext}"
                dest_size = (dist_dir / resized_name).stat().st_size
                log(("RESIZED", resized_name, src_sizes[image.filename], dest_size))
        if post.is_draft:
            newer_url, older_url = None, None
            idx_url = "index.html"
            back_url = "index.html"
        else:
            newer_url, older_url = _adjacent_post_urls(post_id, published_post_ids_sorted_desc)
            idx_url = _post_index_page_url(post_id, published_post_ids_sorted_desc, config["posts_per_page"])
            back_url = None
        _write_post_html(post, idx_url, dist_dir, config, template, newer_url=newer_url, older_url=older_url, back_url=back_url, categories=config["categories"])
        log((action, f"{post_id}.html", post.char_count, post.is_micro, len(post.images), post.is_draft))

    return created, updated, deleted


def _rebuild_stale_special_pages(config, content_dir, dist_dir, template, values, manifest, prev_pages, any_relevant_change, pages_dynamic_updates, warnings, log):
    specials_rebuilt = False
    for name in config["special_pages"]:
        page_filename = f"{name}.html"
        should_build = _special_page_changed(content_dir, manifest, f"{name}.md", special_page_image_pattern(name))
        if not should_build and any_relevant_change:
            should_build = bool(prev_pages.get(page_filename, {}).get("dynamic"))
        if should_build:
            def _warn_special(msg, _page_filename=page_filename):
                warnings.append((_page_filename, msg))

            w, dynamic_flag = _build_special_page(name, content_dir, dist_dir, config, template, values, _warn_special)
            if w:
                warnings.append((page_filename, w))
            log(("UPDATED", page_filename))
            pages_dynamic_updates[page_filename] = {"dynamic": dynamic_flag}
            specials_rebuilt = True
    return specials_rebuilt


def _write_generated_pages(published_posts_sorted_desc, dist_dir, config, template, log):
    _write_index_pages(published_posts_sorted_desc, dist_dir, config, template, categories=config["categories"])
    per_page = config["posts_per_page"]
    total_pages = max(1, (len(published_posts_sorted_desc) + per_page - 1) // per_page)
    for page_num in range(1, total_pages + 1):
        log(("UPDATED", index_page_url(page_num)))
    _write_category_pages(published_posts_sorted_desc, dist_dir, config, template)
    categories = config["categories"]
    for slug, _, _, total_cat_pages in _category_pages(published_posts_sorted_desc, categories, per_page):
        for page_num in range(1, total_cat_pages + 1):
            log(("UPDATED", category_page_url(slug, page_num)))
    micro_posts = [p for p in published_posts_sorted_desc if p.is_micro]
    _write_microblog_pages(published_posts_sorted_desc, dist_dir, config, template)
    micro_per_page = config["micro_posts_per_page"]
    total_micro_pages = max(1, (len(micro_posts) + micro_per_page - 1) // micro_per_page) if micro_posts else 0
    for page_num in range(1, total_micro_pages + 1):
        log(("UPDATED", microblog_page_url(page_num)))
    (dist_dir / "feed.xml").write_text(render_feed(published_posts_sorted_desc, config))
    log(("UPDATED", "feed.xml"))
    archive_html = render_template(
        template,
        title=render_page_title(config["site_name"], "Archive", page_num=None),
        content=render_archive_page_content(published_posts_sorted_desc, categories=config["categories"]),
        canonical=canonical_url(config["site_url"], "archive.html"),
        navigation=render_navigation(config["navigation"], "archive.html"),
    )
    (dist_dir / "archive.html").write_text(archive_html)
    log(("UPDATED", "archive.html"))


def _write_sitemap_and_robots(published_post_ids_sorted_desc, published_posts_sorted_desc, posts_cache, content_dir, dist_dir, config, special_page_posts_by_name, log):
    per_page = config["posts_per_page"]
    total_pages = max(1, (len(published_post_ids_sorted_desc) + per_page - 1) // per_page)
    index_lastmod = _lastmod([content_dir / f"{pid}.md" for pid in published_post_ids_sorted_desc])
    sitemap_pages = []
    for pid in published_post_ids_sorted_desc:
        if posts_cache[pid].is_noindex:
            continue
        post_files = [content_dir / f"{pid}.md"] + [
            f for f in content_dir.iterdir() if re.match(rf'^{pid}-image-', f.name)
        ]
        sitemap_pages.append((f"{pid}.html", _lastmod(post_files)))
    for page_num in range(1, total_pages + 1):
        sitemap_pages.append((index_page_url(page_num), index_lastmod))
    categories = config["categories"]
    if categories:
        for slug, _, cat_posts, total_cat_pages in _category_pages(published_posts_sorted_desc, categories, per_page):
            cat_lastmod = _lastmod([
                path
                for p in cat_posts
                for path in [content_dir / f"{p.id}.md"] + [content_dir / img.filename for img in p.images]
            ])
            for page_num in range(1, total_cat_pages + 1):
                sitemap_pages.append((category_page_url(slug, page_num), cat_lastmod))
    micro_posts_all = [p for p in published_posts_sorted_desc if p.is_micro]
    if micro_posts_all:
        micro_lastmod = _lastmod([content_dir / f"{p.id}.md" for p in micro_posts_all])
        micro_per_page_sitemap = config["micro_posts_per_page"]
        total_micro_pages_sitemap = max(1, (len(micro_posts_all) + micro_per_page_sitemap - 1) // micro_per_page_sitemap)
        for page_num in range(1, total_micro_pages_sitemap + 1):
            sitemap_pages.append((microblog_page_url(page_num), micro_lastmod))
    for name in config["special_pages"]:
        if special_page_posts_by_name[name].is_noindex:
            continue
        page_files = [content_dir / f"{name}.md"] + [
            content_dir / img for img in _special_page_image_filenames(content_dir, name)
        ]
        sitemap_pages.append((f"{name}.html", _lastmod(page_files)))
    sitemap_pages.append(("archive.html", index_lastmod))
    (dist_dir / "sitemap.xml").write_text(render_sitemap(sitemap_pages, config))
    log(("UPDATED", "sitemap.xml"))
    (dist_dir / "robots.txt").write_text(render_robots_txt(config))
    log(("UPDATED", "robots.txt"))


def build(cwd, filename=None, flush=False, resources=False, on_progress=None):
    cwd = Path(cwd)
    content_dir = cwd / "content"
    dist_dir = cwd / "dist"
    manifest_path = cwd / "manifest.json"

    validate_project(cwd)

    config = load_config(cwd / "config.yaml")
    validate_config(config)
    validate_content(content_dir, config)
    template = (cwd / "templates" / "index.html").read_text().replace(
        'MAGNETIZER_BUILD_ID', str(int(time.time()))
    )

    if flush:
        _flush_dist(dist_dir, manifest_path)

    manifest = load_manifest(manifest_path)
    prev_pages = manifest.get("pages", {})
    log = []
    warnings = []

    def _log(entry):
        log.append(entry)
        if on_progress:
            on_progress()

    (
        all_post_ids_sorted_desc, posts_cache,
        published_post_ids_sorted_desc, published_posts_sorted_desc,
        special_page_posts, special_page_posts_by_name,
    ) = _load_content(content_dir, config)

    # Sitewide dynamic-value computation runs unconditionally (even for a single-page
    # preview build) so that any shortcodes on the page(s) being built expand correctly.
    values = _compute_dynamic_values(published_posts_sorted_desc, special_page_posts, _date.today(), warnings)

    pages_dynamic_updates = {}
    deleted_page_filenames = set()

    post_ids_to_build: set[int] = set()

    if filename:
        stem = Path(filename).stem
        if stem in config["special_pages"]:
            _build_requested_special_page(
                stem, content_dir, dist_dir, config, template, values,
                pages_dynamic_updates, warnings, _log,
            )
            changed_post_ids = set()
        else:
            post_id = int(stem)
            changed_post_ids = {post_id}
            post_ids_to_build = {post_id}
        any_relevant_change = False
    else:
        changed_post_ids = get_changed_post_ids(content_dir, manifest)
        post_ids_to_build, any_relevant_change = _determine_full_build_scope(
            changed_post_ids, content_dir, manifest, prev_pages, config,
            all_post_ids_sorted_desc, published_post_ids_sorted_desc,
        )

    created, updated, deleted = _build_changed_posts(
        post_ids_to_build, changed_post_ids, posts_cache, manifest,
        published_post_ids_sorted_desc, content_dir, dist_dir, config, template,
        values, pages_dynamic_updates, deleted_page_filenames, warnings, _log,
    )

    if filename:
        # Single-file preview build (post or special page): patch just this one page's
        # dynamic flag into the manifest, leaving every other entry untouched.
        single_page_filename = f"{Path(filename).stem}.html"
        if single_page_filename in pages_dynamic_updates:
            update_page_dynamic_flag(
                manifest_path, manifest, single_page_filename,
                pages_dynamic_updates[single_page_filename]["dynamic"],
            )

    specials_rebuilt = False
    if not filename:
        # A single-file build only ever touches the one page requested — a special
        # page named directly as FILENAME is handled above; any other special page,
        # even one whose own file also changed, is left untouched.
        specials_rebuilt = _rebuild_stale_special_pages(
            config, content_dir, dist_dir, template, values, manifest, prev_pages,
            any_relevant_change, pages_dynamic_updates, warnings, _log,
        )

    if not filename and post_ids_to_build:
        _write_generated_pages(published_posts_sorted_desc, dist_dir, config, template, _log)

    if not filename and log:
        _write_sitemap_and_robots(
            published_post_ids_sorted_desc, published_posts_sorted_desc, posts_cache,
            content_dir, dist_dir, config, special_page_posts_by_name, _log,
        )

    resources_dir = cwd / "resources"
    changed_resource_filenames = get_changed_resource_filenames(resources_dir, manifest)
    copied, deleted_resources = _sync_resources(
        resources_dir, dist_dir, changed_resource_filenames, replace=(resources or flush)
    )
    for name in copied:
        _log(("COPIED", f"resources/{name}"))
    for name in deleted_resources:
        _log(("REMOVED", f"resources/{name}"))

    if not filename:
        any_change = bool(post_ids_to_build) or specials_rebuilt or bool(copied) or bool(deleted_resources)
        if any_change:
            final_pages = {**prev_pages, **pages_dynamic_updates}
            for page_filename in deleted_page_filenames:
                final_pages.pop(page_filename, None)
            save_manifest(content_dir, manifest_path, resources_dir=resources_dir, pages=final_pages)

    return {"created": created, "updated": updated, "deleted": deleted, "log": log, "warnings": warnings}
