from pathlib import Path
from PIL import Image, ImageOps


def fix_orientation_and_strip_exif(img):
    """Bake EXIF orientation into the pixels, then drop the EXIF block (camera
    model, GPS, timestamps, ...) for privacy. Shared with ingest.py, which
    needs this same step but a different output shape (one downscaled
    content-original per image, not a dist-ready resized+thumbnail pair)."""
    img = ImageOps.exif_transpose(img)
    img.info.pop("exif", None)
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
