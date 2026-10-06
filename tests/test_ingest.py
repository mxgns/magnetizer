"""Tests for ingest.py

Covers all behaviour described in spec/ingest.md:
  - inbox/ scanning and validation (one .md max, recognised image extensions)
  - HEIC/HEIF conversion, EXIF orientation, GPS/metadata stripping
  - downscale-only resizing, SVG passthrough
  - natural sort of images
  - post-id continuation
  - markdown merge rules (date/images/category/draft)
  - draft trigger via underscore-prefixed filename
  - atomicity on failure, --dry-run
  - empty inbox no-op
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pillow_heif
import pytest
from PIL import Image as PILImage

from magnetizer.inbox import cleanup_inbox_sources, commit_staged_files, today_in_london

pillow_heif.register_heif_opener()

INGEST_SCRIPT = Path(__file__).parent.parent / "ingest.py"


def run_ingest(args, cwd):
    return subprocess.run(
        [sys.executable, str(INGEST_SCRIPT)] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def project_dir(tmp_path):
    """Project root with empty content/ and inbox/ directories."""
    (tmp_path / "content").mkdir()
    (tmp_path / "inbox").mkdir()
    return tmp_path


@pytest.fixture
def project_dir_with_posts(tmp_path):
    """Project root with posts 1 and 2 already in content/."""
    content = tmp_path / "content"
    content.mkdir()
    (tmp_path / "inbox").mkdir()
    (content / "1.md").write_text("---\ndate: 2026-01-01\n---\n")
    (content / "2.md").write_text("---\ndate: 2026-01-02\n---\n")
    (content / "2-image-01.jpg").write_bytes(make_jpeg_bytes(40, 30))
    return tmp_path


def make_jpeg_bytes(width, height):
    import io
    img = PILImage.new("RGB", (width, height), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_jpeg(path, width, height, orientation=None, gps=False):
    img = PILImage.new("RGB", (width, height), color=(128, 128, 128))
    exif = img.getexif()
    exif[0x0110] = "TestCameraModel"
    if orientation is not None:
        exif[0x0112] = orientation
    if gps:
        exif[0x8825] = {1: "N", 2: (51, 30, 0), 3: "W", 4: (0, 7, 0)}
    img.save(path, exif=exif)
    return path


def make_png(path, width, height):
    img = PILImage.new("RGB", (width, height), color=(10, 20, 30))
    img.save(path)
    return path


def make_svg(path, content='<svg xmlns="http://www.w3.org/2000/svg"></svg>'):
    path.write_text(content)
    return path


def make_heic(path, width, height, orientation=None, gps=False):
    img = PILImage.new("RGB", (width, height), color=(200, 100, 50))
    exif = img.getexif()
    if orientation is not None:
        exif[0x0112] = orientation
    if gps:
        exif[0x8825] = {1: "N", 2: (51, 30, 0), 3: "W", 4: (0, 7, 0)}
    # pillow-heif only honours a raw EXIF blob here, not a PIL Exif object --
    # passed the object directly, it silently writes orientation=1 regardless.
    img.save(path, format="HEIF", quality=90, exif=exif.tobytes())
    return path


def open_image(path):
    return PILImage.open(path)


# ---------------------------------------------------------------------------
# Empty inbox
# ---------------------------------------------------------------------------

class TestEmptyInbox:

    def test_empty_inbox_exits_zero(self, project_dir):
        result = run_ingest([], cwd=project_dir)
        assert result.returncode == 0

    def test_empty_inbox_prints_nothing_to_ingest(self, project_dir):
        result = run_ingest([], cwd=project_dir)
        assert "Nothing to ingest." in result.stdout

    def test_empty_inbox_makes_no_changes(self, project_dir):
        run_ingest([], cwd=project_dir)
        assert list((project_dir / "content").iterdir()) == []

    def test_inbox_with_only_dotfiles_is_still_empty(self, project_dir):
        (project_dir / "inbox" / ".gitkeep").write_text("")
        result = run_ingest([], cwd=project_dir)
        assert "Nothing to ingest." in result.stdout
        assert (project_dir / "inbox" / ".gitkeep").exists()


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class TestValidationErrors:

    def test_multiple_md_files_is_an_error(self, project_dir):
        inbox = project_dir / "inbox"
        (inbox / "a.md").write_text("Hello")
        (inbox / "b.md").write_text("World")
        result = run_ingest([], cwd=project_dir)
        assert result.returncode != 0
        assert list((project_dir / "content").iterdir()) == []

    def test_unsupported_file_type_is_an_error(self, project_dir):
        inbox = project_dir / "inbox"
        make_jpeg(inbox / "photo.jpg", 100, 80)
        (inbox / "notes.txt").write_text("not an image")
        result = run_ingest([], cwd=project_dir)
        assert result.returncode != 0
        assert list((project_dir / "content").iterdir()) == []

    def test_validation_error_leaves_inbox_untouched(self, project_dir):
        inbox = project_dir / "inbox"
        (inbox / "a.md").write_text("Hello")
        (inbox / "b.md").write_text("World")
        run_ingest([], cwd=project_dir)
        assert (inbox / "a.md").exists()
        assert (inbox / "b.md").exists()

    def test_preexisting_content_defect_aborts_the_whole_run(self, project_dir):
        # An orphan image with no matching .md -- a real defect in content/,
        # unrelated to this run. validate_content runs against the merged
        # view (real content/ + staged additions), so it must still catch
        # this and abort before anything is touched.
        content = project_dir / "content"
        make_jpeg(content / "99-image-01.jpg", 10, 10)
        make_jpeg(project_dir / "inbox" / "photo.jpg", 100, 80)
        result = run_ingest([], cwd=project_dir)
        assert result.returncode != 0
        assert (project_dir / "inbox" / "photo.jpg").exists()
        assert list(content.iterdir()) == [content / "99-image-01.jpg"]


# ---------------------------------------------------------------------------
# Post-id continuation
# ---------------------------------------------------------------------------

class TestPostIdContinuation:

    def test_first_post_gets_id_1(self, project_dir):
        make_jpeg(project_dir / "inbox" / "photo.jpg", 100, 80)
        run_ingest([], cwd=project_dir)
        assert (project_dir / "content" / "1.md").exists()

    def test_post_id_continues_from_existing_content(self, project_dir_with_posts):
        make_jpeg(project_dir_with_posts / "inbox" / "photo.jpg", 100, 80)
        run_ingest([], cwd=project_dir_with_posts)
        assert (project_dir_with_posts / "content" / "3.md").exists()


# ---------------------------------------------------------------------------
# Image processing: HEIC conversion
# ---------------------------------------------------------------------------

class TestHeicConversion:

    def test_heic_is_converted_to_jpg(self, project_dir):
        make_heic(project_dir / "inbox" / "photo.heic", 200, 150)
        run_ingest([], cwd=project_dir)
        assert (project_dir / "content" / "1-image-01.jpg").exists()
        assert not (project_dir / "content" / "1-image-01.heic").exists()

    def test_heif_extension_is_also_converted_to_jpg(self, project_dir):
        make_heic(project_dir / "inbox" / "photo.heif", 200, 150)
        run_ingest([], cwd=project_dir)
        assert (project_dir / "content" / "1-image-01.jpg").exists()

    def test_converted_heic_output_is_a_valid_jpeg(self, project_dir):
        make_heic(project_dir / "inbox" / "photo.heic", 200, 150)
        run_ingest([], cwd=project_dir)
        img = open_image(project_dir / "content" / "1-image-01.jpg")
        assert img.format == "JPEG"


# ---------------------------------------------------------------------------
# Image processing: orientation, GPS/metadata stripping
# ---------------------------------------------------------------------------

class TestOrientationAndMetadata:

    def test_jpeg_orientation_is_applied(self, project_dir):
        # Physical pixels are landscape; Orientation=6 means rotate 90 CW on display.
        make_jpeg(project_dir / "inbox" / "photo.jpg", 200, 100, orientation=6)
        run_ingest([], cwd=project_dir)
        img = open_image(project_dir / "content" / "1-image-01.jpg")
        assert img.size == (100, 200)

    def test_heic_orientation_is_applied(self, project_dir):
        make_heic(project_dir / "inbox" / "photo.heic", 200, 100, orientation=6)
        run_ingest([], cwd=project_dir)
        img = open_image(project_dir / "content" / "1-image-01.jpg")
        assert img.size == (100, 200)

    def test_jpeg_gps_exif_is_stripped(self, project_dir):
        make_jpeg(project_dir / "inbox" / "photo.jpg", 100, 80, gps=True)
        run_ingest([], cwd=project_dir)
        img = open_image(project_dir / "content" / "1-image-01.jpg")
        assert 0x8825 not in dict(img.getexif())

    def test_heic_gps_exif_is_stripped(self, project_dir):
        src = make_heic(project_dir / "inbox" / "photo.heic", 100, 80, gps=True)
        assert 0x8825 in dict(open_image(src).getexif())  # source really has GPS
        run_ingest([], cwd=project_dir)
        img = open_image(project_dir / "content" / "1-image-01.jpg")
        assert 0x8825 not in dict(img.getexif())

    def test_all_exif_is_stripped_not_just_gps(self, project_dir):
        make_jpeg(project_dir / "inbox" / "photo.jpg", 100, 80)
        run_ingest([], cwd=project_dir)
        img = open_image(project_dir / "content" / "1-image-01.jpg")
        assert dict(img.getexif()) == {}

    def test_png_icc_profile_is_stripped(self, project_dir):
        src = project_dir / "inbox" / "photo.png"
        PILImage.new("RGB", (100, 80), color=(10, 20, 30)).save(src, icc_profile=b"fake-icc-profile-bytes")
        run_ingest([], cwd=project_dir)
        img = open_image(project_dir / "content" / "1-image-01.png")
        assert "icc_profile" not in img.info


# ---------------------------------------------------------------------------
# Image processing: downscale-only
# ---------------------------------------------------------------------------

class TestDownscaleOnly:

    def test_large_image_is_downscaled(self, project_dir):
        make_jpeg(project_dir / "inbox" / "photo.jpg", 4000, 2000)
        run_ingest(["--max-edge", "1000"], cwd=project_dir)
        img = open_image(project_dir / "content" / "1-image-01.jpg")
        assert img.size[0] <= 1000

    def test_small_image_is_never_upscaled(self, project_dir):
        make_jpeg(project_dir / "inbox" / "photo.jpg", 100, 80)
        run_ingest(["--max-edge", "2000"], cwd=project_dir)
        img = open_image(project_dir / "content" / "1-image-01.jpg")
        assert img.size == (100, 80)


# ---------------------------------------------------------------------------
# SVG passthrough
# ---------------------------------------------------------------------------

class TestSvgPassthrough:

    def test_svg_is_copied_as_is(self, project_dir):
        svg_content = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="5"/></svg>'
        make_svg(project_dir / "inbox" / "icon.svg", svg_content)
        run_ingest([], cwd=project_dir)
        output = project_dir / "content" / "1-image-01.svg"
        assert output.exists()
        assert output.read_text() == svg_content


# ---------------------------------------------------------------------------
# Natural sort of images within a post
# ---------------------------------------------------------------------------

class TestNaturalSort:

    def test_images_are_numbered_in_natural_sort_order(self, project_dir):
        inbox = project_dir / "inbox"
        make_jpeg(inbox / "IMG_10.jpg", 10, 10)
        make_jpeg(inbox / "IMG_2.jpg", 20, 20)
        make_jpeg(inbox / "IMG_1.jpg", 30, 30)
        run_ingest([], cwd=project_dir)
        content = project_dir / "content"
        # IMG_1 -> 01 (30x30), IMG_2 -> 02 (20x20), IMG_10 -> 03 (10x10)
        assert open_image(content / "1-image-01.jpg").size == (30, 30)
        assert open_image(content / "1-image-02.jpg").size == (20, 20)
        assert open_image(content / "1-image-03.jpg").size == (10, 10)


# ---------------------------------------------------------------------------
# today_in_london() -- the merge-case missing-date default must use
# Europe/London, not naive system-local time (e.g. a CI runner in UTC)
# ---------------------------------------------------------------------------

class TestTodayInLondon:

    def test_matches_london_date_for_a_given_instant(self):
        # 23:30 UTC in June is already past midnight in London (BST, UTC+1)
        # -- the London date is one day ahead of the UTC date.
        now = datetime(2026, 6, 15, 23, 30, tzinfo=ZoneInfo("UTC"))
        assert today_in_london(now) == "2026-06-16"

    def test_uses_london_date_not_utc_date_in_winter_too(self):
        # In winter (GMT, UTC+0) the two should coincide -- confirms the
        # function isn't just always adding a day.
        now = datetime(2026, 1, 15, 23, 30, tzinfo=ZoneInfo("UTC"))
        assert today_in_london(now) == "2026-01-15"


# ---------------------------------------------------------------------------
# commit_staged_files() -- moving staged files into content/ must be
# all-or-nothing: a failure partway through must not leave a partial post.
# ---------------------------------------------------------------------------

class TestCommitStagedFilesAtomicity:

    def _make_staging(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "1-image-01.jpg").write_bytes(b"a")
        (staging / "1-image-02.jpg").write_bytes(b"b")
        (staging / "1.md").write_text("---\ndate: 2026-01-01\n---\n")
        content = tmp_path / "content"
        content.mkdir()
        return staging, content

    def test_all_files_moved_on_success(self, tmp_path):
        staging, content = self._make_staging(tmp_path)
        commit_staged_files(staging, content)
        assert sorted(f.name for f in content.iterdir()) == ["1-image-01.jpg", "1-image-02.jpg", "1.md"]

    def test_partial_move_failure_rolls_back_content_dir(self, tmp_path, monkeypatch):
        staging, content = self._make_staging(tmp_path)

        real_move = shutil.move
        calls = []

        def failing_move(src, dst):
            calls.append(src)
            if len(calls) == 2:
                raise OSError("simulated disk failure")
            return real_move(src, dst)

        monkeypatch.setattr("magnetizer.inbox.shutil.move", failing_move)

        with pytest.raises(OSError):
            commit_staged_files(staging, content)

        assert list(content.iterdir()) == []


# ---------------------------------------------------------------------------
# cleanup_inbox_sources() -- best-effort: the post is already committed by
# this point, so one file failing to delete must not be treated as the whole
# run failing.
# ---------------------------------------------------------------------------

class TestCleanupInboxSources:

    def test_all_sources_deleted_on_success(self, tmp_path):
        md = tmp_path / "post.md"
        md.write_text("hi")
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"a")
        cleanup_inbox_sources(md, [img])
        assert not md.exists()
        assert not img.exists()

    def test_one_failure_does_not_raise_and_still_removes_others(self, tmp_path, monkeypatch, capsys):
        md = tmp_path / "post.md"
        md.write_text("hi")
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"a")

        real_unlink = Path.unlink

        def failing_unlink(self):
            if self == img:
                raise OSError("simulated permission error")
            return real_unlink(self)

        monkeypatch.setattr(Path, "unlink", failing_unlink)

        cleanup_inbox_sources(md, [img])  # must not raise
        assert not md.exists()
        assert "Warning" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Markdown: no .md supplied -> generated skeleton
# ---------------------------------------------------------------------------

class TestGeneratedSkeleton:

    def test_no_md_generates_skeleton_with_date(self, project_dir):
        make_jpeg(project_dir / "inbox" / "photo.jpg", 100, 80)
        run_ingest([], cwd=project_dir)
        text = (project_dir / "content" / "1.md").read_text()
        assert "date:" in text

    def test_no_md_skeleton_is_never_a_draft(self, project_dir):
        make_jpeg(project_dir / "inbox" / "photo.jpg", 100, 80)
        run_ingest([], cwd=project_dir)
        text = (project_dir / "content" / "1.md").read_text()
        assert "draft" not in text


# ---------------------------------------------------------------------------
# Markdown merge rules
# ---------------------------------------------------------------------------

class TestMarkdownMerge:

    def test_existing_date_is_preserved(self, project_dir):
        (project_dir / "inbox" / "post.md").write_text("---\ndate: 2026-02-02\n---\n\nBody text.")
        run_ingest([], cwd=project_dir)
        text = (project_dir / "content" / "1.md").read_text()
        assert "date: 2026-02-02" in text

    def test_missing_date_is_added(self, project_dir):
        (project_dir / "inbox" / "post.md").write_text("---\ntitle: Hi\n---\n\nBody text.")
        run_ingest([], cwd=project_dir)
        text = (project_dir / "content" / "1.md").read_text()
        assert "date:" in text

    def test_body_is_preserved_verbatim(self, project_dir):
        (project_dir / "inbox" / "post.md").write_text("---\ndate: 2026-02-02\n---\n\nThis is my post body.")
        run_ingest([], cwd=project_dir)
        text = (project_dir / "content" / "1.md").read_text()
        assert "This is my post body." in text

    def test_missing_category_is_added_empty(self, project_dir):
        (project_dir / "inbox" / "post.md").write_text("---\ndate: 2026-02-02\n---\n\nBody.")
        run_ingest([], cwd=project_dir)
        text = (project_dir / "content" / "1.md").read_text()
        assert "category:" in text

    def test_existing_category_is_preserved(self, project_dir):
        (project_dir / "inbox" / "post.md").write_text("---\ndate: 2026-02-02\ncategory: travel\n---\n\nBody.")
        run_ingest([], cwd=project_dir)
        text = (project_dir / "content" / "1.md").read_text()
        assert "category: travel" in text

    def test_images_list_padded_up_to_image_count(self, project_dir):
        inbox = project_dir / "inbox"
        (inbox / "post.md").write_text("---\ndate: 2026-02-02\nimages:\n  - My caption\n---\n\nBody.")
        make_jpeg(inbox / "a.jpg", 10, 10)
        make_jpeg(inbox / "b.jpg", 10, 10)
        run_ingest([], cwd=project_dir)
        text = (project_dir / "content" / "1.md").read_text()
        assert "My caption" in text
        assert "Image 2" in text

    def test_images_list_longer_than_image_count_warns_not_truncates(self, project_dir):
        inbox = project_dir / "inbox"
        (inbox / "post.md").write_text("---\ndate: 2026-02-02\nimages:\n  - One\n  - Two\n  - Three\n---\n\nBody.")
        make_jpeg(inbox / "a.jpg", 10, 10)
        result = run_ingest([], cwd=project_dir)
        text = (project_dir / "content" / "1.md").read_text()
        assert "One" in text and "Two" in text and "Three" in text
        assert "warn" in (result.stdout + result.stderr).lower()


# ---------------------------------------------------------------------------
# Draft trigger
# ---------------------------------------------------------------------------

class TestDraftTrigger:

    def test_underscore_prefixed_md_produces_draft_true(self, project_dir):
        (project_dir / "inbox" / "_secret-post.md").write_text("---\ndate: 2026-02-02\n---\n\nBody.")
        run_ingest([], cwd=project_dir)
        text = (project_dir / "content" / "1.md").read_text()
        assert "draft: true" in text

    def test_non_underscore_prefixed_md_is_not_a_draft(self, project_dir):
        (project_dir / "inbox" / "post.md").write_text("---\ndate: 2026-02-02\n---\n\nBody.")
        run_ingest([], cwd=project_dir)
        text = (project_dir / "content" / "1.md").read_text()
        assert "draft" not in text

    def test_leading_underscore_never_leaks_into_output_filename(self, project_dir):
        (project_dir / "inbox" / "_secret-post.md").write_text("---\ndate: 2026-02-02\n---\n\nBody.")
        run_ingest([], cwd=project_dir)
        assert (project_dir / "content" / "1.md").exists()
        assert not (project_dir / "content" / "_1.md").exists()

    def test_no_md_at_all_is_never_a_draft_even_with_underscore_folder_history(self, project_dir):
        make_jpeg(project_dir / "inbox" / "photo.jpg", 100, 80)
        run_ingest([], cwd=project_dir)
        text = (project_dir / "content" / "1.md").read_text()
        assert "draft" not in text


# ---------------------------------------------------------------------------
# --dry-run
# ---------------------------------------------------------------------------

class TestDryRun:

    def test_dry_run_reports_would_create(self, project_dir):
        make_jpeg(project_dir / "inbox" / "photo.jpg", 100, 80)
        result = run_ingest(["--dry-run"], cwd=project_dir)
        assert "Would create post 1" in result.stdout

    def test_dry_run_does_not_touch_content(self, project_dir):
        make_jpeg(project_dir / "inbox" / "photo.jpg", 100, 80)
        run_ingest(["--dry-run"], cwd=project_dir)
        assert list((project_dir / "content").iterdir()) == []

    def test_dry_run_does_not_touch_inbox(self, project_dir):
        make_jpeg(project_dir / "inbox" / "photo.jpg", 100, 80)
        run_ingest(["--dry-run"], cwd=project_dir)
        assert (project_dir / "inbox" / "photo.jpg").exists()

    def test_dry_run_exits_zero_on_success(self, project_dir):
        make_jpeg(project_dir / "inbox" / "photo.jpg", 100, 80)
        result = run_ingest(["--dry-run"], cwd=project_dir)
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Success output / source cleanup
# ---------------------------------------------------------------------------

class TestSuccessOutput:

    def test_success_prints_post_created(self, project_dir):
        make_jpeg(project_dir / "inbox" / "photo.jpg", 100, 80)
        result = run_ingest([], cwd=project_dir)
        assert "Post 1 created" in result.stdout

    def test_success_deletes_processed_source_files(self, project_dir):
        inbox = project_dir / "inbox"
        make_jpeg(inbox / "photo.jpg", 100, 80)
        (inbox / "post.md").write_text("---\ndate: 2026-02-02\n---\n\nBody.")
        run_ingest([], cwd=project_dir)
        assert not (inbox / "photo.jpg").exists()
        assert not (inbox / "post.md").exists()

    def test_success_leaves_inbox_gitkeep_untouched(self, project_dir):
        inbox = project_dir / "inbox"
        (inbox / ".gitkeep").write_text("")
        make_jpeg(inbox / "photo.jpg", 100, 80)
        run_ingest([], cwd=project_dir)
        assert (inbox / ".gitkeep").exists()


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

class TestCLIInterface:

    def test_help_short_flag(self, tmp_path):
        result = run_ingest(["-h"], cwd=tmp_path)
        assert result.returncode == 0

    def test_help_long_flag(self, tmp_path):
        result = run_ingest(["--help"], cwd=tmp_path)
        assert result.returncode == 0

    def test_help_output_contains_usage(self, tmp_path):
        result = run_ingest(["--help"], cwd=tmp_path)
        output = result.stdout + result.stderr
        assert "ingest.py" in output or "usage" in output.lower()

    def test_help_describes_dry_run_option(self, tmp_path):
        result = run_ingest(["--help"], cwd=tmp_path)
        output = result.stdout + result.stderr
        assert "--dry-run" in output

    def test_missing_inbox_directory_is_an_error(self, tmp_path):
        (tmp_path / "content").mkdir()
        result = run_ingest([], cwd=tmp_path)
        assert result.returncode != 0
        assert "inbox" in (result.stdout + result.stderr).lower()

    def test_missing_content_directory_is_an_error(self, tmp_path):
        (tmp_path / "inbox").mkdir()
        result = run_ingest([], cwd=tmp_path)
        assert result.returncode != 0
        assert "content" in (result.stdout + result.stderr).lower()

    def test_non_ascii_post_body_survives_a_non_utf8_locale(self, project_dir):
        # Path.read_text()/write_text() without an explicit encoding fall back
        # to the locale-dependent default. Force a non-UTF-8 default (ASCII)
        # to genuinely reproduce that failure mode, rather than relying on
        # this sandbox's own default encoding happening to be UTF-8.
        (project_dir / "inbox" / "post.md").write_bytes(
            "---\ndate: 2026-02-02\n---\n\nCafé ☕, naïve, 日本語.".encode("utf-8")
        )
        env = {**os.environ, "LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0"}
        result = subprocess.run(
            [sys.executable, str(INGEST_SCRIPT)],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        text = (project_dir / "content" / "1.md").read_text(encoding="utf-8")
        assert "Café ☕, naïve, 日本語." in text

    def test_custom_inbox_and_content_directories(self, tmp_path):
        (tmp_path / "my-inbox").mkdir()
        (tmp_path / "my-content").mkdir()
        make_jpeg(tmp_path / "my-inbox" / "photo.jpg", 100, 80)
        result = run_ingest(["--inbox", "my-inbox", "--content", "my-content"], cwd=tmp_path)
        assert result.returncode == 0
        assert (tmp_path / "my-content" / "1.md").exists()
