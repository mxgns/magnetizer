from pathlib import Path

import yaml


def load_metadata(path):
    p = Path(path)
    if not p.is_file():
        return {}
    data = yaml.safe_load(p.read_text()) or {}
    metadata = {}
    for key, value in data.items():
        if not isinstance(value, dict) or not (value.get("title") or value.get("description")):
            raise ValueError(
                f"metadata.yaml entry '{key}' must be a mapping with a 'title' and/or 'description' key, e.g.:\n"
                f"{key}:\n  title: ...\n  description: ..."
            )
        metadata[key] = {"title": value.get("title") or None, "description": value.get("description") or None}
    return metadata
