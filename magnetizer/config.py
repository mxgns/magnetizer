from copy import deepcopy
from pathlib import Path

import yaml

DEFAULTS = {
    "site_name": "My Blog",
    "site_url": "",
    "image_max_dimension": 1600,
    "image_quality": 75,
    "thumbnail_max_dimension": 400,
    "thumbnail_quality": 70,
    "posts_per_page": 12,
    "notes_per_page": 20,
    "gallery_per_page": 60,
    "images_per_post": 2,
    "feed_max_posts": 30,
    "index_meta_description": None,
    "index_title": None,
    "categories": {},
    "navigation": {},
    "special_pages": [],
    "ai_disclosure_html": None,
    "404-page-input-filename": None,
    "404-page-output-filename": None,
}


def _normalize_categories(raw_categories):
    normalized = {}
    for slug, value in raw_categories.items():
        if not isinstance(value, dict) or not value.get("name"):
            raise ValueError(
                f"category '{slug}' in config.yaml must be a mapping with at least a 'name' key, e.g.:\n"
                f"categories:\n  {slug}:\n    name: ...\n    description: ... (optional)"
            )
        normalized[slug] = {"name": value["name"], "description": value.get("description") or None}
    return normalized


def load_config(path):
    config = deepcopy(DEFAULTS)
    p = Path(path)
    if p.is_file():
        data = yaml.safe_load(p.read_text()) or {}
        if "site_name" not in data and "site_title" in data:
            data["site_name"] = data["site_title"]
        for key in DEFAULTS:
            if key in data:
                config[key] = data[key]
    config["categories"] = _normalize_categories(config["categories"])
    if config["notes_per_page"] < 1:
        raise ValueError("notes_per_page must be a positive integer")
    if config["gallery_per_page"] < 1:
        raise ValueError("gallery_per_page must be a positive integer")
    if config["images_per_post"] < 0:
        raise ValueError("images_per_post must not be negative")
    if config["feed_max_posts"] < 1:
        raise ValueError("feed_max_posts must be a positive integer")
    return config
