from pathlib import Path

from PIL import Image

_GPS_IFD_TAG = 0x8825
_SCAN_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def count_gps_images(directory):
    """Scan every raster image under directory and return (total_scanned,
    with_gps) — counts only, never GPS values or filenames, since this is
    meant to run against real published output."""
    total = 0
    with_gps = 0
    for path in Path(directory).rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _SCAN_EXTENSIONS:
            continue
        total += 1
        with Image.open(path) as img:
            if _GPS_IFD_TAG in img.getexif():
                with_gps += 1
    return total, with_gps
