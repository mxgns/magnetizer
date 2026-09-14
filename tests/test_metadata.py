"""Tests for magnetizer/metadata.py — load_metadata()"""

import pytest

from magnetizer.metadata import load_metadata


def write_metadata(tmp_path, content):
    p = tmp_path / "metadata.yaml"
    p.write_text(content)
    return p


class TestMissingOrEmpty:

    def test_missing_file_returns_empty_dict(self, tmp_path):
        assert load_metadata(tmp_path / "metadata.yaml") == {}

    def test_empty_file_returns_empty_dict(self, tmp_path):
        p = write_metadata(tmp_path, "")
        assert load_metadata(p) == {}


class TestEntries:

    def test_entry_with_title_only(self, tmp_path):
        p = write_metadata(tmp_path, "archive:\n  title: My archive\n")
        assert load_metadata(p) == {"archive": {"title": "My archive", "description": None}}

    def test_entry_with_description_only(self, tmp_path):
        p = write_metadata(tmp_path, "archive:\n  description: Overview of everything.\n")
        assert load_metadata(p) == {"archive": {"title": None, "description": "Overview of everything."}}

    def test_entry_with_title_and_description(self, tmp_path):
        p = write_metadata(
            tmp_path,
            "archive:\n  title: My archive\n  description: Overview of everything.\n",
        )
        assert load_metadata(p) == {
            "archive": {"title": "My archive", "description": "Overview of everything."},
        }

    def test_multiple_entries_are_independent(self, tmp_path):
        p = write_metadata(
            tmp_path,
            "archive:\n  title: My archive\nsearch:\n  description: Search the site.\n",
        )
        metadata = load_metadata(p)
        assert metadata["archive"] == {"title": "My archive", "description": None}
        assert metadata["search"] == {"title": None, "description": "Search the site."}

    def test_blank_title_treated_as_unset(self, tmp_path):
        p = write_metadata(tmp_path, "archive:\n  title:\n  description: Overview.\n")
        assert load_metadata(p)["archive"]["title"] is None

    def test_blank_description_treated_as_unset(self, tmp_path):
        p = write_metadata(tmp_path, "archive:\n  title: My archive\n  description:\n")
        assert load_metadata(p)["archive"]["description"] is None

    def test_mutating_returned_metadata_does_not_leak_into_next_load(self, tmp_path):
        p = write_metadata(tmp_path, "archive:\n  title: My archive\n")
        metadata = load_metadata(p)
        metadata["archive"]["title"] = "Mutated"
        metadata["search"] = {"title": "Injected", "description": None}
        fresh = load_metadata(p)
        assert fresh == {"archive": {"title": "My archive", "description": None}}


class TestInvalidEntries:

    def test_entry_with_neither_title_nor_description_raises_error(self, tmp_path):
        p = write_metadata(tmp_path, "archive:\n  title:\n  description:\n")
        with pytest.raises(ValueError):
            load_metadata(p)

    def test_entry_that_is_a_plain_string_raises_error(self, tmp_path):
        p = write_metadata(tmp_path, "archive: My archive\n")
        with pytest.raises(ValueError):
            load_metadata(p)

    def test_entry_that_is_an_empty_mapping_raises_error(self, tmp_path):
        p = write_metadata(tmp_path, "archive: {}\n")
        with pytest.raises(ValueError):
            load_metadata(p)

    def test_non_mapping_document_root_raises_error(self, tmp_path):
        p = write_metadata(tmp_path, "- archive\n- search\n")
        with pytest.raises(ValueError):
            load_metadata(p)

    def test_scalar_document_root_raises_error(self, tmp_path):
        p = write_metadata(tmp_path, "just some text\n")
        with pytest.raises(ValueError):
            load_metadata(p)
