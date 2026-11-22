"""Tests for magnetizer.preview — the local HTTP server behind preview.py"""

import threading
import urllib.error
import urllib.request

import pytest

from magnetizer.preview import make_server


@pytest.fixture
def serve(tmp_path):
    servers = []

    def _serve(dist):
        server = make_server(dist, port=0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield _serve
    for server in servers:
        server.shutdown()
        server.server_close()


def fetch(url):
    try:
        with urllib.request.urlopen(url) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


class TestMakeServer:

    def test_binds_to_localhost_only(self, tmp_path):
        server = make_server(tmp_path, port=0)
        try:
            assert server.server_address[0] == "127.0.0.1"
        finally:
            server.server_close()

    def test_serves_files_from_dist(self, tmp_path, serve):
        (tmp_path / "37.html").write_text("<p>post 37</p>")
        assert fetch(serve(tmp_path) + "/37.html") == (200, "<p>post 37</p>")

    def test_serves_index_html_at_root(self, tmp_path, serve):
        (tmp_path / "index.html").write_text("<p>home</p>")
        assert fetch(serve(tmp_path) + "/") == (200, "<p>home</p>")

    def test_serves_root_relative_resource_paths(self, tmp_path, serve):
        (tmp_path / "resources").mkdir()
        (tmp_path / "resources" / "style.css").write_text("body {}")
        assert fetch(serve(tmp_path) + "/resources/style.css") == (200, "body {}")

    def test_ignores_query_string(self, tmp_path, serve):
        (tmp_path / "style.css").write_text("body {}")
        assert fetch(serve(tmp_path) + "/style.css?v=123") == (200, "body {}")

    def test_missing_page_serves_custom_404_page(self, tmp_path, serve):
        (tmp_path / "404.html").write_text("<p>not here</p>")
        assert fetch(serve(tmp_path) + "/nope.html") == (404, "<p>not here</p>")

    def test_missing_page_without_404_page_still_returns_404(self, tmp_path, serve):
        status, _ = fetch(serve(tmp_path) + "/nope.html")
        assert status == 404

    def test_does_not_serve_files_outside_dist(self, tmp_path, serve):
        dist = tmp_path / "dist"
        dist.mkdir()
        (tmp_path / "secret.txt").write_text("secret")
        status, body = fetch(serve(dist) + "/../secret.txt")
        assert "secret" not in body

    def test_does_not_follow_symlinks_out_of_dist(self, tmp_path, serve):
        dist = tmp_path / "dist"
        dist.mkdir()
        (tmp_path / "secret.txt").write_text("secret")
        (dist / "leak.txt").symlink_to(tmp_path / "secret.txt")
        status, body = fetch(serve(dist) + "/leak.txt")
        assert status == 404
        assert "secret" not in body

    def test_does_not_follow_symlinked_directory_out_of_dist(self, tmp_path, serve):
        dist = tmp_path / "dist"
        dist.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("secret")
        (dist / "linked").symlink_to(outside)
        status, body = fetch(serve(dist) + "/linked/secret.txt")
        assert status == 404
        assert "secret" not in body

    def test_symlinked_404_page_outside_dist_is_not_served(self, tmp_path, serve):
        dist = tmp_path / "dist"
        dist.mkdir()
        (tmp_path / "secret.txt").write_text("secret")
        (dist / "404.html").symlink_to(tmp_path / "secret.txt")
        status, body = fetch(serve(dist) + "/nope.html")
        assert status == 404
        assert "secret" not in body

    def test_symlinks_within_dist_still_work(self, tmp_path, serve):
        (tmp_path / "real.html").write_text("<p>real</p>")
        (tmp_path / "alias.html").symlink_to(tmp_path / "real.html")
        assert fetch(serve(tmp_path) + "/alias.html") == (200, "<p>real</p>")


class TestLastEditedMd:

    def _build_manifest(self, content):
        from magnetizer.manifest import load_manifest, save_manifest
        save_manifest(content, content.parent / "manifest.json")
        return load_manifest(content.parent / "manifest.json")

    def _content(self, tmp_path, *names):
        content = tmp_path / "content"
        content.mkdir()
        for name in names:
            (content / name).write_text(f"# {name}\n")
        return content

    def _edit(self, path, text, mtime):
        import os
        path.write_text(text)
        os.utime(path, (mtime, mtime))

    def test_none_when_nothing_changed(self, tmp_path):
        from magnetizer.preview import last_edited_md
        content = self._content(tmp_path, "1.md", "2.md")
        manifest = self._build_manifest(content)
        assert last_edited_md(content, manifest) is None

    def test_none_without_a_previous_manifest(self, tmp_path):
        from magnetizer.preview import last_edited_md
        content = self._content(tmp_path, "1.md")
        assert last_edited_md(content, {}) is None

    def test_returns_edited_md(self, tmp_path):
        from magnetizer.preview import last_edited_md
        content = self._content(tmp_path, "1.md", "2.md")
        manifest = self._build_manifest(content)
        self._edit(content / "2.md", "# changed\n", 2_000_000_000)
        assert last_edited_md(content, manifest) == "2.md"

    def test_returns_new_md(self, tmp_path):
        from magnetizer.preview import last_edited_md
        content = self._content(tmp_path, "1.md")
        manifest = self._build_manifest(content)
        (content / "2.md").write_text("# new\n")
        assert last_edited_md(content, manifest) == "2.md"

    def test_most_recently_modified_wins(self, tmp_path):
        from magnetizer.preview import last_edited_md
        content = self._content(tmp_path, "1.md", "2.md", "3.md")
        manifest = self._build_manifest(content)
        self._edit(content / "1.md", "# a\n", 2_000_000_200)
        self._edit(content / "3.md", "# b\n", 2_000_000_100)
        assert last_edited_md(content, manifest) == "1.md"

    def test_touched_but_unchanged_is_ignored(self, tmp_path):
        from magnetizer.preview import last_edited_md
        content = self._content(tmp_path, "1.md")
        manifest = self._build_manifest(content)
        self._edit(content / "1.md", "# 1.md\n", 2_000_000_000)
        assert last_edited_md(content, manifest) is None

    def test_ignores_non_md_files(self, tmp_path):
        from magnetizer.preview import last_edited_md
        content = self._content(tmp_path, "1.md", "1-image-01.jpeg")
        manifest = self._build_manifest(content)
        self._edit(content / "1-image-01.jpeg", "new bytes", 2_000_000_000)
        assert last_edited_md(content, manifest) is None


class TestPageForMd:

    _CONFIG = {"404-page-input-filename": None, "404-page-output-filename": None}

    def test_post(self):
        from magnetizer.preview import page_for_md
        assert page_for_md("12.md", self._CONFIG) == "12.html"

    def test_special_page(self):
        from magnetizer.preview import page_for_md
        assert page_for_md("about.md", self._CONFIG) == "about.html"

    def test_post_comment_goes_to_its_post(self):
        from magnetizer.preview import page_for_md
        assert page_for_md("12-comment-03.md", self._CONFIG) == "12.html"

    def test_special_page_comment_goes_to_its_page(self):
        from magnetizer.preview import page_for_md
        assert page_for_md("about-comment-01.md", self._CONFIG) == "about.html"

    def test_404_page_uses_configured_output_filename(self):
        from magnetizer.preview import page_for_md
        config = {"404-page-input-filename": "error-404.md", "404-page-output-filename": "404.html"}
        assert page_for_md("error-404.md", config) == "404.html"

    def test_404_page_comment_goes_to_configured_output_filename(self):
        from magnetizer.preview import page_for_md
        config = {"404-page-input-filename": "error-404.md", "404-page-output-filename": "404.html"}
        assert page_for_md("error-404-comment-01.md", config) == "404.html"
