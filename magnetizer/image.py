from pathlib import Path
from PIL import Image, ImageOps


def fix_orientation_and_strip_exif(img):
    """Bake EXIF orientation into the pixels, then drop EXIF and any ICC
    colour profile (camera model, GPS, timestamps, ...) for privacy. Shared
    with ingest.py, which needs this same step but a different output shape
    (one downscaled content-original per image, not a dist-ready
    resized+thumbnail pair)."""
    img = ImageOps.exif_transpose(img)
    img.info.pop("exif", None)
    img.info.pop("icc_profile", None)
    return img


def resize_image(src, dest, max_dimension, quality):
    img = Image.open(src)
    img = fix_orientation_and_strip_exif(img)
    w, h = img.size
    long_edge = max(w, h)
    if long_edge > max_dimension:
        scale = max_dimension / long_edge
        img = img.resize((round(w * scale), round(h * scale)), Image.Resampling.LANCZOS)
    img.save(dest, quality=quality, optimize=True)


def image_dimensions(path):
    with Image.open(path) as img:
        return img.size


_ORIENTATION_TAG = 0x0112
_SWAPPED_ORIENTATIONS = {5, 6, 7, 8}


def source_image_dimensions(path):
    """Like image_dimensions(), but for a content/ source file rather than an
    already-resized dist/ one -- so it corrects for EXIF orientation itself,
    since resize_image() hasn't baked that in yet for this file. Reads the
    Orientation tag directly and swaps width/height for the four
    orientations that rotate 90 degrees, rather than calling
    ImageOps.exif_transpose(), which would decode the full image's pixels
    just to answer a question its header already has the answer to."""
    with Image.open(path) as img:
        w, h = img.size
        orientation = img.getexif().get(_ORIENTATION_TAG, 1)
    return (h, w) if orientation in _SWAPPED_ORIENTATIONS else (w, h)
