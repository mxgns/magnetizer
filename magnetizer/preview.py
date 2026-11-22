"""Local HTTP server for previewing a built dist/ — see preview.py."""

import functools
import re
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from magnetizer.manifest import is_file_changed

_COMMENT_SUFFIX = re.compile(r'-comment-\d{2}$')


class _PreviewHandler(SimpleHTTPRequestHandler):
    """Serves dist/ like GitHub Pages does as far as this site relies on it:
    a missing path gets dist/404.html (if built) with a 404 status. Symlinks
    are only followed if they resolve to somewhere inside dist/."""

    def _within_root(self, path):
        root = Path(self.directory).resolve()
        return Path(path).resolve().is_relative_to(root)

    def send_head(self):
        if not self._within_root(self.translate_path(self.path)):
            self.send_error(HTTPStatus.NOT_FOUND)
            return None
        return super().send_head()

    def send_error(self, code, message=None, explain=None):
        not_found_page = Path(self.directory) / "404.html"
        if (
            code != HTTPStatus.NOT_FOUND
            or not not_found_page.is_file()
            or not self._within_root(not_found_page)
        ):
            super().send_error(code, message, explain)
            return
        body = not_found_page.read_bytes()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # keep the terminal quiet; build output is what matters


def make_server(dist_path, port=8000):
    """Return a server (not yet serving) for dist_path, on localhost only."""
    handler = functools.partial(_PreviewHandler, directory=str(dist_path))
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def last_edited_md(content_dir, manifest):
    """The .md file in content_dir changed since manifest was saved (new or
    different content) with the newest mtime, or None if none changed — or
    if there's no previous manifest, so a first build has nothing to compare."""
    if not manifest:
        return None
    changed = [
        f for f in Path(content_dir).glob("*.md")
        if not f.name.startswith(".") and is_file_changed(manifest, f.name, f)
    ]
    if not changed:
        return None
    return max(changed, key=lambda f: f.stat().st_mtime).name


def page_for_md(md_name, config):
    """The dist/ page an .md file ends up on: its own page, or for a comment
    the page it belongs to."""
    stem = _COMMENT_SUFFIX.sub("", md_name[:-len(".md")])
    if stem + ".md" == config.get("404-page-input-filename"):
        return config["404-page-output-filename"]
    return f"{stem}.html"
