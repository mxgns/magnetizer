"""Tests for magnetizer/manifest.py — load, save, and change detection"""

import hashlib
import json
import os
import pytest
from unittest.mock import patch
from magnetizer.manifest import (
    get_changed_post_ids,
    get_changed_resource_filenames,
    is_file_changed,
    load_manifest,
    save_manifest,
    update_page_dynamic_flag,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_content(tmp_path, filenames):
    content = tmp_path / "content"
    content.mkdir(exist_ok=True)
    for name in filenames:
        (content / name).write_bytes(b"x")
    return content


def make_resources(tmp_path, filenames):
    resources = tmp_path / "resources"
    resources.mkdir(exist_ok=True)
    for name in filenames:
        (resources / name).write_bytes(b"x")
    return resources


def record_for(path, data=b"x"):
    """A correct manifest record for a file currently holding `data`."""
    stat = path.stat()
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": stat.st_size,
        "mtime": stat.st_mtime,
    }


# ---------------------------------------------------------------------------
# load_manifest
# ---------------------------------------------------------------------------

class TestLoadManifest:

    def test_returns_empty_dict_when_file_absent(self, tmp_path):
        assert load_manifest(tmp_path / "manifest.json") == {}

    def test_loads_existing_v2_manifest(self, tmp_path):
        data = {"_version": 2, "1.md": {"sha256": "abc", "size": 1, "mtime": 1748123456.0}}
        p = tmp_path / "manifest.json"
        p.write_text(json.dumps(data))
        assert load_manifest(p) == data

    def test_manifest_without_version_key_is_treated_as_absent(self, tmp_path):
        # The earlier mtime-only format had no "_version" key at all.
        data = {"1.md": {"mtime": 1748123456.0}}
        p = tmp_path / "manifest.json"
        p.write_text(json.dumps(data))
        assert load_manifest(p) == {}

    def test_manifest_with_wrong_version_is_treated_as_absent(self, tmp_path):
        data = {"_version": 1, "1.md": {"mtime": 1748123456.0}}
        p = tmp_path / "manifest.json"
        p.write_text(json.dumps(data))
        assert load_manifest(p) == {}

    def test_loads_manifest_with_multiple_entries(self, tmp_path):
        data = {
            "_version": 2,
            "1.md": {"sha256": "aaa", "size": 1, "mtime": 1748123456.0},
            "1-image-01.jpg": {"sha256": "bbb", "size": 2, "mtime": 1748123457.0},
            "2.md": {"sha256": "ccc", "size": 3, "mtime": 1748123789.0},
        }
        p = tmp_path / "manifest.json"
        p.write_text(json.dumps(data))
        assert load_manifest(p) == data


# ---------------------------------------------------------------------------
# save_manifest
# ---------------------------------------------------------------------------

class TestSaveManifest:

    def test_creates_manifest_file(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p)
        assert p.exists()

    def test_manifest_is_valid_json(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p)
        data = json.loads(p.read_text())
        assert isinstance(data, dict)

    def test_manifest_has_version_2(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p)
        data = json.loads(p.read_text())
        assert data["_version"] == 2

    def test_manifest_contains_each_content_file(self, tmp_path):
        content = make_content(tmp_path, ["1.md", "1-image-01.jpg", "2.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p)
        data = json.loads(p.read_text())
        assert set(data.keys()) - {"_version"} == {"1.md", "1-image-01.jpg", "2.md"}

    def test_manifest_entries_have_sha256_size_and_mtime(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p)
        data = json.loads(p.read_text())
        entry = data["1.md"]
        assert isinstance(entry["sha256"], str) and len(entry["sha256"]) == 64
        assert isinstance(entry["size"], int)
        assert isinstance(entry["mtime"], float)

    def test_sha256_matches_file_content(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p)
        data = json.loads(p.read_text())
        assert data["1.md"]["sha256"] == hashlib.sha256(b"x").hexdigest()

    def test_size_matches_file_size(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p)
        data = json.loads(p.read_text())
        assert data["1.md"]["size"] == (content / "1.md").stat().st_size

    def test_mtime_matches_actual_file_mtime(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p)
        actual_mtime = (content / "1.md").stat().st_mtime
        data = json.loads(p.read_text())
        assert data["1.md"]["mtime"] == actual_mtime

    def test_overwrites_existing_manifest(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        p.write_text(json.dumps({"_version": 2, "old.md": {"sha256": "x", "size": 1, "mtime": 0.0}}))
        save_manifest(content, p)
        data = json.loads(p.read_text())
        assert "old.md" not in data
        assert "1.md" in data

    def test_manifest_includes_resource_files_when_resources_dir_given(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        resources = make_resources(tmp_path, ["style.css"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p, resources_dir=resources)
        data = json.loads(p.read_text())
        assert "resources/style.css" in data

    def test_resource_manifest_entry_has_sha256_size_and_mtime(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        resources = make_resources(tmp_path, ["style.css"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p, resources_dir=resources)
        entry = json.loads(p.read_text())["resources/style.css"]
        assert isinstance(entry["sha256"], str) and len(entry["sha256"]) == 64
        assert isinstance(entry["size"], int)
        assert isinstance(entry["mtime"], float)

    def test_manifest_without_resources_dir_excludes_resource_keys(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p)
        data = json.loads(p.read_text())
        assert not any(k.startswith("resources/") for k in data)


# ---------------------------------------------------------------------------
# save_manifest — fast path (reuse stored hash via prev_manifest)
# ---------------------------------------------------------------------------

class TestSaveManifestFastPath:

    def test_unchanged_file_keeps_same_sha256(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p)
        prev = json.loads(p.read_text())

        save_manifest(content, p, prev_manifest=prev)
        data = json.loads(p.read_text())
        assert data["1.md"]["sha256"] == prev["1.md"]["sha256"]

    def test_unchanged_file_is_not_reread(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p)
        prev = json.loads(p.read_text())

        with patch("magnetizer.manifest._hash_file") as mock_hash:
            save_manifest(content, p, prev_manifest=prev)
        mock_hash.assert_not_called()

    def test_file_with_mismatched_size_is_rehashed(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        prev = {"_version": 2, "1.md": {"sha256": "stale", "size": 999, "mtime": (content / "1.md").stat().st_mtime}}

        save_manifest(content, p, prev_manifest=prev)
        data = json.loads(p.read_text())
        assert data["1.md"]["sha256"] == hashlib.sha256(b"x").hexdigest()

    def test_no_prev_manifest_still_works(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p)
        data = json.loads(p.read_text())
        assert data["1.md"]["sha256"] == hashlib.sha256(b"x").hexdigest()


# ---------------------------------------------------------------------------
# save_manifest — pages
# ---------------------------------------------------------------------------

class TestSaveManifestPages:

    def test_omits_pages_key_when_not_given(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p)
        data = json.loads(p.read_text())
        assert "pages" not in data

    def test_writes_pages_dict_when_given(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p, pages={"1.html": {"dynamic": True}})
        data = json.loads(p.read_text())
        assert data["pages"] == {"1.html": {"dynamic": True}}

    def test_empty_pages_dict_is_written_as_is(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p, pages={})
        data = json.loads(p.read_text())
        assert data["pages"] == {}


# ---------------------------------------------------------------------------
# save_manifest — atomicity
# ---------------------------------------------------------------------------

class TestSaveManifestAtomic:

    def test_no_leftover_temp_files_after_save(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        save_manifest(content, p)
        leftovers = [f for f in tmp_path.iterdir() if f.name != "manifest.json" and f.name != "content"]
        assert leftovers == []

    def test_original_manifest_untouched_if_write_fails_partway(self, tmp_path, monkeypatch):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        original = json.dumps({"_version": 2, "sentinel": {"sha256": "x", "size": 1, "mtime": 1.0}})
        p.write_text(original)

        def _boom(*args, **kwargs):
            raise OSError("simulated crash")

        monkeypatch.setattr(os, "replace", _boom)
        with pytest.raises(OSError):
            save_manifest(content, p)

        assert p.read_text() == original

    def test_no_leftover_temp_files_after_failed_write(self, tmp_path, monkeypatch):
        content = make_content(tmp_path, ["1.md"])
        p = tmp_path / "manifest.json"
        p.write_text(json.dumps({"_version": 2}))

        monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
        with pytest.raises(OSError):
            save_manifest(content, p)

        leftovers = [f for f in tmp_path.iterdir() if f.name not in ("manifest.json", "content")]
        assert leftovers == []


# ---------------------------------------------------------------------------
# update_page_dynamic_flag
# ---------------------------------------------------------------------------

class TestUpdatePageDynamicFlag:

    def test_sets_dynamic_flag_for_page(self, tmp_path):
        p = tmp_path / "manifest.json"
        manifest = {"_version": 2, "1.md": {"sha256": "a", "size": 1, "mtime": 1.0}}
        update_page_dynamic_flag(p, manifest, "1.html", True)
        data = json.loads(p.read_text())
        assert data["pages"] == {"1.html": {"dynamic": True}}

    def test_preserves_other_manifest_entries(self, tmp_path):
        p = tmp_path / "manifest.json"
        manifest = {
            "_version": 2,
            "1.md": {"sha256": "a", "size": 1, "mtime": 1.0},
            "2.md": {"sha256": "b", "size": 1, "mtime": 2.0},
        }
        update_page_dynamic_flag(p, manifest, "1.html", False)
        data = json.loads(p.read_text())
        assert data["1.md"] == {"sha256": "a", "size": 1, "mtime": 1.0}
        assert data["2.md"] == {"sha256": "b", "size": 1, "mtime": 2.0}

    def test_preserves_other_pages_entries(self, tmp_path):
        p = tmp_path / "manifest.json"
        manifest = {"_version": 2, "pages": {"about.html": {"dynamic": True}}}
        update_page_dynamic_flag(p, manifest, "1.html", False)
        data = json.loads(p.read_text())
        assert data["pages"] == {
            "about.html": {"dynamic": True},
            "1.html": {"dynamic": False},
        }

    def test_overwrites_existing_page_entry(self, tmp_path):
        p = tmp_path / "manifest.json"
        manifest = {"_version": 2, "pages": {"1.html": {"dynamic": True}}}
        update_page_dynamic_flag(p, manifest, "1.html", False)
        data = json.loads(p.read_text())
        assert data["pages"]["1.html"] == {"dynamic": False}

    def test_is_atomic(self, tmp_path):
        p = tmp_path / "manifest.json"
        update_page_dynamic_flag(p, {}, "1.html", True)
        leftovers = [f for f in tmp_path.iterdir() if f.name != "manifest.json"]
        assert leftovers == []

    def test_writes_version_2_even_from_empty_manifest(self, tmp_path):
        # Guards against a manifest that only ever went through single-file
        # preview builds (no normal build has run yet) being misread as the
        # old mtime-only format on the next load.
        p = tmp_path / "manifest.json"
        update_page_dynamic_flag(p, {}, "1.html", True)
        data = json.loads(p.read_text())
        assert data["_version"] == 2


# ---------------------------------------------------------------------------
# is_file_changed
# ---------------------------------------------------------------------------

class TestIsFileChanged:

    def test_new_file_not_in_manifest_is_changed(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        assert is_file_changed({}, "1.md", content / "1.md") is True

    def test_unchanged_file_matching_manifest_is_not_changed(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        manifest = {"_version": 2, "1.md": record_for(content / "1.md")}
        assert is_file_changed(manifest, "1.md", content / "1.md") is False

    def test_touched_file_with_identical_content_is_not_changed(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        real_record = record_for(content / "1.md")
        # Simulate a fresh checkout / touch: content identical, but the stored
        # mtime no longer matches, so this forces the rehash path rather than
        # the fast path.
        stale_mtime_record = {**real_record, "mtime": real_record["mtime"] + 1000}
        manifest = {"_version": 2, "1.md": stale_mtime_record}
        assert is_file_changed(manifest, "1.md", content / "1.md") is False

    def test_file_with_different_content_is_changed(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        manifest = {"_version": 2, "1.md": {"sha256": "not-the-real-hash", "size": 999, "mtime": 0.0}}
        assert is_file_changed(manifest, "1.md", content / "1.md") is True

    def test_deleted_file_still_in_manifest_is_changed(self, tmp_path):
        content = make_content(tmp_path, [])
        manifest = {"_version": 2, "1.md": {"sha256": "a", "size": 1, "mtime": 1.0}}
        assert is_file_changed(manifest, "1.md", content / "1.md") is True

    def test_fast_path_does_not_reread_file(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        manifest = {"_version": 2, "1.md": record_for(content / "1.md")}
        with patch("magnetizer.manifest._hash_file") as mock_hash:
            is_file_changed(manifest, "1.md", content / "1.md")
        mock_hash.assert_not_called()


# ---------------------------------------------------------------------------
# get_changed_post_ids
# ---------------------------------------------------------------------------

class TestGetChangedPostIds:

    def test_all_posts_changed_when_manifest_empty(self, tmp_path):
        content = make_content(tmp_path, ["1.md", "2.md"])
        changed = get_changed_post_ids(content, {})
        assert changed == {1, 2}

    def test_no_changes_when_content_unchanged(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        manifest = {"_version": 2, "1.md": record_for(content / "1.md")}
        assert get_changed_post_ids(content, manifest) == set()

    def test_touch_without_edit_is_not_a_change(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        real_record = record_for(content / "1.md")
        stale_mtime_record = {**real_record, "mtime": 0.0}
        manifest = {"_version": 2, "1.md": stale_mtime_record}
        assert get_changed_post_ids(content, manifest) == set()

    def test_detects_modified_md_file(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        manifest = {"_version": 2, "1.md": {"sha256": "stale", "size": 999, "mtime": 0.0}}
        assert 1 in get_changed_post_ids(content, manifest)

    def test_detects_new_md_file_not_in_manifest(self, tmp_path):
        content = make_content(tmp_path, ["1.md", "2.md"])
        manifest = {"_version": 2, "1.md": record_for(content / "1.md")}  # 2.md absent
        assert 2 in get_changed_post_ids(content, manifest)

    def test_detects_deleted_md_file(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        manifest = {
            "_version": 2,
            "1.md": record_for(content / "1.md"),
            "2.md": {"sha256": "a", "size": 1, "mtime": 1748123456.0},  # 2.md was deleted
        }
        assert 2 in get_changed_post_ids(content, manifest)

    def test_detects_changed_image_returns_its_post_id(self, tmp_path):
        content = make_content(tmp_path, ["1.md", "1-image-01.jpg"])
        manifest = {
            "_version": 2,
            "1.md": record_for(content / "1.md"),
            "1-image-01.jpg": {"sha256": "stale", "size": 999, "mtime": 0.0},
        }
        assert 1 in get_changed_post_ids(content, manifest)

    def test_detects_new_image_returns_its_post_id(self, tmp_path):
        content = make_content(tmp_path, ["1.md", "1-image-01.jpg"])
        manifest = {"_version": 2, "1.md": record_for(content / "1.md")}  # image not in manifest
        assert 1 in get_changed_post_ids(content, manifest)

    def test_detects_deleted_image_returns_its_post_id(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        manifest = {
            "_version": 2,
            "1.md": record_for(content / "1.md"),
            "1-image-01.jpg": {"sha256": "a", "size": 1, "mtime": 1748123456.0},  # deleted
        }
        assert 1 in get_changed_post_ids(content, manifest)

    def test_unchanged_post_not_included(self, tmp_path):
        content = make_content(tmp_path, ["1.md", "2.md"])
        manifest = {
            "_version": 2,
            "1.md": record_for(content / "1.md"),
            "2.md": {"sha256": "stale", "size": 999, "mtime": 0.0},  # only post 2 changed
        }
        changed = get_changed_post_ids(content, manifest)
        assert 1 not in changed
        assert 2 in changed

    def test_returns_set_of_integers(self, tmp_path):
        content = make_content(tmp_path, ["1.md"])
        result = get_changed_post_ids(content, {})
        assert isinstance(result, set)
        assert all(isinstance(x, int) for x in result)

    def test_unchanged_files_are_not_reread(self, tmp_path):
        content = make_content(tmp_path, ["1.md", "2.md"])
        manifest = {
            "_version": 2,
            "1.md": record_for(content / "1.md"),
            "2.md": record_for(content / "2.md"),
        }
        with patch("magnetizer.manifest._hash_file") as mock_hash:
            get_changed_post_ids(content, manifest)
        mock_hash.assert_not_called()


# ---------------------------------------------------------------------------
# get_changed_resource_filenames
# ---------------------------------------------------------------------------

class TestGetChangedResourceFilenames:

    def test_all_resources_changed_when_manifest_empty(self, tmp_path):
        resources = make_resources(tmp_path, ["style.css"])
        assert get_changed_resource_filenames(resources, {}) == {"style.css"}

    def test_no_changes_when_content_unchanged(self, tmp_path):
        resources = make_resources(tmp_path, ["style.css"])
        manifest = {"_version": 2, "resources/style.css": record_for(resources / "style.css")}
        assert get_changed_resource_filenames(resources, manifest) == set()

    def test_touch_without_edit_is_not_a_change(self, tmp_path):
        resources = make_resources(tmp_path, ["style.css"])
        real_record = record_for(resources / "style.css")
        stale_mtime_record = {**real_record, "mtime": 0.0}
        manifest = {"_version": 2, "resources/style.css": stale_mtime_record}
        assert get_changed_resource_filenames(resources, manifest) == set()

    def test_detects_modified_resource_file(self, tmp_path):
        resources = make_resources(tmp_path, ["style.css"])
        manifest = {"_version": 2, "resources/style.css": {"sha256": "stale", "size": 999, "mtime": 0.0}}
        assert "style.css" in get_changed_resource_filenames(resources, manifest)

    def test_detects_new_resource_file_not_in_manifest(self, tmp_path):
        resources = make_resources(tmp_path, ["style.css", "extra.css"])
        manifest = {"_version": 2, "resources/style.css": record_for(resources / "style.css")}
        assert "extra.css" in get_changed_resource_filenames(resources, manifest)

    def test_detects_deleted_resource_file(self, tmp_path):
        resources = make_resources(tmp_path, ["style.css"])
        manifest = {
            "_version": 2,
            "resources/style.css": record_for(resources / "style.css"),
            "resources/old.css": {"sha256": "a", "size": 1, "mtime": 1748123456.0},
        }
        assert "old.css" in get_changed_resource_filenames(resources, manifest)

    def test_unchanged_resource_not_included(self, tmp_path):
        resources = make_resources(tmp_path, ["style.css", "extra.css"])
        manifest = {
            "_version": 2,
            "resources/style.css": record_for(resources / "style.css"),
            "resources/extra.css": {"sha256": "stale", "size": 999, "mtime": 0.0},
        }
        changed = get_changed_resource_filenames(resources, manifest)
        assert "style.css" not in changed
        assert "extra.css" in changed

    def test_returns_set_of_strings(self, tmp_path):
        resources = make_resources(tmp_path, ["style.css"])
        result = get_changed_resource_filenames(resources, {})
        assert isinstance(result, set)
        assert all(isinstance(x, str) for x in result)

    def test_unchanged_files_are_not_reread(self, tmp_path):
        resources = make_resources(tmp_path, ["style.css"])
        manifest = {"_version": 2, "resources/style.css": record_for(resources / "style.css")}
        with patch("magnetizer.manifest._hash_file") as mock_hash:
            get_changed_resource_filenames(resources, manifest)
        mock_hash.assert_not_called()
