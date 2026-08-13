"""Tests for magnetizer/posts_index.py — render_posts_index()"""

import json

from magnetizer.posts_index import render_posts_index


class TestRenderPostsIndex:

    def test_returns_valid_json(self):
        result = render_posts_index([(1, "My Post", "photography", "2026-05-24")])
        json.loads(result)

    def test_empty_entries_produces_empty_object(self):
        result = render_posts_index([])
        assert json.loads(result) == {}

    def test_id_used_as_object_key(self):
        data = json.loads(render_posts_index([(1, "My Post", None, None)]))
        assert "1" in data

    def test_string_id_used_as_object_key(self):
        data = json.loads(render_posts_index([("about", "About", None, None)]))
        assert "about" in data

    def test_title_field(self):
        data = json.loads(render_posts_index([(1, "My Post", None, None)]))
        assert data["1"]["title"] == "My Post"

    def test_category_field(self):
        data = json.loads(render_posts_index([(1, "My Post", "photography", None)]))
        assert data["1"]["category"] == "photography"

    def test_category_null_when_none(self):
        data = json.loads(render_posts_index([(1, "My Post", None, None)]))
        assert data["1"]["category"] is None

    def test_date_field(self):
        data = json.loads(render_posts_index([(1, "My Post", None, "2026-05-24")]))
        assert data["1"]["date"] == "2026-05-24"

    def test_date_null_when_none(self):
        data = json.loads(render_posts_index([(1, "My Post", None, None)]))
        assert data["1"]["date"] is None

    def test_multiple_entries_all_present(self):
        data = json.loads(render_posts_index([
            (1, "First Post", "travel", "2026-05-24"),
            (2, "Second Post", "photography", "2026-05-25"),
            ("index", "Test Blog", None, None),
        ]))
        assert set(data.keys()) == {"1", "2", "index"}
        assert data["2"]["title"] == "Second Post"
        assert data["index"]["title"] == "Test Blog"
