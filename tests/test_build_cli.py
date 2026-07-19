"""CLI integration tests for build.py"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image as PILImage

from conftest import MINIMAL_MD, make_project

BUILD_SCRIPT = Path(__file__).parent.parent / "build.py"


def run_build(args, cwd):
    return subprocess.run(
        [sys.executable, str(BUILD_SCRIPT)] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

class TestHelp:

    def test_help_exits_zero(self, tmp_path):
        assert run_build(["--help"], cwd=tmp_path).returncode == 0

    def test_help_output_mentions_build(self, tmp_path):
        result = run_build(["--help"], cwd=tmp_path)
        assert "build.py" in result.stdout or "usage" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Validation errors surfaced through CLI
# ---------------------------------------------------------------------------

class TestCLIValidation:

    def test_exits_nonzero_when_content_missing(self, tmp_path):
        (tmp_path / "dist").mkdir()
        (tmp_path / "templates").mkdir()
        (tmp_path / "resources").mkdir()
        (tmp_path / "config.yaml").write_text("site_url: https://example.github.io\n")
        result = run_build([], cwd=tmp_path)
        assert result.returncode != 0

    def test_error_mentions_missing_directory(self, tmp_path):
        (tmp_path / "dist").mkdir()
        (tmp_path / "templates").mkdir()
        (tmp_path / "resources").mkdir()
        (tmp_path / "config.yaml").write_text("site_url: https://example.github.io\n")
        result = run_build([], cwd=tmp_path)
        assert "content" in result.stderr.lower()

    def test_exits_nonzero_when_content_has_no_md_files(self, tmp_path):
        make_project(tmp_path)  # content/ is empty
        result = run_build([], cwd=tmp_path)
        assert result.returncode != 0

    def test_filename_with_flush_is_rejected(self, tmp_path):
        make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build(["1.md", "--flush"], cwd=tmp_path)
        assert result.returncode != 0

    def test_filename_with_resources_is_rejected(self, tmp_path):
        make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build(["1.md", "--resources"], cwd=tmp_path)
        assert result.returncode != 0

    def test_filename_with_push_is_rejected(self, tmp_path):
        make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build(["1.md", "--push"], cwd=tmp_path)
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# Basic build
# ---------------------------------------------------------------------------

class TestCLIBasicBuild:

    def test_exits_zero_on_success(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        assert run_build([], cwd=p).returncode == 0

    def test_post_html_created(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        run_build([], cwd=p)
        assert (p / "dist" / "1.html").exists()

    def test_index_html_created(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        run_build([], cwd=p)
        assert (p / "dist" / "index.html").exists()

    def test_resources_copied(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        run_build([], cwd=p)
        assert (p / "dist" / "resources" / "style.css").exists()

    def test_manifest_written(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        run_build([], cwd=p)
        assert (p / "manifest.json").exists()


# ---------------------------------------------------------------------------
# --flush
# ---------------------------------------------------------------------------

class TestCLIFlush:

    def test_flush_removes_stale_dist_files(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        stale = p / "dist" / "stale.html"
        stale.write_text("<html>old</html>")
        run_build(["--flush"], cwd=p)
        assert not stale.exists()

    def test_flush_rebuilds_posts(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        run_build(["--flush"], cwd=p)
        assert (p / "dist" / "1.html").exists()


# ---------------------------------------------------------------------------
# --resources
# ---------------------------------------------------------------------------

class TestCLIResources:

    def test_resources_replaces_existing(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        (p / "dist" / "resources").mkdir()
        old = p / "dist" / "resources" / "old.css"
        old.write_text("old")
        run_build(["--resources"], cwd=p)
        assert not old.exists()
        assert (p / "dist" / "resources" / "style.css").exists()


# ---------------------------------------------------------------------------
# Single filename
# ---------------------------------------------------------------------------

class TestCLISingleFile:

    def test_single_file_creates_post_html(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        run_build(["1.md"], cwd=p)
        assert (p / "dist" / "1.html").exists()

    def test_single_file_does_not_create_other_post_html(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        run_build(["1.md"], cwd=p)
        assert not (p / "dist" / "2.html").exists()

    def test_single_file_does_not_create_index(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        run_build(["1.md"], cwd=p)
        assert not (p / "dist" / "index.html").exists()

    def test_single_file_does_not_write_source_mtime_entries(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        run_build(["1.md"], cwd=p)
        manifest = json.loads((p / "manifest.json").read_text())
        assert "1.md" not in manifest
        assert manifest["pages"] == {"1.html": {"dynamic": False}}


# ---------------------------------------------------------------------------
# Outcome summary
# ---------------------------------------------------------------------------

class TestCLIOutcome:

    def test_outcome_shows_created_count(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build([], cwd=p)
        assert "1 created" in result.stdout

    def test_outcome_shows_all_three_counts(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build([], cwd=p)
        assert "created" in result.stdout
        assert "updated" in result.stdout
        assert "deleted" in result.stdout

    def test_no_changes_message_when_nothing_changed(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        run_build([], cwd=p)
        result = run_build([], cwd=p)
        assert "No changes." in result.stdout

    def test_counts_not_shown_when_nothing_changed(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        run_build([], cwd=p)
        result = run_build([], cwd=p)
        assert "created" not in result.stdout


# ---------------------------------------------------------------------------
# --verbose
# ---------------------------------------------------------------------------

class TestCLIVerbose:

    def test_verbose_shows_post_line(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build(["--verbose"], cwd=p)
        assert "1.html" in result.stdout

    def test_verbose_post_line_includes_zero_padded_id(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build(["--verbose"], cwd=p)
        assert "001" in result.stdout

    def test_verbose_shows_index_in_pages_section(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build(["--verbose"], cwd=p)
        assert "index" in result.stdout

    def test_verbose_shows_feed_in_pages_section(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build(["--verbose"], cwd=p)
        assert "feed.xml" in result.stdout

    def test_verbose_shows_resources_section(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build(["--verbose"], cwd=p)
        assert "style.css" in result.stdout

    def test_verbose_shows_image_count_for_post_with_images(self, tmp_path):
        from PIL import Image as PILImage
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        img = PILImage.new("RGB", (800, 600))
        img.save(p / "content" / "1-image-01.jpg", "JPEG")
        result = run_build(["--verbose"], cwd=p)
        assert "[1 img]" in result.stdout

    def test_verbose_shows_plus_prefix_for_draft_post(self, tmp_path):
        draft_md = "---\ndate: 2026-05-24\ndraft: true\n---\n\nDraft\n"
        p = make_project(tmp_path, posts={1: draft_md})
        result = run_build(["--verbose"], cwd=p)
        assert "+1.html" in result.stdout

    def test_non_verbose_warning_shows_plus_prefix_for_draft(self, tmp_path):
        draft_md = "---\ndate: 2026-05-24\ndraft: true\n---\n\nDraft\n"
        config = "site_name: Test Blog\nsite_url: https://example.github.io\nposts_per_page: 2\ncategories:\n  news: News\n"
        p = make_project(tmp_path, posts={1: draft_md}, config=config)
        result = run_build([], cwd=p)
        assert "+1.html" in result.stdout

    def test_verbose_compatible_with_single_file(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        result = run_build(["1.md", "--verbose"], cwd=p)
        assert result.returncode == 0

    def test_generating_line_has_site_name_then_arrow(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build(["--verbose"], cwd=p)
        assert "Generating Test Blog →" in result.stdout

    def test_pages_summary_shows_configured_special_page_name(self, tmp_path):
        config = "site_name: Test Blog\nsite_url: https://example.github.io\nposts_per_page: 2\nspecial_pages:\n  - now\n"
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=config)
        (p / "content" / "now.md").write_text("---\ntitle: Now\n---\n\nWhat I'm doing now.\n")
        result = run_build(["--verbose"], cwd=p)
        assert "now" in result.stdout
        assert "now.html" not in result.stdout


# ---------------------------------------------------------------------------
# Category pages summary
# ---------------------------------------------------------------------------

_CATEGORIES_CLI_CONFIG = (
    "site_name: Test Blog\nsite_url: https://example.github.io\n"
    "posts_per_page: 2\ncategories:\n  photography: Photography\n  travel: Travel\n"
)
_PHOTO_MD = "---\ndate: 2026-05-24\ntitle: Photo Post\ncategory: photography\n---\n\nContent\n"
_TRAVEL_MD = "---\ndate: 2026-05-24\ntitle: Travel Post\ncategory: travel\n---\n\nContent\n"


class TestCLICategoryPagesSummary:

    def test_verbose_shows_category_count_not_individual_names(self, tmp_path):
        posts = {1: _PHOTO_MD, 2: _PHOTO_MD, 3: _PHOTO_MD, 4: _TRAVEL_MD}
        p = make_project(tmp_path, posts=posts, config=_CATEGORIES_CLI_CONFIG)
        result = run_build(["--verbose"], cwd=p)
        assert "categories(3)" in result.stdout
        assert "photography.html" not in result.stdout
        assert "photography-2.html" not in result.stdout
        assert "travel.html" not in result.stdout

    def test_non_verbose_shows_category_count_not_individual_names(self, tmp_path):
        posts = {1: _PHOTO_MD, 2: _PHOTO_MD, 3: _PHOTO_MD, 4: _TRAVEL_MD}
        p = make_project(tmp_path, posts=posts, config=_CATEGORIES_CLI_CONFIG)
        result = run_build([], cwd=p)
        assert "categories(3)" in result.stdout
        assert "photography.html" not in result.stdout
        assert "photography-2.html" not in result.stdout
        assert "travel.html" not in result.stdout

    def test_single_category_page_still_shows_count(self, tmp_path):
        p = make_project(tmp_path, posts={1: _PHOTO_MD}, config=_CATEGORIES_CLI_CONFIG)
        result = run_build(["--verbose"], cwd=p)
        assert "categories(1)" in result.stdout
        assert "photography.html" not in result.stdout

    def test_no_categories_section_when_no_category_pages_built(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_CATEGORIES_CLI_CONFIG)
        result = run_build(["--verbose"], cwd=p)
        assert "categories(" not in result.stdout


# ---------------------------------------------------------------------------
# Generating header and no-changes message
# ---------------------------------------------------------------------------

class TestCLIHeaderAndStatus:

    def test_generating_line_includes_site_name(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build(["--verbose"], cwd=p)
        assert "Generating Test Blog" in result.stdout

    def test_generating_line_includes_dist_path(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build(["--verbose"], cwd=p)
        assert str(p / "dist") in result.stdout

    def test_generating_line_appears_before_summary(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build(["--verbose"], cwd=p)
        assert result.stdout.index("Generating") < result.stdout.index("created")

    def test_generating_line_not_shown_in_non_verbose_mode(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build([], cwd=p)
        assert "Generating" not in result.stdout

    def test_no_changes_message_shown_on_second_build(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        run_build([], cwd=p)
        result = run_build([], cwd=p)
        assert "No changes." in result.stdout

    def test_summary_counts_not_shown_when_no_changes(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        run_build([], cwd=p)
        result = run_build([], cwd=p)
        assert "created" not in result.stdout

    def test_summary_counts_shown_when_changes_exist(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build([], cwd=p)
        assert "created" in result.stdout
        assert "No changes." not in result.stdout

    def test_done_shown_on_success(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_build([], cwd=p)
        assert "DONE" in result.stdout

    def test_done_shown_when_no_changes(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD})
        run_build([], cwd=p)
        result = run_build([], cwd=p)
        assert "DONE" in result.stdout


# ---------------------------------------------------------------------------
# Deleted posts
# ---------------------------------------------------------------------------

class TestCLIDeletedPost:

    def test_deleted_post_not_shown_in_updated_pages(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD, 2: MINIMAL_MD})
        run_build([], cwd=p)
        (p / "content" / "1.md").unlink()
        result = run_build([], cwd=p)
        assert "1.html" not in result.stdout


# ---------------------------------------------------------------------------
# Microblog pages
# ---------------------------------------------------------------------------

MICRO_MD = "---\ndate: 2026-05-24\n---\n\nShort micro post.\n"
TITLED_MD = "---\ndate: 2026-05-24\ntitle: A Regular Post\n---\n\nThis is a regular post.\n"

class TestCLIMicroblogPages:

    def test_microblog_html_created_when_micro_posts_exist(self, tmp_path):
        p = make_project(tmp_path, posts={1: MICRO_MD})
        run_build([], cwd=p)
        assert (p / "dist" / "microblog.html").exists()

    def test_microblog_html_not_created_when_no_micro_posts(self, tmp_path):
        p = make_project(tmp_path, posts={1: TITLED_MD})
        run_build([], cwd=p)
        assert not (p / "dist" / "microblog.html").exists()

    def test_microblog_page_2_created_when_more_posts_than_per_page(self, tmp_path):
        config = (
            "site_name: Test Blog\nsite_url: https://example.github.io\n"
            "posts_per_page: 10\nmicro_posts_per_page: 1\n"
        )
        p = make_project(tmp_path, posts={1: MICRO_MD, 2: MICRO_MD}, config=config)
        run_build([], cwd=p)
        assert (p / "dist" / "microblog-2.html").exists()

    def test_microblog_html_contains_micro_post_body(self, tmp_path):
        p = make_project(tmp_path, posts={1: MICRO_MD})
        run_build([], cwd=p)
        content = (p / "dist" / "microblog.html").read_text()
        assert "Short micro post." in content


# ---------------------------------------------------------------------------
# Non-post warnings (special pages, build-level) shown on console
# ---------------------------------------------------------------------------

_SPECIAL_PAGE_CONFIG = (
    "site_name: Test Blog\nsite_url: https://example.github.io\n"
    "posts_per_page: 2\nspecial_pages:\n  - about\n"
)


class TestCLINonPostWarnings:

    def test_unknown_shortcode_on_special_page_shown_verbose(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_SPECIAL_PAGE_CONFIG)
        (p / "content" / "about.md").write_text("---\ntitle: About\n---\n\n{{ nonsense }}\n")
        result = run_build(["--verbose"], cwd=p)
        assert "about.html" in result.stdout
        assert "nonsense" in result.stdout

    def test_unknown_shortcode_on_special_page_shown_non_verbose(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_SPECIAL_PAGE_CONFIG)
        (p / "content" / "about.md").write_text("---\ntitle: About\n---\n\n{{ nonsense }}\n")
        result = run_build([], cwd=p)
        assert "about.html" in result.stdout
        assert "nonsense" in result.stdout

    def test_unknown_shortcode_on_special_page_marks_done_with_warnings(self, tmp_path):
        p = make_project(tmp_path, posts={1: MINIMAL_MD}, config=_SPECIAL_PAGE_CONFIG)
        (p / "content" / "about.md").write_text("---\ntitle: About\n---\n\n{{ nonsense }}\n")
        result = run_build([], cwd=p)
        assert "DONE with warnings" in result.stdout

    def test_unknown_shortcode_message_shown_for_post_too(self, tmp_path):
        p = make_project(tmp_path, posts={1: "---\ndate: 2026-05-24\n---\n\n{{ nonsense }}\n"})
        result = run_build([], cwd=p)
        assert "nonsense" in result.stdout
