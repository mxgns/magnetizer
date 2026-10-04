"""CLI integration tests for check_gps.py"""

import subprocess
import sys
from pathlib import Path

from PIL import Image

SCRIPT = Path(__file__).parent.parent / "check_gps.py"


def run(args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def _make_plain_jpeg(path):
    Image.new("RGB", (4, 4)).save(path)


def _make_jpeg_with_gps(path):
    img = Image.new("RGB", (4, 4))
    exif = img.getexif()
    exif[0x8825] = {1: "N", 2: (51, 30, 0), 3: "W", 4: (0, 7, 0)}
    img.save(path, exif=exif)


class TestHelp:

    def test_help_exits_zero(self, tmp_path):
        assert run(["--help"], cwd=tmp_path).returncode == 0


class TestDefaultDirectory:

    def test_defaults_to_dist(self, tmp_path):
        (tmp_path / "dist").mkdir()
        _make_plain_jpeg(tmp_path / "dist" / "1.jpg")
        result = run([], cwd=tmp_path)
        assert result.returncode == 0
        assert "Scanned 1 image" in result.stdout
        assert "0 carry GPS" in result.stdout


class TestExitCode:

    def test_exits_zero_when_no_gps_found(self, tmp_path):
        (tmp_path / "dist").mkdir()
        _make_plain_jpeg(tmp_path / "dist" / "1.jpg")
        assert run([], cwd=tmp_path).returncode == 0

    def test_exits_nonzero_when_gps_found(self, tmp_path):
        (tmp_path / "dist").mkdir()
        _make_jpeg_with_gps(tmp_path / "dist" / "1.jpg")
        result = run([], cwd=tmp_path)
        assert result.returncode == 1
        assert "1 carry GPS" in result.stdout


class TestExplicitDirectory:

    def test_scans_given_directory(self, tmp_path):
        (tmp_path / "other").mkdir()
        _make_jpeg_with_gps(tmp_path / "other" / "1.jpg")
        result = run(["other"], cwd=tmp_path)
        assert "1 carry GPS" in result.stdout


class TestNoLeakedValues:

    def test_output_never_contains_filenames_or_coordinates(self, tmp_path):
        (tmp_path / "dist").mkdir()
        _make_jpeg_with_gps(tmp_path / "dist" / "secret-location.jpg")
        result = run([], cwd=tmp_path)
        assert "secret-location" not in result.stdout
        assert "51" not in result.stdout
