from pathlib import Path
from PIL import Image, ImageOps


def resize_image(src, dest, max_dimension, quality):
    img = Image.open(src)
    # Bake EXIF orientation into the pixels before the EXIF block is dropped below,
    # so rotated phone/camera photos still display right-side up without it.
    img = ImageOps.exif_transpose(img)
    img.info.pop("exif", None)  # strip all EXIF (camera model, GPS, timestamps, ...) for privacy
    w, h = img.size
    long_edge = max(w, h)
    if long_edge > max_dimension:
        scale = max_dimension / long_edge
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    img.save(dest, quality=quality, optimize=True)


def image_dimensions(path):
    with Image.open(path) as img:
        return img.size
