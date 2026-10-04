"""Tests for magnetizer/gps.py — count_gps_images()"""

from PIL import Image

from magnetizer.gps import count_gps_images


def _make_plain_jpeg(path):
    Image.new("RGB", (4, 4)).save(path)


def _make_jpeg_with_gps(path):
    img = Image.new("RGB", (4, 4))
    exif = img.getexif()
    gps_ifd = {1: "N", 2: (51, 30, 0), 3: "W", 4: (0, 7, 0)}
    exif[0x8825] = gps_ifd  # GPS IFD pointer
    img.save(path, exif=exif)


class TestCountGpsImages:

    def test_no_images_returns_zero_zero(self, tmp_path):
        assert count_gps_images(tmp_path) == (0, 0)

    def test_plain_image_has_no_gps(self, tmp_path):
        _make_plain_jpeg(tmp_path / "1.jpg")
        assert count_gps_images(tmp_path) == (1, 0)

    def test_image_with_gps_is_counted(self, tmp_path):
        _make_jpeg_with_gps(tmp_path / "1.jpg")
        assert count_gps_images(tmp_path) == (1, 1)

    def test_mixed_images_counted_correctly(self, tmp_path):
        _make_plain_jpeg(tmp_path / "1.jpg")
        _make_jpeg_with_gps(tmp_path / "2.jpg")
        _make_plain_jpeg(tmp_path / "3.jpg")
        assert count_gps_images(tmp_path) == (3, 1)

    def test_scans_subdirectories(self, tmp_path):
        (tmp_path / "sub").mkdir()
        _make_jpeg_with_gps(tmp_path / "sub" / "1.jpg")
        assert count_gps_images(tmp_path) == (1, 1)

    def test_non_image_files_are_ignored(self, tmp_path):
        (tmp_path / "notes.txt").write_text("hello")
        (tmp_path / "page.html").write_text("<html></html>")
        assert count_gps_images(tmp_path) == (0, 0)

    def test_case_insensitive_extension(self, tmp_path):
        _make_jpeg_with_gps(tmp_path / "1.JPG")
        assert count_gps_images(tmp_path) == (1, 1)

    def test_png_is_scanned(self, tmp_path):
        Image.new("RGB", (4, 4)).save(tmp_path / "1.png")
        assert count_gps_images(tmp_path) == (1, 0)
