import json
import os
import re
import tempfile
from pathlib import Path


def load_manifest(path):
    p = Path(path)
    if not p.is_file():
        return {}
    return json.loads(p.read_text())


def _atomic_write(path, data):
    path = Path(path)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(json.dumps(data, indent=2))
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def save_manifest(content_dir, path, resources_dir=None, pages=None):
    data = {}
    for f in Path(content_dir).iterdir():
        if not f.name.startswith('.'):
            data[f.name] = {"mtime": f.stat().st_mtime}
    if resources_dir is not None:
        resources_dir = Path(resources_dir)
        if resources_dir.exists():
            for f in resources_dir.iterdir():
                if not f.name.startswith('.'):
                    data[f"resources/{f.name}"] = {"mtime": f.stat().st_mtime}
    if pages is not None:
        data["pages"] = pages
    _atomic_write(path, data)


def update_page_dynamic_flag(path, manifest, page_filename, dynamic):
    pages = {**manifest.get("pages", {}), page_filename: {"dynamic": dynamic}}
    updated = {**manifest, "pages": pages}
    _atomic_write(path, updated)


def _post_id_from_filename(name):
    m = re.match(r'^(\d+)', name)
    return int(m.group(1)) if m else None


def get_changed_resource_filenames(resources_dir, manifest):
    resources_dir = Path(resources_dir)
    current_files = {}
    if resources_dir.exists():
        for f in resources_dir.iterdir():
            if not f.name.startswith('.'):
                current_files[f.name] = f.stat().st_mtime

    changed = set()
    for name, mtime in current_files.items():
        key = f"resources/{name}"
        if key not in manifest or manifest[key]["mtime"] != mtime:
            changed.add(name)
    for key in manifest:
        if key.startswith("resources/"):
            name = key[len("resources/"):]
            if name not in current_files:
                changed.add(name)
    return changed


def get_changed_post_ids(content_dir, manifest):
    content_dir = Path(content_dir)
    current_files = {
        f.name: f.stat().st_mtime
        for f in content_dir.iterdir()
        if not f.name.startswith('.')
    }

    changed = set()

    for name, mtime in current_files.items():
        if name not in manifest or manifest[name]["mtime"] != mtime:
            post_id = _post_id_from_filename(name)
            if post_id is not None:
                changed.add(post_id)

    for name in manifest:
        if name not in current_files:
            post_id = _post_id_from_filename(name)
            if post_id is not None:
                changed.add(post_id)

    return changed
