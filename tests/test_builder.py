"""Tests for magnetizer/builder.py — build orchestration"""

import json
import re
import shutil
from pathlib import Path

import pytest
from PIL import Image as PILImage

from magnetizer.builder import build
from conftest import MINIMAL_MD, make_project


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TITLED_MD = "---\ndate: 2026-05-24\ntitle: My Post\n---\n\n# My Post\n\nContent here.\n"


def make_jpg(path, width=800, height=600):
    img = PILImage.new("RGB", (width, height), color=(100, 150, 200))
    img.save(path, "JPEG")


def make_svg(path):
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="5"/></svg>')


# ---------------------------------------------------------------------------
# Basic post generation
# ---------------------------------------------------------------------------

class TestBasicBuild:

    def test_post_html_file_created(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert (p / "dist" / "1.html").exists()

    def test_post_html_contains_post_body(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert "Hello world" in (p / "dist" / "1.html").read_text()

    def test_post_html_uses_template(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        html = (p / "dist" / "1.html").read_text()
        assert "<html>" in html
        assert "MAGNETIZER_CONTENT" not in html
        assert "MAGNETIZER_METADATA" not in html

    def test_post_html_title_is_site_name_when_no_post_title(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert "Test Blog" in (p / "dist" / "1.html").read_text()

    def test_post_html_title_is_post_title_dash_site_name(self, tmp_path):
        p = make_project(tmp_path, posts={1: TITLED_MD})
        build(p)
        assert "My Post - Test Blog" in (p / "dist" / "1.html").read_text()

    def test_multiple_posts_each_get_html_file(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p)
        assert (p / "dist" / "1.html").exists()
        assert (p / "dist" / "2.html").exists()

    def test_manifest_written_after_build(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert (p / "manifest.json").exists()

    def test_manifest_contains_content_files(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        data = json.loads((p / "manifest.json").read_text())
        assert "1.md" in data

    def test_manifest_contains_resource_files(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        data = json.loads((p / "manifest.json").read_text())
        assert "resources/style.css" in data


# ---------------------------------------------------------------------------
# Image processing
# ---------------------------------------------------------------------------

class TestImageProcessing:

    def test_resized_image_created_in_dist(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        make_jpg(p / "content" / "1-image-01.jpg", 2400, 1800)
        build(p)
        assert (p / "dist" / "1-image-01-resized.jpg").exists()

    def test_resized_image_long_edge_within_max(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config="site_url: https://example.github.io\nimage_max_dimension: 1200\nposts_per_page: 12\n")
        make_jpg(p / "content" / "1-image-01.jpg", 2400, 1800)
        build(p)
        img = PILImage.open(p / "dist" / "1-image-01-resized.jpg")
        assert max(img.size) <= 1200

    def test_multiple_resized_images_all_created(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        make_jpg(p / "content" / "1-image-01.jpg")
        make_jpg(p / "content" / "1-image-02.jpg")
        build(p)
        assert (p / "dist" / "1-image-01-resized.jpg").exists()
        assert (p / "dist" / "1-image-02-resized.jpg").exists()

    def test_post_html_references_resized_image(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        make_jpg(p / "content" / "1-image-01.jpg")
        build(p)
        html = (p / "dist" / "1.html").read_text()
        assert "1-image-01-resized.jpg" in html

    def test_svg_image_copied_to_dist(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        make_svg(p / "content" / "1-image-01.svg")
        build(p)
        assert (p / "dist" / "1-image-01.svg").exists()

    def test_svg_not_resized(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        make_svg(p / "content" / "1-image-01.svg")
        build(p)
        assert not (p / "dist" / "1-image-01-resized.svg").exists()

    def test_svg_referenced_directly_in_html(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        make_svg(p / "content" / "1-image-01.svg")
        build(p)
        html = (p / "dist" / "1.html").read_text()
        assert "1-image-01.svg" in html
        assert "resized" not in html

    def test_svg_and_jpg_together(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        make_jpg(p / "content" / "1-image-01.jpg")
        make_svg(p / "content" / "1-image-02.svg")
        build(p)
        assert (p / "dist" / "1-image-01-resized.jpg").exists()
        assert (p / "dist" / "1-image-02.svg").exists()


# ---------------------------------------------------------------------------
# Index pages
# ---------------------------------------------------------------------------

class TestIndexPages:

    def test_index_html_created(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert (p / "dist" / "index.html").exists()

    def test_index_html_contains_post(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert "Hello world" in (p / "dist" / "index.html").read_text()

    def test_index_page_title_is_site_name(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        html = (p / "dist" / "index.html").read_text()
        assert "<title>Test Blog</title>" in html

    def test_index_page_title_includes_index_title_when_configured(self, tmp_path):
        config = "site_name: Test Blog\nsite_url: https://example.github.io\nposts_per_page: 2\nindex_title: My Photos\n"
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=config)
        build(p)
        assert "<title>Test Blog - My Photos</title>" in (p / "dist" / "index.html").read_text()

    def test_index_page_2_title_not_affected_by_index_title(self, tmp_path):
        config = "site_name: Test Blog\nsite_url: https://example.github.io\nposts_per_page: 1\nindex_title: My Photos\n"
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD}, config=config)
        build(p)
        assert "<title>Test Blog - Page 2</title>" in (p / "dist" / "index-2.html").read_text()

    def test_multiple_pages_created_when_posts_exceed_per_page(self, tmp_path):
        # posts_per_page=2 in CONFIG, so 3 posts → 2 index pages
        posts = {i: MINIMAL_MD for i in range(1, 4)}
        p = make_project(tmp_path, posts=posts)
        build(p)
        assert (p / "dist" / "index.html").exists()
        assert (p / "dist" / "index-2.html").exists()

    def test_second_index_page_title_includes_page_number(self, tmp_path):
        posts = {i: MINIMAL_MD for i in range(1, 4)}
        p = make_project(tmp_path, posts=posts)
        build(p)
        html = (p / "dist" / "index-2.html").read_text()
        assert "Test Blog - Page 2" in html

    def test_posts_in_reverse_chronological_order_on_index(self, tmp_path):
        # Higher post-id = newer, should appear first
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD, 3: MINIMAL_MD})
        build(p)
        html = (p / "dist" / "index.html").read_text()
        pos3 = html.index('id="post-3"')
        pos2 = html.index('id="post-2"')
        assert pos3 < pos2

    def test_post_page_back_link_points_to_correct_index_page(self, tmp_path):
        # posts_per_page=2: post 1 is on index-2.html, posts 2+3 on index.html
        posts = {i: MINIMAL_MD for i in range(1, 4)}
        p = make_project(tmp_path, posts=posts)
        build(p)
        html = (p / "dist" / "1.html").read_text()
        assert 'href="index-2.html#post-1"' in html

    def test_post_on_first_index_page_has_correct_back_link(self, tmp_path):
        posts = {i: MINIMAL_MD for i in range(1, 4)}
        p = make_project(tmp_path, posts=posts)
        build(p)
        html = (p / "dist" / "3.html").read_text()
        assert 'href="index.html#post-3"' in html


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

class TestResources:

    def test_resources_copied_on_first_build(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert (p / "dist" / "resources" / "style.css").exists()

    def test_extra_files_in_dist_resources_are_preserved(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        (p / "dist" / "resources").mkdir()
        sentinel = p / "dist" / "resources" / "extra.css"
        sentinel.write_text("existing")
        build(p)
        assert sentinel.exists()  # files not in source resources/ are untouched

    def test_changed_resource_file_copied_on_rebuild(self, tmp_path):
        import time
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        time.sleep(0.01)
        (p / "resources" / "style.css").write_text("body { color: red; }")
        build(p)
        assert "color: red" in (p / "dist" / "resources" / "style.css").read_text()

    def test_unchanged_resource_not_updated_on_rebuild(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        mtime_after_first = (p / "dist" / "resources" / "style.css").stat().st_mtime
        build(p)
        assert (p / "dist" / "resources" / "style.css").stat().st_mtime == mtime_after_first

    def test_deleted_resource_removed_from_dist_on_rebuild(self, tmp_path):
        import time
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        (p / "resources" / "extra.css").write_text("extra {}")
        build(p)
        assert (p / "dist" / "resources" / "extra.css").exists()
        time.sleep(0.01)
        (p / "resources" / "extra.css").unlink()
        build(p)
        assert not (p / "dist" / "resources" / "extra.css").exists()

    def test_resources_replaced_with_resources_flag(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        (p / "dist" / "resources").mkdir()
        sentinel = p / "dist" / "resources" / "old.css"
        sentinel.write_text("old")
        build(p, resources=True)
        assert not sentinel.exists()
        assert (p / "dist" / "resources" / "style.css").exists()


# ---------------------------------------------------------------------------
# --flush
# ---------------------------------------------------------------------------

class TestFlush:

    def test_flush_clears_dist(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        stale = p / "dist" / "stale.html"
        stale.write_text("<html>old</html>")
        build(p, flush=True)
        assert not stale.exists()

    def test_flush_rebuilds_all_posts(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p, flush=True)
        assert (p / "dist" / "1.html").exists()
        assert (p / "dist" / "2.html").exists()

    def test_flush_deletes_manifest_before_build(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        old_manifest = p / "manifest.json"
        old_manifest.write_text(json.dumps({"old.md": {"mtime": 0.0}}))
        build(p, flush=True)
        data = json.loads(old_manifest.read_text())
        assert "old.md" not in data

    def test_flush_copies_resources(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p, flush=True)
        assert (p / "dist" / "resources" / "style.css").exists()

    def test_flush_preserves_git_directory(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        git_dir = p / "dist" / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]")
        build(p, flush=True)
        assert git_dir.exists()

    def test_flush_preserves_cname(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        cname = p / "dist" / "CNAME"
        cname.write_text("example.com")
        build(p, flush=True)
        assert cname.exists()

    def test_flush_preserves_nojekyll(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        nojekyll = p / "dist" / ".nojekyll"
        nojekyll.write_text("")
        build(p, flush=True)
        assert nojekyll.exists()


# ---------------------------------------------------------------------------
# Incremental build
# ---------------------------------------------------------------------------

class TestIncrementalBuild:

    def test_unchanged_post_html_not_regenerated(self, tmp_path):
        # Posts 1 and 3 are neighbours of post 2 and will be rebuilt to update
        # nav links; post 4 is not adjacent to post 2 and must stay untouched.
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD, 3: MINIMAL_MD, 4: MINIMAL_MD})
        build(p)
        mtime_before = (p / "dist" / "4.html").stat().st_mtime

        import time
        time.sleep(0.01)
        (p / "content" / "2.md").write_text(MINIMAL_MD)

        build(p)
        assert (p / "dist" / "4.html").stat().st_mtime == mtime_before

    def test_changed_post_html_is_regenerated(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p)
        mtime_before = (p / "dist" / "2.html").stat().st_mtime

        import time
        time.sleep(0.01)
        (p / "content" / "2.md").write_text("---\ndate: 2026-05-24\n---\n\nUpdated!\n")

        build(p)
        assert (p / "dist" / "2.html").stat().st_mtime > mtime_before

    def test_manifest_updated_after_incremental_build(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)

        import time
        time.sleep(0.01)
        (p / "content" / "1.md").write_text("---\ndate: 2026-05-24\n---\n\nUpdated!\n")
        new_mtime = (p / "content" / "1.md").stat().st_mtime

        build(p)
        data = json.loads((p / "manifest.json").read_text())
        assert data["1.md"]["mtime"] == new_mtime


# ---------------------------------------------------------------------------
# Single-file (preview) build
# ---------------------------------------------------------------------------

class TestSingleFileBuild:

    def test_single_file_produces_its_html(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p, filename="1.md")
        assert (p / "dist" / "1.html").exists()

    def test_single_file_does_not_build_other_posts(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p, filename="1.md")
        assert not (p / "dist" / "2.html").exists()

    def test_single_file_does_not_create_index_pages(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p, filename="1.md")
        assert not (p / "dist" / "index.html").exists()

    def test_single_file_does_not_write_source_mtime_entries(self, tmp_path):
        # Single-file builds still don't run the normal manifest rescan — the only
        # thing written is the "pages" dynamic-flag entry for the page just built.
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p, filename="1.md")
        manifest = json.loads((p / "manifest.json").read_text())
        assert "1.md" not in manifest
        assert manifest["pages"] == {"1.html": {"dynamic": False}}


# ---------------------------------------------------------------------------
# Build outcome
# ---------------------------------------------------------------------------

class TestBuildOutcome:

    def test_fresh_build_returns_created_count(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        result = build(p)
        assert result["created"] == 2

    def test_fresh_build_returns_zero_updated(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = build(p)
        assert result["updated"] == 0

    def test_fresh_build_returns_zero_deleted(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = build(p)
        assert result["deleted"] == 0

    def test_incremental_build_returns_updated_count(self, tmp_path):
        import time
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p)
        time.sleep(0.01)
        (p / "content" / "1.md").write_text("---\ndate: 2026-05-24\n---\n\nUpdated!\n")
        result = build(p)
        assert result["updated"] == 1

    def test_incremental_build_returns_zero_created_for_existing(self, tmp_path):
        import time
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p)
        time.sleep(0.01)
        (p / "content" / "1.md").write_text("---\ndate: 2026-05-24\n---\n\nUpdated!\n")
        result = build(p)
        assert result["created"] == 0

    def test_deleted_post_returns_deleted_count(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p)
        (p / "content" / "1.md").unlink()
        result = build(p)
        assert result["deleted"] == 1

    def test_no_changes_returns_zero_for_all(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        result = build(p)
        assert result["created"] == 0
        assert result["updated"] == 0
        assert result["deleted"] == 0


# ---------------------------------------------------------------------------
# Feed generation
# ---------------------------------------------------------------------------

class TestFeed:

    def test_feed_xml_created_on_full_build(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert (p / "dist" / "feed.xml").exists()

    def test_feed_xml_not_created_on_single_file_build(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p, filename="1.md")
        assert not (p / "dist" / "feed.xml").exists()

    def test_feed_xml_recreated_on_flush(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        (p / "dist" / "feed.xml").write_text("old content")
        build(p, flush=True)
        assert "old content" not in (p / "dist" / "feed.xml").read_text()


# ---------------------------------------------------------------------------
# Sitemap and robots.txt
# ---------------------------------------------------------------------------

class TestSitemap:

    def test_sitemap_created_on_full_build(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert (p / "dist" / "sitemap.xml").exists()

    def test_sitemap_not_created_on_single_file_build(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p, filename="1.md")
        assert not (p / "dist" / "sitemap.xml").exists()

    def test_sitemap_recreated_on_flush(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        (p / "dist" / "sitemap.xml").write_text("old content")
        build(p, flush=True)
        assert "old content" not in (p / "dist" / "sitemap.xml").read_text()

    def test_sitemap_contains_post_url(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert "1.html" in (p / "dist" / "sitemap.xml").read_text()

    def test_sitemap_contains_index_url(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert "index.html" in (p / "dist" / "sitemap.xml").read_text()

    def test_sitemap_contains_archive_url(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert "archive.html" in (p / "dist" / "sitemap.xml").read_text()

    def test_sitemap_contains_about_url_when_about_exists(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text("---\ntitle: About\n---\n\nAbout me.\n")
        build(p)
        assert "about.html" in (p / "dist" / "sitemap.xml").read_text()

    def test_sitemap_excludes_about_url_when_no_about(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert "about.html" not in (p / "dist" / "sitemap.xml").read_text()

    def test_sitemap_still_includes_about_after_content_change(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        (p / "content" / "about.md").write_text("---\ntitle: About\n---\n\nUpdated content.\n")
        build(p)
        assert "about.html" in (p / "dist" / "sitemap.xml").read_text()

    def test_sitemap_includes_cookies_url_when_configured(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        build(p)
        assert "cookies.html" in (p / "dist" / "sitemap.xml").read_text()

    def test_sitemap_contains_lastmod(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert "<lastmod>" in (p / "dist" / "sitemap.xml").read_text()

    def test_sitemap_in_log(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        assert ("UPDATED", "sitemap.xml") in build(p)["log"]

    def test_robots_txt_created_on_full_build(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert (p / "dist" / "robots.txt").exists()

    def test_robots_txt_not_created_on_single_file_build(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p, filename="1.md")
        assert not (p / "dist" / "robots.txt").exists()

    def test_robots_txt_contains_sitemap_url(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert "sitemap.xml" in (p / "dist" / "robots.txt").read_text()

    def test_robots_txt_in_log(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        assert ("UPDATED", "robots.txt") in build(p)["log"]

    def test_sitemap_contains_category_url_when_category_has_posts(self, tmp_path):
        p = make_project(tmp_path, posts={1: _CATEGORY_MD}, config=_CATEGORIES_CONFIG)
        build(p)
        assert "photography.html" in (p / "dist" / "sitemap.xml").read_text()

    def test_sitemap_excludes_category_url_when_no_matching_posts(self, tmp_path):
        p = make_project(tmp_path, posts={1: _CATEGORY_MD}, config=_CATEGORIES_CONFIG)
        build(p)
        assert "travel.html" not in (p / "dist" / "sitemap.xml").read_text()

    def test_sitemap_excludes_category_urls_when_no_categories_configured(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert "photography.html" not in (p / "dist" / "sitemap.xml").read_text()

    def test_sitemap_contains_paginated_category_url(self, tmp_path):
        p = make_project(tmp_path, posts={1: _CATEGORY_MD, 2: _CATEGORY_MD, 3: _CATEGORY_MD}, config=_CATEGORIES_CONFIG)
        build(p)
        assert "photography-2.html" in (p / "dist" / "sitemap.xml").read_text()

    def test_sitemap_category_lastmod_updated_when_post_image_changes(self, tmp_path):
        import os
        p = make_project(tmp_path, posts={1: _CATEGORY_MD}, config=_CATEGORIES_CONFIG)
        make_jpg(p / "content" / "1-image-01.jpg")
        # Pin .md to 2021-01-01 and image to an older date so first lastmod = 2021-01-01
        md_mtime = 1609459200.0   # 2021-01-01
        img_mtime_old = 1000000000.0  # 2001-09-08
        os.utime(p / "content" / "1.md", (md_mtime, md_mtime))
        os.utime(p / "content" / "1-image-01.jpg", (img_mtime_old, img_mtime_old))
        build(p)
        sitemap_before = (p / "dist" / "sitemap.xml").read_text()
        # Move image forward to 2022-01-01 — newer than .md, so category lastmod must change
        img_mtime_new = 1640995200.0  # 2022-01-01
        os.utime(p / "content" / "1-image-01.jpg", (img_mtime_new, img_mtime_new))
        build(p)
        sitemap_after = (p / "dist" / "sitemap.xml").read_text()
        assert sitemap_before != sitemap_after


# ---------------------------------------------------------------------------
# Post navigation
# ---------------------------------------------------------------------------

class TestPostNavigation:

    def test_post_has_link_to_newer_post(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p)
        assert "2.html" in (p / "dist" / "1.html").read_text()

    def test_post_has_link_to_older_post(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p)
        assert "1.html" in (p / "dist" / "2.html").read_text()

    def test_newest_post_has_no_newer_link(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p)
        assert "Newer post" not in (p / "dist" / "2.html").read_text()

    def test_oldest_post_has_no_older_link(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p)
        assert "Older post" not in (p / "dist" / "1.html").read_text()

    def test_only_post_has_no_post_navigation(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        html = (p / "dist" / "1.html").read_text()
        assert "Newer post" not in html
        assert "Older post" not in html

    def test_previous_newest_post_gets_newer_link_when_new_post_added(self, tmp_path):
        import time
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p)
        assert "Newer post" not in (p / "dist" / "2.html").read_text()
        time.sleep(0.01)
        (p / "content" / "3.md").write_text(MINIMAL_MD)
        build(p)
        assert "Newer post" in (p / "dist" / "2.html").read_text()

    def test_neighbors_get_nav_links_updated_when_post_deleted(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD, 3: MINIMAL_MD})
        build(p)
        (p / "content" / "2.md").unlink()
        build(p)
        assert "2.html" not in (p / "dist" / "1.html").read_text()
        assert "2.html" not in (p / "dist" / "3.html").read_text()

    def test_neighbor_rebuild_not_counted_in_outcome(self, tmp_path):
        import time
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p)
        time.sleep(0.01)
        (p / "content" / "3.md").write_text(MINIMAL_MD)
        result = build(p)
        assert result["created"] == 1
        assert result["updated"] == 0


# ---------------------------------------------------------------------------
# About page
# ---------------------------------------------------------------------------

ABOUT_MD = "---\ndate: 2026-05-24\ntitle: About\n---\n\nThis is the about page.\n"

_ABOUT_CONFIG = (
    "site_name: Test Blog\nsite_url: https://example.github.io\n"
    "posts_per_page: 2\nspecial_pages:\n  - about\n"
)

class TestAboutPage:

    def test_about_html_created_when_configured_and_md_exists(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        assert (p / "dist" / "about.html").exists()

    def test_build_errors_when_about_configured_but_md_missing(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        with pytest.raises(SystemExit):
            build(p)

    def test_build_errors_when_about_md_exists_but_not_configured(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        (p / "content" / "about.md").write_text(ABOUT_MD)
        with pytest.raises(SystemExit):
            build(p)

    def test_about_html_contains_body_content(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        assert "about page" in (p / "dist" / "about.html").read_text()

    def test_about_html_uses_template(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        assert "<html>" in (p / "dist" / "about.html").read_text()

    def test_about_html_title_includes_post_title_and_site_name(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        assert "About - Test Blog" in (p / "dist" / "about.html").read_text()

    def test_about_not_in_index(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        assert "about.html" not in (p / "dist" / "index.html").read_text()

    def test_about_not_in_post_navigation(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        assert "about.html" not in (p / "dist" / "1.html").read_text()
        assert "about.html" not in (p / "dist" / "2.html").read_text()

    def test_about_back_link_points_to_index(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        assert 'href="index.html"' in (p / "dist" / "about.html").read_text()

    def test_about_back_link_has_no_anchor(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        assert 'href="index.html#' not in (p / "dist" / "about.html").read_text()

    def test_single_file_build_about(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p, filename="about.md")
        assert (p / "dist" / "about.html").exists()

    def test_about_html_created_without_date(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text("---\ntitle: About\n---\n\nNo date here.\n")
        build(p)
        assert (p / "dist" / "about.html").exists()

    def test_about_without_date_has_no_footer(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text("---\ntitle: About\n---\n\nNo date here.\n")
        build(p)
        assert "<footer>" not in (p / "dist" / "about.html").read_text()

    def test_about_image_resized_and_copied(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        make_jpg(p / "content" / "about-image-01.jpg")
        build(p)
        assert (p / "dist" / "about-image-01-resized.jpg").exists()

    def test_about_svg_image_copied_not_resized(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        make_svg(p / "content" / "about-image-01.svg")
        build(p)
        assert (p / "dist" / "about-image-01.svg").exists()
        assert not (p / "dist" / "about-image-01-resized.svg").exists()

    def test_build_errors_on_second_build_when_about_md_deleted_while_configured(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        assert (p / "dist" / "about.html").exists()
        (p / "content" / "about.md").unlink()
        with pytest.raises(SystemExit):
            build(p)

    def test_single_file_build_also_errors_when_about_md_deleted_while_configured(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        (p / "content" / "about.md").unlink()
        with pytest.raises(SystemExit):
            build(p, filename="1.md")


# ---------------------------------------------------------------------------
# Cookies page
# ---------------------------------------------------------------------------

COOKIES_MD = "---\ntitle: Cookie Policy\n---\n\nThis site uses cookies.\n"

_COOKIES_CONFIG = (
    "site_name: Test Blog\nsite_url: https://example.github.io\n"
    "posts_per_page: 2\nspecial_pages:\n  - cookies\n"
)

class TestCookiesPage:

    def test_cookies_html_created_when_configured_and_md_exists(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        build(p)
        assert (p / "dist" / "cookies.html").exists()

    def test_build_errors_when_cookies_configured_but_md_missing(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        with pytest.raises(SystemExit):
            build(p)

    def test_build_errors_when_cookies_md_exists_but_not_configured(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        with pytest.raises(SystemExit):
            build(p)

    def test_cookies_html_contains_body_content(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        build(p)
        assert "uses cookies" in (p / "dist" / "cookies.html").read_text()

    def test_cookies_html_uses_template(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        build(p)
        assert "<html>" in (p / "dist" / "cookies.html").read_text()

    def test_cookies_html_title_includes_post_title_and_site_name(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        build(p)
        assert "Cookie Policy - Test Blog" in (p / "dist" / "cookies.html").read_text()

    def test_cookies_not_in_index(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        build(p)
        assert "cookies.html" not in (p / "dist" / "index.html").read_text()

    def test_cookies_not_in_post_navigation(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        build(p)
        assert "cookies.html" not in (p / "dist" / "1.html").read_text()
        assert "cookies.html" not in (p / "dist" / "2.html").read_text()

    def test_cookies_back_link_points_to_index(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        build(p)
        assert 'href="index.html"' in (p / "dist" / "cookies.html").read_text()

    def test_cookies_back_link_has_no_anchor(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        build(p)
        assert 'href="index.html#' not in (p / "dist" / "cookies.html").read_text()

    def test_single_file_build_cookies(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        build(p, filename="cookies.md")
        assert (p / "dist" / "cookies.html").exists()

    def test_single_file_build_cookies_does_not_create_index(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        build(p, filename="cookies.md")
        assert not (p / "dist" / "index.html").exists()

    def test_build_errors_on_second_build_when_cookies_md_deleted_while_configured(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        build(p)
        assert (p / "dist" / "cookies.html").exists()
        (p / "content" / "cookies.md").unlink()
        with pytest.raises(SystemExit):
            build(p)


# ---------------------------------------------------------------------------
# Heading level warnings — about and cookies pages
# ---------------------------------------------------------------------------

class TestAboutAndCookiesHeadingWarnings:

    def test_warning_for_h2_heading_in_about_body(self, tmp_path):
        md = "---\ntitle: About\n---\n\n## A heading\n\nContent.\n"
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(md)
        warnings = build(p)["warnings"]
        assert any(f == "about.html" and "heading" in msg.lower() for f, msg in warnings)

    def test_no_warning_for_h3_heading_in_about_body(self, tmp_path):
        md = "---\ntitle: About\n---\n\n### A heading\n\nContent.\n"
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(md)
        warnings = build(p)["warnings"]
        assert not any(f == "about.html" for f, msg in warnings)

    def test_warning_for_h1_heading_in_cookies_body(self, tmp_path):
        md = "---\ntitle: Cookie Policy\n---\n\n# A heading\n\nContent.\n"
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(md)
        warnings = build(p)["warnings"]
        assert any(f == "cookies.html" and "heading" in msg.lower() for f, msg in warnings)

    def test_no_warning_for_h3_heading_in_cookies_body(self, tmp_path):
        md = "---\ntitle: Cookie Policy\n---\n\n### A heading\n\nContent.\n"
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(md)
        warnings = build(p)["warnings"]
        assert not any(f == "cookies.html" for f, msg in warnings)

    def test_warning_propagated_when_about_built_by_filename(self, tmp_path):
        md = "---\ntitle: About\n---\n\n## A heading\n\nContent.\n"
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(md)
        warnings = build(p, filename="about.md")["warnings"]
        assert any(f == "about.html" and "heading" in msg.lower() for f, msg in warnings)

    def test_warning_propagated_when_cookies_built_by_filename(self, tmp_path):
        md = "---\ntitle: Cookie Policy\n---\n\n# A heading\n\nContent.\n"
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(md)
        warnings = build(p, filename="cookies.md")["warnings"]
        assert any(f == "cookies.html" and "heading" in msg.lower() for f, msg in warnings)


# ---------------------------------------------------------------------------
# Special pages — generic mechanism (not just about/cookies)
# ---------------------------------------------------------------------------

NOW_MD = "---\ntitle: Now\n---\n\nWhat I'm doing now.\n"

_NOW_CONFIG = (
    "site_name: Test Blog\nsite_url: https://example.github.io\n"
    "posts_per_page: 2\nspecial_pages:\n  - now\n"
)

_MULTI_SPECIAL_PAGES_CONFIG = (
    "site_name: Test Blog\nsite_url: https://example.github.io\n"
    "posts_per_page: 2\nspecial_pages:\n  - about\n  - cookies\n  - now\n"
)

class TestSpecialPagesGeneric:

    def test_arbitrary_special_page_name_builds(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_NOW_CONFIG)
        (p / "content" / "now.md").write_text(NOW_MD)
        build(p)
        assert (p / "dist" / "now.html").exists()
        assert "doing now" in (p / "dist" / "now.html").read_text()

    def test_multiple_special_pages_all_built_together(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_MULTI_SPECIAL_PAGES_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        (p / "content" / "now.md").write_text(NOW_MD)
        build(p)
        assert (p / "dist" / "about.html").exists()
        assert (p / "dist" / "cookies.html").exists()
        assert (p / "dist" / "now.html").exists()

    def test_build_errors_when_one_of_several_special_pages_is_missing(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_MULTI_SPECIAL_PAGES_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        # now.md deliberately missing
        with pytest.raises(SystemExit):
            build(p)

    def test_special_page_supports_images_regardless_of_name(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_NOW_CONFIG)
        (p / "content" / "now.md").write_text(NOW_MD)
        make_jpg(p / "content" / "now-image-01.jpg")
        build(p)
        assert (p / "dist" / "now-image-01-resized.jpg").exists()

    def test_category_slug_matching_configured_special_page_name_errors(self, tmp_path):
        config = (
            "site_name: Test Blog\nsite_url: https://example.github.io\n"
            "posts_per_page: 2\nspecial_pages:\n  - now\ncategories:\n  now: Now\n"
        )
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=config)
        (p / "content" / "now.md").write_text(NOW_MD)
        with pytest.raises(SystemExit):
            build(p)

    def test_single_file_build_of_unrelated_post_does_not_rebuild_unchanged_special_page(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD}, config=_NOW_CONFIG)
        (p / "content" / "now.md").write_text(NOW_MD)
        build(p)
        log = build(p, filename="1.md")["log"]
        assert ("UPDATED", "now.html") not in log


# ---------------------------------------------------------------------------
# Verbose log
# ---------------------------------------------------------------------------

class TestVerboseLog:

    def test_created_post_in_log(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        log = build(p)["log"]
        assert any(e[0] == "CREATED" and e[1] == "1.html" for e in log)

    def test_updated_post_in_log(self, tmp_path):
        import time
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        time.sleep(0.01)
        (p / "content" / "1.md").write_text("---\ndate: 2026-05-24\n---\n\nUpdated!\n")
        log = build(p)["log"]
        assert any(e[0] == "UPDATED" and e[1] == "1.html" for e in log)

    def test_post_log_entry_includes_char_count(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        log = build(p)["log"]
        entry = next(e for e in log if e[0] == "CREATED" and e[1] == "1.html")
        assert isinstance(entry[2], int) and entry[2] > 0

    def test_post_log_entry_is_note_true_for_note(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})  # "Hello world" — a Note
        log = build(p)["log"]
        entry = next(e for e in log if e[0] == "CREATED" and e[1] == "1.html")
        assert entry[3] is True

    def test_post_log_entry_is_note_false_for_regular_post(self, tmp_path):
        regular_md = "---\ndate: 2026-05-24\ntitle: My Post\n---\n\nNot a note.\n"
        p = make_project(tmp_path, posts={1: regular_md})
        log = build(p)["log"]
        entry = next(e for e in log if e[0] == "CREATED" and e[1] == "1.html")
        assert entry[3] is False

    def test_post_log_entry_image_count_zero_when_no_images(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        log = build(p)["log"]
        entry = next(e for e in log if e[0] == "CREATED" and e[1] == "1.html")
        assert entry[4] == 0

    def test_post_log_entry_image_count_matches_images(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        make_jpg(p / "content" / "1-image-01.jpg")
        make_jpg(p / "content" / "1-image-02.jpg")
        log = build(p)["log"]
        entry = next(e for e in log if e[0] == "CREATED" and e[1] == "1.html")
        assert entry[4] == 2

    def test_post_log_entry_is_draft_false_for_published_post(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        log = build(p)["log"]
        entry = next(e for e in log if e[0] == "CREATED" and e[1] == "1.html")
        assert entry[5] is False

    def test_post_log_entry_is_draft_true_for_draft_post(self, tmp_path):
        draft_md = "---\ndate: 2026-05-24\ndraft: true\n---\n\nDraft content\n"
        p = make_project(tmp_path, posts={1: draft_md})
        log = build(p)["log"]
        entry = next(e for e in log if e[0] == "CREATED" and e[1] == "1.html")
        assert entry[5] is True

    def test_removed_post_in_log(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p)
        (p / "content" / "2.md").unlink()
        assert ("REMOVED", "2.html") in build(p)["log"]

    def test_resized_image_in_log(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        make_jpg(p / "content" / "1-image-01.jpg")
        log = build(p)["log"]
        assert any(e[0] == "RESIZED" and e[1] == "1-image-01-resized.jpg" for e in log)

    def test_resized_log_entry_includes_src_and_dest_sizes(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        make_jpg(p / "content" / "1-image-01.jpg")
        log = build(p)["log"]
        entry = next(e for e in log if e[0] == "RESIZED")
        action, name, src_size, dest_size = entry
        assert isinstance(src_size, int) and src_size > 0
        assert isinstance(dest_size, int) and dest_size > 0

    def test_resized_log_src_larger_than_dest_for_large_image(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        make_jpg(p / "content" / "1-image-01.jpg", width=3000, height=2000)
        log = build(p)["log"]
        entry = next(e for e in log if e[0] == "RESIZED")
        _, _, src_size, dest_size = entry
        assert src_size > dest_size

    def test_index_page_in_log(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        assert ("UPDATED", "index.html") in build(p)["log"]

    def test_second_index_page_in_log(self, tmp_path):
        posts = {i: MINIMAL_MD for i in range(1, 4)}  # posts_per_page=2, so 2 pages
        p = make_project(tmp_path, posts=posts)
        assert ("UPDATED", "index-2.html") in build(p)["log"]

    def test_feed_in_log(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        assert ("UPDATED", "feed.xml") in build(p)["log"]

    def test_archive_in_log(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        assert ("UPDATED", "archive.html") in build(p)["log"]

    def test_resources_copied_in_log(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        assert ("COPIED", "resources/style.css") in build(p)["log"]

    def test_resources_not_in_log_when_unchanged_on_rebuild(self, tmp_path):
        import time
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        time.sleep(0.01)
        (p / "content" / "1.md").write_text("---\ndate: 2026-05-24\n---\n\nUpdated!\n")
        log = build(p)["log"]
        assert not any(entry[0] == "COPIED" and entry[1].startswith("resources/") for entry in log)

    def test_about_page_in_log_on_first_build(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        assert ("UPDATED", "about.html") in build(p)["log"]

    def test_about_page_not_in_log_when_unchanged(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        assert ("UPDATED", "about.html") not in build(p)["log"]

    def test_cookies_page_in_log_on_first_build(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        assert ("UPDATED", "cookies.html") in build(p)["log"]

    def test_cookies_page_not_in_log_when_unchanged(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        build(p)
        assert ("UPDATED", "cookies.html") not in build(p)["log"]

    def test_log_empty_when_nothing_changed(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert build(p)["log"] == []


# ---------------------------------------------------------------------------
# Build ID placeholder
# ---------------------------------------------------------------------------

BUILD_ID_TEMPLATE = (
    "<!DOCTYPE html><html><head>"
    "<link rel=\"stylesheet\" href=\"style.css?v=MAGNETIZER_BUILD_ID\">"
    "MAGNETIZER_METADATA</head>"
    "<body>MAGNETIZER_CONTENT</body></html>"
)

CANONICAL_TEMPLATE = (
    "<!DOCTYPE html><html><head>"
    "MAGNETIZER_METADATA</head>"
    "<body>MAGNETIZER_CONTENT</body></html>"
)

META_DESCRIPTION_TEMPLATE = (
    "<!DOCTYPE html><html><head>"
    "MAGNETIZER_METADATA</head>"
    "<body>MAGNETIZER_CONTENT</body></html>"
)


class TestBuildId:

    def test_build_id_placeholder_is_replaced(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        (p / "templates" / "index.html").write_text(BUILD_ID_TEMPLATE)
        build(p)
        assert "MAGNETIZER_BUILD_ID" not in (p / "dist" / "1.html").read_text()

    def test_build_id_is_numeric(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        (p / "templates" / "index.html").write_text(BUILD_ID_TEMPLATE)
        build(p)
        html = (p / "dist" / "1.html").read_text()
        import re
        m = re.search(r'style\.css\?v=(\S+)"', html)
        assert m and m.group(1).isdigit()

    def test_build_id_same_across_all_pages(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        (p / "templates" / "index.html").write_text(BUILD_ID_TEMPLATE)
        build(p)
        import re
        def get_build_id(path):
            m = re.search(r'style\.css\?v=(\d+)', path.read_text())
            return m.group(1) if m else None
        assert get_build_id(p / "dist" / "1.html") == get_build_id(p / "dist" / "index.html")


# ---------------------------------------------------------------------------
# Canonical URLs
# ---------------------------------------------------------------------------

class TestCanonicalUrls:

    def test_post_page_has_canonical_url(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        (p / "templates" / "index.html").write_text(CANONICAL_TEMPLATE)
        build(p)
        assert 'href="https://example.github.io/1.html"' in (p / "dist" / "1.html").read_text()

    def test_index_page_canonical_is_root_url(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        (p / "templates" / "index.html").write_text(CANONICAL_TEMPLATE)
        build(p)
        assert 'href="https://example.github.io/"' in (p / "dist" / "index.html").read_text()

    def test_second_index_page_canonical_includes_filename(self, tmp_path):
        posts = {i: MINIMAL_MD for i in range(1, 4)}
        p = make_project(tmp_path, posts=posts)
        (p / "templates" / "index.html").write_text(CANONICAL_TEMPLATE)
        build(p)
        assert 'href="https://example.github.io/index-2.html"' in (p / "dist" / "index-2.html").read_text()

    def test_about_page_has_canonical_url(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        (p / "templates" / "index.html").write_text(CANONICAL_TEMPLATE)
        build(p)
        assert 'href="https://example.github.io/about.html"' in (p / "dist" / "about.html").read_text()

    def test_archive_page_has_canonical_url(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        (p / "templates" / "index.html").write_text(CANONICAL_TEMPLATE)
        build(p)
        assert 'href="https://example.github.io/archive.html"' in (p / "dist" / "archive.html").read_text()

    def test_cookies_page_has_canonical_url(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_COOKIES_CONFIG)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        (p / "templates" / "index.html").write_text(CANONICAL_TEMPLATE)
        build(p)
        assert 'href="https://example.github.io/cookies.html"' in (p / "dist" / "cookies.html").read_text()


# ---------------------------------------------------------------------------
# Index meta description
# ---------------------------------------------------------------------------

class TestIndexMetaDescription:

    def test_index_page_includes_meta_description_when_configured(self, tmp_path):
        config = "site_name: Test Blog\nsite_url: https://example.github.io\nposts_per_page: 2\nindex_meta_description: A great blog.\n"
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=config)
        (p / "templates" / "index.html").write_text(META_DESCRIPTION_TEMPLATE)
        build(p)
        assert '<meta name="description" content="A great blog.">' in (p / "dist" / "index.html").read_text()

    def test_second_index_page_also_has_meta_description(self, tmp_path):
        config = "site_name: Test Blog\nsite_url: https://example.github.io\nposts_per_page: 2\nindex_meta_description: A great blog.\n"
        posts = {i: MINIMAL_MD for i in range(1, 4)}
        p = make_project(tmp_path, posts=posts, config=config)
        (p / "templates" / "index.html").write_text(META_DESCRIPTION_TEMPLATE)
        build(p)
        assert '<meta name="description" content="A great blog.">' in (p / "dist" / "index-2.html").read_text()

    def test_post_page_does_not_include_meta_description(self, tmp_path):
        config = "site_name: Test Blog\nsite_url: https://example.github.io\nposts_per_page: 2\nindex_meta_description: A great blog.\n"
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=config)
        (p / "templates" / "index.html").write_text(META_DESCRIPTION_TEMPLATE)
        build(p)
        assert '<meta name="description"' not in (p / "dist" / "1.html").read_text()

    def test_placeholder_removed_when_meta_description_not_configured(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        (p / "templates" / "index.html").write_text(META_DESCRIPTION_TEMPLATE)
        build(p)
        assert 'MAGNETIZER_METADATA' not in (p / "dist" / "index.html").read_text()


# ---------------------------------------------------------------------------
# AI-assisted disclosure banner
# ---------------------------------------------------------------------------

AI_ASSISTED_MD = "---\ndate: 2026-05-24\nai_assisted: true\n---\n\nBody text.\n"


class TestAiDisclosure:

    def test_default_text_used_when_not_configured(self, tmp_path):
        p = make_project(tmp_path, posts={1: AI_ASSISTED_MD})
        build(p)
        assert "entirely or partially created using AI" in (p / "dist" / "1.html").read_text()

    def test_configured_text_used_when_provided(self, tmp_path):
        config = (
            "site_name: Test Blog\nsite_url: https://example.github.io\n"
            'ai_disclosure_html: \'Custom text with a <a href="48.html">link</a>.\'\n'
        )
        p = make_project(tmp_path, posts={1: AI_ASSISTED_MD}, config=config)
        build(p)
        html = (p / "dist" / "1.html").read_text()
        assert 'Custom text with a <a href="48.html">link</a>.' in html
        assert "entirely or partially created using AI" not in html

    def test_no_banner_for_non_ai_assisted_post(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert "ai-disclosure" not in (p / "dist" / "1.html").read_text()

    def test_configured_text_appears_on_index_page(self, tmp_path):
        config = (
            "site_name: Test Blog\nsite_url: https://example.github.io\n"
            'ai_disclosure_html: \'Custom text with a <a href="48.html">link</a>.\'\n'
        )
        p = make_project(tmp_path, posts={1: AI_ASSISTED_MD}, config=config)
        build(p)
        html = (p / "dist" / "index.html").read_text()
        assert 'Custom text with a <a href="48.html">link</a>.' in html


# ---------------------------------------------------------------------------
# Archive page
# ---------------------------------------------------------------------------

class TestArchivePage:

    def test_archive_html_created_after_build_with_changes(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert (p / "dist" / "archive.html").exists()

    def test_archive_html_not_created_on_single_file_build(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p, filename="1.md")
        assert not (p / "dist" / "archive.html").exists()

    def test_archive_html_not_created_when_no_changes(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        (p / "dist" / "archive.html").unlink()
        build(p)  # no changes — archive should not be recreated
        assert not (p / "dist" / "archive.html").exists()

    def test_archive_contains_post_link(self, tmp_path):
        p = make_project(tmp_path, posts={1: TITLED_MD})
        build(p)
        assert "1.html" in (p / "dist" / "archive.html").read_text()

    def test_archive_title_includes_site_name(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert "<title>Archive - Test Blog</title>" in (p / "dist" / "archive.html").read_text()


# ---------------------------------------------------------------------------
# Alt text warnings
# ---------------------------------------------------------------------------

class TestAltTextWarnings:

    def test_warning_when_post_has_images_without_alt_texts(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        make_jpg(p / "content" / "1-image-01.jpg")
        warnings = build(p)["warnings"]
        assert any(f == "1.html" and "alt" in msg.lower() for f, msg in warnings)

    def test_no_warning_when_all_images_have_alt_texts(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: My Post\nimages:\n  - Alt text\n---\n\nHello\n"
        p = make_project(tmp_path, posts={1: md})
        make_jpg(p / "content" / "1-image-01.jpg")
        assert build(p)["warnings"] == []

    def test_no_warning_when_post_has_no_images(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        assert build(p)["warnings"] == []

    def test_each_alt_text_warning_appears_only_once(self, tmp_path, capsys):
        md = "---\ndate: 2026-05-24\nimage:\n  - Alt\n---\n\nHello\n"
        p = make_project(tmp_path, posts={1: md})
        make_jpg(p / "content" / "1-image-01.jpg")
        warnings = build(p)["warnings"]
        assert capsys.readouterr().out.count("unknown frontmatter key") == 1
        assert sum(1 for f, msg in warnings if "alt" in msg.lower()) == 1


# ---------------------------------------------------------------------------
# Note detection
# ---------------------------------------------------------------------------

class TestNoteDetection:

    def test_note_classification_correct_on_incremental_build(self, tmp_path):
        import time
        note_md = "---\ndate: 2026-06-01\n---\n\nA quick thought.\n"
        normal_md = "---\ndate: 2026-06-06\ntitle: Normal Post\n---\n\nContent\n"
        config = "site_name: Test Blog\nsite_url: https://example.github.io\nposts_per_page: 10\n"
        # Posts 1-4; post 1 is the Note. Changing post 4 makes the builder
        # rebuild posts 3 and 4 (changed + its neighbour) but NOT post 1, so
        # post 1 is loaded fresh for the archive without going through posts_cache.
        p = make_project(tmp_path, posts={1: note_md, 2: normal_md, 3: normal_md, 4: normal_md}, config=config)
        build(p)

        time.sleep(0.01)
        (p / "content" / "4.md").write_text("---\ndate: 2026-06-06\ntitle: Normal Post\n---\n\nUpdated\n")
        build(p)

        assert '<h2>Notes</h2>' in (p / "dist" / "archive.html").read_text()


# ---------------------------------------------------------------------------
# Post type validation — invalid posts, title/name warnings
# ---------------------------------------------------------------------------

class TestInvalidPostError:

    def test_error_when_post_has_no_title_no_image_no_content(self, tmp_path):
        md = "---\ndate: 2026-05-24\n---\n"
        p = make_project(tmp_path, posts={1: md})
        with pytest.raises(SystemExit):
            build(p)

    def test_error_message_mentions_post_id(self, tmp_path, capsys):
        md = "---\ndate: 2026-05-24\n---\n"
        p = make_project(tmp_path, posts={1: md})
        with pytest.raises(SystemExit):
            build(p)
        assert "1" in capsys.readouterr().err

    def test_no_error_when_only_title_set(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: Just a title\n---\n"
        p = make_project(tmp_path, posts={1: md})
        build(p)
        assert (p / "dist" / "1.html").exists()

    def test_no_error_when_only_image_set(self, tmp_path):
        md = "---\ndate: 2026-05-24\n---\n"
        p = make_project(tmp_path, posts={1: md})
        make_jpg(p / "content" / "1-image-01.jpg")
        build(p)
        assert (p / "dist" / "1.html").exists()

    def test_no_error_when_only_content_set(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        assert (p / "dist" / "1.html").exists()

    def test_no_error_for_empty_draft_post(self, tmp_path):
        md = "---\ndate: 2026-05-24\ndraft: true\n---\n"
        p = make_project(tmp_path, posts={1: md})
        build(p)
        assert (p / "dist" / "1.html").exists()

    def test_error_when_special_page_has_no_title_no_image_no_content(self, tmp_path):
        config = (
            "site_name: Test Blog\nsite_url: https://example.github.io\n"
            "posts_per_page: 2\nspecial_pages:\n  - about\n"
        )
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=config)
        (p / "content" / "about.md").write_text("---\ndate: 2026-05-24\n---\n")
        with pytest.raises(SystemExit):
            build(p)


class TestTitleAndNameWarnings:

    def test_warning_when_title_and_name_both_set(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: Real Title\nname: Fallback name\n---\n\nContent.\n"
        p = make_project(tmp_path, posts={1: md})
        warnings = build(p)["warnings"]
        assert any(f == "1.html" and "name" in msg.lower() for f, msg in warnings)

    def test_no_warning_when_only_title_set(self, tmp_path):
        p = make_project(tmp_path, posts={1: TITLED_MD})
        assert not any("name" in msg.lower() for _, msg in build(p)["warnings"])

    def test_no_warning_when_only_name_set(self, tmp_path):
        md = "---\ndate: 2026-05-24\nname: A quiet morning\n---\n\nContent.\n"
        p = make_project(tmp_path, posts={1: md})
        assert not any("name" in msg.lower() for _, msg in build(p)["warnings"])


class TestTitleWithoutImageOrContentWarning:

    def test_warning_when_title_set_with_no_image_or_content(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: Just a title\n---\n"
        p = make_project(tmp_path, posts={1: md})
        warnings = build(p)["warnings"]
        assert any(f == "1.html" and "title" in msg.lower() for f, msg in warnings)

    def test_no_warning_when_title_set_with_content(self, tmp_path):
        p = make_project(tmp_path, posts={1: TITLED_MD})
        assert not any("title" in msg.lower() for _, msg in build(p)["warnings"])

    def test_no_warning_when_title_set_with_image(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: Just a title\n---\n"
        p = make_project(tmp_path, posts={1: md})
        make_jpg(p / "content" / "1-image-01.jpg")
        assert not any("title" in msg.lower() for _, msg in build(p)["warnings"])

    def test_no_warning_for_long_untitled_text_post(self, tmp_path):
        # Previously warned as "No title" — now a legitimate, unbounded-length Note.
        long_body = "Word " * 50
        md = f"---\ndate: 2026-05-24\n---\n\n{long_body}\n"
        p = make_project(tmp_path, posts={1: md})
        assert not any("title" in msg.lower() for _, msg in build(p)["warnings"])

    def test_no_warning_for_untitled_post_with_image_and_text(self, tmp_path):
        # Previously warned as "mixed post without title" — now a legitimate Image post.
        long_body = "Word " * 50
        md = f"---\ndate: 2026-05-24\nimages:\n  - Alt\n---\n\n{long_body}\n"
        p = make_project(tmp_path, posts={1: md})
        make_jpg(p / "content" / "1-image-01.jpg")
        assert not any("title" in msg.lower() for _, msg in build(p)["warnings"])

    def test_no_warning_for_photo_only_post(self, tmp_path):
        md = "---\ndate: 2026-05-24\nimages:\n  - Alt\n---\n\n"
        p = make_project(tmp_path, posts={1: md})
        make_jpg(p / "content" / "1-image-01.jpg")
        assert not any("title" in msg.lower() for _, msg in build(p)["warnings"])


# ---------------------------------------------------------------------------
# Category warnings
# ---------------------------------------------------------------------------

_CATEGORIES_CONFIG = (
    "site_name: Test Blog\nsite_url: https://example.github.io\n"
    "posts_per_page: 2\ncategories:\n  photography: Photography\n  travel: Travel\n"
)
_CATEGORY_MD = "---\ndate: 2026-05-24\ntitle: My Post\ncategory: photography\n---\n\nHello world\n"
_NO_CATEGORY_MD = "---\ndate: 2026-05-24\ntitle: My Post\n---\n\nHello world\n"


class TestCategoryWarnings:

    def test_warning_when_post_missing_category_and_categories_configured(self, tmp_path):
        p = make_project(tmp_path, posts={1: _NO_CATEGORY_MD}, config=_CATEGORIES_CONFIG)
        warnings = build(p)["warnings"]
        assert any(f == "1.html" and "category" in msg.lower() for f, msg in warnings)

    def test_no_warning_when_categories_not_configured(self, tmp_path):
        p = make_project(tmp_path, posts={1: _NO_CATEGORY_MD})
        assert not any("category" in msg.lower() for _, msg in build(p)["warnings"])

    def test_no_warning_when_post_has_valid_category(self, tmp_path):
        p = make_project(tmp_path, posts={1: _CATEGORY_MD}, config=_CATEGORIES_CONFIG)
        assert not any("category" in msg.lower() for _, msg in build(p)["warnings"])

    def test_warning_when_post_has_unknown_category(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: My Post\ncategory: unknown-cat\n---\n\nHello\n"
        p = make_project(tmp_path, posts={1: md}, config=_CATEGORIES_CONFIG)
        warnings = build(p)["warnings"]
        assert any(f == "1.html" and "unknown" in msg.lower() for f, msg in warnings)

    def test_no_warning_for_unknown_category_when_no_categories_configured(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: My Post\ncategory: unknown-cat\n---\n\nHello\n"
        p = make_project(tmp_path, posts={1: md})
        assert not any("unknown" in msg.lower() for _, msg in build(p)["warnings"])


# ---------------------------------------------------------------------------
# Heading level warnings
# ---------------------------------------------------------------------------

class TestHeadingLevelWarnings:

    def test_warning_for_h1_heading_in_post_body(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: My Post\n---\n\n# A heading\n\nContent.\n"
        p = make_project(tmp_path, posts={1: md})
        warnings = build(p)["warnings"]
        assert any(f == "1.html" and "<h1>" in msg for f, msg in warnings)

    def test_warning_for_h2_heading_in_post_body(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: My Post\n---\n\n## A heading\n\nContent.\n"
        p = make_project(tmp_path, posts={1: md})
        warnings = build(p)["warnings"]
        assert any(f == "1.html" and "<h2>" in msg for f, msg in warnings)

    def test_warning_lists_both_h1_and_h2_when_both_present(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: My Post\n---\n\n# One\n\n## Two\n\nContent.\n"
        p = make_project(tmp_path, posts={1: md})
        warnings = build(p)["warnings"]
        entry = next(msg for f, msg in warnings if f == "1.html")
        assert "<h1>" in entry and "<h2>" in entry

    def test_no_warning_for_h3_heading_in_post_body(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: My Post\n---\n\n### A heading\n\nContent.\n"
        p = make_project(tmp_path, posts={1: md})
        assert not any("heading" in msg.lower() for _, msg in build(p)["warnings"])

    def test_no_warning_when_no_headings_in_post_body(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        assert not any("heading" in msg.lower() for _, msg in build(p)["warnings"])


# ---------------------------------------------------------------------------
# Category pages
# ---------------------------------------------------------------------------

class TestCategoryPages:

    def test_category_page_created_for_configured_category(self, tmp_path):
        p = make_project(tmp_path, posts={1: _CATEGORY_MD}, config=_CATEGORIES_CONFIG)
        build(p)
        assert (p / "dist" / "photography.html").exists()

    def test_all_category_pages_created(self, tmp_path):
        travel_md = "---\ndate: 2026-05-24\ntitle: Travel Post\ncategory: travel\n---\n\nContent\n"
        p = make_project(tmp_path, posts={1: _CATEGORY_MD, 2: travel_md}, config=_CATEGORIES_CONFIG)
        build(p)
        assert (p / "dist" / "photography.html").exists()
        assert (p / "dist" / "travel.html").exists()

    def test_category_page_not_created_on_single_file_build(self, tmp_path):
        p = make_project(tmp_path, posts={1: _CATEGORY_MD}, config=_CATEGORIES_CONFIG)
        build(p, filename="1.md")
        assert not (p / "dist" / "photography.html").exists()

    def test_category_page_not_created_when_no_categories_configured(self, tmp_path):
        p = make_project(tmp_path, posts={1: _CATEGORY_MD})
        build(p)
        assert not (p / "dist" / "photography.html").exists()

    def test_category_page_contains_posts_of_that_category(self, tmp_path):
        p = make_project(tmp_path, posts={1: _CATEGORY_MD}, config=_CATEGORIES_CONFIG)
        build(p)
        assert "Hello world" in (p / "dist" / "photography.html").read_text()

    def test_category_page_excludes_posts_of_other_categories(self, tmp_path):
        travel_md = "---\ndate: 2026-05-24\ntitle: Travel Post\ncategory: travel\n---\n\nTravel content\n"
        p = make_project(tmp_path, posts={1: _CATEGORY_MD, 2: travel_md}, config=_CATEGORIES_CONFIG)
        build(p)
        photography_html = (p / "dist" / "photography.html").read_text()
        assert "Travel content" not in photography_html

    def test_category_page_has_h1_with_category_name(self, tmp_path):
        p = make_project(tmp_path, posts={1: _CATEGORY_MD}, config=_CATEGORIES_CONFIG)
        build(p)
        assert "<h1>Photography</h1>" in (p / "dist" / "photography.html").read_text()

    def test_category_page_paginated_when_exceeds_posts_per_page(self, tmp_path):
        posts = {i: _CATEGORY_MD for i in range(1, 4)}  # 3 posts, per_page=2
        p = make_project(tmp_path, posts=posts, config=_CATEGORIES_CONFIG)
        build(p)
        assert (p / "dist" / "photography-2.html").exists()

    def test_category_page_includes_category_link_in_posts(self, tmp_path):
        p = make_project(tmp_path, posts={1: _CATEGORY_MD}, config=_CATEGORIES_CONFIG)
        build(p)
        assert 'class="category"' in (p / "dist" / "photography.html").read_text()

    def test_category_page_in_log(self, tmp_path):
        p = make_project(tmp_path, posts={1: _CATEGORY_MD}, config=_CATEGORIES_CONFIG)
        assert ("UPDATED", "photography.html") in build(p)["log"]

    def test_second_category_page_in_log(self, tmp_path):
        posts = {i: _CATEGORY_MD for i in range(1, 4)}  # 3 posts, per_page=2
        p = make_project(tmp_path, posts=posts, config=_CATEGORIES_CONFIG)
        assert ("UPDATED", "photography-2.html") in build(p)["log"]


# ---------------------------------------------------------------------------
# Archive categories list
# ---------------------------------------------------------------------------

class TestArchiveCategoriesList:

    def test_archive_contains_categories_heading(self, tmp_path):
        p = make_project(tmp_path, posts={1: _CATEGORY_MD}, config=_CATEGORIES_CONFIG)
        build(p)
        assert "<h2>Categories</h2>" in (p / "dist" / "archive.html").read_text()

    def test_archive_contains_category_link(self, tmp_path):
        p = make_project(tmp_path, posts={1: _CATEGORY_MD}, config=_CATEGORIES_CONFIG)
        build(p)
        assert '<a href="photography.html">Photography</a>' in (p / "dist" / "archive.html").read_text()

    def test_archive_has_no_categories_heading_without_config(self, tmp_path):
        p = make_project(tmp_path, posts={1: _NO_CATEGORY_MD})
        build(p)
        assert "<h2>Categories</h2>" not in (p / "dist" / "archive.html").read_text()


# ---------------------------------------------------------------------------
# Draft posts
# ---------------------------------------------------------------------------

_DRAFT_MD = "---\ndate: 2026-05-24\ntitle: Draft Post\ndraft: true\n---\n\nDraft content\n"


class TestDraftPosts:

    def test_draft_post_html_is_still_built(self, tmp_path):
        p = make_project(tmp_path, posts={1: _DRAFT_MD})
        build(p)
        assert (p / "dist" / "1.html").exists()

    def test_draft_post_excluded_from_index_page(self, tmp_path):
        p = make_project(tmp_path, posts={1: _DRAFT_MD})
        build(p)
        assert "Draft content" not in (p / "dist" / "index.html").read_text()

    def test_draft_post_excluded_from_category_page(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: Draft Post\ndraft: true\ncategory: photography\n---\n\nDraft content\n"
        p = make_project(tmp_path, posts={1: md}, config=_CATEGORIES_CONFIG)
        build(p)
        assert not (p / "dist" / "photography.html").exists()

    def test_draft_post_excluded_from_feed(self, tmp_path):
        p = make_project(tmp_path, posts={1: _DRAFT_MD})
        build(p)
        assert "Draft content" not in (p / "dist" / "feed.xml").read_text()

    def test_draft_post_excluded_from_sitemap(self, tmp_path):
        p = make_project(tmp_path, posts={1: _DRAFT_MD})
        build(p)
        assert "1.html" not in (p / "dist" / "sitemap.xml").read_text()

    def test_draft_post_excluded_from_archive(self, tmp_path):
        p = make_project(tmp_path, posts={1: _DRAFT_MD})
        build(p)
        assert "Draft Post" not in (p / "dist" / "archive.html").read_text()

    def test_draft_post_skipped_in_post_navigation(self, tmp_path):
        # Posts 1, 3 are published; post 2 is draft — post 3's older link must point to 1
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: _DRAFT_MD, 3: MINIMAL_MD})
        build(p)
        assert "1.html" in (p / "dist" / "3.html").read_text()
        assert "3.html" in (p / "dist" / "1.html").read_text()

    def test_non_draft_post_not_excluded(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: Published\ndraft: false\n---\n\nPublished content\n"
        p = make_project(tmp_path, posts={1: md})
        build(p)
        assert "Published content" in (p / "dist" / "index.html").read_text()

    def test_draft_post_back_link_has_no_anchor_fragment(self, tmp_path):
        p = make_project(tmp_path, posts={1: _DRAFT_MD})
        build(p)
        assert 'href="index.html#post-1"' not in (p / "dist" / "1.html").read_text()

    def test_incremental_rebuild_updates_nav_when_consecutive_draft_published(self, tmp_path):
        p = make_project(tmp_path, posts={
            1: MINIMAL_MD,
            2: _DRAFT_MD,
            3: _DRAFT_MD,
            4: MINIMAL_MD,
        })
        build(p)
        assert "4.html" in (p / "dist" / "1.html").read_text()
        (p / "content" / "3.md").write_text(
            "---\ndate: 2026-05-24\ntitle: Now Published\n---\n\nContent\n"
        )
        build(p)
        assert "3.html" in (p / "dist" / "1.html").read_text()


# ---------------------------------------------------------------------------
# Noindex posts
# ---------------------------------------------------------------------------

_NOINDEX_MD = "---\ndate: 2026-05-24\ntitle: Noindex Post\nnoindex: true\n---\n\nNoindex content\n"


class TestNoindexPosts:

    def test_noindex_post_html_is_still_built(self, tmp_path):
        p = make_project(tmp_path, posts={1: _NOINDEX_MD})
        build(p)
        assert (p / "dist" / "1.html").exists()

    def test_noindex_post_still_shown_on_index_page(self, tmp_path):
        p = make_project(tmp_path, posts={1: _NOINDEX_MD})
        build(p)
        assert "Noindex content" in (p / "dist" / "index.html").read_text()

    def test_noindex_post_still_shown_on_category_page(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: Noindex Post\nnoindex: true\ncategory: photography\n---\n\nNoindex content\n"
        p = make_project(tmp_path, posts={1: md}, config=_CATEGORIES_CONFIG)
        build(p)
        assert "Noindex content" in (p / "dist" / "photography.html").read_text()

    def test_noindex_post_still_shown_in_feed(self, tmp_path):
        p = make_project(tmp_path, posts={1: _NOINDEX_MD})
        build(p)
        assert "Noindex content" in (p / "dist" / "feed.xml").read_text()

    def test_noindex_post_still_shown_in_archive(self, tmp_path):
        p = make_project(tmp_path, posts={1: _NOINDEX_MD})
        build(p)
        assert "Noindex Post" in (p / "dist" / "archive.html").read_text()

    def test_noindex_post_excluded_from_sitemap(self, tmp_path):
        p = make_project(tmp_path, posts={1: _NOINDEX_MD})
        build(p)
        assert "1.html" not in (p / "dist" / "sitemap.xml").read_text()

    def test_noindex_post_has_robots_meta_tag(self, tmp_path):
        p = make_project(tmp_path, posts={1: _NOINDEX_MD})
        build(p)
        assert '<meta name="robots" content="noindex">' in (p / "dist" / "1.html").read_text()

    def test_noindex_not_mentioned_in_robots_txt(self, tmp_path):
        p = make_project(tmp_path, posts={1: _NOINDEX_MD})
        build(p)
        assert "Disallow" not in (p / "dist" / "robots.txt").read_text()

    def test_non_noindex_post_not_excluded_from_sitemap(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: Published\nnoindex: false\n---\n\nPublished content\n"
        p = make_project(tmp_path, posts={1: md})
        build(p)
        assert "1.html" in (p / "dist" / "sitemap.xml").read_text()

    def test_non_noindex_post_has_no_robots_meta_tag(self, tmp_path):
        md = "---\ndate: 2026-05-24\ntitle: Published\nnoindex: false\n---\n\nPublished content\n"
        p = make_project(tmp_path, posts={1: md})
        build(p)
        assert 'name="robots"' not in (p / "dist" / "1.html").read_text()

    def test_noindex_special_page_still_built(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        md = "---\ndate: 2026-05-24\ntitle: About\nnoindex: true\n---\n\nAbout content\n"
        (p / "content" / "about.md").write_text(md)
        build(p)
        assert "About content" in (p / "dist" / "about.html").read_text()

    def test_noindex_special_page_excluded_from_sitemap(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        md = "---\ndate: 2026-05-24\ntitle: About\nnoindex: true\n---\n\nAbout content\n"
        (p / "content" / "about.md").write_text(md)
        build(p)
        assert "about.html" not in (p / "dist" / "sitemap.xml").read_text()

    def test_noindex_special_page_has_robots_meta_tag(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        md = "---\ndate: 2026-05-24\ntitle: About\nnoindex: true\n---\n\nAbout content\n"
        (p / "content" / "about.md").write_text(md)
        build(p)
        assert '<meta name="robots" content="noindex">' in (p / "dist" / "about.html").read_text()

    def test_non_noindex_special_page_not_excluded_from_sitemap(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        assert "about.html" in (p / "dist" / "sitemap.xml").read_text()

    def test_non_noindex_special_page_has_no_robots_meta_tag(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        assert 'name="robots"' not in (p / "dist" / "about.html").read_text()


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------

class TestWarnings:

    def test_outcome_has_warnings_key(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        assert "warnings" in build(p)

    def test_no_warnings_for_clean_note(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        assert build(p)["warnings"] == []

    def test_missing_alt_text_produces_warning(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        make_jpg(p / "content" / "1-image-01.jpg")
        warnings = build(p)["warnings"]
        assert any(filename == "1.html" and "alt" in msg.lower() for filename, msg in warnings)

    def test_missing_category_produces_warning(self, tmp_path):
        config = (
            "site_name: Test Blog\nsite_url: https://example.github.io\n"
            "posts_per_page: 2\ncategories:\n  photo: Photography\n"
        )
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=config)
        warnings = build(p)["warnings"]
        assert any(filename == "1.html" and "category" in msg.lower() for filename, msg in warnings)

    def test_invalid_category_produces_warning(self, tmp_path):
        config = (
            "site_name: Test Blog\nsite_url: https://example.github.io\n"
            "posts_per_page: 2\ncategories:\n  photo: Photography\n"
        )
        cat_md = "---\ndate: 2026-05-24\ncategory: unknown\n---\n\nContent\n"
        p = make_project(tmp_path, posts={1: cat_md}, config=config)
        warnings = build(p)["warnings"]
        assert any(filename == "1.html" and "unknown" in msg.lower() for filename, msg in warnings)

    def test_high_level_heading_produces_warning(self, tmp_path):
        h1_md = "---\ndate: 2026-05-24\ntitle: My Post\n---\n\n# Top Level\n\nContent.\n"
        p = make_project(tmp_path, posts={1: h1_md})
        warnings = build(p)["warnings"]
        assert any(filename == "1.html" and "heading" in msg.lower() for filename, msg in warnings)

    def test_warning_is_tuple_of_filename_and_message(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        make_jpg(p / "content" / "1-image-01.jpg")
        warnings = build(p)["warnings"]
        assert len(warnings) > 0
        filename, msg = warnings[0]
        assert isinstance(filename, str)
        assert isinstance(msg, str)

    def test_multiple_warnings_for_same_post(self, tmp_path):
        # Title+name both set, and the image has no alt text — two independent warnings.
        md = "---\ndate: 2026-05-24\ntitle: My Post\nname: Fallback\n---\n\nContent\n"
        p = make_project(tmp_path, posts={1: md})
        make_jpg(p / "content" / "1-image-01.jpg")
        warnings = build(p)["warnings"]
        post_warnings = [msg for f, msg in warnings if f == "1.html"]
        assert len(post_warnings) >= 2


# ---------------------------------------------------------------------------
# Progress callback
# ---------------------------------------------------------------------------

class TestProgressCallback:

    def test_on_progress_not_required(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)  # should not raise

    def test_on_progress_called_for_each_log_entry(self, tmp_path):
        calls = []
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        outcome = build(p, on_progress=lambda: calls.append(1))
        assert len(calls) == len(outcome["log"])

    def test_on_progress_called_during_filename_build(self, tmp_path):
        calls = []
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        outcome = build(p, filename="1.md", on_progress=lambda: calls.append(1))
        assert len(calls) == len(outcome["log"])

    def test_on_progress_called_zero_times_when_no_changes(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        calls = []
        build(p, on_progress=lambda: calls.append(1))
        assert calls == []


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

_NAVIGATION_CONFIG = (
    "site_name: Test Blog\nsite_url: https://example.github.io\n"
    "posts_per_page: 2\nnavigation:\n  index.html: Home\n  archive.html: Archive\n"
)


class TestNavigation:

    def test_navigation_rendered_on_index_page(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_NAVIGATION_CONFIG)
        build(p)
        html = (p / "dist" / "index.html").read_text()
        assert '<a href="index.html" class="nav-index current" aria-current="page">Home</a>' in html
        assert '<a href="archive.html" class="nav-archive">Archive</a>' in html

    def test_navigation_rendered_on_archive_page(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_NAVIGATION_CONFIG)
        build(p)
        html = (p / "dist" / "archive.html").read_text()
        assert '<a href="archive.html" class="nav-archive current" aria-current="page">Archive</a>' in html
        assert '<a href="index.html" class="nav-index">Home</a>' in html

    def test_navigation_rendered_on_post_page_with_no_current_page(self, tmp_path):
        p = make_project(tmp_path, posts={1: TITLED_MD}, config=_NAVIGATION_CONFIG)
        build(p)
        html = (p / "dist" / "1.html").read_text()
        assert '<a href="index.html" class="nav-index">Home</a>' in html
        assert '<a href="archive.html" class="nav-archive">Archive</a>' in html
        assert 'current' not in html

    def test_navigation_rendered_on_about_page(self, tmp_path):
        config = _NAVIGATION_CONFIG + "special_pages:\n  - about\n"
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=config)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        html = (p / "dist" / "about.html").read_text()
        assert '<a href="index.html" class="nav-index">Home</a>' in html
        assert '<a href="archive.html" class="nav-archive">Archive</a>' in html
        assert 'current' not in html

    def test_navigation_rendered_on_category_page(self, tmp_path):
        config = _NAVIGATION_CONFIG + "categories:\n  photography: Photography\n"
        md = "---\ndate: 2026-05-24\ntitle: My Post\ncategory: photography\n---\n\nHello\n"
        p = make_project(tmp_path, posts={1: md}, config=config)
        build(p)
        html = (p / "dist" / "photography.html").read_text()
        assert '<a href="index.html" class="nav-index">Home</a>' in html
        assert '<a href="archive.html" class="nav-archive">Archive</a>' in html
        assert 'current' not in html

    def test_navigation_rendered_on_notes_page(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_NAVIGATION_CONFIG)
        build(p)
        html = (p / "dist" / "notes.html").read_text()
        assert '<a href="index.html" class="nav-index">Home</a>' in html
        assert '<a href="archive.html" class="nav-archive">Archive</a>' in html
        assert 'current' not in html

    def test_navigation_rendered_on_cookies_page(self, tmp_path):
        config = _NAVIGATION_CONFIG + "special_pages:\n  - cookies\n"
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=config)
        (p / "content" / "cookies.md").write_text(COOKIES_MD)
        build(p)
        html = (p / "dist" / "cookies.html").read_text()
        assert '<a href="index.html" class="nav-index">Home</a>' in html
        assert '<a href="archive.html" class="nav-archive">Archive</a>' in html
        assert 'current' not in html

    def test_no_navigation_when_not_configured(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        html = (p / "dist" / "index.html").read_text()
        assert '<a href="index.html" class="nav-index">Home</a>' not in html
        assert 'current' not in html


# ---------------------------------------------------------------------------
# Dynamic shortcode values
# ---------------------------------------------------------------------------

_DYNAMIC_ABOUT_CONFIG = (
    "site_name: Test Blog\nsite_url: https://example.github.io\n"
    "posts_per_page: 2\nspecial_pages:\n  - about\n"
)


class TestDynamicShortcodeExpansion:

    def test_shortcode_expanded_in_rendered_html(self, tmp_path):
        p = make_project(tmp_path, posts={
            1: "---\ndate: 2026-05-24\n---\n\nWe have {{ post_count }} posts.\n",
            2: MINIMAL_MD,
        })
        build(p)
        html = (p / "dist" / "1.html").read_text()
        assert '<span class="post-count">2</span>' in html

    def test_today_shortcode_expands_to_date_format(self, tmp_path):
        p = make_project(tmp_path, posts={1: "---\ndate: 2026-05-24\n---\n\nToday is {{ today }}.\n"})
        build(p)
        html = (p / "dist" / "1.html").read_text()
        assert re.search(r'<span class="today">\d{1,2}/\d{1,2}/\d{2}</span>', html)

    def test_ai_post_list_end_to_end(self, tmp_path):
        p = make_project(tmp_path, posts={
            1: "---\ndate: 2026-05-24\ntitle: First\nai_assisted: true\n---\n\nContent.\n",
            2: "---\ndate: 2026-06-01\ntitle: Second\n---\n\nContent.\n",
            3: "---\ndate: 2026-06-10\ntitle: Third\nai_assisted: true\n---\n\n{{ ai_post_list }}\n",
        })
        build(p)
        html = (p / "dist" / "3.html").read_text()
        assert (
            '<ul class="ai-post-list">'
            '<li><a href="3.html">Third</a></li>'
            '<li><a href="1.html">First</a></li>'
            '</ul>'
        ) in html

    def test_unknown_shortcode_warns_with_name_and_file(self, tmp_path):
        p = make_project(tmp_path, posts={1: "---\ndate: 2026-05-24\n---\n\n{{ nonsense }}\n"})
        warnings = build(p)["warnings"]
        assert any(f == "1.html" and "nonsense" in msg for f, msg in warnings)

    def test_unknown_shortcode_before_more_marker_warns_only_once(self, tmp_path):
        # The excerpt (shown on index/category pages) is rendered from the same source
        # text as the part of the body before the marker — an unknown shortcode there
        # must only produce one warning, not one from the body pass and one from the
        # excerpt pass over the same occurrence.
        md = "---\ndate: 2026-05-24\n---\n\n{{ nonsense }}\n\n<!-- more -->\n\nRest of the story.\n"
        p = make_project(tmp_path, posts={1: md})
        warnings = build(p)["warnings"]
        matching = [msg for f, msg in warnings if f == "1.html" and "nonsense" in msg]
        assert len(matching) == 1

    def test_unknown_shortcode_rendered_literally(self, tmp_path):
        p = make_project(tmp_path, posts={1: "---\ndate: 2026-05-24\n---\n\n{{ nonsense }}\n"})
        build(p)
        html = (p / "dist" / "1.html").read_text()
        assert "{{ nonsense }}" in html

    def test_inline_block_shortcode_warns_and_stays_literal(self, tmp_path):
        p = make_project(tmp_path, posts={
            1: "---\ndate: 2026-05-24\n---\n\nRecent posts: {{ ai_post_list }} end.\n",
        })
        outcome = build(p)
        html = (p / "dist" / "1.html").read_text()
        assert "{{ ai_post_list }}" in html
        assert any(f == "1.html" and "ai_post_list" in msg for f, msg in outcome["warnings"])


class TestAiPostListIncludesSpecialPages:

    def test_ai_assisted_special_page_appears_in_ai_post_list(self, tmp_path):
        p = make_project(tmp_path, posts={
            1: "---\ndate: 2026-05-24\n---\n\n{{ ai_post_list }}\n",
        }, config=_DYNAMIC_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(
            "---\ntitle: About Page\nai_assisted: true\n---\n\nStatic content.\n"
        )
        build(p)
        html = (p / "dist" / "1.html").read_text()
        assert '<a href="about.html">About Page</a>' in html

    def test_non_ai_assisted_special_page_excluded(self, tmp_path):
        p = make_project(tmp_path, posts={
            1: "---\ndate: 2026-05-24\n---\n\n{{ ai_post_list }}\n",
        }, config=_DYNAMIC_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text("---\ntitle: About Page\n---\n\nStatic content.\n")
        build(p)
        html = (p / "dist" / "1.html").read_text()
        assert '<ul class="ai-post-list"><li>(none)</li></ul>' in html

    def test_special_page_not_counted_in_post_count(self, tmp_path):
        p = make_project(tmp_path, posts={
            1: "---\ndate: 2026-05-24\n---\n\n{{ post_count }}\n",
        }, config=_DYNAMIC_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(
            "---\ntitle: About Page\nai_assisted: true\n---\n\nStatic content.\n"
        )
        build(p)
        html = (p / "dist" / "1.html").read_text()
        assert '<span class="post-count">1</span>' in html

    def test_special_page_not_counted_in_word_count(self, tmp_path):
        p = make_project(tmp_path, posts={
            1: "---\ndate: 2026-05-24\n---\n\n{{ word_count }}\n",
        }, config=_DYNAMIC_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(
            "---\ntitle: About Page\nai_assisted: true\n---\n\nMany extra words that should not be counted here at all.\n"
        )
        build(p)
        html = (p / "dist" / "1.html").read_text()
        # post 1's own body is just "{{ word_count }}" — expands to itself as 0 words
        assert '<span class="word-count">0</span>' in html

    def test_updating_special_page_ai_assisted_flag_updates_ai_post_list_elsewhere(self, tmp_path):
        # Post 1's own file is never touched between builds — it only picks up the
        # change via the forced-dynamic-rebuild mechanism (it's flagged dynamic after
        # build #1, since {{ ai_post_list }} was recognised and expanded).
        p = make_project(tmp_path, posts={
            1: "---\ndate: 2026-05-24\n---\n\n{{ ai_post_list }}\n",
        }, config=_DYNAMIC_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text("---\ntitle: About Page\n---\n\nStatic content.\n")
        build(p)
        assert '<li>(none)</li>' in (p / "dist" / "1.html").read_text()

        (p / "content" / "about.md").write_text(
            "---\ntitle: About Page\nai_assisted: true\n---\n\nStatic content.\n"
        )
        build(p)
        assert '<a href="about.html">About Page</a>' in (p / "dist" / "1.html").read_text()


class TestDynamicManifestFlag:

    def test_page_with_shortcode_flagged_dynamic(self, tmp_path):
        p = make_project(tmp_path, posts={1: "---\ndate: 2026-05-24\n---\n\n{{ post_count }}\n"})
        build(p)
        manifest = json.loads((p / "manifest.json").read_text())
        assert manifest["pages"]["1.html"] == {"dynamic": True}

    def test_page_without_shortcode_flagged_not_dynamic(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        manifest = json.loads((p / "manifest.json").read_text())
        assert manifest["pages"]["1.html"] == {"dynamic": False}

    def test_removing_shortcode_unflags_page(self, tmp_path):
        p = make_project(tmp_path, posts={1: "---\ndate: 2026-05-24\n---\n\n{{ post_count }}\n"})
        build(p)
        manifest = json.loads((p / "manifest.json").read_text())
        assert manifest["pages"]["1.html"]["dynamic"] is True

        (p / "content" / "1.md").write_text(MINIMAL_MD)
        build(p)
        manifest = json.loads((p / "manifest.json").read_text())
        assert manifest["pages"]["1.html"]["dynamic"] is False

    def test_unknown_shortcode_does_not_set_dynamic(self, tmp_path):
        p = make_project(tmp_path, posts={1: "---\ndate: 2026-05-24\n---\n\n{{ nonsense }}\n"})
        build(p)
        manifest = json.loads((p / "manifest.json").read_text())
        assert manifest["pages"]["1.html"]["dynamic"] is False

    def test_shortcode_inside_code_block_does_not_set_dynamic(self, tmp_path):
        md = "---\ndate: 2026-05-24\n---\n\n`{{ post_count }}`\n"
        p = make_project(tmp_path, posts={1: md})
        build(p)
        manifest = json.loads((p / "manifest.json").read_text())
        assert manifest["pages"]["1.html"]["dynamic"] is False

    def test_deleted_post_pruned_from_pages_manifest(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p)
        manifest = json.loads((p / "manifest.json").read_text())
        assert "2.html" in manifest["pages"]

        (p / "content" / "2.md").unlink()
        build(p)
        manifest = json.loads((p / "manifest.json").read_text())
        assert "2.html" not in manifest["pages"]

    def test_special_page_with_shortcode_flagged_dynamic(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_DYNAMIC_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text("---\ntitle: About\n---\n\n{{ post_count }}\n")
        build(p)
        manifest = json.loads((p / "manifest.json").read_text())
        assert manifest["pages"]["about.html"] == {"dynamic": True}


class TestDynamicForcedRebuild:

    def test_new_post_triggers_rebuild_of_other_dynamic_post(self, tmp_path):
        p = make_project(tmp_path, posts={
            1: "---\ndate: 2026-05-24\n---\n\nWe have {{ post_count }} posts.\n",
        })
        build(p)
        assert '<span class="post-count">1</span>' in (p / "dist" / "1.html").read_text()

        (p / "content" / "2.md").write_text(MINIMAL_MD)
        build(p)
        assert '<span class="post-count">2</span>' in (p / "dist" / "1.html").read_text()

    def test_new_post_triggers_rebuild_of_dynamic_special_page(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_DYNAMIC_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(
            "---\ntitle: About\n---\n\nWe have {{ post_count }} posts.\n"
        )
        build(p)
        assert '<span class="post-count">1</span>' in (p / "dist" / "about.html").read_text()

        (p / "content" / "2.md").write_text(MINIMAL_MD)
        build(p)
        assert '<span class="post-count">2</span>' in (p / "dist" / "about.html").read_text()

    def test_unrelated_non_dynamic_page_not_rebuilt(self, tmp_path):
        # Three existing posts, none with shortcodes. A 4th, newly-added post only
        # neighbors the previously-highest-numbered post (3) for prev/next nav links —
        # post 1 is neither changed, a neighbor, nor dynamic, so it must be left alone.
        p = make_project(tmp_path, posts={
            1: "---\ndate: 2026-05-01\n---\n\nPost one.\n",
            2: "---\ndate: 2026-05-10\n---\n\nPost two.\n",
            3: "---\ndate: 2026-05-20\n---\n\nPost three.\n",
        })
        build(p)
        original_mtime = (p / "dist" / "1.html").stat().st_mtime

        (p / "content" / "10.md").write_text("---\ndate: 2026-06-01\n---\n\nUnrelated new post, far away.\n")
        build(p)
        assert (p / "dist" / "1.html").stat().st_mtime == original_mtime

    def test_no_changes_anywhere_does_not_rebuild_dynamic_page(self, tmp_path):
        # Rebuilding with zero source changes must be a true no-op, even though a
        # dynamic-flagged page exists — the forced-rebuild mechanism exists to catch
        # up a dynamic page when something ELSE changed, not to force work every build.
        p = make_project(tmp_path, posts={
            1: "---\ndate: 2026-05-24\n---\n\nWe have {{ post_count }} posts.\n",
        })
        build(p)
        original_mtime = (p / "dist" / "1.html").stat().st_mtime

        outcome = build(p)
        assert outcome["log"] == []
        assert (p / "dist" / "1.html").stat().st_mtime == original_mtime

    def test_no_changes_anywhere_leaves_manifest_untouched(self, tmp_path):
        p = make_project(tmp_path, posts={
            1: "---\ndate: 2026-05-24\n---\n\nWe have {{ post_count }} posts.\n",
        })
        build(p)
        original_manifest = (p / "manifest.json").read_text()

        build(p)
        assert (p / "manifest.json").read_text() == original_manifest

    def test_special_page_only_change_still_triggers_dynamic_post_rebuild(self, tmp_path):
        # A special page changing (not a post) is still a real, relevant change —
        # dynamic posts must catch up even though no post itself was touched.
        p = make_project(tmp_path, posts={
            1: "---\ndate: 2026-05-24\n---\n\n{{ ai_post_list }}\n",
        }, config=_DYNAMIC_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text("---\ntitle: About\n---\n\nStatic content.\n")
        build(p)
        assert '<li>(none)</li>' in (p / "dist" / "1.html").read_text()

        (p / "content" / "about.md").write_text(
            "---\ntitle: About\nai_assisted: true\n---\n\nStatic content.\n"
        )
        build(p)
        assert '<a href="about.html">About</a>' in (p / "dist" / "1.html").read_text()


class TestDynamicSinglePageBuild:

    def test_single_page_build_computes_fresh_values(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p)
        (p / "content" / "2.md").write_text(
            "---\ndate: 2026-06-01\n---\n\nWe have {{ post_count }} posts.\n"
        )
        build(p, filename="2.md")
        assert '<span class="post-count">2</span>' in (p / "dist" / "2.html").read_text()

    def test_single_page_build_does_not_rebuild_other_dynamic_pages(self, tmp_path):
        p = make_project(tmp_path, posts={
            1: "---\ndate: 2026-05-24\n---\n\nWe have {{ post_count }} posts.\n",
        })
        build(p)
        original_html = (p / "dist" / "1.html").read_text()
        assert '<span class="post-count">1</span>' in original_html

        (p / "content" / "2.md").write_text(MINIMAL_MD)
        build(p, filename="2.md")
        assert (p / "dist" / "1.html").read_text() == original_html

    def test_single_page_build_updates_its_own_dynamic_flag(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        build(p, filename="1.md")
        manifest = json.loads((p / "manifest.json").read_text())
        assert manifest["pages"]["1.html"] == {"dynamic": False}

        (p / "content" / "1.md").write_text("---\ndate: 2026-05-24\n---\n\n{{ post_count }}\n")
        build(p, filename="1.md")
        manifest = json.loads((p / "manifest.json").read_text())
        assert manifest["pages"]["1.html"] == {"dynamic": True}

    def test_single_page_build_preserves_other_manifest_entries(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        build(p)
        before = json.loads((p / "manifest.json").read_text())

        build(p, filename="1.md")
        after = json.loads((p / "manifest.json").read_text())
        assert after["2.md"] == before["2.md"]
        assert after["pages"]["2.html"] == before["pages"]["2.html"]

    def test_single_page_special_build_does_not_rebuild_dynamic_post(self, tmp_path):
        p = make_project(tmp_path, posts={
            1: "---\ndate: 2026-05-24\n---\n\nWe have {{ post_count }} posts.\n",
        }, config=_DYNAMIC_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text("---\ntitle: About\n---\n\nStatic content.\n")
        build(p)
        original_post_html = (p / "dist" / "1.html").read_text()

        (p / "content" / "2.md").write_text(MINIMAL_MD)
        build(p, filename="about.md")
        assert (p / "dist" / "1.html").read_text() == original_post_html


class TestSpecialPagePreviewBuildSharedTail:

    def test_special_page_preview_syncs_resources(self, tmp_path):
        # A special-page single-file build used to return early before resource
        # syncing ran at all — unlike a post single-file build, which always reached
        # it. Both must behave the same way.
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        (p / "resources" / "new.css").write_text("body { color: red; }")
        build(p, filename="about.md")
        assert (p / "dist" / "resources" / "new.css").exists()

    def test_special_page_preview_not_double_processed(self, tmp_path):
        # The general special_pages loop (which independently rebuilds any special
        # page whose own file changed, regardless of what was targeted) must not
        # re-process the same page a second time when it's also the preview target.
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        outcome = build(p, filename="about.md")
        updated_entries = [e for e in outcome["log"] if e[1] == "about.html"]
        assert len(updated_entries) == 1

    def test_post_preview_does_not_rebuild_an_unrelated_changed_special_page(self, tmp_path):
        # A single-file build must only ever touch the one page requested — an
        # unrelated special page whose own file also changed must be left alone.
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD}, config=_ABOUT_CONFIG)
        (p / "content" / "about.md").write_text(ABOUT_MD)
        build(p)
        (p / "content" / "about.md").write_text(
            "---\ndate: 2026-05-24\ntitle: About\n---\n\nUpdated about content.\n"
        )
        build(p, filename="1.md")
        assert "Updated about content" not in (p / "dist" / "about.html").read_text()
