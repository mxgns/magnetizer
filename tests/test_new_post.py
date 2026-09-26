"""Tests for new-post.py

Covers all behaviour described in the specification:
  - content/ directory validation
  - post-id determination
  - markdown file creation and format
  - image copying and numbering
  - missing-image warnings
  - success output
  - CLI interface (help, argument forms)
"""

import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import pytest


NEW_POST_SCRIPT = Path(__file__).parent.parent / "new-post.py"


def run_new_post(args, cwd):
    return subprocess.run(
        [sys.executable, str(NEW_POST_SCRIPT)] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def project_dir(tmp_path):
    """Project root with an empty content/ directory."""
    (tmp_path / "content").mkdir()
    return tmp_path


@pytest.fixture
def project_dir_with_posts(tmp_path):
    """Project root with posts 1 and 2 already in content/."""
    content = tmp_path / "content"
    content.mkdir()
    (content / "1.md").write_text("---\ndate: 2026-01-01\n---\n")
    (content / "2.md").write_text("---\ndate: 2026-01-02\n---\n")
    (content / "2-image-01.jpg").write_bytes(b"\xff\xd8\xff")
    return tmp_path


@pytest.fixture
def sample_jpg(project_dir):
    """A .jpg image sitting at the project root (not inside content/)."""
    img = project_dir / "photo.jpg"
    img.write_bytes(b"\xff\xd8\xff")
    return img


# ---------------------------------------------------------------------------
# content/ directory validation
# ---------------------------------------------------------------------------

class TestContentDirectoryValidation:

    def test_exits_with_error_when_no_content_dir(self, tmp_path):
        result = run_new_post([], cwd=tmp_path)
        assert result.returncode != 0

    def test_error_message_mentions_content(self, tmp_path):
        result = run_new_post([], cwd=tmp_path)
        output = result.stdout + result.stderr
        assert "content" in output.lower()

    def test_succeeds_when_content_dir_exists(self, project_dir):
        result = run_new_post([], cwd=project_dir)
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Post-id determination
# ---------------------------------------------------------------------------

class TestPostIdDetermination:

    def test_first_post_gets_id_1(self, project_dir):
        run_new_post([], cwd=project_dir)
        assert (project_dir / "content" / "1.md").exists()

    def test_post_id_is_max_existing_plus_one(self, project_dir_with_posts):
        run_new_post([], cwd=project_dir_with_posts)
        assert (project_dir_with_posts / "content" / "3.md").exists()

    def test_post_id_handles_non_sequential_existing_ids(self, project_dir):
        content = project_dir / "content"
        (content / "1.md").write_text("---\ndate: 2026-01-01\n---\n")
        (content / "5.md").write_text("---\ndate: 2026-01-05\n---\n")
        run_new_post([], cwd=project_dir)
        assert (project_dir / "content" / "6.md").exists()

    def test_post_id_considers_image_filenames(self, project_dir):
        content = project_dir / "content"
        (content / "1.md").write_text("---\ndate: 2026-01-01\n---\n")
        (content / "3.md").write_text("---\ndate: 2026-01-03\n---\n")
        (content / "3-image-01.jpg").write_bytes(b"\xff\xd8\xff")
        run_new_post([], cwd=project_dir)
        assert (project_dir / "content" / "4.md").exists()


# ---------------------------------------------------------------------------
# Markdown file creation
# ---------------------------------------------------------------------------

class TestMarkdownFileCreation:

    def test_creates_md_file_in_content(self, project_dir):
        run_new_post([], cwd=project_dir)
        assert (project_dir / "content" / "1.md").exists()

    def test_md_file_contains_date_frontmatter_key(self, project_dir):
        run_new_post([], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "date:" in content

    def test_md_file_date_is_todays_date(self, project_dir):
        today = date.today().isoformat()
        run_new_post([], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert today in content

    def test_md_file_date_is_iso8601_format(self, project_dir):
        run_new_post([], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        import re
        assert re.search(r"date: \d{4}-\d{2}-\d{2}", content)

    def test_md_no_title_key_in_frontmatter_when_none_given(self, project_dir):
        run_new_post([], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "title:" not in content

    def test_md_title_key_in_frontmatter_when_title_given(self, project_dir):
        run_new_post(["My Post Title"], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "title: My Post Title" in content

    def test_md_no_h1_in_body_when_title_given(self, project_dir):
        run_new_post(["My Post Title"], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "# My Post Title" not in content

    def test_md_no_h1_in_body_when_no_title_given(self, project_dir):
        run_new_post([], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "# " not in content

    def test_md_has_category_field_in_frontmatter(self, project_dir):
        run_new_post([], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "category:" in content

    def test_md_exact_format_without_title(self, project_dir):
        today = date.today().isoformat()
        run_new_post([], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        expected = f"---\ndate: {today}\ncategory: \n---\n"
        assert content == expected

    def test_md_exact_format_with_title(self, project_dir):
        today = date.today().isoformat()
        run_new_post(["This is my title"], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        expected = f"---\ndate: {today}\ntitle: This is my title\ncategory: \n---\n"
        assert content == expected

    def test_md_images_list_included_when_images_provided(self, project_dir, sample_jpg):
        run_new_post([str(sample_jpg)], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "images:" in content

    def test_md_images_placeholder_alt_text(self, project_dir, sample_jpg):
        run_new_post([str(sample_jpg)], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "- Image 1" in content

    def test_md_images_placeholder_numbered_correctly(self, project_dir):
        img1 = project_dir / "photo1.jpg"
        img2 = project_dir / "photo2.jpg"
        img1.write_bytes(b"\xff\xd8\xff")
        img2.write_bytes(b"\xff\xd8\xff")
        run_new_post([str(img1), str(img2)], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "- Image 1" in content
        assert "- Image 2" in content

    def test_md_exact_format_with_image(self, project_dir, sample_jpg):
        today = date.today().isoformat()
        run_new_post([str(sample_jpg)], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        expected = f"---\ndate: {today}\nimages:\n  - Image 1\ncategory: \n---\n"
        assert content == expected

    def test_md_no_images_key_when_no_images(self, project_dir):
        run_new_post([], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "images:" not in content

    def test_md_images_count_matches_copied_not_missing(self, project_dir, sample_jpg):
        run_new_post([str(sample_jpg), "missing.jpg"], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "- Image 1" in content
        assert "- Image 2" not in content

    def test_md_frontmatter_wrapped_in_triple_dashes(self, project_dir):
        run_new_post([], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert content.startswith("---\n")
        lines = content.splitlines()
        closing_dashes = [i for i, l in enumerate(lines) if l == "---"]
        assert len(closing_dashes) >= 2


# ---------------------------------------------------------------------------
# Image handling
# ---------------------------------------------------------------------------

class TestImageHandling:

    def test_image_is_copied_into_content(self, project_dir, sample_jpg):
        run_new_post([str(sample_jpg)], cwd=project_dir)
        images = list((project_dir / "content").glob("*-image-*.jpg"))
        assert len(images) == 1

    def test_image_renamed_to_post_id_image_01(self, project_dir, sample_jpg):
        run_new_post([str(sample_jpg)], cwd=project_dir)
        assert (project_dir / "content" / "1-image-01.jpg").exists()

    def test_second_image_numbered_02(self, project_dir, tmp_path):
        img1 = project_dir / "photo1.jpg"
        img2 = project_dir / "photo2.jpg"
        img1.write_bytes(b"\xff\xd8\xff")
        img2.write_bytes(b"\xff\xd8\xff")
        run_new_post([str(img1), str(img2)], cwd=project_dir)
        assert (project_dir / "content" / "1-image-01.jpg").exists()
        assert (project_dir / "content" / "1-image-02.jpg").exists()

    def test_three_images_numbered_01_02_03(self, project_dir):
        for name in ("a.jpg", "b.jpg", "c.jpg"):
            (project_dir / name).write_bytes(b"\xff\xd8\xff")
        run_new_post(
            [str(project_dir / "a.jpg"),
             str(project_dir / "b.jpg"),
             str(project_dir / "c.jpg")],
            cwd=project_dir,
        )
        assert (project_dir / "content" / "1-image-01.jpg").exists()
        assert (project_dir / "content" / "1-image-02.jpg").exists()
        assert (project_dir / "content" / "1-image-03.jpg").exists()

    def test_jpg_extension_preserved(self, project_dir):
        img = project_dir / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff")
        run_new_post([str(img)], cwd=project_dir)
        assert (project_dir / "content" / "1-image-01.jpg").exists()

    def test_jpeg_extension_preserved(self, project_dir):
        img = project_dir / "photo.jpeg"
        img.write_bytes(b"\xff\xd8\xff")
        run_new_post([str(img)], cwd=project_dir)
        assert (project_dir / "content" / "1-image-01.jpeg").exists()

    def test_png_extension_preserved(self, project_dir):
        img = project_dir / "photo.png"
        img.write_bytes(b"\x89PNG\r\n")
        run_new_post([str(img)], cwd=project_dir)
        assert (project_dir / "content" / "1-image-01.png").exists()

    def test_svg_extension_preserved(self, project_dir):
        img = project_dir / "photo.svg"
        img.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        run_new_post([str(img)], cwd=project_dir)
        assert (project_dir / "content" / "1-image-01.svg").exists()

    def test_svg_not_treated_as_title(self, project_dir):
        img = project_dir / "photo.svg"
        img.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        run_new_post([str(img)], cwd=project_dir)
        md = (project_dir / "content" / "1.md").read_text()
        assert "photo.svg" not in md

    def test_image_numbering_uses_zero_padded_two_digits(self, project_dir, sample_jpg):
        run_new_post([str(sample_jpg)], cwd=project_dir)
        assert (project_dir / "content" / "1-image-01.jpg").exists()

    def test_images_ordered_by_argument_position(self, project_dir):
        img_a = project_dir / "alpha.jpg"
        img_b = project_dir / "beta.jpg"
        img_a.write_bytes(b"\xff\xd8\xff")
        img_b.write_bytes(b"\xff\xd8\xff")
        run_new_post([str(img_a), str(img_b)], cwd=project_dir)
        # alpha was first arg so it should be image-01
        content_files = {f.name for f in (project_dir / "content").iterdir()}
        assert "1-image-01.jpg" in content_files
        assert "1-image-02.jpg" in content_files

    def test_image_with_absolute_path(self, project_dir, tmp_path):
        photos = tmp_path / "photos"
        photos.mkdir()
        img = photos / "myphoto.jpg"
        img.write_bytes(b"\xff\xd8\xff")
        run_new_post([str(img)], cwd=project_dir)
        assert (project_dir / "content" / "1-image-01.jpg").exists()

    def test_missing_image_prints_warning(self, project_dir):
        result = run_new_post(["ghost.jpg"], cwd=project_dir)
        assert "ghost.jpg" in result.stdout
        assert "could not be found" in result.stdout.lower()

    def test_missing_image_warning_format(self, project_dir):
        result = run_new_post(["ghost.jpg"], cwd=project_dir)
        assert "Image ghost.jpg could not be found!" in result.stdout

    def test_missing_image_does_not_prevent_md_file_creation(self, project_dir):
        run_new_post(["ghost.jpg"], cwd=project_dir)
        assert (project_dir / "content" / "1.md").exists()

    def test_missing_image_does_not_prevent_other_images_from_copying(self, project_dir):
        img = project_dir / "real.jpg"
        img.write_bytes(b"\xff\xd8\xff")
        run_new_post(["ghost.jpg", str(img)], cwd=project_dir)
        assert (project_dir / "content" / "1-image-01.jpg").exists()

    def test_images_assigned_to_new_post_id_not_existing_ones(self, project_dir_with_posts):
        img = project_dir_with_posts / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff")
        run_new_post([str(img)], cwd=project_dir_with_posts)
        assert (project_dir_with_posts / "content" / "3-image-01.jpg").exists()


# ---------------------------------------------------------------------------
# Success output
# ---------------------------------------------------------------------------

class TestSuccessOutput:

    def test_success_message_printed(self, project_dir):
        result = run_new_post([], cwd=project_dir)
        assert "Post 1 successfully created." in result.stdout

    def test_success_message_uses_correct_post_id(self, project_dir_with_posts):
        result = run_new_post([], cwd=project_dir_with_posts)
        assert "Post 3 successfully created." in result.stdout

    def test_exit_code_is_zero_on_success(self, project_dir):
        result = run_new_post([], cwd=project_dir)
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

class TestCLIInterface:

    def test_help_short_flag(self, tmp_path):
        result = run_new_post(["-h"], cwd=tmp_path)
        assert result.returncode == 0

    def test_help_long_flag(self, tmp_path):
        result = run_new_post(["--help"], cwd=tmp_path)
        assert result.returncode == 0

    def test_help_output_contains_usage(self, tmp_path):
        result = run_new_post(["--help"], cwd=tmp_path)
        output = result.stdout + result.stderr
        assert "new-post.py" in output or "usage" in output.lower()

    def test_empty_invocation_creates_post(self, project_dir):
        result = run_new_post([], cwd=project_dir)
        assert result.returncode == 0
        assert (project_dir / "content" / "1.md").exists()

    def test_title_only_creates_post_with_title(self, project_dir):
        run_new_post(["Hello World"], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "title: Hello World" in content

    def test_image_only_creates_post_and_copies_image(self, project_dir, sample_jpg):
        result = run_new_post([str(sample_jpg)], cwd=project_dir)
        assert result.returncode == 0
        assert (project_dir / "content" / "1-image-01.jpg").exists()

    def test_images_and_title_creates_complete_post(self, project_dir, sample_jpg):
        run_new_post([str(sample_jpg), "My Great Post"], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "title: My Great Post" in content
        assert (project_dir / "content" / "1-image-01.jpg").exists()

    def test_title_after_images_is_recognised_as_title(self, project_dir):
        img = project_dir / "snap.jpg"
        img.write_bytes(b"\xff\xd8\xff")
        run_new_post([str(img), "Post Title"], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "title: Post Title" in content

    def test_non_image_extension_argument_treated_as_title(self, project_dir):
        run_new_post(["not-an-image.txt"], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "title: not-an-image.txt" in content


# ---------------------------------------------------------------------------
# --latest-images
# ---------------------------------------------------------------------------

def make_image(path, content, mtime_offset):
    """Write an image file with distinguishable content and a controlled mtime.

    mtime_offset is in seconds; higher means more recently modified.
    """
    path.write_bytes(content)
    t = time.time() + mtime_offset
    os.utime(path, (t, t))


@pytest.fixture
def images_dir(tmp_path):
    d = tmp_path / "blog_images"
    d.mkdir()
    return d


class TestLatestImages:

    def test_selects_n_most_recently_modified_images(self, project_dir, images_dir):
        make_image(images_dir / "oldest.jpg", b"oldest", -300)
        make_image(images_dir / "middle.jpg", b"middle", -200)
        make_image(images_dir / "newest.jpg", b"newest", -100)
        result = run_new_post(["--latest-images", "2", str(images_dir)], cwd=project_dir)
        assert result.returncode == 0
        copied = {f.read_bytes() for f in (project_dir / "content").glob("1-image-*.jpg")}
        assert copied == {b"newest", b"middle"}

    def test_orders_oldest_in_scope_first(self, project_dir, images_dir):
        make_image(images_dir / "older.jpg", b"older", -200)
        make_image(images_dir / "newer.jpg", b"newer", -100)
        run_new_post(["--latest-images", "2", str(images_dir)], cwd=project_dir)
        content_dir = project_dir / "content"
        assert (content_dir / "1-image-01.jpg").read_bytes() == b"older"
        assert (content_dir / "1-image-02.jpg").read_bytes() == b"newer"

    def test_excluded_older_image_does_not_affect_chronological_order(self, project_dir, images_dir):
        make_image(images_dir / "excluded.jpg", b"excluded", -300)
        make_image(images_dir / "older.jpg", b"older", -200)
        make_image(images_dir / "newer.jpg", b"newer", -100)
        run_new_post(["--latest-images", "2", str(images_dir)], cwd=project_dir)
        content_dir = project_dir / "content"
        assert (content_dir / "1-image-01.jpg").read_bytes() == b"older"
        assert (content_dir / "1-image-02.jpg").read_bytes() == b"newer"

    def test_ignores_non_image_files_in_directory(self, project_dir, images_dir):
        make_image(images_dir / "photo.jpg", b"photo", -100)
        (images_dir / "notes.txt").write_text("not an image")
        result = run_new_post(["--latest-images", "1", str(images_dir)], cwd=project_dir)
        assert result.returncode == 0
        assert (project_dir / "content" / "1-image-01.jpg").exists()

    def test_ignores_images_in_subdirectories(self, project_dir, images_dir):
        make_image(images_dir / "top.jpg", b"top", -200)
        sub = images_dir / "sub"
        sub.mkdir()
        make_image(sub / "nested.jpg", b"nested", -100)
        result = run_new_post(["--latest-images", "1", str(images_dir)], cwd=project_dir)
        assert result.returncode == 0
        assert (project_dir / "content" / "1-image-01.jpg").read_bytes() == b"top"

    def test_errors_when_fewer_images_than_requested(self, project_dir, images_dir):
        make_image(images_dir / "only.jpg", b"only", -100)
        result = run_new_post(["--latest-images", "3", str(images_dir)], cwd=project_dir)
        assert result.returncode != 0
        assert not (project_dir / "content" / "1.md").exists()

    def test_errors_when_directory_does_not_exist(self, project_dir, tmp_path):
        missing = tmp_path / "does_not_exist"
        result = run_new_post(["--latest-images", "1", str(missing)], cwd=project_dir)
        assert result.returncode != 0
        assert not (project_dir / "content" / "1.md").exists()

    def test_requires_directory_argument(self, project_dir):
        result = run_new_post(["--latest-images", "3"], cwd=project_dir)
        assert result.returncode != 0

    def test_combines_with_title(self, project_dir, images_dir):
        make_image(images_dir / "photo.jpg", b"photo", -100)
        run_new_post(["--latest-images", "1", str(images_dir), "My Title"], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "title: My Title" in content
        assert (project_dir / "content" / "1-image-01.jpg").exists()

    def test_md_frontmatter_lists_images_with_placeholders(self, project_dir, images_dir):
        make_image(images_dir / "a.jpg", b"a", -200)
        make_image(images_dir / "b.jpg", b"b", -100)
        run_new_post(["--latest-images", "2", str(images_dir)], cwd=project_dir)
        content = (project_dir / "content" / "1.md").read_text()
        assert "- Image 1" in content
        assert "- Image 2" in content

    def test_uses_post_id_sequencing_like_normal_images(self, project_dir_with_posts, images_dir):
        make_image(images_dir / "photo.jpg", b"photo", -100)
        run_new_post(["--latest-images", "1", str(images_dir)], cwd=project_dir_with_posts)
        assert (project_dir_with_posts / "content" / "3-image-01.jpg").exists()

    def test_rejects_negative_count(self, project_dir, images_dir):
        make_image(images_dir / "photo.jpg", b"photo", -100)
        result = run_new_post(["--latest-images", "-1", str(images_dir)], cwd=project_dir)
        assert result.returncode != 0
        assert not (project_dir / "content" / "1.md").exists()

    def test_unreadable_directory_reports_controlled_error(self, project_dir, images_dir):
        make_image(images_dir / "photo.jpg", b"photo", -100)
        os.chmod(images_dir, 0o000)
        try:
            result = run_new_post(["--latest-images", "1", str(images_dir)], cwd=project_dir)
        finally:
            os.chmod(images_dir, 0o755)
        assert result.returncode != 0
        assert "Traceback" not in result.stderr
        assert not (project_dir / "content" / "1.md").exists()
