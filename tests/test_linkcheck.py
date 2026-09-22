"""Tests for magnetizer.linkcheck — verifying internal links in dist/ resolve
to a file that actually exists, after a build has finished."""

from magnetizer.linkcheck import check_internal_links

SITE_URL = "https://example.github.io"


def _write(dist_dir, name, html):
    (dist_dir / name).write_text(html)


class TestCheckInternalLinks:

    def test_no_warning_when_link_target_exists(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist, "2.html", "<html></html>")
        _write(dist, "1.html", '<a href="2.html">next</a>')
        assert check_internal_links(dist, SITE_URL) == []

    def test_warning_when_link_target_missing(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist, "1.html", '<a href="99.html">missing</a>')
        assert check_internal_links(dist, SITE_URL) == [("1.html", "Broken internal link: '99.html'")]

    def test_root_slash_resolves_to_index_html(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist, "index.html", "<html></html>")
        _write(dist, "1.html", '<a href="/">home</a>')
        assert check_internal_links(dist, SITE_URL) == []

    def test_root_relative_link_resolves_against_dist_root(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist, "2.html", "<html></html>")
        _write(dist, "1.html", '<a href="/2.html">next</a>')
        assert check_internal_links(dist, SITE_URL) == []

    def test_root_relative_link_to_missing_page_warns(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist, "1.html", '<a href="/99.html">missing</a>')
        assert check_internal_links(dist, SITE_URL) == [("1.html", "Broken internal link: '/99.html'")]

    def test_external_link_not_checked(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist, "1.html", '<a href="https://other.example/page">out</a>')
        assert check_internal_links(dist, SITE_URL) == []

    def test_absolute_link_to_own_site_checked(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist, "1.html", f'<a href="{SITE_URL}/99.html">missing</a>')
        warnings = check_internal_links(dist, SITE_URL)
        assert len(warnings) == 1
        assert warnings[0][0] == "1.html"

    def test_mailto_link_not_checked(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist, "1.html", '<a href="mailto:hello@example.com">email</a>')
        assert check_internal_links(dist, SITE_URL) == []

    def test_tel_link_not_checked(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist, "1.html", '<a href="tel:+441234567890">call</a>')
        assert check_internal_links(dist, SITE_URL) == []

    def test_obfuscated_mailto_link_not_checked(self, tmp_path):
        # Python-Markdown's <email@example.com> autolink syntax HTML-entity
        # obfuscates the mailto: href as anti-spam, e.g. &#109;&#97;... for
        # "ma..." -- the literal attribute text never starts with "mailto:".
        dist = tmp_path / "dist"
        dist.mkdir()
        obfuscated = "".join(f"&#{ord(c)};" for c in "mailto:hello@example.com")
        _write(dist, "1.html", f'<a href="{obfuscated}">email</a>')
        assert check_internal_links(dist, SITE_URL) == []

    def test_same_page_fragment_not_checked(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist, "1.html", '<a href="#section">jump</a>')
        assert check_internal_links(dist, SITE_URL) == []

    def test_fragment_on_existing_page_not_flagged(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist, "2.html", "<html></html>")
        _write(dist, "1.html", '<a href="2.html#section">jump</a>')
        assert check_internal_links(dist, SITE_URL) == []

    def test_fragment_on_missing_page_still_flagged(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist, "1.html", '<a href="99.html#section">jump</a>')
        assert check_internal_links(dist, SITE_URL) == [("1.html", "Broken internal link: '99.html#section'")]

    def test_duplicate_broken_link_on_same_page_warns_once(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist, "1.html", '<a href="99.html">a</a><a href="99.html">b</a>')
        warnings = check_internal_links(dist, SITE_URL)
        assert len(warnings) == 1

    def test_broken_link_on_each_page_reported_separately(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist, "1.html", '<a href="99.html">a</a>')
        _write(dist, "2.html", '<a href="99.html">a</a>')
        warnings = check_internal_links(dist, SITE_URL)
        assert sorted(warnings) == [
            ("1.html", "Broken internal link: '99.html'"),
            ("2.html", "Broken internal link: '99.html'"),
        ]

    def test_link_to_missing_resource_file_checked(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        _write(dist, "1.html", '<a href="missing.css">style</a>')
        assert check_internal_links(dist, SITE_URL) == [("1.html", "Broken internal link: 'missing.css'")]

    def test_link_to_existing_resource_file_not_flagged(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        resources = dist / "resources"
        resources.mkdir()
        (resources / "style.css").write_text("body {}")
        _write(dist, "1.html", '<a href="resources/style.css">style</a>')
        assert check_internal_links(dist, SITE_URL) == []

    def test_dotted_directories_ignored_when_resolving_targets(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        git_dir = dist / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("")
        _write(dist, "1.html", '<a href=".git/config">nope</a>')
        assert check_internal_links(dist, SITE_URL) == [("1.html", "Broken internal link: '.git/config'")]

    def test_no_warnings_for_empty_dist(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        assert check_internal_links(dist, SITE_URL) == []
