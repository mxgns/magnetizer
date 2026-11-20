"""Local HTTP server for previewing a built dist/ — see preview.py."""

import functools
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class _PreviewHandler(SimpleHTTPRequestHandler):
    """Serves dist/ like GitHub Pages does as far as this site relies on it:
    a missing path gets dist/404.html (if built) with a 404 status."""

    def send_error(self, code, message=None, explain=None):
        not_found_page = Path(self.directory) / "404.html"
        if code != HTTPStatus.NOT_FOUND or not not_found_page.is_file():
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
