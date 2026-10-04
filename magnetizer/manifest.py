import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

_MANIFEST_VERSION = 2
_HASH_CHUNK_SIZE = 1 << 20


def _hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_HASH_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_record(path, prev_record):
    """Return (record, changed) for path, given its previous manifest record (or
    None). Fast path: if size and mtime both match the previous record, reuse its
    stored sha256 without re-reading the file. Otherwise (new file, no previous
    record, or a size/mtime mismatch -- including every file after a fresh
    checkout) hash the file fresh; sha256 is what's actually compared, so a touch
    or a fresh checkout of unchanged content is correctly not a change."""
    stat = path.stat()
    size, mtime = stat.st_size, stat.st_mtime
    if prev_record is not None and prev_record.get("size") == size and prev_record.get("mtime") == mtime:
        return prev_record, False
    sha256 = _hash_file(path)
    changed = prev_record is None or prev_record.get("sha256") != sha256
    return {"sha256": sha256, "size": size, "mtime": mtime}, changed


def is_file_changed(manifest, key, path):
    """Single-file version of the fast-path/hash change check, for callers that
    don't need a full directory scan."""
    path = Path(path)
    if not path.exists():
        return key in manifest
    _, changed = _file_record(path, manifest.get(key))
    return changed


def load_manifest(path):
    p = Path(path)
    if not p.is_file():
        return {}
    data = json.loads(p.read_text())
    if data.get("_version") != _MANIFEST_VERSION:
        return {}
    return data


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


def save_manifest(content_dir, path, resources_dir=None, pages=None, prev_manifest=None):
    prev_manifest = prev_manifest or {}
    data = {"_version": _MANIFEST_VERSION}
    for f in Path(content_dir).iterdir():
        if f.name.startswith('.') or not f.is_file():
            continue
        record, _ = _file_record(f, prev_manifest.get(f.name))
        data[f.name] = record
    if resources_dir is not None:
        resources_dir = Path(resources_dir)
        if resources_dir.exists():
            for f in resources_dir.iterdir():
                if f.name.startswith('.') or not f.is_file():
                    continue
                key = f"resources/{f.name}"
                record, _ = _file_record(f, prev_manifest.get(key))
                data[key] = record
    if pages is not None:
        data["pages"] = pages
    _atomic_write(path, data)


def update_page_dynamic_flag(path, manifest, page_filename, dynamic):
    pages = {**manifest.get("pages", {}), page_filename: {"dynamic": dynamic}}
    updated = {**manifest, "_version": _MANIFEST_VERSION, "pages": pages}
    _atomic_write(path, updated)


def _post_id_from_filename(name):
    m = re.match(r'^(\d+)', name)
    return int(m.group(1)) if m else None


def get_changed_resource_filenames(resources_dir, manifest):
    resources_dir = Path(resources_dir)
    current_files = set()
    changed = set()
    if resources_dir.exists():
        for f in resources_dir.iterdir():
            if f.name.startswith('.') or not f.is_file():
                continue
            current_files.add(f.name)
            key = f"resources/{f.name}"
            if is_file_changed(manifest, key, f):
                changed.add(f.name)

    for key in manifest:
        if key.startswith("resources/"):
            name = key[len("resources/"):]
            if name not in current_files:
                changed.add(name)
    return changed


def get_changed_post_ids(content_dir, manifest):
    content_dir = Path(content_dir)
    current_files = {f.name for f in content_dir.iterdir() if not f.name.startswith('.')}

    changed = set()

    for name in current_files:
        if is_file_changed(manifest, name, content_dir / name):
            post_id = _post_id_from_filename(name)
            if post_id is not None:
                changed.add(post_id)

    for name in manifest:
        if name in ("_version", "pages"):
            continue
        if name.startswith("resources/"):
            continue
        if name not in current_files:
            post_id = _post_id_from_filename(name)
            if post_id is not None:
                changed.add(post_id)

    return changed
