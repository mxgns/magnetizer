"""Tests for magnetizer/content.py — Post dataclass and parse_post()"""

import pytest
from magnetizer.content import Post, parse_post, Comment, parse_comment, special_page_comment_pattern, thumbnail_filename


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_md(date="2026-05-24", title=None, body="", category=None):
    """Build a minimal markdown string with frontmatter."""
    lines = ["---", f"date: {date}"]
    if title:
        lines.append(f"title: {title}")
    if category is not None:
        lines.append(f"category: {category}")
    lines.append("---")
    if body:
        lines.append("")
        lines.append(body)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Post dataclass
# ---------------------------------------------------------------------------

class TestPostDataclass:

    def test_post_id(self):
        post = parse_post(make_md(), 7, [])
        assert post.id == 7

    def test_post_url(self):
        post = parse_post(make_md(), 7, [])
        assert post.url == "7.html"


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

class TestFrontmatterParsing:

    def test_date_extracted(self):
        post = parse_post(make_md(date="2026-05-24"), 1, [])
        assert post.date == "2026-05-24"

    def test_title_extracted_when_present(self):
        post = parse_post(make_md(title="My Great Post"), 1, [])
        assert post.title == "My Great Post"

    def test_title_is_none_when_absent(self):
        post = parse_post(make_md(), 1, [])
        assert post.title is None

    def test_title_with_colon_preserved(self):
        post = parse_post(make_md(title="Hello: World"), 1, [])
        assert post.title == "Hello: World"

    def test_blank_title_treated_as_unset(self):
        md = "---\ndate: 2026-05-24\ntitle:\n---\nSome body text\n"
        post = parse_post(md, 1, [])
        assert post.title is None

    def test_whitespace_only_title_treated_as_unset(self):
        md = "---\ndate: 2026-05-24\ntitle:   \n---\nSome body text\n"
        post = parse_post(md, 1, [])
        assert post.title is None


# ---------------------------------------------------------------------------
# name frontmatter field
# ---------------------------------------------------------------------------

class TestNameFrontmatter:

    def test_name_extracted_when_present(self):
        md = "---\ndate: 2026-05-24\nname: Sunset over the harbour\n---\n"
        post = parse_post(md, 1, [])
        assert post.name == "Sunset over the harbour"

    def test_name_is_none_when_absent(self):
        post = parse_post(make_md(), 1, [])
        assert post.name is None

    def test_name_key_does_not_trigger_unknown_key_warning(self, capsys):
        md = "---\ndate: 2026-05-24\nname: A note\n---\n"
        parse_post(md, 1, [])
        assert "Warning" not in capsys.readouterr().out

    def test_blank_name_treated_as_unset(self):
        md = "---\ndate: 2026-05-24\nname:\n---\nSome body text\n"
        post = parse_post(md, 1, [])
        assert post.name is None

    def test_whitespace_only_name_treated_as_unset(self):
        md = "---\ndate: 2026-05-24\nname:   \n---\nSome body text\n"
        post = parse_post(md, 1, [])
        assert post.name is None

    def test_name_still_stored_when_title_also_set(self):
        # parse_post doesn't apply title/name precedence itself — it just
        # reports what's in the frontmatter; the consumer decides which wins.
        md = "---\ndate: 2026-05-24\ntitle: Real Title\nname: Fallback name\n---\n"
        post = parse_post(md, 1, [])
        assert post.title == "Real Title"
        assert post.name == "Fallback name"


# ---------------------------------------------------------------------------
# Post type classification
# ---------------------------------------------------------------------------

class TestPostType:

    def test_full_when_title_set(self):
        post = parse_post(make_md(title="My Title"), 1, [])
        assert post.post_type == "full"

    def test_full_when_title_set_with_images_and_content(self):
        post = parse_post(make_md(title="My Title", body="Some text"), 1, ["1-image-01.jpg"])
        assert post.post_type == "full"

    def test_full_when_title_set_with_no_images_or_content(self):
        post = parse_post(make_md(title="My Title"), 1, [])
        assert post.post_type == "full"

    def test_image_when_no_title_and_top_level_image(self):
        post = parse_post(make_md(), 1, ["1-image-01.jpg"])
        assert post.post_type == "image"

    def test_image_when_no_title_multiple_images_and_content(self):
        post = parse_post(make_md(body="Caption"), 1, ["1-image-01.jpg", "1-image-02.jpg"])
        assert post.post_type == "image"

    def test_note_when_no_title_no_images_with_content(self):
        post = parse_post(make_md(body="Just some thoughts."), 1, [])
        assert post.post_type == "note"

    def test_note_regardless_of_length(self):
        # Notes have no length cap, unlike the old microblog classification.
        post = parse_post(make_md(body="x" * 500), 1, [])
        assert post.post_type == "note"

    def test_note_when_only_inline_image_and_text(self):
        md = "---\ndate: 2026-05-24\n---\nSome text.\n\n{{ image 1 }}\n"
        post = parse_post(md, 1, ["1-image-01.jpg"])
        assert post.post_type == "note"

    def test_note_when_only_inline_image_and_no_other_text(self):
        md = "---\ndate: 2026-05-24\n---\n{{ image 1 }}\n"
        post = parse_post(md, 1, ["1-image-01.jpg"])
        assert post.post_type == "note"

    def test_image_when_top_level_image_alongside_inline_image(self):
        md = "---\ndate: 2026-05-24\n---\n{{ image 1 }}\n"
        post = parse_post(md, 1, ["1-image-01.jpg", "1-image-02.jpg"])
        # image 2 is never referenced inline, so it's a top-level image
        assert post.post_type == "image"

    def test_blank_title_falls_back_to_classification(self):
        md = "---\ndate: 2026-05-24\ntitle:\n---\nSome text.\n"
        post = parse_post(md, 1, [])
        assert post.post_type == "note"

    def test_post_type_none_when_no_title_no_images_no_content(self):
        # parse_post doesn't raise here — flagging this as invalid and
        # erroring the build is the caller's responsibility.
        post = parse_post(make_md(), 1, [])
        assert post.post_type is None

    def test_post_type_none_when_body_is_whitespace_only(self):
        md = "---\ndate: 2026-05-24\n---\n   \n\n   \n"
        post = parse_post(md, 1, [])
        assert post.post_type is None


# ---------------------------------------------------------------------------
# UK date formatting
# ---------------------------------------------------------------------------

class TestDateUK:

    def test_date_uk_format(self):
        post = parse_post(make_md(date="2026-05-24"), 1, [])
        assert post.date_uk == "24 May 2026"

    def test_date_uk_no_leading_zero_on_day(self):
        post = parse_post(make_md(date="2026-05-04"), 1, [])
        assert post.date_uk == "4 May 2026"

    def test_date_uk_january(self):
        post = parse_post(make_md(date="2026-01-01"), 1, [])
        assert post.date_uk == "1 January 2026"

    def test_date_uk_december(self):
        post = parse_post(make_md(date="2026-12-31"), 1, [])
        assert post.date_uk == "31 December 2026"


# ---------------------------------------------------------------------------
# Markdown body → HTML
# ---------------------------------------------------------------------------

class TestBodyHtml:

    def test_empty_body_produces_empty_string(self):
        post = parse_post(make_md(), 1, [])
        assert post.body_html == ""

    def test_paragraph_converted_to_html(self):
        post = parse_post(make_md(body="Hello world"), 1, [])
        assert "<p>Hello world</p>" in post.body_html

    def test_bold_converted_to_strong(self):
        post = parse_post(make_md(body="Hello **world**"), 1, [])
        assert "<strong>world</strong>" in post.body_html

    def test_heading_converted(self):
        post = parse_post(make_md(body="## Section"), 1, [])
        assert "<h2>Section</h2>" in post.body_html

    def test_link_converted(self):
        post = parse_post(make_md(body="[click](http://example.com)"), 1, [])
        assert 'href="http://example.com"' in post.body_html

    def test_multiple_paragraphs(self):
        post = parse_post(make_md(body="First\n\nSecond"), 1, [])
        assert post.body_html.count("<p>") == 2

    def test_frontmatter_not_included_in_body(self):
        post = parse_post(make_md(date="2026-05-24", title="My Title"), 1, [])
        assert "2026-05-24" not in post.body_html
        assert "My Title" not in post.body_html

    def test_mark_syntax_converted_to_mark_element(self):
        post = parse_post(make_md(body="This is ==highlighted== text"), 1, [])
        assert "<mark>highlighted</mark>" in post.body_html

    def test_mark_syntax_in_excerpt_converted_to_mark_element(self):
        body = "Before ==marked==<!-- more -->After"
        post = parse_post(make_md(body=body), 1, [])
        assert post.excerpt_html is not None
        assert "<mark>marked</mark>" in post.excerpt_html

    def test_table_syntax_converted_to_table_element(self):
        body = (
            "| Column 1 | Column 2 |\n"
            "|----------|----------|\n"
            "| Item 1   | Item 2   |"
        )
        post = parse_post(make_md(body=body), 1, [])
        assert "<table>" in post.body_html
        assert "<th>Column 1</th>" in post.body_html
        assert "<td>Item 1</td>" in post.body_html


# ---------------------------------------------------------------------------
# External links
# ---------------------------------------------------------------------------

class TestExternalLinks:

    def test_absolute_link_gets_target_blank_and_rel_noopener(self):
        body = "[click](https://example.com)"
        post = parse_post(make_md(body=body), 1, [], site_url="https://mxgns.uk")
        assert 'target="_blank"' in post.body_html
        assert 'rel="noopener"' in post.body_html

    def test_absolute_link_gets_external_link_class(self):
        body = "[click](https://example.com)"
        post = parse_post(make_md(body=body), 1, [], site_url="https://mxgns.uk")
        assert 'class="external-link"' in post.body_html

    def test_relative_link_is_untouched(self):
        body = "[click](/about.html)"
        post = parse_post(make_md(body=body), 1, [], site_url="https://mxgns.uk")
        assert post.body_html == '<p><a href="/about.html">click</a></p>'

    def test_link_starting_with_site_url_is_untouched(self):
        body = "[click](https://mxgns.uk/5.html)"
        post = parse_post(make_md(body=body), 1, [], site_url="https://mxgns.uk")
        assert post.body_html == '<p><a href="https://mxgns.uk/5.html">click</a></p>'

    def test_raw_html_link_with_existing_class_keeps_it_and_gains_external_link(self):
        body = 'Get it <a href="https://example.com/file.zip" class="download-link">here</a>.'
        post = parse_post(make_md(body=body), 1, [], site_url="https://mxgns.uk")
        assert 'class="download-link external-link"' in post.body_html

    def test_excerpt_html_also_marks_external_links(self):
        body = "Before [click](https://example.com)<!-- more -->After"
        post = parse_post(make_md(body=body), 1, [], site_url="https://mxgns.uk")
        assert post.excerpt_html is not None
        assert 'target="_blank"' in post.excerpt_html

    def test_no_site_url_still_marks_absolute_links_external(self):
        # Without a configured site_url there's nothing to compare against,
        # so any absolute link is treated as external.
        body = "[click](https://example.com)"
        post = parse_post(make_md(body=body), 1, [])
        assert 'target="_blank"' in post.body_html

    def test_protocol_relative_link_to_another_host_is_external(self):
        body = 'A <a href="//example.com">link</a>.'
        post = parse_post(make_md(body=body), 1, [], site_url="https://mxgns.uk")
        assert 'target="_blank"' in post.body_html
        assert 'rel="noopener"' in post.body_html

    def test_protocol_relative_link_to_own_host_is_untouched(self):
        body = 'A <a href="//mxgns.uk/5.html">link</a>.'
        post = parse_post(make_md(body=body), 1, [], site_url="https://mxgns.uk")
        assert 'target="_blank"' not in post.body_html

    def test_lookalike_subdomain_is_still_external(self):
        # A naive startswith(site_url) check would wrongly treat this as
        # internal since the string "https://mxgns.uk" is a prefix of it.
        body = "[click](https://mxgns.uk.evil.com/phish)"
        post = parse_post(make_md(body=body), 1, [], site_url="https://mxgns.uk")
        assert 'target="_blank"' in post.body_html

    def test_single_quoted_href_is_detected(self):
        body = "A <a href='https://example.com'>link</a>."
        post = parse_post(make_md(body=body), 1, [], site_url="https://mxgns.uk")
        assert 'target="_blank"' in post.body_html
        assert 'rel="noopener"' in post.body_html

    def test_uppercase_anchor_attributes_are_detected_and_merged(self):
        body = 'A <A HREF="https://example.com" REL="nofollow" TARGET="_self">link</A>.'
        post = parse_post(make_md(body=body), 1, [], site_url="https://mxgns.uk")
        assert 'target="_blank"' in post.body_html
        assert 'rel="nofollow noopener"' in post.body_html

    def test_existing_rel_gains_noopener_without_duplicating_attribute(self):
        body = 'A <a href="https://example.com" rel="nofollow">link</a>.'
        post = parse_post(make_md(body=body), 1, [], site_url="https://mxgns.uk")
        assert post.body_html.count('rel=') == 1
        assert 'rel="nofollow noopener"' in post.body_html

    def test_existing_rel_already_containing_noopener_is_untouched(self):
        body = 'A <a href="https://example.com" rel="noopener">link</a>.'
        post = parse_post(make_md(body=body), 1, [], site_url="https://mxgns.uk")
        assert post.body_html.count('rel=') == 1
        assert 'rel="noopener"' in post.body_html

    def test_existing_target_is_overridden_without_duplicating_attribute(self):
        body = 'A <a href="https://example.com" target="_self">link</a>.'
        post = parse_post(make_md(body=body), 1, [], site_url="https://mxgns.uk")
        assert post.body_html.count('target=') == 1
        assert 'target="_blank"' in post.body_html


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

class TestImages:

    def test_images_empty_when_none_provided(self):
        post = parse_post(make_md(), 1, [])
        assert post.images == []

    def test_single_image_included(self):
        post = parse_post(make_md(), 1, ["1-image-01.jpg"])
        assert post.images[0].filename == "1-image-01.jpg"

    def test_multiple_images_in_correct_order(self):
        post = parse_post(make_md(), 1, ["1-image-01.jpg", "1-image-02.png"])
        assert [img.filename for img in post.images] == ["1-image-01.jpg", "1-image-02.png"]

    def test_images_sorted_by_image_number(self):
        post = parse_post(make_md(), 1, ["1-image-03.jpg", "1-image-01.png", "1-image-02.jpg"])
        assert [img.filename for img in post.images] == ["1-image-01.png", "1-image-02.jpg", "1-image-03.jpg"]


# ---------------------------------------------------------------------------
# Read more marker
# ---------------------------------------------------------------------------

class TestReadMore:

    def test_excerpt_html_is_none_when_no_more_tag(self):
        post = parse_post(make_md(body="Hello world"), 1, [])
        assert post.excerpt_html is None

    def test_excerpt_html_contains_content_before_more_tag(self):
        post = parse_post(make_md(body="Intro.\n\n<!-- more -->\n\nRest."), 1, [])
        assert post.excerpt_html is not None
        assert "<p>Intro.</p>" in post.excerpt_html

    def test_excerpt_html_excludes_content_after_more_tag(self):
        post = parse_post(make_md(body="Intro.\n\n<!-- more -->\n\nRest."), 1, [])
        assert post.excerpt_html is not None
        assert "Rest" not in post.excerpt_html

    def test_body_html_contains_full_content_when_more_tag_present(self):
        post = parse_post(make_md(body="Intro.\n\n<!-- more -->\n\nRest."), 1, [])
        assert "<p>Intro.</p>" in post.body_html
        assert "<p>Rest.</p>" in post.body_html

    def test_more_tag_not_present_in_excerpt_html(self):
        post = parse_post(make_md(body="Intro.\n\n<!-- more -->\n\nRest."), 1, [])
        assert post.excerpt_html is not None
        assert "<!-- more -->" not in post.excerpt_html

    def test_more_tag_not_present_in_body_html(self):
        post = parse_post(make_md(body="Intro.\n\n<!-- more -->\n\nRest."), 1, [])
        assert "<!-- more -->" not in post.body_html

    def test_body_html_preserves_paragraph_break_when_more_tag_inline(self):
        post = parse_post(make_md(body="Intro.<!-- more -->Rest."), 1, [])
        assert "<p>Intro.</p>" in post.body_html
        assert "<p>Rest.</p>" in post.body_html


# ---------------------------------------------------------------------------
# Optional date
# ---------------------------------------------------------------------------

class TestOptionalDate:

    def test_date_is_none_when_not_in_frontmatter(self):
        post = parse_post("---\n---\n", 1, [])
        assert post.date is None

    def test_date_uk_is_none_when_not_in_frontmatter(self):
        post = parse_post("---\n---\n", 1, [])
        assert post.date_uk is None


# ---------------------------------------------------------------------------
# Image dataclass and alt texts
# ---------------------------------------------------------------------------

class TestImageAltTexts:

    def test_images_are_image_objects(self):
        from magnetizer.content import Image
        post = parse_post(make_md(), 1, ["1-image-01.jpg"])
        assert isinstance(post.images[0], Image)

    def test_image_alt_from_frontmatter(self):
        md = "---\ndate: 2026-05-24\nimages:\n  - A sunny beach\n---\n"
        post = parse_post(md, 1, ["1-image-01.jpg"])
        assert post.images[0].alt == "A sunny beach"

    def test_image_alt_empty_when_no_images_key(self):
        post = parse_post(make_md(), 1, ["1-image-01.jpg"])
        assert post.images[0].alt == ""

    def test_image_alt_empty_for_extra_images_beyond_alt_list(self):
        md = "---\ndate: 2026-05-24\nimages:\n  - First alt\n---\n"
        post = parse_post(md, 1, ["1-image-01.jpg", "1-image-02.jpg"])
        assert post.images[0].alt == "First alt"
        assert post.images[1].alt == ""

    def test_multiple_alts_assigned_in_order(self):
        md = "---\ndate: 2026-05-24\nimages:\n  - First\n  - Second\n---\n"
        post = parse_post(md, 1, ["1-image-01.jpg", "1-image-02.jpg"])
        assert post.images[0].alt == "First"
        assert post.images[1].alt == "Second"

    def test_colon_in_title_preserved_alongside_images_list(self):
        md = "---\ndate: 2026-05-24\ntitle: Title: with colon\nimages:\n  - Alt text\n---\n"
        post = parse_post(md, 1, ["1-image-01.jpg"])
        assert post.title == "Title: with colon"
        assert post.images[0].alt == "Alt text"


# ---------------------------------------------------------------------------
# Frontmatter key validation
# ---------------------------------------------------------------------------

class TestFrontmatterKeyValidation:

    def test_no_warning_for_valid_keys(self, capsys):
        parse_post(make_md(date="2026-05-24", title="Hello"), 1, [])
        assert "Warning" not in capsys.readouterr().out

    def test_warning_for_unknown_key(self, capsys):
        md = "---\ndate: 2026-05-24\nfoo: bar\n---\n"
        parse_post(md, 1, [])
        assert "Warning" in capsys.readouterr().out

    def test_warning_mentions_post_id(self, capsys):
        md = "---\ndate: 2026-05-24\nfoo: bar\n---\n"
        parse_post(md, 12, [])
        assert "12" in capsys.readouterr().out

    def test_warning_mentions_unknown_key(self, capsys):
        md = "---\ndate: 2026-05-24\nfoo: bar\n---\n"
        parse_post(md, 1, [])
        assert "foo" in capsys.readouterr().out

    def test_warning_for_each_unknown_key(self, capsys):
        md = "---\ndate: 2026-05-24\nfoo: bar\nbaz: qux\n---\n"
        parse_post(md, 1, [])
        output = capsys.readouterr().out
        assert "foo" in output
        assert "baz" in output

    def test_images_key_is_allowed(self, capsys):
        md = "---\ndate: 2026-05-24\nimages:\n  - Alt text\n---\n"
        parse_post(md, 1, ["1-image-01.jpg"])
        assert "Warning" not in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Character count
# ---------------------------------------------------------------------------

class TestCharCount:

    def test_character_count_uses_normalised_whitespace(self):
        # Extra newlines and spaces should not inflate the count
        body = "Short post.\n\n\n\n"
        post = parse_post(make_md(body=body), 1, [])
        assert post.char_count == len("Short post.")

    def test_char_count_stored_on_post(self):
        post = parse_post(make_md(body="Hello world"), 1, [])
        assert post.char_count == 11

    def test_char_count_excludes_markdown_syntax(self):
        post = parse_post(make_md(body="**bold**"), 1, [])
        assert post.char_count == 4

    def test_char_count_treats_smart_quotes_as_single_characters(self):
        # smarty renders "MXGNS" as &ldquo;MXGNS&rdquo; — each entity is one
        # visible character, not the length of its raw HTML representation.
        post = parse_post(make_md(body='"MXGNS"'), 1, [])
        assert post.char_count == 7

    def test_char_count_treats_smart_apostrophe_as_single_character(self):
        post = parse_post(make_md(body="it's a test"), 1, [])
        assert post.char_count == 11

    def test_char_count_based_on_plain_text_not_raw_markdown(self):
        # Raw length is 182 but plain text is 178
        body = "**" + "x" * 178 + "**"
        post = parse_post(make_md(body=body), 1, [])
        assert post.char_count == 178


# ---------------------------------------------------------------------------
# Favourite posts
# ---------------------------------------------------------------------------

class TestFavourite:

    def test_is_favourite_when_frontmatter_true(self):
        md = "---\ndate: 2026-05-24\nfavourite: true\n---\n"
        post = parse_post(md, 1, [])
        assert post.is_favourite is True

    def test_is_not_favourite_by_default(self):
        post = parse_post(make_md(), 1, [])
        assert post.is_favourite is False

    def test_favourite_false_is_not_favourite(self):
        md = "---\ndate: 2026-05-24\nfavourite: false\n---\n"
        post = parse_post(md, 1, [])
        assert post.is_favourite is False

    def test_favourite_key_does_not_trigger_unknown_key_warning(self, capsys):
        md = "---\ndate: 2026-05-24\nfavourite: true\n---\n"
        parse_post(md, 1, [])
        assert "Warning" not in capsys.readouterr().out



# ---------------------------------------------------------------------------
# Noindex
# ---------------------------------------------------------------------------

class TestNoindex:

    def test_is_not_noindex_by_default(self):
        post = parse_post(make_md(), 1, [])
        assert post.is_noindex is False

    def test_is_noindex_when_frontmatter_true(self):
        md = "---\ndate: 2026-05-24\nnoindex: true\n---\n"
        post = parse_post(md, 1, [])
        assert post.is_noindex is True

    def test_noindex_false_is_not_noindex(self):
        md = "---\ndate: 2026-05-24\nnoindex: false\n---\n"
        post = parse_post(md, 1, [])
        assert post.is_noindex is False

    def test_noindex_key_does_not_trigger_unknown_key_warning(self, capsys):
        md = "---\ndate: 2026-05-24\nnoindex: true\n---\n"
        parse_post(md, 1, [])
        assert "Warning" not in capsys.readouterr().out

    def test_noindex_empty_yaml_value_treated_as_not_noindex(self):
        # YAML `noindex:` with no value parses as None; must not crash or set is_noindex
        md = "---\ndate: 2026-05-24\nnoindex:\n---\n"
        post = parse_post(md, 1, [])
        assert post.is_noindex is False


# ---------------------------------------------------------------------------
# AI-assisted disclosure
# ---------------------------------------------------------------------------

class TestAiAssisted:

    def test_is_not_ai_assisted_by_default(self):
        post = parse_post(make_md(), 1, [])
        assert post.is_ai_assisted is False

    def test_is_ai_assisted_when_frontmatter_true(self):
        md = "---\ndate: 2026-05-24\nai_assisted: true\n---\n"
        post = parse_post(md, 1, [])
        assert post.is_ai_assisted is True

    def test_ai_assisted_false_is_not_ai_assisted(self):
        md = "---\ndate: 2026-05-24\nai_assisted: false\n---\n"
        post = parse_post(md, 1, [])
        assert post.is_ai_assisted is False

    def test_ai_assisted_key_does_not_trigger_unknown_key_warning(self, capsys):
        md = "---\ndate: 2026-05-24\nai_assisted: true\n---\n"
        parse_post(md, 1, [])
        assert "Warning" not in capsys.readouterr().out

    def test_ai_assisted_empty_yaml_value_treated_as_not_ai_assisted(self):
        md = "---\ndate: 2026-05-24\nai_assisted:\n---\n"
        post = parse_post(md, 1, [])
        assert post.is_ai_assisted is False


# ---------------------------------------------------------------------------
# Smart / typographic quotes
# ---------------------------------------------------------------------------

class TestSmartQuotes:

    def test_double_quotes_converted(self):
        post = parse_post(make_md(body='"hello"'), 1, [])
        assert '&ldquo;' in post.body_html
        assert '&rdquo;' in post.body_html

    def test_single_quotes_converted(self):
        post = parse_post(make_md(body="'hello'"), 1, [])
        assert '&lsquo;' in post.body_html
        assert '&rsquo;' in post.body_html

    def test_apostrophe_converted(self):
        post = parse_post(make_md(body="it's a test"), 1, [])
        assert '&rsquo;' in post.body_html
        assert "it's" not in post.body_html

    def test_quotes_in_inline_code_not_converted(self):
        post = parse_post(make_md(body='Use `"value"` here'), 1, [])
        assert '"value"' in post.body_html

    def test_quotes_in_fenced_code_block_not_converted(self):
        post = parse_post(make_md(body='```\n"not converted"\n```'), 1, [])
        assert '"not converted"' in post.body_html

    def test_double_dash_converted_to_en_dash(self):
        post = parse_post(make_md(body='a--b'), 1, [])
        assert '&ndash;' in post.body_html
        assert '--' not in post.body_html

    def test_triple_dash_converted_to_em_dash(self):
        post = parse_post(make_md(body='a---b'), 1, [])
        assert '&mdash;' in post.body_html

    def test_ellipsis_converted(self):
        post = parse_post(make_md(body='hello...'), 1, [])
        assert '&hellip;' in post.body_html
        assert '...' not in post.body_html

    def test_dashes_in_inline_code_not_converted(self):
        post = parse_post(make_md(body='Use `a--b` here'), 1, [])
        assert 'a--b' in post.body_html

    def test_dashes_in_fenced_code_block_not_converted(self):
        post = parse_post(make_md(body='```\na--b\n```'), 1, [])
        assert 'a--b' in post.body_html

    def test_ellipsis_in_inline_code_not_converted(self):
        post = parse_post(make_md(body='Use `hello...` here'), 1, [])
        assert 'hello...' in post.body_html

    def test_ellipsis_in_fenced_code_block_not_converted(self):
        post = parse_post(make_md(body='```\nhello...\n```'), 1, [])
        assert 'hello...' in post.body_html

    def test_smart_quotes_applied_to_excerpt(self):
        post = parse_post(make_md(body='"intro"\n\n<!-- more -->\n\n"rest"'), 1, [])
        assert post.excerpt_html is not None
        assert '&ldquo;' in post.excerpt_html


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

class TestCategory:

    def test_category_is_none_by_default(self):
        post = parse_post(make_md(), 1, [])
        assert post.category is None

    def test_category_extracted_from_frontmatter(self):
        post = parse_post(make_md(category="photography"), 1, [])
        assert post.category == "photography"

    def test_category_normalised_to_lowercase(self):
        post = parse_post(make_md(category="Photography"), 1, [])
        assert post.category == "photography"

    def test_category_mixed_case_normalised(self):
        post = parse_post(make_md(category="Travel & Leisure"), 1, [])
        assert post.category == "travel & leisure"

    def test_empty_category_is_none(self):
        post = parse_post(make_md(category=""), 1, [])
        assert post.category is None

    def test_category_key_does_not_trigger_unknown_key_warning(self, capsys):
        parse_post(make_md(category="photography"), 1, [])
        assert "unknown frontmatter key" not in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Container blocks (::: ... :::)
# ---------------------------------------------------------------------------

class TestContainerBlocksInPostBody:

    def test_bare_fence_gets_default_class(self):
        post = parse_post(make_md(body=":::\nMy container content\n:::"), 1, [])
        assert '<div class="container">' in post.body_html
        assert "<p>My container content</p>" in post.body_html

    def test_custom_class_appended_to_default(self):
        post = parse_post(make_md(body="::: my-container-class\nContent\n:::"), 1, [])
        assert '<div class="container my-container-class">' in post.body_html

    def test_unpaired_fence_treated_as_literal_text(self):
        post = parse_post(make_md(body=":::\nJust text, no closing fence."), 1, [])
        assert "<div" not in post.body_html
        assert "Just text, no closing fence." in post.body_html


# ---------------------------------------------------------------------------
# Inline image tokens ({{ image N }})
# ---------------------------------------------------------------------------

class TestInlineImageTokens:

    def test_token_replaced_with_figure(self):
        md = "---\ndate: 2026-05-24\nimages:\n  - A sunny beach\n---\n{{ image 1 }}\n"
        post = parse_post(md, 1, ["1-image-01.jpg"])
        assert '<figure><img src="1-image-01-resized.jpg" alt="A sunny beach"></figure>' in post.body_html

    def test_referenced_image_kept_in_full_images_list(self):
        md = "---\ndate: 2026-05-24\n---\n{{ image 1 }}\n"
        post = parse_post(md, 1, ["1-image-01.jpg"])
        assert len(post.images) == 1
        assert post.images[0].filename == "1-image-01.jpg"

    def test_referenced_image_recorded_as_inline(self):
        md = "---\ndate: 2026-05-24\n---\n{{ image 1 }}\n"
        post = parse_post(md, 1, ["1-image-01.jpg"])
        assert post.inline_image_filenames == frozenset({"1-image-01.jpg"})

    def test_post_without_tokens_has_no_inline_images(self):
        post = parse_post(make_md(body="Hello world"), 1, [])
        assert post.inline_image_filenames == frozenset()

    def test_multiple_tokens_for_different_images(self):
        md = (
            "---\ndate: 2026-05-24\nimages:\n  - First\n  - Second\n  - Third\n---\n"
            "Intro text.\n\n{{ image 2 }}\n\nMore text.\n\n{{ image 3 }}\n"
        )
        post = parse_post(md, 1, ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"])
        assert '<figure><img src="1-image-02-resized.jpg" alt="Second"></figure>' in post.body_html
        assert '<figure><img src="1-image-03-resized.jpg" alt="Third"></figure>' in post.body_html
        assert post.inline_image_filenames == frozenset({"1-image-02.jpg", "1-image-03.jpg"})

    def test_svg_image_token_uses_unresized_filename(self):
        md = "---\ndate: 2026-05-24\nimages:\n  - A diagram\n---\n{{ image 1 }}\n"
        post = parse_post(md, 1, ["1-image-01.svg"])
        assert '<figure><img src="1-image-01.svg" alt="A diagram"></figure>' in post.body_html

    def test_out_of_range_token_errors(self):
        md = "---\ndate: 2026-05-24\n---\n{{ image 2 }}\n"
        with pytest.raises(SystemExit):
            parse_post(md, 1, ["1-image-01.jpg"])

    def test_zero_index_token_errors(self):
        md = "---\ndate: 2026-05-24\n---\n{{ image 0 }}\n"
        with pytest.raises(SystemExit):
            parse_post(md, 1, ["1-image-01.jpg"])

    def test_token_with_no_images_errors(self):
        md = "---\ndate: 2026-05-24\n---\n{{ image 1 }}\n"
        with pytest.raises(SystemExit):
            parse_post(md, 1, [])

    def test_token_inline_with_other_text_on_same_line_errors(self):
        md = "---\ndate: 2026-05-24\n---\nSee this: {{ image 1 }} nice right?\n"
        with pytest.raises(SystemExit):
            parse_post(md, 1, ["1-image-01.jpg"])

    def test_token_sharing_block_with_other_lines_errors(self):
        # No blank line separating the token from surrounding text — same
        # markdown block, so it doesn't count as standalone.
        md = "---\ndate: 2026-05-24\n---\nIntro text\n{{ image 1 }}\nmore text\n"
        with pytest.raises(SystemExit):
            parse_post(md, 1, ["1-image-01.jpg"])

    def test_token_before_more_marker_appears_in_excerpt(self):
        md = (
            "---\ndate: 2026-05-24\nimages:\n  - A sunny beach\n---\n"
            "Intro.\n\n{{ image 1 }}\n\n<!-- more -->\n\nRest.\n"
        )
        post = parse_post(md, 1, ["1-image-01.jpg"])
        assert post.excerpt_html is not None
        assert '<figure><img src="1-image-01-resized.jpg" alt="A sunny beach"></figure>' in post.excerpt_html
        assert post.inline_image_filenames == frozenset({"1-image-01.jpg"})

    def test_token_after_more_marker_excluded_from_excerpt_but_marked_inline(self):
        md = (
            "---\ndate: 2026-05-24\nimages:\n  - A sunny beach\n---\n"
            "Intro.\n\n<!-- more -->\n\n{{ image 1 }}\n"
        )
        post = parse_post(md, 1, ["1-image-01.jpg"])
        assert post.excerpt_html is not None
        assert "figure" not in post.excerpt_html
        assert '<figure><img src="1-image-01-resized.jpg" alt="A sunny beach"></figure>' in post.body_html
        assert post.inline_image_filenames == frozenset({"1-image-01.jpg"})

    def test_excerpt_inline_image_filenames_includes_only_pre_marker_images(self):
        md = (
            "---\ndate: 2026-05-24\n---\n"
            "Intro.\n\n{{ image 1 }}\n\n<!-- more -->\n\n{{ image 2 }}\n"
        )
        post = parse_post(md, 1, ["1-image-01.jpg", "1-image-02.jpg"])
        assert post.inline_image_filenames == frozenset({"1-image-01.jpg", "1-image-02.jpg"})
        assert post.excerpt_inline_image_filenames == frozenset({"1-image-01.jpg"})

    def test_excerpt_inline_image_filenames_equals_full_set_when_no_more_marker(self):
        md = "---\ndate: 2026-05-24\n---\n{{ image 1 }}\n"
        post = parse_post(md, 1, ["1-image-01.jpg"])
        assert post.excerpt_inline_image_filenames == frozenset({"1-image-01.jpg"})

    def test_excerpt_inline_image_filenames_empty_when_no_tokens(self):
        post = parse_post(make_md(body="Hello"), 1, [])
        assert post.excerpt_inline_image_filenames == frozenset()


# ---------------------------------------------------------------------------
# Comments — parse_comment()
# ---------------------------------------------------------------------------

def make_comment_md(date="2026-08-05", author="Magnus", body="Hello there."):
    lines = ["---"]
    if date is not None:
        lines.append(f"date: {date}")
    if author is not None:
        lines.append(f"author: {author}")
    lines.append("---")
    if body:
        lines.append("")
        lines.append(body)
    return "\n".join(lines) + "\n"


class TestParseComment:

    def test_date_extracted(self):
        comment = parse_comment(make_comment_md(date="2026-08-05"), "1-comment-01.md")
        assert comment.date == "2026-08-05"

    def test_date_uk_formatted(self):
        comment = parse_comment(make_comment_md(date="2026-08-05"), "1-comment-01.md")
        assert comment.date_uk == "5 August 2026"

    def test_author_extracted(self):
        comment = parse_comment(make_comment_md(author="Magnus"), "1-comment-01.md")
        assert comment.author == "Magnus"

    def test_filename_stored(self):
        comment = parse_comment(make_comment_md(), "1-comment-01.md")
        assert comment.filename == "1-comment-01.md"

    def test_body_rendered_as_html(self):
        comment = parse_comment(make_comment_md(body="Hello **world**"), "1-comment-01.md")
        assert "<p>Hello <strong>world</strong></p>" in comment.body_html

    def test_missing_date_errors(self):
        md = "---\nauthor: Magnus\n---\nHi\n"
        with pytest.raises(SystemExit):
            parse_comment(md, "1-comment-01.md")

    def test_missing_author_errors(self):
        md = "---\ndate: 2026-08-05\n---\nHi\n"
        with pytest.raises(SystemExit):
            parse_comment(md, "1-comment-01.md")

    def test_blank_author_errors(self):
        md = "---\ndate: 2026-08-05\nauthor:\n---\nHi\n"
        with pytest.raises(SystemExit):
            parse_comment(md, "1-comment-01.md")

    def test_blank_date_errors(self):
        md = "---\ndate:\nauthor: Magnus\n---\nHi\n"
        with pytest.raises(SystemExit):
            parse_comment(md, "1-comment-01.md")

    def test_unknown_key_warns(self, capsys):
        md = "---\ndate: 2026-08-05\nauthor: Magnus\nfoo: bar\n---\nHi\n"
        parse_comment(md, "1-comment-01.md")
        out = capsys.readouterr().out
        assert "Warning" in out
        assert "foo" in out

    def test_warning_mentions_filename(self, capsys):
        md = "---\ndate: 2026-08-05\nauthor: Magnus\nfoo: bar\n---\nHi\n"
        parse_comment(md, "12-comment-02.md")
        assert "12-comment-02.md" in capsys.readouterr().out

    def test_no_warning_for_valid_keys(self, capsys):
        parse_comment(make_comment_md(), "1-comment-01.md")
        assert "Warning" not in capsys.readouterr().out

    def test_empty_body_produces_empty_string(self):
        comment = parse_comment(make_comment_md(body=""), "1-comment-01.md")
        assert comment.body_html == ""


class TestCommentAuthorSlug:

    def test_simple_name(self):
        comment = parse_comment(make_comment_md(author="Magnus"), "1-comment-01.md")
        assert comment.author_slug == "magnus"

    def test_name_with_space_collapsed_to_hyphen(self):
        comment = parse_comment(make_comment_md(author="Jane Doe"), "1-comment-01.md")
        assert comment.author_slug == "jane-doe"

    def test_name_with_punctuation_collapsed(self):
        comment = parse_comment(make_comment_md(author="O'Brien!!"), "1-comment-01.md")
        assert comment.author_slug == "o-brien"

    def test_uppercase_name_lowercased(self):
        comment = parse_comment(make_comment_md(author="MAGNUS"), "1-comment-01.md")
        assert comment.author_slug == "magnus"


class TestCommentAuthorInitial:

    def test_simple_name(self):
        comment = parse_comment(make_comment_md(author="Magnus"), "1-comment-01.md")
        assert comment.author_initial == "M"

    def test_lowercase_name_uppercased(self):
        comment = parse_comment(make_comment_md(author="magnus"), "1-comment-01.md")
        assert comment.author_initial == "M"

    def test_already_uppercase_first_letter(self):
        comment = parse_comment(make_comment_md(author="MAGNUS"), "1-comment-01.md")
        assert comment.author_initial == "M"

    def test_single_character_name(self):
        comment = parse_comment(make_comment_md(author="M"), "1-comment-01.md")
        assert comment.author_initial == "M"

    def test_only_first_character_used(self):
        comment = parse_comment(make_comment_md(author="Jane Doe"), "1-comment-01.md")
        assert comment.author_initial == "J"

    def test_accented_character_uppercased(self):
        comment = parse_comment(make_comment_md(author="åsa"), "1-comment-01.md")
        assert comment.author_initial == "Å"


class TestCommentExternalLinks:

    def test_external_link_gets_target_blank_and_rel_noopener(self):
        comment = parse_comment(make_comment_md(body="[click](https://example.com)"), "1-comment-01.md", site_url="https://mxgns.uk")
        assert 'target="_blank"' in comment.body_html
        assert 'rel="noopener"' in comment.body_html
        assert 'class="external-link"' in comment.body_html

    def test_relative_link_untouched(self):
        comment = parse_comment(make_comment_md(body="[click](/about.html)"), "1-comment-01.md", site_url="https://mxgns.uk")
        assert 'target="_blank"' not in comment.body_html

    def test_link_to_own_site_untouched(self):
        comment = parse_comment(make_comment_md(body="[click](https://mxgns.uk/5.html)"), "1-comment-01.md", site_url="https://mxgns.uk")
        assert 'target="_blank"' not in comment.body_html


class TestCommentNoExtendedFeatures:

    def test_container_fence_not_expanded(self):
        comment = parse_comment(make_comment_md(body="::: my-class\nContent\n:::"), "1-comment-01.md")
        assert '<div class="container' not in comment.body_html

    def test_shortcode_left_as_literal_text(self):
        comment = parse_comment(make_comment_md(body="{{ post_count }}"), "1-comment-01.md")
        assert "{{ post_count }}" in comment.body_html

    def test_inline_image_token_left_as_literal_text(self):
        comment = parse_comment(make_comment_md(body="{{ image 1 }}"), "1-comment-01.md")
        assert "{{ image 1 }}" in comment.body_html


class TestSpecialPageCommentPattern:

    def test_matches_expected_filename(self):
        pattern = special_page_comment_pattern("about")
        assert pattern.match("about-comment-01.md")

    def test_does_not_match_different_name(self):
        pattern = special_page_comment_pattern("about")
        assert not pattern.match("cookies-comment-01.md")

    def test_does_not_match_image_filename(self):
        pattern = special_page_comment_pattern("about")
        assert not pattern.match("about-image-01.jpg")


# ---------------------------------------------------------------------------
# Post.comments
# ---------------------------------------------------------------------------

class TestPostComments:

    def test_comments_empty_by_default(self):
        post = parse_post(make_md(), 1, [])
        assert post.comments == []

    def test_comments_attached(self):
        comment = parse_comment(make_comment_md(), "1-comment-01.md")
        post = parse_post(make_md(), 1, [], comments=[comment])
        assert post.comments == [comment]

    def test_comments_sorted_by_number_oldest_first(self):
        c2 = parse_comment(make_comment_md(), "1-comment-02.md")
        c1 = parse_comment(make_comment_md(), "1-comment-01.md")
        post = parse_post(make_md(), 1, [], comments=[c2, c1])
        assert [c.filename for c in post.comments] == ["1-comment-01.md", "1-comment-02.md"]

    def test_comments_sorted_leniently_with_gaps(self):
        c3 = parse_comment(make_comment_md(), "1-comment-03.md")
        c1 = parse_comment(make_comment_md(), "1-comment-01.md")
        post = parse_post(make_md(), 1, [], comments=[c3, c1])
        assert [c.filename for c in post.comments] == ["1-comment-01.md", "1-comment-03.md"]


# ---------------------------------------------------------------------------
# thumbnail_filename
# ---------------------------------------------------------------------------

class TestThumbnailFilename:

    def test_jpg_gets_thumb_suffix(self):
        assert thumbnail_filename("1-image-01.jpg") == "1-image-01-thumb.jpg"

    def test_png_gets_thumb_suffix(self):
        assert thumbnail_filename("1-image-01.png") == "1-image-01-thumb.png"

    def test_svg_unchanged(self):
        assert thumbnail_filename("1-image-01.svg") == "1-image-01.svg"
