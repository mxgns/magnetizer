"""Tests for magnetizer/dynamic.py — shortcode value computation and expansion"""

from datetime import date

from tests.conftest import make_post
from magnetizer.dynamic import (
    compute_base_values,
    compute_word_count,
    expand_shortcodes,
    format_int,
    format_today,
    render_ai_post_list,
    wrap_scalar,
)


# ---------------------------------------------------------------------------
# format_int
# ---------------------------------------------------------------------------

class TestFormatInt:

    def test_below_1000_no_separator(self):
        assert format_int(42) == "42"

    def test_zero(self):
        assert format_int(0) == "0"

    def test_four_digits(self):
        assert format_int(2345) == "2,345"

    def test_five_digits(self):
        assert format_int(12345) == "12,345"

    def test_millions(self):
        assert format_int(1000000) == "1,000,000"

    def test_negative(self):
        assert format_int(-1234) == "-1,234"


# ---------------------------------------------------------------------------
# wrap_scalar
# ---------------------------------------------------------------------------

class TestWrapScalar:

    def test_wraps_in_span_with_class(self):
        assert wrap_scalar("post_count", "42") == '<span class="post-count">42</span>'

    def test_underscores_become_hyphens_in_class(self):
        assert wrap_scalar("example_value_name", "3") == '<span class="example-value-name">3</span>'


# ---------------------------------------------------------------------------
# format_today
# ---------------------------------------------------------------------------

class TestFormatToday:

    def test_no_leading_zeros(self):
        assert format_today(date(2026, 7, 17)) == "17/7/26"

    def test_single_digit_day_and_month(self):
        assert format_today(date(2026, 1, 1)) == "1/1/26"

    def test_double_digit_day_and_month(self):
        assert format_today(date(2030, 12, 25)) == "25/12/30"


# ---------------------------------------------------------------------------
# render_ai_post_list
# ---------------------------------------------------------------------------

class TestRenderAiPostList:

    def test_empty_when_no_matching_posts(self):
        posts = [make_post(post_id=1, is_ai_assisted=False)]
        assert render_ai_post_list(posts) == '<ul class="ai-post-list"><li>(none)</li></ul>'

    def test_single_matching_post(self):
        posts = [make_post(post_id=1, title="My Post", is_ai_assisted=True)]
        result = render_ai_post_list(posts)
        assert result == '<ul class="ai-post-list"><li><a href="1.html">My Post</a></li></ul>'

    def test_newest_first_by_date(self):
        posts = [
            make_post(post_id=1, date="2026-01-01", title="Older", is_ai_assisted=True),
            make_post(post_id=2, date="2026-06-01", title="Newer", is_ai_assisted=True),
        ]
        result = render_ai_post_list(posts)
        assert result.index("Newer") < result.index("Older")

    def test_ties_broken_by_descending_filename_number(self):
        posts = [
            make_post(post_id=5, date="2026-01-01", title="Five", is_ai_assisted=True),
            make_post(post_id=9, date="2026-01-01", title="Nine", is_ai_assisted=True),
        ]
        result = render_ai_post_list(posts)
        assert result.index("Nine") < result.index("Five")

    def test_non_matching_posts_excluded(self):
        posts = [
            make_post(post_id=1, title="Yes", is_ai_assisted=True),
            make_post(post_id=2, title="No", is_ai_assisted=False),
        ]
        result = render_ai_post_list(posts)
        assert "No" not in result
        assert "Yes" in result

    def test_title_html_escaped(self):
        posts = [make_post(post_id=1, title="A & B <em>", is_ai_assisted=True)]
        result = render_ai_post_list(posts)
        assert "A &amp; B &lt;em&gt;" in result
        assert "<em>" not in result.replace('href="1.html"', '')

    def test_url_attribute_escaped(self):
        posts = [make_post(post_id=1, title="Post", is_ai_assisted=True)]
        posts[0].url = '1.html?x="&y'
        result = render_ai_post_list(posts)
        assert 'href="1.html?x=&quot;&amp;y"' in result

    def test_special_page_with_string_id_included(self):
        # Special pages (parsed via the same parse_post() as regular posts) carry a
        # string id (their name) rather than an int — must not crash and must render.
        special_page = make_post(post_id="syntax", title="Syntax Guide", is_ai_assisted=True)
        result = render_ai_post_list([special_page])
        assert result == '<ul class="ai-post-list"><li><a href="syntax.html">Syntax Guide</a></li></ul>'

    def test_mixed_int_and_string_ids_sorted_without_crashing(self):
        post = make_post(post_id=1, date="2026-01-01", title="Post", is_ai_assisted=True)
        special_page = make_post(post_id="syntax", date="2026-01-01", title="Syntax", is_ai_assisted=True)
        result = render_ai_post_list([post, special_page])
        assert "Post" in result
        assert "Syntax" in result


# ---------------------------------------------------------------------------
# compute_base_values
# ---------------------------------------------------------------------------

class TestComputeBaseValues:

    def test_post_count(self):
        posts = [make_post(post_id=1), make_post(post_id=2)]
        values = compute_base_values(posts, date(2026, 7, 17), lambda msg: None)
        assert values["post_count"] == '<span class="post-count">2</span>'

    def test_image_count_sums_images_across_posts(self):
        posts = [
            make_post(post_id=1, images=["1-image-01.jpg", "1-image-02.jpg"]),
            make_post(post_id=2, images=["2-image-01.jpg"]),
        ]
        values = compute_base_values(posts, date(2026, 7, 17), lambda msg: None)
        assert values["image_count"] == '<span class="image-count">3</span>'

    def test_image_count_zero_when_no_images_field(self):
        posts = [make_post(post_id=1, images=None)]
        values = compute_base_values(posts, date(2026, 7, 17), lambda msg: None)
        assert values["image_count"] == '<span class="image-count">0</span>'

    def test_today_present(self):
        values = compute_base_values([], date(2026, 7, 17), lambda msg: None)
        assert values["today"] == '<span class="today">17/7/26</span>'

    def test_ai_post_list_present(self):
        posts = [make_post(post_id=1, title="Post", is_ai_assisted=True)]
        values = compute_base_values(posts, date(2026, 7, 17), lambda msg: None)
        assert values["ai_post_list"] == '<ul class="ai-post-list"><li><a href="1.html">Post</a></li></ul>'

    def test_no_posts_defaults(self):
        values = compute_base_values([], date(2026, 7, 17), lambda msg: None)
        assert values["post_count"] == '<span class="post-count">0</span>'
        assert values["image_count"] == '<span class="image-count">0</span>'
        assert values["ai_post_list"] == '<ul class="ai-post-list"><li>(none)</li></ul>'

    def test_ai_post_list_candidates_defaults_to_published_posts(self):
        posts = [make_post(post_id=1, title="Post", is_ai_assisted=True)]
        values = compute_base_values(posts, date(2026, 7, 17), lambda msg: None)
        assert "Post" in values["ai_post_list"]

    def test_ai_post_list_candidates_used_when_given(self):
        posts = [make_post(post_id=1, is_ai_assisted=False)]
        special_page = make_post(post_id="syntax", title="Syntax Guide", is_ai_assisted=True)
        values = compute_base_values(
            posts, date(2026, 7, 17), lambda msg: None,
            ai_post_list_candidates=posts + [special_page],
        )
        assert "Syntax Guide" in values["ai_post_list"]

    def test_counts_unaffected_by_extra_ai_post_list_candidates(self):
        posts = [make_post(post_id=1)]
        special_page = make_post(post_id="syntax", is_ai_assisted=True, images=["syntax-image-01.jpg"])
        values = compute_base_values(
            posts, date(2026, 7, 17), lambda msg: None,
            ai_post_list_candidates=posts + [special_page],
        )
        assert values["post_count"] == '<span class="post-count">1</span>'
        assert values["image_count"] == '<span class="image-count">0</span>'


# ---------------------------------------------------------------------------
# expand_shortcodes
# ---------------------------------------------------------------------------

_VALUES = {
    "post_count": '<span class="post-count">42</span>',
    "word_count": '<span class="word-count">1,234</span>',
    "image_count": '<span class="image-count">65</span>',
    "today": '<span class="today">17/7/26</span>',
    "ai_post_list": '<ul class="ai-post-list"><li><a href="1.html">Post</a></li></ul>',
}


class TestExpandShortcodesScalars:

    def test_single_scalar_in_paragraph(self):
        html, used = expand_shortcodes("<p>Count: {{ post_count }}</p>", _VALUES, "1.md", None)
        assert html == '<p>Count: <span class="post-count">42</span></p>'
        assert used == {"post_count"}

    def test_whitespace_variants_all_equivalent(self):
        for variant in ("{{post_count}}", "{{ post_count }}", "{{  post_count  }}"):
            html, used = expand_shortcodes(f"<p>{variant}</p>", _VALUES, "1.md", None)
            assert html == '<p><span class="post-count">42</span></p>'
            assert used == {"post_count"}

    def test_multiple_shortcodes_each_wrapped_independently(self):
        html, used = expand_shortcodes(
            "<p>{{ post_count }} posts, {{ word_count }} words</p>", _VALUES, "1.md", None
        )
        assert html == (
            '<p><span class="post-count">42</span> posts, '
            '<span class="word-count">1,234</span> words</p>'
        )
        assert used == {"post_count", "word_count"}


class TestExpandShortcodesUnknown:

    def test_unknown_shortcode_warns_and_renders_literal(self):
        warnings = []
        html, used = expand_shortcodes(
            "<p>{{ nonsense }}</p>", _VALUES, "1.md", warnings.append
        )
        assert html == "<p>{{ nonsense }}</p>"
        assert used == set()
        assert warnings and "nonsense" in warnings[0]

    def test_malformed_unclosed_no_warning(self):
        warnings = []
        html, used = expand_shortcodes(
            "<p>{{ post_count</p>", _VALUES, "1.md", warnings.append
        )
        assert html == "<p>{{ post_count</p>"
        assert used == set()
        assert warnings == []


class TestExpandShortcodesExclusionContexts:

    def test_inline_code_not_expanded(self):
        html, used = expand_shortcodes(
            "<p>Use <code>{{ post_count }}</code> in your post.</p>", _VALUES, "1.md", None
        )
        assert "<code>{{ post_count }}</code>" in html
        assert used == set()

    def test_fenced_pre_code_block_not_expanded(self):
        html, used = expand_shortcodes(
            "<pre><code>{{ post_count }}\n</code></pre>", _VALUES, "1.md", None
        )
        assert "{{ post_count }}" in html
        assert used == set()

    def test_comment_not_expanded(self):
        html, used = expand_shortcodes(
            "<p>Hi</p><!-- {{ post_count }} -->", _VALUES, "1.md", None
        )
        assert "<!-- {{ post_count }} -->" in html
        assert used == set()

    def test_script_not_expanded(self):
        html, used = expand_shortcodes(
            "<script>var x = '{{ post_count }}';</script>", _VALUES, "1.md", None
        )
        assert "{{ post_count }}" in html
        assert used == set()

    def test_style_not_expanded(self):
        html, used = expand_shortcodes(
            "<style>.x::before { content: '{{ post_count }}'; }</style>", _VALUES, "1.md", None
        )
        assert "{{ post_count }}" in html
        assert used == set()

    def test_tag_attribute_not_expanded(self):
        html, used = expand_shortcodes(
            '<p><a href="{{ post_count }}">link</a></p>', _VALUES, "1.md", None
        )
        assert 'href="{{ post_count }}"' in html
        assert used == set()

    def test_shortcode_after_quoted_gt_in_attribute_not_expanded(self):
        # A literal `>` inside a quoted attribute value must not be mistaken for the
        # tag's real closing bracket — otherwise the rest of the attribute leaks out
        # as "text" and becomes eligible for expansion.
        html, used = expand_shortcodes(
            '<p><a title="x > {{ post_count }}">link</a></p>', _VALUES, "1.md", None
        )
        assert html == '<p><a title="x > {{ post_count }}">link</a></p>'
        assert used == set()


class TestExpandShortcodesBlock:

    def test_sole_content_of_paragraph_unwraps_p(self):
        html, used = expand_shortcodes("<p>{{ ai_post_list }}</p>", _VALUES, "1.md", None)
        assert html == _VALUES["ai_post_list"]
        assert used == {"ai_post_list"}

    def test_inline_usage_warns_and_stays_literal(self):
        warnings = []
        html, used = expand_shortcodes(
            "<p>Recent: {{ ai_post_list }}</p>", _VALUES, "1.md", warnings.append
        )
        assert html == "<p>Recent: {{ ai_post_list }}</p>"
        assert used == set()
        assert warnings and "ai_post_list" in warnings[0]

    def test_generated_output_not_recursively_expanded(self):
        values = {**_VALUES, "ai_post_list": '<ul class="ai-post-list"><li><a href="1.html">Post {{ post_count }}</a></li></ul>'}
        html, used = expand_shortcodes("<p>{{ ai_post_list }}</p>", values, "1.md", None)
        assert "{{ post_count }}" in html
        assert used == {"ai_post_list"}


# ---------------------------------------------------------------------------
# compute_word_count
# ---------------------------------------------------------------------------

class TestComputeWordCount:

    def test_simple_word_count(self):
        posts = [make_post(post_id=1, body_html="<p>one two three</p>")]
        base = {k: v for k, v in _VALUES.items() if k != "word_count"}
        assert compute_word_count(posts, base) == 3

    def test_word_count_shortcode_in_body_counts_as_empty(self):
        posts = [make_post(post_id=1, body_html="<p>one two {{ word_count }} three</p>")]
        base = {k: v for k, v in _VALUES.items() if k != "word_count"}
        assert compute_word_count(posts, base) == 3

    def test_other_shortcode_expanded_text_counts(self):
        posts = [make_post(post_id=1, body_html="<p>Count: {{ post_count }}</p>")]
        base = {k: v for k, v in _VALUES.items() if k != "word_count"}
        # "Count:" + the expanded visible text "42" = 2 words
        assert compute_word_count(posts, base) == 2

    def test_sums_across_posts(self):
        posts = [
            make_post(post_id=1, body_html="<p>one two</p>"),
            make_post(post_id=2, body_html="<p>three four five</p>"),
        ]
        base = {k: v for k, v in _VALUES.items() if k != "word_count"}
        assert compute_word_count(posts, base) == 5
