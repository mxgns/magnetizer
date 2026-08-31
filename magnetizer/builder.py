import re
import shutil
import sys
import time
from datetime import date as _date
from datetime import datetime as _datetime
from pathlib import Path

from magnetizer.config import load_config
from magnetizer.content import (
    _IMAGE_EXT_RE,
    parse_comment,
    parse_post,
    resized_filename,
    special_page_comment_pattern,
    special_page_image_pattern,
    thumbnail_filename,
)
from magnetizer.dynamic import compute_base_values, compute_word_count, expand_shortcodes, format_int, wrap_scalar
from magnetizer.image import image_dimensions, resize_image
from magnetizer.manifest import (
    get_changed_post_ids,
    get_changed_resource_filenames,
    load_manifest,
    save_manifest,
    update_page_dynamic_flag,
)
from magnetizer.render import (
    archive_display_text,
    canonical_url,
    category_page_url,
    gallery_page_url,
    index_page_url,
    notes_page_url,
    post_display_text,
    render_archive_page_content,
    render_category_page_content,
    render_gallery_page_content,
    render_index_page_content,
    render_notes_page_content,
    render_navigation,
    render_page_title,
    render_post_page_content,
    render_template,
)
from magnetizer.feed import render_feed
from magnetizer.posts_index import render_posts_index
from magnetizer.sitemap import render_sitemap, render_robots_txt
from magnetizer.validate import validate_config, validate_content, validate_project

_FLUSH_PRESERVE = {'.git', 'CNAME', '.nojekyll'}


def _error(msg):
    print(f"\033[31mERROR\033[0m: {msg}", file=sys.stderr)
    sys.exit(1)


def _check_no_invalid_posts(published_posts_sorted_desc, special_page_posts, not_found_post=None):
    for post in published_posts_sorted_desc:
        if post.post_type is None:
            _error(f"post {post.id} has no title, no images and no content — it needs at least one")
    for post in special_page_posts:
        if post.post_type is None:
            _error(f"special page '{post.id}' has no title, no images and no content — it needs at least one")
    if not_found_post is not None and not_found_post.post_type is None:
        _error(f"the 404 page '{not_found_post.id}' has no title, no images and no content — it needs at least one")


def _not_found_page_name(config):
    """The 404 page's content-file stem (e.g. "error-404" for
    404-page-input-filename: error-404.md), or None if not configured."""
    input_filename = config.get("404-page-input-filename")
    return Path(input_filename).stem if input_filename else None


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


_ORPHAN_COMMENT_PATTERN = re.compile(r'^([1-9]\d*)-comment-\d{2}\.md$')


def _comment_filenames_for_post(content_dir, post_id):
    pattern = re.compile(rf'^{post_id}-comment-\d{{2}}\.md$')
    return sorted(
        f.name for f in content_dir.iterdir() if pattern.match(f.name)
    )


def _load_comments(content_dir, filenames, site_url=""):
    return [
        parse_comment((content_dir / name).read_text(), name, site_url)
        for name in filenames
    ]


def _orphan_comment_warnings(content_dir, published_post_ids):
    warnings = []
    for f in sorted(content_dir.iterdir(), key=lambda f: f.name):
        m = _ORPHAN_COMMENT_PATTERN.match(f.name)
        if m and int(m.group(1)) not in published_post_ids:
            warnings.append(("build", f"Comment '{f.name}' has no matching post {m.group(1)}.md in content/"))
    return warnings


def _load_post(content_dir, post_id, site_url=""):
    md_path = content_dir / f"{post_id}.md"
    md_text = md_path.read_text()
    images = _image_filenames_for_post(content_dir, post_id)
    comments = _load_comments(content_dir, _comment_filenames_for_post(content_dir, post_id), site_url)
    return parse_post(md_text, post_id, images, site_url, comments=comments)


def _delete_post_files(dist_dir, post_id):
    for f in list(dist_dir.iterdir()):
        if re.match(rf'^{post_id}[-.]', f.name):
            f.unlink()


def _delete_special_page_image_files(dist_dir, name):
    pattern = re.compile(rf'^{re.escape(name)}-image-')
    for f in list(dist_dir.iterdir()):
        if pattern.match(f.name):
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
            resize_image(
                content_dir / image.filename,
                dist_dir / f"{stem}-thumb.{ext}",
                max_dimension=config["thumbnail_max_dimension"],
                quality=config["thumbnail_quality"],
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


def _warn_if_title_and_name_set(post):
    if post.title and post.name:
        return "Title and name both set"
    return None


def _warn_if_title_without_image_or_content(post):
    has_content = bool(post.body_html and post.body_html.strip())
    if post.title and not post.images and not has_content:
        return "Title but no image or content"
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


def _page_id(filename):
    return filename.rsplit('.', 1)[0]


def _write_post_html(post, dist_dir, config, template, newer_url=None, older_url=None, categories=None):
    content_html = render_post_page_content(post, newer_url=newer_url, older_url=older_url, categories=categories, ai_disclosure_html=config["ai_disclosure_html"])
    title = render_page_title(config["site_name"], post_display_text(post), page_num=None)
    filename = f"{post.id}.html"
    html = render_template(template, title=title, content=content_html,
                           canonical=canonical_url(config["site_url"], filename),
                           navigation=render_navigation(config["navigation"], filename),
                           is_noindex=post.is_noindex, page_id=_page_id(filename))
    (dist_dir / filename).write_text(html)


def _write_index_pages(posts_sorted_desc, dist_dir, config, template, categories=None):
    per_page = config["posts_per_page"]
    total = len(posts_sorted_desc)
    total_pages = max(1, (total + per_page - 1) // per_page)

    for page_num in range(1, total_pages + 1):
        slice_ = posts_sorted_desc[(page_num - 1) * per_page: page_num * per_page]
        content_html = render_index_page_content(slice_, page_num, total_pages, categories=categories, ai_disclosure_html=config["ai_disclosure_html"], images_per_post=config["images_per_post"])
        title = render_page_title(config["site_name"], None, page_num=page_num, index_title=config["index_title"])
        filename = index_page_url(page_num)
        html = render_template(template, title=title, content=content_html,
                               canonical=canonical_url(config["site_url"], filename),
                               meta_description=config["index_meta_description"],
                               navigation=render_navigation(config["navigation"], filename),
                               page_id=_page_id(filename))
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
                ai_disclosure_html=config["ai_disclosure_html"], images_per_post=config["images_per_post"]
            )
            title = render_page_title(config["site_name"], display_name, page_num=None)
            filename = category_page_url(slug, page_num)
            html = render_template(template, title=title, content=content_html,
                                   canonical=canonical_url(config["site_url"], filename),
                                   navigation=render_navigation(config["navigation"], filename),
                                   page_id=_page_id(filename))
            (dist_dir / filename).write_text(html)


def _write_notes_pages(posts_sorted_desc, dist_dir, config, template):
    note_posts = [p for p in posts_sorted_desc if p.post_type == "note"]
    if not note_posts:
        return
    per_page = config["notes_per_page"]
    total = len(note_posts)
    total_pages = max(1, (total + per_page - 1) // per_page)
    categories = config["categories"]
    for page_num in range(1, total_pages + 1):
        slice_ = note_posts[(page_num - 1) * per_page: page_num * per_page]
        content_html = render_notes_page_content(slice_, page_num, total_pages, categories=categories, ai_disclosure_html=config["ai_disclosure_html"], images_per_post=config["images_per_post"])
        title = render_page_title(config["site_name"], "Short notes", page_num=None)
        filename = notes_page_url(page_num)
        html = render_template(template, title=title, content=content_html,
                               canonical=canonical_url(config["site_url"], filename),
                               navigation=render_navigation(config["navigation"], filename),
                               page_id=_page_id(filename))
        (dist_dir / filename).write_text(html)


def _gallery_photos(posts_sorted_desc, dist_dir):
    """Every raster photo across all published posts (top-level and inline
    alike — see the Gallery page spec), newest post first, image number
    ascending within a post. Special-page images never contribute, since
    posts_sorted_desc only ever holds published posts."""
    photos = []
    for post in posts_sorted_desc:
        for image in post.images:
            if image.filename.lower().endswith('.svg'):
                continue
            thumb_name = thumbnail_filename(image.filename)
            width, height = image_dimensions(dist_dir / thumb_name)
            photos.append({
                "post_id": post.id,
                "post_url": post.url,
                "source": image.filename,
                "full": resized_filename(image.filename),
                "thumb": thumb_name,
                "alt": image.alt,
                "width": width,
                "height": height,
            })
    return photos


def _gallery_pages(photos, per_page):
    """Yield (page_num, photos_slice, total_pages) for each gallery page —
    the single source of truth for gallery pagination, shared by rendering,
    build logging, the sitemap and posts.json. Paginates strictly by photo
    count, so a post's photos can straddle a page boundary."""
    total = len(photos)
    if not total:
        return
    total_pages = max(1, (total + per_page - 1) // per_page)
    for page_num in range(1, total_pages + 1):
        yield page_num, photos[(page_num - 1) * per_page: page_num * per_page], total_pages


def _write_gallery_pages(photos, dist_dir, config, template):
    per_page = config["gallery_per_page"]
    for page_num, slice_, total_pages in _gallery_pages(photos, per_page):
        content_html = render_gallery_page_content(slice_, page_num, total_pages)
        title = render_page_title(config["site_name"], "Photo archive", page_num=None)
        filename = gallery_page_url(page_num)
        html = render_template(template, title=title, content=content_html,
                               canonical=canonical_url(config["site_url"], filename),
                               navigation=render_navigation(config["navigation"], filename),
                               page_id=_page_id(filename))
        (dist_dir / filename).write_text(html)


def _special_page_image_filenames(content_dir, name):
    pattern = special_page_image_pattern(name)
    return sorted(f.name for f in content_dir.iterdir() if pattern.match(f.name))


def _special_page_comment_filenames(content_dir, name):
    pattern = special_page_comment_pattern(name)
    return sorted(f.name for f in content_dir.iterdir() if pattern.match(f.name))


def _load_special_page_post(content_dir, name, site_url=""):
    md_text = (content_dir / f"{name}.md").read_text()
    images = _special_page_image_filenames(content_dir, name)
    comments = _load_comments(content_dir, _special_page_comment_filenames(content_dir, name), site_url)
    return parse_post(md_text, name, images, site_url, comments=comments)


def _build_special_page(name, content_dir, dist_dir, config, template, values, warn, output_filename=None):
    post = _load_special_page_post(content_dir, name, config["site_url"])
    w = _warn_if_heading_too_high(post)

    expanded_body, used_names = expand_shortcodes(post.body_html, values, f"{name}.md", warn)
    post.body_html = expanded_body
    dynamic_flag = bool(used_names)

    _delete_special_page_image_files(dist_dir, name)
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
            resize_image(
                content_dir / image.filename,
                dist_dir / f"{stem}-thumb.{ext}",
                max_dimension=config["thumbnail_max_dimension"],
                quality=config["thumbnail_quality"],
            )

    content_html = render_post_page_content(post, ai_disclosure_html=config["ai_disclosure_html"])
    title = render_page_title(config["site_name"], post_display_text(post), page_num=None)
    filename = output_filename or f"{name}.html"
    html = render_template(template, title=title, content=content_html,
                           canonical=canonical_url(config["site_url"], filename),
                           navigation=render_navigation(config["navigation"], filename),
                           is_noindex=post.is_noindex, page_id=_page_id(filename))
    (dist_dir / filename).write_text(html)
    return w, dynamic_flag


def _special_page_changed(content_dir, manifest, md_name, patterns=()):
    relevant = {md_name}
    for pattern in patterns:
        for f in content_dir.iterdir():
            if pattern.match(f.name):
                relevant.add(f.name)
        for name in manifest:
            if pattern.match(name):
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
            posts_cache[pid] = _load_post(content_dir, pid, config["site_url"])

    published_post_ids_sorted_desc = [
        pid for pid in all_post_ids_sorted_desc
        if pid in posts_cache
    ]
    published_posts_sorted_desc = [posts_cache[pid] for pid in published_post_ids_sorted_desc]

    # {{ ai_post_list }} also draws on ai_assisted special pages (e.g. an About page) —
    # every other dynamic value stays scoped to published posts only.
    special_page_posts = [
        _load_special_page_post(content_dir, name, config["site_url"])
        for name in config["special_pages"]
        if (content_dir / f"{name}.md").exists()
    ]
    special_page_posts_by_name = {p.id: p for p in special_page_posts}

    not_found_name = _not_found_page_name(config)
    not_found_post = (
        _load_special_page_post(content_dir, not_found_name, config["site_url"])
        if not_found_name else None
    )

    return (
        all_post_ids_sorted_desc, posts_cache,
        published_post_ids_sorted_desc, published_posts_sorted_desc,
        special_page_posts, special_page_posts_by_name, not_found_post,
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


def _build_requested_not_found_page(name, output_filename, content_dir, dist_dir, config, template, values, pages_dynamic_updates, warnings, log):
    def _warn_special(msg):
        warnings.append((output_filename, msg))

    w, dynamic_flag = _build_special_page(name, content_dir, dist_dir, config, template, values, _warn_special, output_filename=output_filename)
    if w:
        warnings.append((output_filename, w))
    log(("UPDATED", output_filename))
    pages_dynamic_updates[output_filename] = {"dynamic": dynamic_flag}


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
    special_page_checks = [(name, f"{name}.md") for name in config["special_pages"]]
    not_found_name = _not_found_page_name(config)
    if not_found_name:
        special_page_checks.append((not_found_name, config["404-page-input-filename"]))
    any_special_page_changed = any(
        _special_page_changed(content_dir, manifest, md_name, [special_page_image_pattern(name), special_page_comment_pattern(name)])
        for name, md_name in special_page_checks
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
                _warn_if_title_and_name_set(post),
                _warn_if_title_without_image_or_content(post),
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
                thumb_name = f"{stem}-thumb.{ext}"
                thumb_size = (dist_dir / thumb_name).stat().st_size
                log(("THUMBNAIL", thumb_name, src_sizes[image.filename], thumb_size))
        newer_url, older_url = _adjacent_post_urls(post_id, published_post_ids_sorted_desc)
        _write_post_html(post, dist_dir, config, template, newer_url=newer_url, older_url=older_url, categories=config["categories"])
        log((action, f"{post_id}.html", post.char_count, post.post_type == "note", len(post.images)))

    return created, updated, deleted


def _rebuild_stale_special_pages(config, content_dir, dist_dir, template, values, manifest, prev_pages, any_relevant_change, pages_dynamic_updates, warnings, log):
    specials_rebuilt = False
    for name in config["special_pages"]:
        page_filename = f"{name}.html"
        should_build = _special_page_changed(content_dir, manifest, f"{name}.md", [special_page_image_pattern(name), special_page_comment_pattern(name)])
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


def _rebuild_stale_not_found_page(config, content_dir, dist_dir, template, values, manifest, prev_pages, any_relevant_change, pages_dynamic_updates, warnings, log):
    name = _not_found_page_name(config)
    if not name:
        return False
    output_filename = config["404-page-output-filename"]
    should_build = _special_page_changed(content_dir, manifest, config["404-page-input-filename"], [special_page_image_pattern(name), special_page_comment_pattern(name)])
    if not should_build and any_relevant_change:
        should_build = bool(prev_pages.get(output_filename, {}).get("dynamic"))
    if not should_build:
        return False

    def _warn_special(msg, _page_filename=output_filename):
        warnings.append((_page_filename, msg))

    w, dynamic_flag = _build_special_page(name, content_dir, dist_dir, config, template, values, _warn_special, output_filename=output_filename)
    if w:
        warnings.append((output_filename, w))
    log(("UPDATED", output_filename))
    pages_dynamic_updates[output_filename] = {"dynamic": dynamic_flag}
    return True


def _write_generated_pages(published_posts_sorted_desc, dist_dir, config, template, log, build_date, photos):
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
    note_posts = [p for p in published_posts_sorted_desc if p.post_type == "note"]
    _write_notes_pages(published_posts_sorted_desc, dist_dir, config, template)
    notes_per_page = config["notes_per_page"]
    total_notes_pages = max(1, (len(note_posts) + notes_per_page - 1) // notes_per_page) if note_posts else 0
    for page_num in range(1, total_notes_pages + 1):
        log(("UPDATED", notes_page_url(page_num)))
    _write_gallery_pages(photos, dist_dir, config, template)
    for page_num, _, _ in _gallery_pages(photos, config["gallery_per_page"]):
        log(("UPDATED", gallery_page_url(page_num)))
    (dist_dir / "feed.xml").write_text(render_feed(published_posts_sorted_desc, config))
    log(("UPDATED", "feed.xml"))
    archive_html = render_template(
        template,
        title=render_page_title(config["site_name"], "Archive", page_num=None),
        content=render_archive_page_content(
            published_posts_sorted_desc, categories=config["categories"],
            build_date=build_date, posts_per_page=config["posts_per_page"],
            has_photos=bool(photos),
        ),
        canonical=canonical_url(config["site_url"], "archive.html"),
        navigation=render_navigation(config["navigation"], "archive.html"),
        page_id="archive",
    )
    (dist_dir / "archive.html").write_text(archive_html)
    log(("UPDATED", "archive.html"))


def _write_sitemap_and_robots(published_post_ids_sorted_desc, published_posts_sorted_desc, posts_cache, content_dir, dist_dir, config, special_page_posts_by_name, log, photos):
    per_page = config["posts_per_page"]
    total_pages = max(1, (len(published_post_ids_sorted_desc) + per_page - 1) // per_page)
    index_lastmod = _lastmod(
        [content_dir / f"{pid}.md" for pid in published_post_ids_sorted_desc]
        + [content_dir / c.filename for pid in published_post_ids_sorted_desc for c in posts_cache[pid].comments]
    )
    sitemap_pages = []
    for pid in published_post_ids_sorted_desc:
        if posts_cache[pid].is_noindex:
            continue
        post_files = [content_dir / f"{pid}.md"] + [
            f for f in content_dir.iterdir() if re.match(rf'^{pid}-(image|comment)-', f.name)
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
                for path in (
                    [content_dir / f"{p.id}.md"]
                    + [content_dir / img.filename for img in p.images]
                    + [content_dir / c.filename for c in p.comments]
                )
            ])
            for page_num in range(1, total_cat_pages + 1):
                sitemap_pages.append((category_page_url(slug, page_num), cat_lastmod))
    note_posts_all = [p for p in published_posts_sorted_desc if p.post_type == "note"]
    if note_posts_all:
        notes_lastmod = _lastmod(
            [content_dir / f"{p.id}.md" for p in note_posts_all]
            + [content_dir / c.filename for p in note_posts_all for c in p.comments]
        )
        notes_per_page_sitemap = config["notes_per_page"]
        total_notes_pages_sitemap = max(1, (len(note_posts_all) + notes_per_page_sitemap - 1) // notes_per_page_sitemap)
        for page_num in range(1, total_notes_pages_sitemap + 1):
            sitemap_pages.append((notes_page_url(page_num), notes_lastmod))
    for page_num, photos_slice, _ in _gallery_pages(photos, config["gallery_per_page"]):
        gallery_lastmod = _lastmod([content_dir / photo["source"] for photo in photos_slice])
        sitemap_pages.append((gallery_page_url(page_num), gallery_lastmod))
    for name in config["special_pages"]:
        if special_page_posts_by_name[name].is_noindex:
            continue
        page_files = [content_dir / f"{name}.md"] + [
            content_dir / img for img in _special_page_image_filenames(content_dir, name)
        ] + [
            content_dir / c for c in _special_page_comment_filenames(content_dir, name)
        ]
        sitemap_pages.append((f"{name}.html", _lastmod(page_files)))
    sitemap_pages.append(("archive.html", index_lastmod))
    (dist_dir / "sitemap.xml").write_text(render_sitemap(sitemap_pages, config))
    log(("UPDATED", "sitemap.xml"))
    (dist_dir / "robots.txt").write_text(render_robots_txt(config))
    log(("UPDATED", "robots.txt"))


def _write_posts_index(published_posts_sorted_desc, config, special_page_posts_by_name, not_found_post, dist_dir, log, photos):
    entries = [
        (post.id, archive_display_text(post), post.category, post.date)
        for post in published_posts_sorted_desc
    ]

    per_page = config["posts_per_page"]
    total_pages = max(1, (len(published_posts_sorted_desc) + per_page - 1) // per_page)
    index_title = config["index_title"] or config["site_name"]
    for page_num in range(1, total_pages + 1):
        title = index_title if page_num == 1 else f"{index_title} (page {page_num})"
        entries.append((_page_id(index_page_url(page_num)), title, None, None))

    categories = config["categories"]
    for slug, display_name, _, total_cat_pages in _category_pages(published_posts_sorted_desc, categories, per_page):
        for page_num in range(1, total_cat_pages + 1):
            title = display_name if page_num == 1 else f"{display_name} (page {page_num})"
            entries.append((_page_id(category_page_url(slug, page_num)), title, slug, None))

    note_posts = [p for p in published_posts_sorted_desc if p.post_type == "note"]
    if note_posts:
        notes_per_page = config["notes_per_page"]
        total_notes_pages = max(1, (len(note_posts) + notes_per_page - 1) // notes_per_page)
        for page_num in range(1, total_notes_pages + 1):
            title = "Short notes" if page_num == 1 else f"Short notes (page {page_num})"
            entries.append((_page_id(notes_page_url(page_num)), title, None, None))

    for page_num, _, _ in _gallery_pages(photos, config["gallery_per_page"]):
        title = "Photo archive" if page_num == 1 else f"Photo archive (page {page_num})"
        entries.append((_page_id(gallery_page_url(page_num)), title, None, None))

    entries.append(("archive", "Archive", None, None))

    for name in config["special_pages"]:
        post = special_page_posts_by_name[name]
        entries.append((name, post_display_text(post), None, post.date))

    not_found_name = _not_found_page_name(config)
    if not_found_name and not_found_post is not None:
        output_filename = config["404-page-output-filename"]
        entries.append((_page_id(output_filename), post_display_text(not_found_post), None, not_found_post.date))

    (dist_dir / "posts.json").write_text(render_posts_index(entries))
    log(("UPDATED", "posts.json"))


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
        special_page_posts, special_page_posts_by_name, not_found_post,
    ) = _load_content(content_dir, config)

    _check_no_invalid_posts(published_posts_sorted_desc, special_page_posts, not_found_post)
    warnings.extend(_orphan_comment_warnings(content_dir, set(published_post_ids_sorted_desc)))

    build_date = _date.today()

    # Sitewide dynamic-value computation runs unconditionally (even for a single-page
    # preview build) so that any shortcodes on the page(s) being built expand correctly.
    values = _compute_dynamic_values(published_posts_sorted_desc, special_page_posts, build_date, warnings)

    pages_dynamic_updates = {}
    deleted_page_filenames = set()

    post_ids_to_build: set[int] = set()

    not_found_name = _not_found_page_name(config)

    if filename:
        stem = Path(filename).stem
        if stem in config["special_pages"]:
            _build_requested_special_page(
                stem, content_dir, dist_dir, config, template, values,
                pages_dynamic_updates, warnings, _log,
            )
            changed_post_ids = set()
        elif not_found_name and stem == not_found_name:
            _build_requested_not_found_page(
                not_found_name, config["404-page-output-filename"], content_dir, dist_dir, config, template, values,
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
        if not_found_name and Path(filename).stem == not_found_name:
            single_page_filename = config["404-page-output-filename"]
        else:
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
        not_found_rebuilt = _rebuild_stale_not_found_page(
            config, content_dir, dist_dir, template, values, manifest, prev_pages,
            any_relevant_change, pages_dynamic_updates, warnings, _log,
        )
        specials_rebuilt = specials_rebuilt or not_found_rebuilt

    photos = None
    if not filename and post_ids_to_build:
        photos = _gallery_photos(published_posts_sorted_desc, dist_dir)
        _write_generated_pages(published_posts_sorted_desc, dist_dir, config, template, _log, build_date, photos)

    if not filename and log:
        # post_ids_to_build can be empty while log is still non-empty (e.g. a
        # stale special page rebuilt on its own) — in that case photos wasn't
        # computed above yet.
        if photos is None:
            photos = _gallery_photos(published_posts_sorted_desc, dist_dir)
        _write_sitemap_and_robots(
            published_post_ids_sorted_desc, published_posts_sorted_desc, posts_cache,
            content_dir, dist_dir, config, special_page_posts_by_name, _log, photos,
        )
        _write_posts_index(
            published_posts_sorted_desc, config, special_page_posts_by_name, not_found_post, dist_dir, _log, photos,
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
