"""Tests for magnetizer/render.py — all HTML generation functions"""

from datetime import date, timedelta
from html.parser import HTMLParser

import pytest
from magnetizer.content import Image, Post
from magnetizer.render import (
    archive_display_text,
    canonical_url,
    category_page_url,
    gallery_page_url,
    notes_page_url,
    post_display_text,
    render_archive_page_content,
    render_article,
    render_category_page_content,
    render_gallery_page_content,
    render_index_page_content,
    render_notes_page_content,
    render_navigation,
    render_page_title,
    render_post_page_content,
    render_template,
)
from conftest import make_comment, make_post


# ---------------------------------------------------------------------------
# render_article — structure
# ---------------------------------------------------------------------------

class TestRenderArticleStructure:

    def test_article_element_present(self):
        html = render_article(make_post(), on_index_page=False)
        assert "<article" in html
        assert "</article>" in html

    def test_article_id_attribute(self):
        html = render_article(make_post(post_id=7), on_index_page=False)
        assert 'id="post-7"' in html

    def test_article_has_single_post_class_on_post_page(self):
        html = render_article(make_post(post_type=None), on_index_page=False)
        assert 'class="single-post"' in html

    def test_article_has_multiple_posts_class_on_index_page(self):
        html = render_article(make_post(post_type=None), on_index_page=True)
        assert 'class="multiple-posts"' in html

    def test_full_post_type_class(self):
        html = render_article(make_post(post_type="full"), on_index_page=False)
        assert 'class="single-post full-post"' in html

    def test_image_post_type_class(self):
        html = render_article(make_post(post_type="image", title=None), on_index_page=False)
        assert 'class="single-post image-post"' in html

    def test_note_post_type_class(self):
        html = render_article(make_post(post_type="note", title=None), on_index_page=False)
        assert 'class="single-post note"' in html

    def test_post_type_class_on_index_page(self):
        html = render_article(make_post(post_type="full"), on_index_page=True)
        assert 'class="multiple-posts full-post"' in html

    def test_no_type_class_when_post_type_unset(self):
        html = render_article(make_post(post_type=None), on_index_page=False)
        assert 'class="single-post"' in html

    def test_type_class_appended_alongside_layout_class_not_instead_of_it(self):
        html = render_article(make_post(post_type="note", title=None), on_index_page=False)
        assert 'class="single-post note"' in html
        assert 'class="note"' not in html

    def test_post_body_present(self):
        html = render_article(make_post(body_html="<p>Hello</p>"), on_index_page=False)
        assert "<p>Hello</p>" in html

    def test_post_body_inside_div(self):
        html = render_article(make_post(body_html="<p>Hello</p>"), on_index_page=False)
        assert '<div class="post-body">' in html

    def test_footer_present(self):
        html = render_article(make_post(), on_index_page=False)
        assert "<footer>" in html

    def test_footer_omitted_when_no_date(self):
        post = Post(id=1, date=None, date_uk=None, title="About",
                    url="about.html", body_html="<p>Hi</p>", images=[])
        html = render_article(post, on_index_page=False)
        assert "<footer>" not in html

    def test_time_element_with_datetime_attribute(self):
        html = render_article(make_post(date="2026-05-24"), on_index_page=False)
        assert '<time datetime="2026-05-24">' in html

    def test_time_element_contains_uk_date(self):
        html = render_article(make_post(date_uk="24 May 2026"), on_index_page=False)
        assert "24 May 2026" in html


# ---------------------------------------------------------------------------
# render_article — title
# ---------------------------------------------------------------------------

class TestRenderArticleTitle:

    def test_h1_present_when_post_has_title(self):
        html = render_article(make_post(title="My Title"), on_index_page=False)
        assert "<h1>" in html or '<h1 ' in html

    def test_h1_contains_title_text(self):
        html = render_article(make_post(title="My Title"), on_index_page=False)
        assert "My Title" in html

    def test_h1_present_with_fallback_text_when_no_title(self):
        html = render_article(make_post(title=None, date_uk="24 May 2026"), on_index_page=False)
        assert "<h1>" in html or "<h1 " in html

    def test_h1_fallback_text_uses_name_when_set(self):
        html = render_article(make_post(title=None, name="A quiet morning"), on_index_page=False)
        assert "<h1>A quiet morning</h1>" in html

    def test_h1_fallback_text_uses_generated_note_label_when_no_images(self):
        html = render_article(make_post(title=None, date_uk="24 May 2026", images=[]), on_index_page=False)
        assert "<h1>Note posted 24 May 2026</h1>" in html

    def test_h1_fallback_text_uses_generated_photo_label_singular(self):
        html = render_article(
            make_post(title=None, date_uk="24 May 2026", images=["1-image-01.jpg"]), on_index_page=False
        )
        assert "<h1>Photo posted 24 May 2026</h1>" in html

    def test_h1_fallback_text_uses_generated_photos_label_plural(self):
        html = render_article(
            make_post(title=None, date_uk="24 May 2026", images=["1-image-01.jpg", "1-image-02.jpg"]),
            on_index_page=False,
        )
        assert "<h1>Photos posted 24 May 2026</h1>" in html

    def test_h1_fallback_text_omits_date_when_post_has_no_date(self):
        html = render_article(make_post(title=None, date_uk=None, images=[]), on_index_page=False)
        assert "<h1>Note</h1>" in html

    def test_h1_fallback_text_ignores_inline_only_images(self):
        html = render_article(
            make_post(
                title=None, date_uk="24 May 2026",
                images=["1-image-01.jpg"], inline_image_filenames=frozenset({"1-image-01.jpg"}),
            ),
            on_index_page=False,
        )
        assert "<h1>Note posted 24 May 2026</h1>" in html

    def test_h2_fallback_text_on_index_page_wrapped_in_link(self):
        html = render_article(make_post(post_id=5, title=None, name="A quiet morning"), on_index_page=True)
        assert '<h2><a href="5.html">A quiet morning</a></h2>' in html

    def test_h2_present_when_post_has_title_on_index_page(self):
        html = render_article(make_post(title="My Title"), on_index_page=True)
        assert "<h2>" in html or '<h2 ' in html

    def test_no_h1_for_title_on_index_page(self):
        html = render_article(make_post(title="My Title"), on_index_page=True)
        assert "<h1>" not in html and "<h1 " not in html

    def test_no_h2_for_title_on_post_page(self):
        html = render_article(make_post(title="My Title"), on_index_page=False)
        assert "<h2>" not in html and "<h2 " not in html


# ---------------------------------------------------------------------------
# render_article — links on index vs post page
# ---------------------------------------------------------------------------

class TestRenderArticleLinks:

    def test_h2_contains_link_on_index_page(self):
        html = render_article(make_post(post_id=3, title="My Title"), on_index_page=True)
        assert '<h2><a href="3.html">My Title</a></h2>' in html

    def test_h1_has_no_link_on_post_page(self):
        html = render_article(make_post(post_id=3, title="My Title"), on_index_page=False)
        assert '<h1>My Title</h1>' in html

    def test_time_contains_link_on_index_page(self):
        html = render_article(make_post(post_id=3, date="2026-05-24", date_uk="24 May 2026"), on_index_page=True)
        assert '<a href="3.html">24 May 2026</a>' in html

    def test_time_has_no_link_on_post_page(self):
        html = render_article(make_post(post_id=3, date_uk="24 May 2026"), on_index_page=False)
        assert "24 May 2026" in html
        assert '<a href="3.html">24 May 2026</a>' not in html


# ---------------------------------------------------------------------------
# render_article — images
# ---------------------------------------------------------------------------

class TestRenderArticleImages:

    def test_no_images_block_when_post_has_no_images(self):
        html = render_article(make_post(images=[]), on_index_page=False)
        assert "post-images" not in html
        assert "<figure>" not in html

    def test_images_block_present_when_post_has_images(self):
        html = render_article(make_post(images=["1-image-01.jpg"]), on_index_page=False)
        assert '<div class="post-images">' in html

    def test_figure_element_per_image(self):
        html = render_article(make_post(images=["1-image-01.jpg", "1-image-02.png"]), on_index_page=False)
        assert html.count("<figure>") == 2

    def test_img_src_uses_resized_filename(self):
        html = render_article(make_post(images=["1-image-01.jpg"]), on_index_page=False)
        assert 'src="1-image-01-resized.jpg"' in html

    def test_resized_filename_for_png(self):
        html = render_article(make_post(images=["1-image-01.png"]), on_index_page=False)
        assert 'src="1-image-01-resized.png"' in html

    def test_svg_uses_original_filename_not_resized(self):
        html = render_article(make_post(images=["1-image-01.svg"]), on_index_page=False)
        assert 'src="1-image-01.svg"' in html
        assert "resized" not in html

    def test_images_in_order(self):
        html = render_article(
            make_post(images=["1-image-01.jpg", "1-image-02.jpg"]),
            on_index_page=False,
        )
        assert html.index("1-image-01-resized.jpg") < html.index("1-image-02-resized.jpg")

    def test_images_block_before_h1_and_body(self):
        html = render_article(
            make_post(title="T", images=["1-image-01.jpg"], body_html="<p>B</p>"),
            on_index_page=False,
        )
        images_pos = html.index("post-images")
        h1_pos = html.index("<h1>")
        body_pos = html.index("post-body")
        assert images_pos < h1_pos < body_pos

    def test_images_wrapped_in_link_on_index_page(self):
        html = render_article(make_post(post_id=1, images=["1-image-01.jpg"]), on_index_page=True)
        assert '<a href="1.html"><img src="1-image-01-resized.jpg" alt=""></a>' in html

    def test_images_not_wrapped_in_link_on_post_page(self):
        html = render_article(make_post(post_id=1, images=["1-image-01.jpg"]), on_index_page=False)
        assert '<a href="1.html"><img' not in html
        assert 'src="1-image-01-resized.jpg"' in html


# ---------------------------------------------------------------------------
# render_article — index page photo limit
# ---------------------------------------------------------------------------

class TestRenderArticleIndexPagePhotoLimit:

    def test_only_first_two_images_shown_on_index_page(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=True)
        assert html.count("<figure>") == 2

    def test_third_image_not_shown_on_index_page(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=True)
        assert "1-image-03-resized.jpg" not in html

    def test_all_images_shown_on_post_page(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=False)
        assert html.count("<figure>") == 3

    def test_more_photos_link_present_when_more_than_two_images(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=True)
        assert 'class="more-photos"' in html

    def test_more_photos_link_points_to_post(self):
        images = ["5-image-01.jpg", "5-image-02.jpg", "5-image-03.jpg"]
        html = render_article(make_post(post_id=5, images=images), on_index_page=True)
        assert 'href="5.html"' in html

    def test_more_photos_singular_when_one_hidden(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=True)
        assert "1 more photo" in html
        assert "1 more photos" not in html

    def test_more_photos_plural_when_multiple_hidden(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg", "1-image-04.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=True)
        assert "2 more photos" in html

    def test_no_more_photos_link_with_exactly_two_images(self):
        images = ["1-image-01.jpg", "1-image-02.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=True)
        assert 'class="more-photos"' not in html

    def test_no_more_photos_link_with_one_image(self):
        images = ["1-image-01.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=True)
        assert 'class="more-photos"' not in html

    def test_no_more_photos_link_on_post_page(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=False)
        assert 'class="more-photos"' not in html

    def test_more_photos_link_outside_post_images_div(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=True)
        div_start = html.index('<div class="post-images">')
        div_end = html.index('</div>', div_start) + len('</div>')
        link_pos = html.index('class="more-photos"')
        assert not (div_start < link_pos < div_end)

    def test_more_photos_link_appears_after_post_body(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=True)
        body_end = html.index('</div>', html.index('class="post-body"')) + len('</div>')
        link_pos = html.index('class="more-photos"')
        assert link_pos > body_end

    def test_more_photos_link_appears_before_footer(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=True)
        link_pos = html.index('class="more-photos"')
        footer_pos = html.index('<footer>')
        assert link_pos < footer_pos

    def test_no_separate_more_photos_link_when_read_more_present(self):
        # When a <!-- more --> excerpt is shown, hidden photos are folded
        # into the "Read more" link's text instead of a separate link.
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        post = make_post(images=images, body_html="<p>Full body</p>", excerpt_html="<p>Intro</p>")
        html = render_article(post, on_index_page=True)
        assert 'class="more-photos"' not in html

    def test_read_more_text_includes_hidden_photo_count(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        post = make_post(images=images, body_html="<p>Full body</p>", excerpt_html="<p>Intro</p>")
        html = render_article(post, on_index_page=True)
        assert '<a href="1.html" class="read-more">Read more (+1 photo)</a>' in html

    def test_read_more_text_plain_when_no_hidden_images(self):
        images = ["1-image-01.jpg", "1-image-02.jpg"]
        post = make_post(images=images, body_html="<p>Full body</p>", excerpt_html="<p>Intro</p>")
        html = render_article(post, on_index_page=True)
        assert '<a href="1.html" class="read-more">Read more</a>' in html

    def test_img_alt_text_from_image_object(self):
        img = Image(filename="1-image-01.jpg", alt="A sunny beach")
        html = render_article(make_post(post_id=1, images=[img]), on_index_page=False)
        assert 'alt="A sunny beach"' in html

    def test_img_empty_alt_when_no_alt_text(self):
        html = render_article(make_post(post_id=1, images=["1-image-01.jpg"]), on_index_page=False)
        assert 'alt=""' in html

    def test_img_alt_double_quote_escaped(self):
        img = Image(filename="1-image-01.jpg", alt='Say "hello"')
        html = render_article(make_post(post_id=1, images=[img]), on_index_page=False)
        assert 'alt="Say &quot;hello&quot;"' in html

    def test_img_alt_ampersand_escaped(self):
        img = Image(filename="1-image-01.jpg", alt="A & B")
        html = render_article(make_post(post_id=1, images=[img]), on_index_page=False)
        assert 'alt="A &amp; B"' in html


# ---------------------------------------------------------------------------
# render_article — configurable images_per_post limit
# ---------------------------------------------------------------------------

class TestRenderArticleConfigurableImagesPerPost:

    def test_default_limit_is_still_two(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=True)
        assert html.count("<figure>") == 2

    def test_custom_limit_shows_more_images(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=True, images_per_post=3)
        assert html.count("<figure>") == 3
        assert 'class="more-photos"' not in html

    def test_custom_limit_hides_beyond_it(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg", "1-image-04.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=True, images_per_post=1)
        assert html.count("<figure>") == 1
        assert "3 more photos" in html

    def test_limit_of_zero_shows_no_images_on_index_page(self):
        images = ["1-image-01.jpg", "1-image-02.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=True, images_per_post=0)
        assert "post-images" not in html
        assert "2 more photos" in html

    def test_limit_does_not_affect_post_page(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        html = render_article(make_post(post_id=1, images=images), on_index_page=False, images_per_post=1)
        assert html.count("<figure>") == 3
        assert 'class="more-photos"' not in html

    def test_custom_limit_folds_into_read_more_count(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        post = make_post(images=images, body_html="<p>Full body</p>", excerpt_html="<p>Intro</p>")
        html = render_article(post, on_index_page=True, images_per_post=1)
        assert '<a href="1.html" class="read-more">Read more (+2 photos)</a>' in html


# ---------------------------------------------------------------------------
# render_article — images used inline via {{ image N }} excluded from top strip
# ---------------------------------------------------------------------------

class TestRenderArticleInlineImagesExcludedFromTop:

    def test_inline_image_not_shown_at_top_on_post_page(self):
        images = ["1-image-01.jpg", "1-image-02.jpg"]
        post = make_post(post_id=1, images=images, inline_image_filenames={"1-image-01.jpg"})
        html = render_article(post, on_index_page=False)
        assert "1-image-01-resized.jpg" not in html
        assert "1-image-02-resized.jpg" in html
        assert html.count("<figure>") == 1

    def test_inline_image_not_shown_at_top_on_index_page(self):
        images = ["1-image-01.jpg", "1-image-02.jpg"]
        post = make_post(post_id=1, images=images, inline_image_filenames={"1-image-01.jpg"})
        html = render_article(post, on_index_page=True)
        assert "1-image-01-resized.jpg" not in html
        assert "1-image-02-resized.jpg" in html

    def test_no_post_images_block_when_all_images_inline(self):
        images = ["1-image-01.jpg"]
        post = make_post(post_id=1, images=images, inline_image_filenames={"1-image-01.jpg"})
        html = render_article(post, on_index_page=False)
        assert "post-images" not in html

    def test_more_photos_count_excludes_inline_image(self):
        # 3 images total, 1 used inline -> 2 remain for the top strip -> no "more photos" link
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        post = make_post(post_id=1, images=images, inline_image_filenames={"1-image-01.jpg"})
        html = render_article(post, on_index_page=True)
        assert 'class="more-photos"' not in html

    def test_more_photos_count_reflects_remaining_top_images(self):
        # 4 images total, 1 used inline -> 3 remain -> top 2 shown, "1 more photo"
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg", "1-image-04.jpg"]
        post = make_post(post_id=1, images=images, inline_image_filenames={"1-image-01.jpg"})
        html = render_article(post, on_index_page=True)
        assert "1 more photo" in html
        assert "1 more photos" not in html

    def test_read_more_text_includes_inline_image_hidden_after_more_marker(self):
        # 1 top image (no overflow), 1 inline image used after <!-- more --> ->
        # not shown in the excerpt, so it should count as 1 hidden photo,
        # folded into the "Read more" text rather than a separate link.
        post = make_post(
            post_id=1,
            images=["1-image-01.jpg", "1-image-02.jpg"],
            excerpt_html="<p>Intro</p>",
            inline_image_filenames={"1-image-02.jpg"},
            excerpt_inline_image_filenames=frozenset(),
        )
        html = render_article(post, on_index_page=True)
        assert 'class="more-photos"' not in html
        assert '<a href="1.html" class="read-more">Read more (+1 photo)</a>' in html

    def test_read_more_text_plain_for_inline_image_shown_in_excerpt(self):
        # The inline image is used *before* the marker, so it's already
        # visible in the excerpt -> shouldn't count as hidden.
        post = make_post(
            post_id=1,
            images=["1-image-01.jpg"],
            excerpt_html="<p>Intro</p><figure><img src=\"1-image-01-resized.jpg\" alt=\"\"></figure>",
            inline_image_filenames={"1-image-01.jpg"},
            excerpt_inline_image_filenames={"1-image-01.jpg"},
        )
        html = render_article(post, on_index_page=True)
        assert 'class="more-photos"' not in html
        assert '<a href="1.html" class="read-more">Read more</a>' in html

    def test_read_more_text_combines_top_overflow_and_hidden_inline(self):
        # 3 top images (1 hidden beyond the first 2) + 1 inline image hidden
        # after the marker -> 2 hidden in total.
        post = make_post(
            post_id=1,
            images=["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg", "1-image-04.jpg"],
            excerpt_html="<p>Intro</p>",
            inline_image_filenames={"1-image-04.jpg"},
            excerpt_inline_image_filenames=frozenset(),
        )
        html = render_article(post, on_index_page=True)
        assert '<a href="1.html" class="read-more">Read more (+2 photos)</a>' in html

    def test_more_photos_link_absent_on_single_post_page_even_with_hidden_inline(self):
        post = make_post(
            post_id=1,
            images=["1-image-01.jpg", "1-image-02.jpg"],
            excerpt_html="<p>Intro</p>",
            inline_image_filenames={"1-image-02.jpg"},
            excerpt_inline_image_filenames=frozenset(),
        )
        html = render_article(post, on_index_page=False)
        assert 'class="more-photos"' not in html


# ---------------------------------------------------------------------------
# render_article — inline images (in body/excerpt) link through to the post
# on index/category pages, same as top-strip images
# ---------------------------------------------------------------------------

class TestRenderArticleInlineImagesLinkThrough:

    def test_inline_image_in_body_links_to_post_on_index_page(self):
        post = make_post(
            post_id=1,
            images=["1-image-01.jpg"],
            body_html='<p>Text</p><figure><img src="1-image-01-resized.jpg" alt="A cat"></figure>',
            inline_image_filenames={"1-image-01.jpg"},
        )
        html = render_article(post, on_index_page=True)
        assert '<figure><a href="1.html"><img src="1-image-01-resized.jpg" alt="A cat"></a></figure>' in html

    def test_inline_image_in_body_not_linked_on_post_page(self):
        post = make_post(
            post_id=1,
            images=["1-image-01.jpg"],
            body_html='<p>Text</p><figure><img src="1-image-01-resized.jpg" alt="A cat"></figure>',
            inline_image_filenames={"1-image-01.jpg"},
        )
        html = render_article(post, on_index_page=False)
        assert '<figure><img src="1-image-01-resized.jpg" alt="A cat"></figure>' in html
        assert '<a href="1.html"><img' not in html

    def test_inline_image_in_excerpt_links_to_post_on_index_page(self):
        post = make_post(
            post_id=1,
            title="My post",
            images=["1-image-01.jpg"],
            excerpt_html='<p>Intro</p><figure><img src="1-image-01-resized.jpg" alt=""></figure>',
            inline_image_filenames={"1-image-01.jpg"},
            excerpt_inline_image_filenames={"1-image-01.jpg"},
        )
        html = render_article(post, on_index_page=True)
        assert '<figure><a href="1.html"><img src="1-image-01-resized.jpg" alt=""></a></figure>' in html

    def test_multiple_inline_images_all_linked_on_index_page(self):
        post = make_post(
            post_id=1,
            images=["1-image-01.jpg", "1-image-02.jpg"],
            body_html=(
                '<p>Text</p>'
                '<figure><img src="1-image-01-resized.jpg" alt="First"></figure>'
                '<figure><img src="1-image-02-resized.jpg" alt="Second"></figure>'
            ),
            inline_image_filenames={"1-image-01.jpg", "1-image-02.jpg"},
        )
        html = render_article(post, on_index_page=True)
        assert '<figure><a href="1.html"><img src="1-image-01-resized.jpg" alt="First"></a></figure>' in html
        assert '<figure><a href="1.html"><img src="1-image-02-resized.jpg" alt="Second"></a></figure>' in html

    def test_inline_image_on_note_links_through_on_index_page(self):
        post = make_post(
            post_id=1,
            title=None,
            images=["1-image-01.jpg"],
            body_html='<figure><img src="1-image-01-resized.jpg" alt=""></figure>',
            inline_image_filenames={"1-image-01.jpg"},
            post_type="note",
        )
        html = render_article(post, on_index_page=True)
        assert '<figure><a href="1.html"><img src="1-image-01-resized.jpg" alt=""></a></figure>' in html


# ---------------------------------------------------------------------------
# render_article — title HTML escaping
# ---------------------------------------------------------------------------

class TestRenderArticleTitleEscaping:

    def test_title_ampersand_escaped_on_post_page(self):
        html = render_article(make_post(title="A & B"), on_index_page=False)
        assert "&amp;" in html
        assert "<h1>A & B</h1>" not in html

    def test_title_ampersand_escaped_on_index_page(self):
        html = render_article(make_post(title="A & B"), on_index_page=True)
        assert "&amp;" in html

    def test_title_angle_bracket_escaped_on_post_page(self):
        html = render_article(make_post(title="A > B"), on_index_page=False)
        assert "&gt;" in html


# ---------------------------------------------------------------------------
# render_post_page_content
# ---------------------------------------------------------------------------

class TestRenderPostPageContent:

    def test_article_wrapped_in_main(self):
        html = render_post_page_content(make_post())
        assert "<main>" in html
        assert "</main>" in html

    def test_article_inside_main(self):
        html = render_post_page_content(make_post(post_id=1))
        main_start = html.index("<main>")
        article_start = html.index("<article")
        main_end = html.index("</main>")
        assert main_start < article_start < main_end

    def test_nav_present(self):
        html = render_post_page_content(make_post())
        assert "<nav>" in html

    def test_back_link(self):
        html = render_post_page_content(make_post(post_id=5))
        assert '<a href="index.html">Blog home</a>' in html

    def test_back_link_has_no_utf_symbol(self):
        html = render_post_page_content(make_post())
        assert "⌂" not in html

    def test_article_rendered_without_links(self):
        html = render_post_page_content(make_post(post_id=1, title="T"))
        assert '<h1>T</h1>' in html

    def test_ai_disclosure_html_threaded_through(self):
        custom = 'Custom disclosure with a <a href="48.html">link</a>.'
        html = render_post_page_content(make_post(is_ai_assisted=True), ai_disclosure_html=custom)
        assert custom in html

    def test_back_link_in_separate_nav_from_post_navigation(self):
        html = render_post_page_content(make_post(), newer_url="2.html", older_url="1.html")
        back_pos = html.index("Blog home")
        older_pos = html.index("Older post")
        last_nav_before_back = html.rindex("<nav>", 0, back_pos)
        assert last_nav_before_back > older_pos


class TestRenderPostPageNavigation:

    def test_no_post_nav_when_only_post(self):
        html = render_post_page_content(make_post())
        assert "Newer post" not in html
        assert "Older post" not in html

    def test_newer_link_present_when_newer_exists(self):
        html = render_post_page_content(make_post(), newer_url="2.html")
        assert "Newer post" in html
        assert "←" not in html

    def test_older_link_present_when_older_exists(self):
        html = render_post_page_content(make_post(), older_url="1.html")
        assert "Older post" in html
        assert "→" not in html

    def test_newer_link_href(self):
        html = render_post_page_content(make_post(), newer_url="5.html")
        assert 'href="5.html"' in html

    def test_older_link_href(self):
        html = render_post_page_content(make_post(), older_url="3.html")
        assert 'href="3.html"' in html

    def test_newer_link_has_newer_class(self):
        html = render_post_page_content(make_post(), newer_url="2.html")
        assert 'class="newer"' in html

    def test_older_link_has_older_class(self):
        html = render_post_page_content(make_post(), older_url="1.html")
        assert 'class="older"' in html

    def test_newer_link_omitted_when_no_newer_post(self):
        html = render_post_page_content(make_post(), older_url="1.html")
        assert "Newer post" not in html

    def test_older_link_omitted_when_no_older_post(self):
        html = render_post_page_content(make_post(), newer_url="2.html")
        assert "Older post" not in html


# ---------------------------------------------------------------------------
# render_index_page_content
# ---------------------------------------------------------------------------

class TestRenderIndexPageContent:

    def test_articles_wrapped_in_main(self):
        posts = [make_post(post_id=1), make_post(post_id=2)]
        html = render_index_page_content(posts, page_num=1, total_pages=1)
        assert "<main>" in html
        assert html.count("<article") == 2

    def test_all_posts_rendered(self):
        posts = [make_post(post_id=i) for i in range(1, 6)]
        html = render_index_page_content(posts, page_num=1, total_pages=1)
        assert html.count("<article") == 5

    def test_articles_rendered_with_links(self):
        posts = [make_post(post_id=1, title="T")]
        html = render_index_page_content(posts, page_num=1, total_pages=1)
        assert '<h2><a href="1.html">T</a></h2>' in html

    def test_images_per_post_threaded_to_articles(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        posts = [make_post(post_id=1, images=images)]
        html = render_index_page_content(posts, page_num=1, total_pages=1, images_per_post=3)
        assert html.count("<figure>") == 3

    def test_nav_present_when_multiple_pages(self):
        posts = [make_post()]
        html = render_index_page_content(posts, page_num=2, total_pages=3)
        assert "<nav>" in html

    def test_no_nav_when_single_page(self):
        posts = [make_post()]
        html = render_index_page_content(posts, page_num=1, total_pages=1)
        assert "<nav>" not in html

    def test_newer_posts_link_absent_on_first_page(self):
        html = render_index_page_content([make_post()], page_num=1, total_pages=3)
        assert "Newer posts" not in html

    def test_older_posts_link_absent_on_last_page(self):
        html = render_index_page_content([make_post()], page_num=3, total_pages=3)
        assert "Older posts" not in html

    def test_both_links_present_on_middle_page(self):
        html = render_index_page_content([make_post()], page_num=2, total_pages=3)
        assert "Newer posts" in html
        assert "Older posts" in html

    def test_newer_posts_link_points_to_previous_page(self):
        html = render_index_page_content([make_post()], page_num=3, total_pages=4)
        assert 'href="index-2.html"' in html

    def test_newer_posts_link_on_page_2_points_to_index(self):
        html = render_index_page_content([make_post()], page_num=2, total_pages=3)
        assert 'href="index.html"' in html

    def test_older_posts_link_points_to_next_page(self):
        html = render_index_page_content([make_post()], page_num=2, total_pages=4)
        assert 'href="index-3.html"' in html

    def test_newer_posts_li_has_newer_class(self):
        html = render_index_page_content([make_post()], page_num=2, total_pages=3)
        assert '<li class="newer">' in html

    def test_older_posts_li_has_older_class(self):
        html = render_index_page_content([make_post()], page_num=1, total_pages=2)
        assert '<li class="older">' in html

    def test_newer_posts_link_has_no_left_arrow(self):
        html = render_index_page_content([make_post()], page_num=2, total_pages=3)
        assert 'Newer posts' in html
        assert '←' not in html

    def test_older_posts_link_has_no_right_arrow(self):
        html = render_index_page_content([make_post()], page_num=1, total_pages=2)
        assert 'Older posts' in html
        assert '→' not in html


# ---------------------------------------------------------------------------
# render_page_title
# ---------------------------------------------------------------------------

class TestRenderPageTitle:

    def test_index_page_1_is_just_site_name(self):
        assert render_page_title("My Blog", None, page_num=1) == "My Blog"

    def test_index_page_2_includes_page_number(self):
        assert render_page_title("My Blog", None, page_num=2) == "My Blog - Page 2"

    def test_post_with_title_is_title_dash_site(self):
        assert render_page_title("My Blog", "A Great Post", page_num=None) == "A Great Post - My Blog"

    def test_post_without_title_is_just_site_name(self):
        assert render_page_title("My Blog", None, page_num=None) == "My Blog"

    def test_index_page_1_with_index_title_appends_index_title(self):
        assert render_page_title("My Blog", None, page_num=1, index_title="Photos") == "My Blog - Photos"

    def test_index_page_1_without_index_title_is_just_site_name(self):
        assert render_page_title("My Blog", None, page_num=1, index_title=None) == "My Blog"

    def test_index_page_2_not_affected_by_index_title(self):
        assert render_page_title("My Blog", None, page_num=2, index_title="Photos") == "My Blog - Page 2"


# ---------------------------------------------------------------------------
# post_display_text
# ---------------------------------------------------------------------------

class TestPostDisplayText:

    def test_uses_title_when_set(self):
        post = make_post(title="A Great Post", name="Fallback name")
        assert post_display_text(post) == "A Great Post"

    def test_uses_name_when_no_title(self):
        post = make_post(title=None, name="A quiet morning")
        assert post_display_text(post) == "A quiet morning"

    def test_generated_note_label_when_no_title_no_name_no_images(self):
        post = make_post(title=None, name=None, date_uk="24 May 2026", images=[])
        assert post_display_text(post) == "Note posted 24 May 2026"

    def test_generated_photo_label_singular_for_one_top_level_image(self):
        post = make_post(title=None, name=None, date_uk="24 May 2026", images=["1-image-01.jpg"])
        assert post_display_text(post) == "Photo posted 24 May 2026"

    def test_generated_photos_label_plural_for_multiple_top_level_images(self):
        post = make_post(
            title=None, name=None, date_uk="24 May 2026",
            images=["1-image-01.jpg", "1-image-02.jpg"],
        )
        assert post_display_text(post) == "Photos posted 24 May 2026"

    def test_inline_only_images_dont_count_towards_photo_label(self):
        post = make_post(
            title=None, name=None, date_uk="24 May 2026",
            images=["1-image-01.jpg"], inline_image_filenames=frozenset({"1-image-01.jpg"}),
        )
        assert post_display_text(post) == "Note posted 24 May 2026"

    def test_generated_label_omits_posted_date_when_no_date(self):
        post = make_post(title=None, name=None, date_uk=None, images=[])
        assert post_display_text(post) == "Note"


# ---------------------------------------------------------------------------
# render_navigation
# ---------------------------------------------------------------------------

class TestRenderNavigation:

    def test_empty_dict_returns_empty_string(self):
        assert render_navigation({}) == ''

    def test_none_returns_empty_string(self):
        assert render_navigation(None) == ''

    def test_renders_ul(self):
        html = render_navigation({"index.html": "Home"})
        assert html.startswith('<ul>')
        assert html.endswith('</ul>')

    def test_renders_li_per_entry(self):
        html = render_navigation({"index.html": "Home", "archive.html": "Archive"})
        assert html.count('<li>') == 2
        assert html.count('</li>') == 2

    def test_link_href_and_label(self):
        html = render_navigation({"archive.html": "Archive"})
        assert '<li><a href="archive.html" class="nav-archive">Archive</a></li>' in html

    def test_entries_rendered_in_config_order(self):
        html = render_navigation({"archive.html": "Archive", "index.html": "Home"})
        assert html.index('Archive') < html.index('Home')

    def test_current_page_gets_current_class_appended(self):
        html = render_navigation({"index.html": "Home", "archive.html": "Archive"},
                                  current_filename="archive.html")
        assert '<a href="archive.html" class="nav-archive current" aria-current="page">Archive</a>' in html

    def test_non_current_pages_have_no_current_class(self):
        html = render_navigation({"index.html": "Home", "archive.html": "Archive"},
                                  current_filename="archive.html")
        assert '<a href="index.html" class="nav-index">Home</a>' in html

    def test_no_current_class_when_current_filename_not_provided(self):
        html = render_navigation({"index.html": "Home"})
        assert 'current' not in html

    def test_no_current_class_when_current_filename_does_not_match(self):
        html = render_navigation({"index.html": "Home"}, current_filename="archive.html")
        assert 'current' not in html

    def test_current_page_gets_aria_current(self):
        html = render_navigation({"index.html": "Home", "archive.html": "Archive"},
                                  current_filename="archive.html")
        assert 'aria-current="page"' in html

    def test_non_current_pages_have_no_aria_current(self):
        html = render_navigation({"index.html": "Home", "archive.html": "Archive"},
                                  current_filename="archive.html")
        assert '<a href="index.html" class="nav-index">Home</a>' in html
        assert html.count('aria-current') == 1

    def test_no_aria_current_when_current_filename_not_provided(self):
        html = render_navigation({"index.html": "Home"})
        assert 'aria-current' not in html

    def test_no_aria_current_when_current_filename_does_not_match(self):
        html = render_navigation({"index.html": "Home"}, current_filename="archive.html")
        assert 'aria-current' not in html

    def test_label_is_html_escaped(self):
        html = render_navigation({"fun.html": "Fun & Games"})
        assert '<a href="fun.html" class="nav-fun">Fun &amp; Games</a>' in html

    def test_each_link_gets_a_unique_class_per_page(self):
        html = render_navigation({"index.html": "Home", "archive.html": "Archive"})
        assert 'class="nav-index"' in html
        assert 'class="nav-archive"' in html

    def test_class_derived_from_href_strips_extension(self):
        html = render_navigation({"feed.xml": "Atom feed"})
        assert 'class="nav-feed"' in html

    def test_class_sanitises_non_alphanumeric_characters(self):
        html = render_navigation({"out-and-about.html": "Out & About"})
        assert 'class="nav-out-and-about"' in html

    def test_href_is_html_escaped(self):
        html = render_navigation({'fun&"games.html': "Fun & Games"})
        assert 'href="fun&amp;&quot;games.html"' in html


# ---------------------------------------------------------------------------
# render_template
# ---------------------------------------------------------------------------

class TestRenderTemplate:

    TEMPLATE = "<head>MAGNETIZER_METADATA</head><body>MAGNETIZER_CONTENT</body>"
    NAVIGATION_TEMPLATE = "<body><nav>MAGNETIZER_NAVIGATION</nav>MAGNETIZER_CONTENT</body>"
    PAGE_ID_TEMPLATE = "<body>MAGNETIZER_CONTENT<span>MAGNETIZER_PAGE_ID</span></body>"

    def test_metadata_placeholder_replaced(self):
        html = render_template(self.TEMPLATE, title="My Page", content="<p>hi</p>")
        assert "MAGNETIZER_METADATA" not in html

    def test_content_placeholder_replaced(self):
        html = render_template(self.TEMPLATE, title="T", content="<main>stuff</main>")
        assert "MAGNETIZER_CONTENT" not in html
        assert "<main>stuff</main>" in html

    def test_rest_of_template_preserved(self):
        html = render_template(self.TEMPLATE, title="T", content="C")
        assert "<head>" in html
        assert "<body>" in html

    def test_metadata_includes_title(self):
        html = render_template(self.TEMPLATE, title="My Page", content="C")
        assert "<title>My Page</title>" in html

    def test_metadata_includes_canonical_when_provided(self):
        html = render_template(self.TEMPLATE, title="T", content="C",
                               canonical="https://example.com/1.html")
        assert 'href="https://example.com/1.html"' in html

    def test_page_id_placeholder_replaced(self):
        html = render_template(self.PAGE_ID_TEMPLATE, title="T", content="C", page_id="56")
        assert "MAGNETIZER_PAGE_ID" not in html
        assert "<span>56</span>" in html

    def test_page_id_defaults_to_empty_string(self):
        html = render_template(self.PAGE_ID_TEMPLATE, title="T", content="C")
        assert "<span></span>" in html

    def test_metadata_omits_canonical_when_not_provided(self):
        html = render_template(self.TEMPLATE, title="T", content="C")
        assert 'rel="canonical"' not in html

    def test_metadata_includes_meta_description_when_provided(self):
        html = render_template(self.TEMPLATE, title="T", content="C",
                               meta_description="A great blog about things.")
        assert '<meta name="description" content="A great blog about things.">' in html

    def test_metadata_omits_meta_description_when_not_provided(self):
        html = render_template(self.TEMPLATE, title="T", content="C")
        assert '<meta name="description"' not in html

    def test_meta_description_special_chars_are_escaped(self):
        html = render_template(self.TEMPLATE, title="T", content="C",
                               meta_description='A "great" blog & <more>')
        assert 'content="A &quot;great&quot; blog &amp; &lt;more&gt;"' in html

    def test_title_special_chars_are_escaped(self):
        html = render_template(self.TEMPLATE, title='A "great" <post> & more', content="C")
        assert "<title>A &quot;great&quot; &lt;post&gt; &amp; more</title>" in html

    def test_canonical_special_chars_are_escaped(self):
        html = render_template(self.TEMPLATE, title="T", content="C",
                               canonical='https://example.com/?a=1&b="2"')
        assert 'href="https://example.com/?a=1&amp;b=&quot;2&quot;"' in html

    def test_metadata_includes_robots_noindex_when_is_noindex_true(self):
        html = render_template(self.TEMPLATE, title="T", content="C", is_noindex=True)
        assert '<meta name="robots" content="noindex">' in html

    def test_metadata_omits_robots_tag_when_not_noindex(self):
        html = render_template(self.TEMPLATE, title="T", content="C")
        assert 'name="robots"' not in html

    def test_metadata_line_order(self):
        html = render_template(self.TEMPLATE, title="T", content="C",
                               canonical="https://example.com/1.html",
                               meta_description="Desc.", is_noindex=True)
        title_pos = html.index("<title>")
        desc_pos = html.index('name="description"')
        canonical_pos = html.index('rel="canonical"')
        robots_pos = html.index('name="robots"')
        assert title_pos < desc_pos < canonical_pos < robots_pos

    def test_metadata_placeholder_in_content_is_not_replaced(self):
        content = "Visit MAGNETIZER_METADATA for more"
        html = render_template(self.TEMPLATE, title="T", content=content)
        assert "Visit MAGNETIZER_METADATA for more" in html

    def test_navigation_placeholder_replaced_when_provided(self):
        html = render_template(self.NAVIGATION_TEMPLATE, title="T", content="C",
                               navigation='<ul><li><a href="index.html">Home</a></li></ul>')
        assert "MAGNETIZER_NAVIGATION" not in html
        assert '<ul><li><a href="index.html">Home</a></li></ul>' in html

    def test_navigation_placeholder_removed_when_not_provided(self):
        html = render_template(self.NAVIGATION_TEMPLATE, title="T", content="C")
        assert "MAGNETIZER_NAVIGATION" not in html
        assert "<nav></nav>" in html


class TestCanonicalUrl:

    def test_index_html_maps_to_root(self):
        assert canonical_url("https://example.com", "index.html") == "https://example.com/"

    def test_index_page_2_includes_filename(self):
        assert canonical_url("https://example.com", "index-2.html") == "https://example.com/index-2.html"

    def test_post_filename_included(self):
        assert canonical_url("https://example.com", "5.html") == "https://example.com/5.html"

    def test_about_filename_included(self):
        assert canonical_url("https://example.com", "about.html") == "https://example.com/about.html"

    def test_archive_filename_included(self):
        assert canonical_url("https://example.com", "archive.html") == "https://example.com/archive.html"

    def test_trailing_slash_in_site_url_is_stripped(self):
        assert canonical_url("https://example.com/", "1.html") == "https://example.com/1.html"


# ---------------------------------------------------------------------------
# render_article — read more
# ---------------------------------------------------------------------------

class TestRenderArticleReadMore:

    def _post_with_excerpt(self):
        return Post(id=1, date="2026-05-24", date_uk="24 May 2026", title="My Post",
                    url="1.html", body_html="<p>Intro.</p><p>Rest.</p>",
                    excerpt_html="<p>Intro.</p>", images=[])

    def test_index_page_shows_excerpt_not_full_body(self):
        html = render_article(self._post_with_excerpt(), on_index_page=True)
        assert "<p>Intro.</p>" in html
        assert "<p>Rest.</p>" not in html

    def test_index_page_shows_read_more_link(self):
        html = render_article(self._post_with_excerpt(), on_index_page=True)
        assert "Read more</a>" in html

    def test_index_page_read_more_link_points_to_post(self):
        html = render_article(self._post_with_excerpt(), on_index_page=True)
        assert 'href="1.html"' in html
        assert 'class="read-more"' in html

    def test_index_page_no_read_more_when_no_excerpt(self):
        html = render_article(make_post(), on_index_page=True)
        assert "Read more" not in html

    def test_post_page_shows_full_body_when_excerpt_present(self):
        html = render_article(self._post_with_excerpt(), on_index_page=False)
        assert "<p>Intro.</p>" in html
        assert "<p>Rest.</p>" in html

    def test_post_page_no_read_more_link(self):
        html = render_article(self._post_with_excerpt(), on_index_page=False)
        assert "Read more" not in html

    def test_note_on_index_page_shows_full_body_despite_excerpt(self):
        post = Post(id=1, date="2026-05-24", date_uk="24 May 2026", title=None,
                    url="1.html", body_html="<p>Intro.</p><p>Rest.</p>",
                    excerpt_html="<p>Intro.</p>", images=[], post_type="note")
        html = render_article(post, on_index_page=True)
        assert "<p>Rest.</p>" in html
        assert "Read more" not in html


# ---------------------------------------------------------------------------
# render_archive_page_content
# ---------------------------------------------------------------------------

def make_dated_post(id, date, title=None, name=None, body_html="", images=None, category=None,
                     post_type=None, date_uk=""):
    return Post(id=id, date=date, date_uk=date_uk, title=title, name=name,
                url=f"{id}.html", body_html=body_html, images=images or [], category=category,
                post_type=post_type)


class TestRenderArchivePageContent:

    def test_has_h1_heading(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")])
        assert "<h1>Archive</h1>" in html

    def test_has_main_element(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")])
        assert "<main>" in html and "</main>" in html

    def test_has_back_link_to_homepage(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")])
        assert '<a href="index.html">Blog home</a>' in html

    def test_month_heading(self):
        # <h3>, not <h2> -- a month heading is a subsection under the page's
        # "Blog Posts" <h2>, not a sibling of it.
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")])
        assert "<h3>May 2026</h3>" in html

    def test_multiple_months_in_reverse_order(self):
        posts = [
            make_dated_post(2, "2026-05-24"),
            make_dated_post(1, "2026-04-10"),
        ]
        html = render_archive_page_content(posts)
        assert html.index("May 2026") < html.index("April 2026")

    def test_titled_post_shows_day_and_title(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24", title="Sunny day")])
        assert '<span class="day">24</span>' in html
        assert "Sunny day" in html

    def test_day_in_span_outside_link(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24", title="Sunny day")])
        assert html.index('<span class="day">') < html.index('<a href="1.html">')

    def test_each_entry_is_a_link_to_post(self):
        html = render_archive_page_content([make_dated_post(5, "2026-05-24", title="Hello")])
        assert 'href="5.html"' in html

    def test_posts_within_month_in_reverse_order(self):
        posts = [
            make_dated_post(3, "2026-05-30"),
            make_dated_post(1, "2026-05-10"),
        ]
        html = render_archive_page_content(posts)
        assert html.index('<span class="day">30</span>') < html.index('<span class="day">10</span>')

    def test_post_without_date_excluded(self):
        posts = [
            make_dated_post(2, "2026-05-24"),
            Post(id=1, date=None, date_uk=None, title="No date",
                 url="1.html", body_html="", images=[]),
        ]
        html = render_archive_page_content(posts)
        assert "No date" not in html

    def test_empty_posts_list(self):
        html = render_archive_page_content([])
        assert "<main>" in html

    def test_day_has_no_leading_zero_in_span(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-03", title="Post")])
        assert '<span class="day">3</span>' in html
        assert '<span class="day">03</span>' not in html

    def test_titled_post_title_escaped_in_archive(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24", title="A & B")])
        assert "&amp;" in html
        assert ">A & B<" not in html

    def test_h1_inside_main(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")])
        assert html.index("<main>") < html.index("<h1>Archive</h1>")

    def test_no_archive_stats_block(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")])
        assert "archive-stats" not in html

    def test_archive_item_full_post_class(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24", title="Hello", post_type="full")])
        assert '<li class="full-post">' in html

    def test_archive_item_image_post_class(self):
        from magnetizer.content import Image
        html = render_archive_page_content(
            [make_dated_post(1, "2026-05-24", images=[Image("1-image-01.jpg")], post_type="image")]
        )
        assert '<li class="image-post">' in html

    def test_archive_item_full_post_class_with_images(self):
        # A title always wins — a titled post with images is still full-post,
        # not a separate "mixed" class.
        from magnetizer.content import Image
        html = render_archive_page_content(
            [make_dated_post(1, "2026-05-24", title="Hello", images=[Image("1-image-01.jpg")], post_type="full")]
        )
        assert '<li class="full-post">' in html

    def test_note_post_not_in_monthly_list(self):
        post = Post(id=1, date="2026-05-24", date_uk="24 May 2026", title=None,
                    url="1.html", body_html="<p>Short text</p>", images=[], post_type="note")
        html = render_archive_page_content([post])
        assert '<li class="note">' not in html
        assert 'href="1.html"' not in html

    def test_archive_item_favourite_adds_class(self):
        post = Post(id=1, date="2026-05-24", date_uk="24 May 2026", title="Hello",
                    url="1.html", body_html="", images=[], is_favourite=True, post_type="full")
        html = render_archive_page_content([post])
        assert '<li class="full-post favourite">' in html

    def test_archive_item_non_favourite_has_no_favourite_class(self):
        post = Post(id=1, date="2026-05-24", date_uk="24 May 2026", title="Hello",
                    url="1.html", body_html="", images=[], is_favourite=False, post_type="full")
        html = render_archive_page_content([post])
        assert '<li class="full-post favourite">' not in html


# ---------------------------------------------------------------------------
# render_archive_page_content — contribution calendar
# ---------------------------------------------------------------------------

def _last_column_block(html):
    """The final <div class="calendar-column">...</div> block — always the
    column ending exactly on build_date, so it's a stable place to check
    build_date's own cell (always the last one)."""
    start = html.rindex('<div class="calendar-column">')
    end = html.index('</div>', start)
    return html[start:end]


def _first_column_block(html):
    start = html.index('<div class="calendar-column">')
    end = html.index('</div>', start)
    return html[start:end]


class TestRenderContributionCalendar:

    def test_section_present(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")], build_date=date(2026, 5, 24))
        assert '<section class="contribution-calendar">' in html

    def test_section_after_h1_and_before_categories(self):
        post = make_dated_post(1, "2026-05-24", category="photography")
        html = render_archive_page_content([post], categories=_CATEGORIES, build_date=date(2026, 5, 24))
        assert html.index("<h1>Archive</h1>") < html.index('<section class="contribution-calendar">')
        assert html.index('<section class="contribution-calendar">') < html.index("<h2>Categories</h2>")

    def test_heading_is_publishing_calendar_with_no_number(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")], build_date=date(2026, 5, 24))
        assert '<h2>Publishing calendar</h2>' in html
        assert 'calendar-count' not in html

    def test_summary_paragraph_after_heading(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")], build_date=date(2026, 5, 24))
        assert html.index('<h2>Publishing calendar</h2>') < html.index('<p class="calendar-summary">')

    def test_summary_counts_posts_and_notes_separately(self):
        posts = [
            make_dated_post(1, "2026-05-20", post_type="full"),
            make_dated_post(2, "2026-05-21", post_type="image"),
            make_dated_post(3, "2026-05-21", post_type="note"),
        ]
        html = render_archive_page_content(posts, build_date=date(2026, 5, 24))
        assert (
            '<p class="calendar-summary">I have posted '
            '<span class="calendar-post-count">2</span> posts and '
            '<span class="calendar-note-count">1</span> notes so far.</p>'
        ) in html

    def test_summary_excludes_posts_outside_window(self):
        # build_date=2026-01-04 -> window start_date is 2024-12-31 (370 days
        # back). A post the day before start_date must not be counted.
        posts = [make_dated_post(1, "2024-12-30")]
        html = render_archive_page_content(posts, build_date=date(2026, 1, 4))
        assert '<span class="calendar-post-count">0</span>' in html
        assert '<span class="calendar-note-count">0</span>' in html

    def test_empty_posts_list_still_renders_grid(self):
        html = render_archive_page_content([], build_date=date(2026, 5, 24))
        assert '<span class="calendar-post-count">0</span>' in html
        assert '<span class="calendar-note-count">0</span>' in html
        assert html.count('<div class="calendar-column">') == 37

    def test_grid_has_37_columns(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")], build_date=date(2026, 5, 24))
        assert html.count('<div class="calendar-column">') == 37

    def test_grid_has_37_month_column_cells(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")], build_date=date(2026, 5, 24))
        assert html.count('<span class="calendar-month">') == 37

    def test_grid_has_370_day_cells_total(self):
        # 37 columns of 10 days each -> 370 cells, always -- there's no
        # "hasn't happened yet" case any more, since the grid always ends
        # exactly on build_date regardless of which weekday it falls on.
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")], build_date=date(2026, 5, 24))
        assert html.count('class="calendar-day level-') == 370

    def test_no_empty_future_cells_concept_remains(self):
        # Previously a Monday/Wednesday build_date left trailing blank cells
        # in the final week. With 10-day columns always ending on build_date,
        # that concept no longer applies, for any build_date/weekday.
        for build_date in (date(2026, 5, 25), date(2026, 5, 27), date(2026, 5, 29)):
            html = render_archive_page_content([], build_date=build_date)
            assert 'calendar-day-empty' not in html

    def test_no_weekday_labels_or_label_column(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")], build_date=date(2026, 5, 24))
        assert 'calendar-day-label' not in html
        assert 'calendar-corner' not in html
        assert 'calendar-day-labels' not in html

    def test_build_date_is_always_the_last_cell_regardless_of_weekday(self):
        # The headline behaviour of the 10-day-column redesign: today is
        # always the bottom-right box, whichever day of the week it is.
        for build_date in (date(2026, 5, 25), date(2026, 5, 26), date(2026, 5, 27), date(2026, 5, 30)):
            posts = [make_dated_post(1, build_date.isoformat())]
            html = render_archive_page_content(posts, build_date=build_date, posts_per_page=12)
            block = _last_column_block(html)
            assert block.rstrip().endswith('<a href="index.html#post-1" class="calendar-day level-1" data-tooltip="'
                                            f'{build_date.day} {build_date.strftime("%B")}: 1 post" '
                                            f'aria-label="{build_date.day} {build_date.strftime("%B")}: 1 post"></a>')

    def test_first_column_starts_370_days_before_build_date(self):
        build_date = date(2026, 5, 24)
        start_date = build_date - timedelta(days=369)
        posts = [make_dated_post(1, start_date.isoformat())]
        html = render_archive_page_content(posts, build_date=build_date, posts_per_page=12)
        block = _first_column_block(html)
        assert block.startswith('<div class="calendar-column">\n<a href="index.html#post-1"')

    def test_leftmost_partial_month_is_labelled(self):
        # build_date=2026-01-04 -> start_date=2024-12-31. The first column
        # spans Dec 31 - Jan 9, straddling a month boundary; Jan 1 (day 2 of
        # that column) is the later month and wins the single label slot.
        html = render_archive_page_content([make_dated_post(1, "2025-06-01")], build_date=date(2026, 1, 4))
        first_month_cell = html.index('<span class="calendar-month">')
        assert html[first_month_cell:first_month_cell + 40].startswith('<span class="calendar-month">Jan</span>')

    def test_month_labels_in_left_to_right_chronological_order(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")], build_date=date(2026, 8, 7))
        assert html.index(">Aug<") < html.index(">Sep<") < html.index(">Dec<") < html.index(">Jan<") < html.index(">Jul<")

    def test_day_with_zero_posts_is_level_0_and_not_a_link(self):
        html = render_archive_page_content([], build_date=date(2026, 5, 24))
        block = _last_column_block(html)
        assert '<span class="calendar-day level-0"' in block
        assert '<a' not in block

    def test_zero_post_day_has_no_tooltip(self):
        html = render_archive_page_content([], build_date=date(2026, 5, 24))
        block = _last_column_block(html)
        assert '<span class="calendar-day level-0"></span>' in block
        assert 'data-tooltip' not in block

    def test_day_with_one_post_is_level_1_and_links_to_index(self):
        posts = [make_dated_post(7, "2026-05-24")]
        html = render_archive_page_content(posts, build_date=date(2026, 5, 24), posts_per_page=12)
        block = _last_column_block(html)
        assert '<a href="index.html#post-7" class="calendar-day level-1" data-tooltip="24 May: 1 post" aria-label="24 May: 1 post"></a>' in block

    def test_tooltip_uses_data_attribute_not_title(self):
        # A custom tooltip, not the native browser title="" tooltip.
        posts = [make_dated_post(7, "2026-05-24")]
        html = render_archive_page_content(posts, build_date=date(2026, 5, 24), posts_per_page=12)
        block = _last_column_block(html)
        assert 'title=' not in block

    def test_tooltip_singular_post_and_note(self):
        posts = [
            make_dated_post(1, "2026-05-24", post_type="full"),
            make_dated_post(2, "2026-05-24", post_type="note"),
        ]
        html = render_archive_page_content(posts, build_date=date(2026, 5, 24), posts_per_page=12)
        block = _last_column_block(html)
        assert 'data-tooltip="24 May: 1 post + 1 note"' in block
        assert 'aria-label="24 May: 1 post + 1 note"' in block

    def test_tooltip_plural_posts_and_notes(self):
        posts = [
            make_dated_post(1, "2026-05-24", post_type="full"),
            make_dated_post(2, "2026-05-24", post_type="image"),
            make_dated_post(3, "2026-05-24", post_type="note"),
            make_dated_post(4, "2026-05-24", post_type="note"),
        ]
        html = render_archive_page_content(posts, build_date=date(2026, 5, 24), posts_per_page=12)
        block = _last_column_block(html)
        assert 'data-tooltip="24 May: 2 posts + 2 notes"' in block

    def test_tooltip_notes_only(self):
        posts = [make_dated_post(1, "2026-05-24", post_type="note")]
        html = render_archive_page_content(posts, build_date=date(2026, 5, 24), posts_per_page=12)
        block = _last_column_block(html)
        assert 'data-tooltip="24 May: 1 note"' in block

    def test_bucketing_caps_at_level_5_for_six_or_more_posts(self):
        posts = [make_dated_post(i, "2026-05-24") for i in range(1, 7)]
        html = render_archive_page_content(posts, build_date=date(2026, 5, 24))
        block = _last_column_block(html)
        assert 'level-5' in block
        assert 'level-6' not in block

    def test_bucketing_exact_levels(self):
        for count, expected_level in [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]:
            posts = [make_dated_post(i, "2026-05-24") for i in range(1, count + 1)]
            html = render_archive_page_content(posts, build_date=date(2026, 5, 24))
            block = _last_column_block(html)
            assert f'level-{expected_level}"' in block
            assert f'level-{expected_level + 1}"' not in block

    def test_multiple_posts_same_day_links_to_newest(self):
        posts = [
            make_dated_post(3, "2026-05-24"),
            make_dated_post(9, "2026-05-24"),
            make_dated_post(1, "2026-05-24"),
        ]
        html = render_archive_page_content(posts, build_date=date(2026, 5, 24), posts_per_page=12)
        block = _last_column_block(html)
        assert 'href="index.html#post-9"' in block

    def test_link_target_paginates_by_position_in_list(self):
        # posts_per_page=2, three posts newest-first -> the 3rd post (index 2)
        # lands on page 2 (index-2.html).
        posts = [
            make_dated_post(3, "2026-05-22"),
            make_dated_post(2, "2026-05-23"),
            make_dated_post(1, "2026-05-24"),
        ]
        html = render_archive_page_content(posts, build_date=date(2026, 5, 24), posts_per_page=2)
        block = _last_column_block(html)
        assert 'href="index-2.html#post-1"' in block

    def test_post_without_date_not_counted_in_calendar(self):
        posts = [
            make_dated_post(2, "2026-05-24"),
            Post(id=1, date=None, date_uk=None, title="No date", url="1.html", body_html="", images=[]),
        ]
        html = render_archive_page_content(posts, build_date=date(2026, 5, 24))
        assert '<span class="calendar-post-count">1</span>' in html


# ---------------------------------------------------------------------------
# render_archive_page_content — categories list
# ---------------------------------------------------------------------------

class TestArchiveCategoriesList:

    def test_categories_heading_present_when_a_category_has_posts(self):
        post = make_dated_post(1, "2026-05-24", category="photography")
        html = render_archive_page_content([post], categories=_CATEGORIES)
        assert "<h2>Categories</h2>" in html

    def test_no_categories_heading_when_categories_param_is_none(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")])
        assert "<h2>Categories</h2>" not in html

    def test_no_categories_heading_when_categories_param_is_empty(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")], categories={})
        assert "<h2>Categories</h2>" not in html

    def test_no_categories_heading_when_no_post_uses_a_category(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")], categories=_CATEGORIES)
        assert "<h2>Categories</h2>" not in html

    def test_category_link_href(self):
        post = make_dated_post(1, "2026-05-24", category="photography")
        html = render_archive_page_content([post], categories=_CATEGORIES)
        assert '<a href="photography.html">' in html

    def test_category_link_text(self):
        post = make_dated_post(1, "2026-05-24", category="photography")
        html = render_archive_page_content([post], categories=_CATEGORIES)
        assert '<a href="photography.html">Photography</a>' in html

    def test_category_with_no_posts_excluded_from_list(self):
        post = make_dated_post(1, "2026-05-24", category="photography")
        html = render_archive_page_content([post], categories=_CATEGORIES)
        assert '<a href="travel.html">' not in html

    def test_category_with_more_posts_listed_first(self):
        posts = [
            make_dated_post(1, "2026-05-24", category="travel"),
            make_dated_post(2, "2026-05-25", category="photography"),
            make_dated_post(3, "2026-05-26", category="photography"),
        ]
        html = render_archive_page_content(posts, categories=_CATEGORIES)
        assert html.index("Photography") < html.index("Travel")

    def test_category_with_fewer_posts_listed_last(self):
        posts = [
            make_dated_post(1, "2026-05-24", category="travel"),
            make_dated_post(2, "2026-05-25", category="travel"),
            make_dated_post(3, "2026-05-26", category="photography"),
        ]
        html = render_archive_page_content(posts, categories=_CATEGORIES)
        assert html.index("Travel") < html.index("Photography")

    def test_category_item_is_li(self):
        post = make_dated_post(1, "2026-05-24", category="photography")
        html = render_archive_page_content([post], categories=_CATEGORIES)
        assert '<li><a href="photography.html">Photography</a> (1)</li>' in html

    def test_category_count_reflects_number_of_posts(self):
        posts = [
            make_dated_post(1, "2026-05-24", category="photography"),
            make_dated_post(2, "2026-05-25", category="photography"),
            make_dated_post(3, "2026-05-26", category="photography"),
        ]
        html = render_archive_page_content(posts, categories=_CATEGORIES)
        assert '<li><a href="photography.html">Photography</a> (3)</li>' in html

    def test_category_counts_are_independent_per_category(self):
        posts = [
            make_dated_post(1, "2026-05-24", category="photography"),
            make_dated_post(2, "2026-05-25", category="photography"),
            make_dated_post(3, "2026-05-26", category="travel"),
        ]
        html = render_archive_page_content(posts, categories=_CATEGORIES)
        assert '<li><a href="photography.html">Photography</a> (2)</li>' in html
        assert '<li><a href="travel.html">Travel</a> (1)</li>' in html

    def test_h1_before_categories_heading(self):
        post = make_dated_post(1, "2026-05-24", category="photography")
        html = render_archive_page_content([post], categories=_CATEGORIES)
        assert html.index("<h1>Archive</h1>") < html.index("<h2>Categories</h2>")

    def test_blog_posts_heading_present_when_categories_shown(self):
        post = make_dated_post(1, "2026-05-24", category="photography")
        html = render_archive_page_content([post], categories=_CATEGORIES)
        assert "<h2>Blog Posts</h2>" in html

    def test_blog_posts_heading_after_categories_list(self):
        post = make_dated_post(1, "2026-05-24", category="photography")
        html = render_archive_page_content([post], categories=_CATEGORIES)
        assert html.index('<a href="photography.html">') < html.index("<h2>Blog Posts</h2>")

    def test_no_blog_posts_heading_when_no_categories_and_no_notes(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")])
        assert "<h2>Blog Posts</h2>" not in html

    def test_category_display_name_escaped(self):
        post = make_dated_post(1, "2026-05-24", category="a-and-b")
        html = render_archive_page_content([post], categories={"a-and-b": "A & B"})
        assert "&amp;" in html
        assert ">A & B<" not in html

    def test_notes_section_shown_when_notes_exist(self):
        post = make_dated_post(1, "2026-05-24", post_type="note")
        html = render_archive_page_content([post])
        assert "<h2>Short notes</h2>" in html

    def test_notes_section_links_to_notes_html(self):
        post = make_dated_post(1, "2026-05-24", post_type="note")
        html = render_archive_page_content([post])
        assert '<a href="notes.html">All short notes</a>' in html

    def test_notes_section_not_shown_when_no_notes(self):
        post = make_dated_post(1, "2026-05-24")
        html = render_archive_page_content([post])
        assert "<h2>Short notes</h2>" not in html

    def test_notes_section_after_categories(self):
        posts = [
            make_dated_post(1, "2026-05-24", category="photography"),
            make_dated_post(2, "2026-05-25", post_type="note"),
        ]
        html = render_archive_page_content(posts, categories=_CATEGORIES)
        assert html.index("<h2>Short notes</h2>") > html.index("</ul>")

    def test_blog_posts_heading_shown_when_notes_exist(self):
        post = make_dated_post(1, "2026-05-24", post_type="note")
        html = render_archive_page_content([post])
        assert "<h2>Blog Posts</h2>" in html

    def test_blog_posts_heading_after_notes_section(self):
        post = make_dated_post(1, "2026-05-24", post_type="note")
        html = render_archive_page_content([post])
        assert html.index("<h2>Blog Posts</h2>") > html.index("<h2>Short notes</h2>")

    def test_photo_archive_section_shown_when_has_photos(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")], has_photos=True)
        assert "<h2>Photo archive</h2>" in html

    def test_photo_archive_section_links_to_gallery_html(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")], has_photos=True)
        assert '<a href="gallery.html">All photos</a>' in html

    def test_photo_archive_section_not_shown_when_no_photos(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")], has_photos=False)
        assert "<h2>Photo archive</h2>" not in html

    def test_photo_archive_section_after_notes_section(self):
        post = make_dated_post(1, "2026-05-24", post_type="note")
        html = render_archive_page_content([post], has_photos=True)
        assert html.index("<h2>Photo archive</h2>") > html.index("<h2>Short notes</h2>")


# ---------------------------------------------------------------------------
# render_archive_page_content — wide-viewport column layout
# ---------------------------------------------------------------------------

class TestArchiveColumnsLayout:

    def test_categories_and_notes_wrapped_in_columns_container(self):
        post = make_dated_post(1, "2026-05-24", category="photography", post_type="note")
        html = render_archive_page_content([post], categories=_CATEGORIES)
        assert '<div class="archive-columns">' in html
        assert html.index('<div class="archive-columns">') < html.index("<h2>Categories</h2>")

    def test_categories_div_wraps_categories_heading_and_list(self):
        post = make_dated_post(1, "2026-05-24", category="photography")
        html = render_archive_page_content([post], categories=_CATEGORIES)
        assert '<div class="archive-categories">\n<h2>Categories</h2>' in html

    def test_notes_div_wraps_notes_heading_and_list(self):
        post = make_dated_post(1, "2026-05-24", post_type="note")
        html = render_archive_page_content([post])
        assert '<div class="archive-notes">\n<h2>Short notes</h2>' in html

    def test_columns_container_has_both_divs_when_both_present(self):
        post = make_dated_post(1, "2026-05-24", category="photography", post_type="note")
        html = render_archive_page_content([post], categories=_CATEGORIES)
        assert "archive-categories" in html
        assert "archive-notes" in html

    def test_columns_container_present_with_only_categories(self):
        post = make_dated_post(1, "2026-05-24", category="photography")
        html = render_archive_page_content([post], categories=_CATEGORIES)
        assert '<div class="archive-columns">' in html
        assert "archive-categories" in html
        assert "archive-notes" not in html

    def test_columns_container_present_with_only_notes(self):
        post = make_dated_post(1, "2026-05-24", post_type="note")
        html = render_archive_page_content([post])
        assert '<div class="archive-columns">' in html
        assert "archive-notes" in html
        assert "archive-categories" not in html

    def test_columns_container_present_with_only_photos(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")], has_photos=True)
        assert '<div class="archive-columns">' in html
        assert "archive-notes" in html
        assert "archive-categories" not in html

    def test_photo_archive_shares_notes_div(self):
        post = make_dated_post(1, "2026-05-24", post_type="note")
        html = render_archive_page_content([post], has_photos=True)
        assert (
            '<div class="archive-notes">\n'
            '<h2>Short notes</h2>\n'
            '<ul>\n'
            '<li><a href="notes.html">All short notes</a></li>\n'
            '</ul>\n'
            '<h2>Photo archive</h2>\n'
            '<ul>\n'
            '<li><a href="gallery.html">All photos</a></li>\n'
            '</ul>\n'
            '</div>'
        ) in html

    def test_no_columns_container_when_neither_categories_nor_notes(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")])
        assert "archive-columns" not in html

    def test_month_sections_wrapped_in_archive_months_div(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24")])
        assert '<div class="archive-months">\n<section>' in html
        assert html.index('</section>\n</div>\n</main>') > 0

    def test_archive_months_div_after_blog_posts_heading(self):
        post = make_dated_post(1, "2026-05-24", category="photography")
        html = render_archive_page_content([post], categories=_CATEGORIES)
        assert html.index("<h2>Blog Posts</h2>") < html.index('<div class="archive-months">')

    def test_no_archive_months_div_when_no_dated_blog_posts(self):
        # A Note has no entry in the monthly list (see test_note_post_not_in_monthly_list),
        # so there's nothing to wrap.
        html = render_archive_page_content([make_dated_post(1, "2026-05-24", post_type="note")])
        assert "archive-months" not in html


# ---------------------------------------------------------------------------
# render_archive_page_content — post descriptions
# ---------------------------------------------------------------------------

class TestArchiveDescriptions:

    def test_titled_post_shows_title(self):
        html = render_archive_page_content([make_dated_post(1, "2026-05-24", title="My Title")])
        assert "My Title" in html

    def test_name_used_when_no_title(self):
        # Notes are excluded from the monthly list entirely, so the only untitled
        # posts that reach _archive_description are Image posts.
        html = render_archive_page_content([
            make_dated_post(1, "2026-05-24", name="A quiet morning",
                            images=[Image("1-image-01.jpg")], post_type="image")
        ])
        assert "A quiet morning" in html

    def test_title_wins_over_name(self):
        html = render_archive_page_content([
            make_dated_post(1, "2026-05-24", title="Real Title", name="Fallback name", post_type="full")
        ])
        assert "Real Title" in html
        assert "Fallback name" not in html

    def test_untitled_post_with_short_text_shows_full_text(self):
        html = render_archive_page_content([
            make_dated_post(1, "2026-05-24", body_html="<p>A short thought.</p>",
                            images=[Image("1-image-01.jpg")], post_type="image")
        ])
        assert "A short thought." in html

    def test_untitled_post_with_text_at_40_chars_not_truncated(self):
        text = "a" * 40
        html = render_archive_page_content([
            make_dated_post(1, "2026-05-24", body_html=f"<p>{text}</p>",
                            images=[Image("1-image-01.jpg")], post_type="image")
        ])
        assert text in html
        assert "…" not in html

    def test_untitled_post_with_text_over_40_chars_truncated(self):
        text = "a" * 41
        html = render_archive_page_content([
            make_dated_post(1, "2026-05-24", body_html=f"<p>{text}</p>",
                            images=[Image("1-image-01.jpg")], post_type="image")
        ])
        assert "a" * 40 + "…" in html

    def test_truncation_breaks_at_word_boundary(self):
        # 40-char cut falls mid-word in "enough" — should truncate before it
        html = render_archive_page_content([
            make_dated_post(1, "2026-05-24", images=[Image("1-image-01.jpg")], post_type="image",
                            body_html="<p>This sentence is intentionally long enough to need truncating.</p>")
        ])
        assert "This sentence is intentionally long…" in html

    def test_truncation_does_not_cut_mid_word(self):
        html = render_archive_page_content([
            make_dated_post(1, "2026-05-24", images=[Image("1-image-01.jpg")], post_type="image",
                            body_html="<p>This sentence is intentionally long enough to need truncating.</p>")
        ])
        assert "enou…" not in html

    def test_generated_fallback_used_when_only_images_no_title_name_or_text(self):
        html = render_archive_page_content([
            make_dated_post(1, "2026-05-24", date_uk="24 May 2026",
                            images=[Image("1-image-01.jpg")], post_type="image")
        ])
        assert "Photo posted 24 May 2026" in html

    def test_generated_fallback_pluralised_for_multiple_images(self):
        html = render_archive_page_content([
            make_dated_post(1, "2026-05-24", date_uk="24 May 2026",
                            images=[Image("1-image-01.jpg"), Image("1-image-02.jpg")], post_type="image")
        ])
        assert "Photos posted 24 May 2026" in html

    def test_untitled_post_with_text_and_images_shows_text_not_generated_label(self):
        html = render_archive_page_content([
            make_dated_post(1, "2026-05-24", post_type="image",
                            body_html="<p>Has text.</p>",
                            images=[Image("1-image-01.jpg")])
        ])
        assert "Has text." in html
        assert "Photo posted" not in html

    def test_uses_first_paragraph_only(self):
        html = render_archive_page_content([
            make_dated_post(1, "2026-05-24", body_html="<p>First.</p><p>Second.</p>",
                            images=[Image("1-image-01.jpg")], post_type="image")
        ])
        assert "First." in html
        assert "Second." not in html

    def test_inline_html_stripped_from_description(self):
        html = render_archive_page_content([
            make_dated_post(1, "2026-05-24", body_html="<p>Hello <strong>world</strong>.</p>")
        ])
        assert "Hello world." in html
        assert "<strong>" not in html

    def test_description_html_escaped(self):
        html = render_archive_page_content([
            make_dated_post(1, "2026-05-24", body_html="<p>A &amp; B</p>")
        ])
        assert "A &amp; B" in html


# ---------------------------------------------------------------------------
# archive_display_text — the same title-fallback chain as the archive
# listing, but as plain text (unescaped) for non-HTML consumers
# ---------------------------------------------------------------------------

class TestArchiveDisplayText:

    def test_title_used_when_present(self):
        assert archive_display_text(make_dated_post(1, "2026-05-24", title="My Title")) == "My Title"

    def test_name_used_when_no_title(self):
        post = make_dated_post(1, "2026-05-24", name="A quiet morning",
                                images=[Image("1-image-01.jpg")], post_type="image")
        assert archive_display_text(post) == "A quiet morning"

    def test_title_wins_over_name(self):
        post = make_dated_post(1, "2026-05-24", title="Real Title", name="Fallback name", post_type="full")
        assert archive_display_text(post) == "Real Title"

    def test_excerpt_used_when_no_title_or_name(self):
        post = make_dated_post(1, "2026-05-24", body_html="<p>A short thought.</p>",
                                images=[Image("1-image-01.jpg")], post_type="image")
        assert archive_display_text(post) == "A short thought."

    def test_excerpt_truncated_over_40_chars(self):
        text = "a" * 41
        post = make_dated_post(1, "2026-05-24", body_html=f"<p>{text}</p>",
                                images=[Image("1-image-01.jpg")], post_type="image")
        assert archive_display_text(post) == "a" * 40 + "…"

    def test_generated_label_used_when_no_title_name_or_text(self):
        post = make_dated_post(1, "2026-05-24", date_uk="24 May 2026",
                                images=[Image("1-image-01.jpg")], post_type="image")
        assert archive_display_text(post) == "Photo posted 24 May 2026"

    def test_result_is_not_html_escaped(self):
        post = make_dated_post(1, "2026-05-24", body_html="<p>A &amp; B</p>")
        assert archive_display_text(post) == "A & B"


# ---------------------------------------------------------------------------
# render_article — category link
# ---------------------------------------------------------------------------

_CATEGORIES = {"photography": "Photography", "travel": "Travel"}


class TestRenderArticleCategory:

    def test_category_link_in_footer_when_category_set(self):
        html = render_article(make_post(category="photography"), on_index_page=False, categories=_CATEGORIES)
        assert 'class="category"' in html

    def test_no_category_link_when_post_has_no_category(self):
        html = render_article(make_post(), on_index_page=False, categories=_CATEGORIES)
        assert 'class="category"' not in html

    def test_no_category_link_when_categories_not_provided(self):
        html = render_article(make_post(category="photography"), on_index_page=False)
        assert 'class="category"' not in html

    def test_no_category_link_when_categories_empty(self):
        html = render_article(make_post(category="photography"), on_index_page=False, categories={})
        assert 'class="category"' not in html

    def test_category_link_href_points_to_category_page(self):
        html = render_article(make_post(category="photography"), on_index_page=False, categories=_CATEGORIES)
        assert 'href="photography.html"' in html

    def test_category_link_text_is_display_name(self):
        html = render_article(make_post(category="photography"), on_index_page=False, categories=_CATEGORIES)
        assert ">Photography<" in html

    def test_category_link_inside_footer(self):
        html = render_article(make_post(category="photography"), on_index_page=False, categories=_CATEGORIES)
        footer_start = html.index('<footer>')
        footer_end = html.index('</footer>')
        link_pos = html.index('class="category"')
        assert footer_start < link_pos < footer_end

    def test_category_link_appears_on_index_page_too(self):
        html = render_article(make_post(category="photography"), on_index_page=True, categories=_CATEGORIES)
        assert 'class="category"' in html

    def test_no_category_link_for_unknown_category(self):
        html = render_article(make_post(category="unknown"), on_index_page=False, categories=_CATEGORIES)
        assert 'class="category"' not in html

    def test_category_display_name_is_html_escaped(self):
        cats = {"fun": "Fun & Games"}
        html = render_article(make_post(category="fun"), on_index_page=False, categories=cats)
        assert "Fun &amp; Games" in html
        assert "Fun & Games<" not in html


# ---------------------------------------------------------------------------
# render_article — AI-assisted disclosure banner
# ---------------------------------------------------------------------------

_VOID_ELEMENTS = {"img", "br", "hr", "meta", "link", "input"}


def _direct_children(html):
    """(tag, class) for each direct child of the outermost element in `html`."""
    class _Collector(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []
            self.children = []

        def handle_starttag(self, tag, attrs):
            if len(self.stack) == 1:
                self.children.append((tag, dict(attrs).get("class", "")))
            if tag not in _VOID_ELEMENTS:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if self.stack and self.stack[-1] == tag:
                self.stack.pop()

    collector = _Collector()
    collector.feed(html)
    return collector.children


class TestRenderArticleAiDisclosure:

    def _post_with_excerpt(self, is_ai_assisted):
        return Post(id=1, date="2026-05-24", date_uk="24 May 2026", title="My Post",
                    url="1.html", body_html="<p>Intro.</p><p>Rest.</p>",
                    excerpt_html="<p>Intro.</p>", images=[], is_ai_assisted=is_ai_assisted)

    def test_no_banner_by_default(self):
        html = render_article(make_post(), on_index_page=False)
        assert "ai-disclosure" not in html

    def test_banner_present_when_ai_assisted(self):
        html = render_article(make_post(is_ai_assisted=True), on_index_page=False)
        assert "ai-disclosure" in html

    def test_banner_has_brown_container_classes(self):
        html = render_article(make_post(is_ai_assisted=True), on_index_page=False)
        assert 'class="container container-brown ai-disclosure"' in html

    def test_banner_uses_default_text_when_not_configured(self):
        html = render_article(make_post(is_ai_assisted=True), on_index_page=False)
        assert "entirely or partially created using AI" in html

    def test_banner_default_text_uses_only_ascii(self):
        # No literal curly-quote characters etc. in the built-in fallback text,
        # so it can't mojibake on a template missing <meta charset="UTF-8">.
        html = render_article(make_post(is_ai_assisted=True), on_index_page=False)
        banner_start = html.index('ai-disclosure')
        banner_end = html.index('</div>', banner_start)
        banner = html[banner_start:banner_end]
        assert all(ord(c) < 128 for c in banner)

    def test_banner_uses_configured_text_when_provided(self):
        custom = 'Custom disclosure with a <a href="48.html">link</a>.'
        html = render_article(make_post(is_ai_assisted=True), on_index_page=False, ai_disclosure_html=custom)
        assert custom in html
        assert "entirely or partially created using AI" not in html

    def test_banner_configured_text_not_escaped(self):
        custom = 'Text with <a href="48.html">a link</a> & an ampersand.'
        html = render_article(make_post(is_ai_assisted=True), on_index_page=False, ai_disclosure_html=custom)
        assert '<a href="48.html">a link</a>' in html
        assert '&amp;' not in html

    def test_banner_has_no_img_tag(self):
        # The icon is a CSS background image (like every other icon on the site),
        # not an <img> pointing at a separate resource file. Scoped to the banner
        # itself, since render_article may legitimately include <img> for post images.
        html = render_article(make_post(is_ai_assisted=True), on_index_page=False)
        start = html.index('<div class="container container-brown ai-disclosure">')
        end = html.index('</div>', start)
        banner = html[start:end]
        assert '<img' not in banner
        assert 'ai-icon.svg' not in banner

    def test_banner_outside_post_body_div(self):
        html = render_article(make_post(is_ai_assisted=True), on_index_page=False)
        body_start = html.index('<div class="post-body">')
        banner_pos = html.index('ai-disclosure')
        assert banner_pos < body_start

    def test_banner_appears_before_body_content(self):
        html = render_article(make_post(is_ai_assisted=True, body_html="<p>Hello</p>"), on_index_page=False)
        assert html.index('ai-disclosure') < html.index('<p>Hello</p>')

    def test_banner_appears_before_heading_on_single_post(self):
        html = render_article(make_post(is_ai_assisted=True, title="My Post"), on_index_page=False)
        assert html.index('ai-disclosure') < html.index('<h1>')

    def test_banner_appears_before_heading_on_index_page(self):
        html = render_article(self._post_with_excerpt(is_ai_assisted=True), on_index_page=True)
        assert html.index('ai-disclosure') < html.index('<h2>')

    def test_banner_is_direct_child_of_article_after_images(self):
        post = make_post(is_ai_assisted=True, images=["1-image-01.jpg"])
        html = render_article(post, on_index_page=False)
        children = _direct_children(html)

        images_index = next(i for i, (_, cls) in enumerate(children) if cls == "post-images")
        banner_index = next(i for i, (_, cls) in enumerate(children) if "ai-disclosure" in cls)
        heading_index = next(i for i, (tag, _) in enumerate(children) if tag == "h1")
        assert images_index < banner_index < heading_index

    def test_banner_appears_in_excerpt_on_index_page(self):
        html = render_article(self._post_with_excerpt(is_ai_assisted=True), on_index_page=True)
        assert "ai-disclosure" in html

    def test_no_banner_in_excerpt_when_not_ai_assisted(self):
        html = render_article(self._post_with_excerpt(is_ai_assisted=False), on_index_page=True)
        assert "ai-disclosure" not in html


# ---------------------------------------------------------------------------
# render_article — notes footer link
# ---------------------------------------------------------------------------

class TestRenderArticleNotesLink:

    def test_notes_link_in_footer_for_note(self):
        html = render_article(make_post(post_type="note", title=None), on_index_page=False)
        assert 'class="notes"' in html

    def test_no_notes_link_for_non_note_post(self):
        html = render_article(make_post(post_type="full"), on_index_page=False)
        assert 'class="notes"' not in html

    def test_notes_link_href_points_to_notes_html(self):
        html = render_article(make_post(post_type="note", title=None), on_index_page=False)
        assert 'href="notes.html"' in html

    def test_notes_link_text_is_short_note(self):
        html = render_article(make_post(post_type="note", title=None), on_index_page=False)
        assert ">Short note<" in html

    def test_notes_link_inside_footer(self):
        html = render_article(make_post(post_type="note", title=None), on_index_page=False)
        footer_start = html.index('<footer>')
        footer_end = html.index('</footer>')
        link_pos = html.index('class="notes"')
        assert footer_start < link_pos < footer_end

    def test_notes_link_before_category_link(self):
        html = render_article(make_post(post_type="note", title=None, category="photography"),
                              on_index_page=False, categories=_CATEGORIES)
        assert html.index('class="notes"') < html.index('class="category"')

    def test_notes_link_appears_on_index_page(self):
        html = render_article(make_post(post_type="note", title=None), on_index_page=True)
        assert 'class="notes"' in html


# ---------------------------------------------------------------------------
# render_article — comments section (single-post pages)
# ---------------------------------------------------------------------------

class TestRenderArticleCommentsSection:

    def test_no_comments_section_when_no_comments(self):
        html = render_article(make_post(), on_index_page=False)
        assert 'class="comments"' not in html

    def test_comments_section_present_when_comments_exist(self):
        html = render_article(make_post(comments=[make_comment()]), on_index_page=False)
        assert '<section class="comments" id="comments">' in html

    def test_comments_section_not_rendered_on_index_page(self):
        html = render_article(make_post(comments=[make_comment()]), on_index_page=True)
        assert '<section class="comments"' not in html

    def test_comments_section_after_footer(self):
        html = render_article(make_post(comments=[make_comment()]), on_index_page=False)
        footer_end = html.index('</footer>')
        section_start = html.index('<section class="comments"')
        assert footer_end < section_start

    def test_comments_section_before_article_close(self):
        html = render_article(make_post(comments=[make_comment()]), on_index_page=False)
        section_start = html.index('<section class="comments"')
        article_close = html.rindex('</article>')
        assert section_start < article_close

    def test_comments_section_present_without_footer(self):
        # A dateless special page has no <footer>, but its comments section
        # still renders — the two are independent.
        post = make_post(date=None, date_uk=None, comments=[make_comment()])
        html = render_article(post, on_index_page=False)
        assert '<footer>' not in html
        assert '<section class="comments" id="comments">' in html

    def test_heading_singular_for_one_comment(self):
        html = render_article(make_post(comments=[make_comment()]), on_index_page=False)
        assert '<h2>1 comment</h2>' in html

    def test_heading_plural_for_multiple_comments(self):
        comments = [make_comment(filename="1-comment-01.md"), make_comment(filename="1-comment-02.md")]
        html = render_article(make_post(comments=comments), on_index_page=False)
        assert '<h2>2 comments</h2>' in html

    def test_each_comment_is_an_article(self):
        html = render_article(make_post(comments=[make_comment()]), on_index_page=False)
        assert '<article class="comment">' in html

    def test_comment_author_heading(self):
        html = render_article(make_post(comments=[make_comment(author="Magnus", author_slug="magnus")]), on_index_page=False)
        assert '<h4 class="author author-magnus">Magnus</h4>' in html

    def test_comment_author_escaped(self):
        html = render_article(make_post(comments=[make_comment(author="Bill & Ted", author_slug="bill-ted")]), on_index_page=False)
        assert 'Bill &amp; Ted' in html

    def test_comment_time_element(self):
        html = render_article(make_post(comments=[make_comment(date="2026-08-05", date_uk="5 August 2026")]), on_index_page=False)
        assert '<time datetime="2026-08-05">5 August 2026</time>' in html

    def test_comment_body_html_included(self):
        html = render_article(make_post(comments=[make_comment(body_html="<p>Nice post!</p>")]), on_index_page=False)
        assert '<p>Nice post!</p>' in html

    def test_comment_avatar_div(self):
        html = render_article(make_post(comments=[make_comment(author_slug="magnus", author_initial="M")]), on_index_page=False)
        assert '<div class="avatar author-magnus" data-initial="M" aria-hidden="true"></div>' in html

    def test_comment_avatar_before_author_heading(self):
        html = render_article(make_post(comments=[make_comment()]), on_index_page=False)
        assert html.index('class="avatar') < html.index('class="author')

    def test_comment_avatar_data_initial_escaped(self):
        # Not a realistic initial, but confirms the attribute is safely escaped.
        html = render_article(make_post(comments=[make_comment(author_initial='"')]), on_index_page=False)
        assert 'data-initial="&quot;"' in html

    def test_comments_rendered_oldest_first(self):
        c1 = make_comment(filename="1-comment-01.md", author="First")
        c2 = make_comment(filename="1-comment-02.md", author="Second")
        # Post.comments is already sorted by parse_post; render_article must
        # preserve that order rather than re-sorting or reversing it.
        html = render_article(make_post(comments=[c1, c2]), on_index_page=False)
        assert html.index('First') < html.index('Second')


# ---------------------------------------------------------------------------
# render_article — comment count link (multi-post pages)
# ---------------------------------------------------------------------------

class TestRenderArticleCommentsCountLink:

    def test_no_link_when_no_comments(self):
        html = render_article(make_post(), on_index_page=True)
        assert 'class="comments"' not in html

    def test_no_link_on_single_post_page(self):
        # The full section is shown instead — see TestRenderArticleCommentsSection.
        html = render_article(make_post(comments=[make_comment()]), on_index_page=False)
        assert 'href="1.html#comments"' not in html

    def test_link_present_on_index_page_when_comments_exist(self):
        html = render_article(make_post(comments=[make_comment()]), on_index_page=True)
        assert 'href="1.html#comments" class="comments"' in html

    def test_link_text_singular(self):
        html = render_article(make_post(comments=[make_comment()]), on_index_page=True)
        assert '>1 comment<' in html

    def test_link_text_plural(self):
        comments = [make_comment(filename="1-comment-01.md"), make_comment(filename="1-comment-02.md")]
        html = render_article(make_post(comments=comments), on_index_page=True)
        assert '>2 comments<' in html

    def test_link_is_last_item_in_footer(self):
        html = render_article(
            make_post(post_type="note", title=None, category="photography", comments=[make_comment()]),
            on_index_page=True, categories=_CATEGORIES,
        )
        footer_start = html.index('<footer>')
        footer_end = html.index('</footer>')
        footer = html[footer_start:footer_end]
        assert footer.rindex('class="comments"') > footer.rindex('class="category"') > footer.rindex('class="notes"')

    def test_link_inside_footer(self):
        html = render_article(make_post(comments=[make_comment()]), on_index_page=True)
        footer_start = html.index('<footer>')
        footer_end = html.index('</footer>')
        link_pos = html.index('class="comments"')
        assert footer_start < link_pos < footer_end


# ---------------------------------------------------------------------------
# category_page_url
# ---------------------------------------------------------------------------

class TestCategoryPageUrl:

    def test_first_page_is_slug_dot_html(self):
        assert category_page_url("photography", 1) == "photography.html"

    def test_second_page_has_number_suffix(self):
        assert category_page_url("photography", 2) == "photography-2.html"

    def test_third_page_has_number_suffix(self):
        assert category_page_url("photography", 3) == "photography-3.html"


# ---------------------------------------------------------------------------
# render_category_page_content
# ---------------------------------------------------------------------------

class TestRenderCategoryPage:

    def test_category_page_has_h1_with_category_name(self):
        html = render_category_page_content([make_post()], "Photography", "photography", 1, 1)
        assert "<h1>Photography</h1>" in html

    def test_category_page_h1_inside_main(self):
        html = render_category_page_content([make_post()], "Photography", "photography", 1, 1)
        main_start = html.index('<main>')
        h1_pos = html.index('<h1>Photography</h1>')
        main_end = html.index('</main>')
        assert main_start < h1_pos < main_end

    def test_category_page_h1_before_articles(self):
        html = render_category_page_content([make_post()], "Photography", "photography", 1, 1)
        assert html.index('<h1>') < html.index('<article')

    def test_category_page_includes_post_articles(self):
        posts = [make_post(post_id=1), make_post(post_id=2)]
        html = render_category_page_content(posts, "Photography", "photography", 1, 1)
        assert html.count('<article') == 2

    def test_images_per_post_threaded_to_articles(self):
        images = ["1-image-01.jpg", "1-image-02.jpg", "1-image-03.jpg"]
        posts = [make_post(post_id=1, images=images)]
        html = render_category_page_content(posts, "Photography", "photography", 1, 1, images_per_post=3)
        assert html.count("<figure>") == 3

    def test_category_page_has_back_to_homepage_link(self):
        html = render_category_page_content([make_post()], "Photography", "photography", 1, 1)
        assert '<a href="index.html">Blog home</a>' in html

    def test_category_page_no_pagination_nav_when_single_page(self):
        html = render_category_page_content([make_post()], "Photography", "photography", 1, 1)
        assert 'photography-2.html' not in html

    def test_category_page_older_link_present_on_page_1_of_2(self):
        html = render_category_page_content([make_post()], "Photography", "photography", 1, 2)
        assert 'href="photography-2.html"' in html

    def test_category_page_newer_link_present_on_page_2_of_2(self):
        html = render_category_page_content([make_post()], "Photography", "photography", 2, 2)
        assert 'href="photography.html"' in html

    def test_category_page_no_newer_link_on_page_1(self):
        html = render_category_page_content([make_post()], "Photography", "photography", 1, 2)
        assert 'class="newer"' not in html

    def test_category_page_no_older_link_on_last_page(self):
        html = render_category_page_content([make_post()], "Photography", "photography", 2, 2)
        assert 'class="older"' not in html

    def test_category_name_is_html_escaped(self):
        html = render_category_page_content([make_post()], "Fun & Games", "fun", 1, 1)
        assert "<h1>Fun &amp; Games</h1>" in html
        assert "<h1>Fun & Games</h1>" not in html

    def test_category_page_passes_categories_to_articles(self):
        post = make_post(category="photography")
        html = render_category_page_content([post], "Photography", "photography", 1, 1,
                                            categories=_CATEGORIES)
        assert 'class="category"' in html


# ---------------------------------------------------------------------------
# notes_page_url
# ---------------------------------------------------------------------------

class TestNotesPageUrl:

    def test_first_page_is_notes_dot_html(self):
        assert notes_page_url(1) == "notes.html"

    def test_second_page_has_number_suffix(self):
        assert notes_page_url(2) == "notes-2.html"

    def test_third_page_has_number_suffix(self):
        assert notes_page_url(3) == "notes-3.html"


# ---------------------------------------------------------------------------
# render_notes_page_content
# ---------------------------------------------------------------------------

_NOTE_POST = Post(id=1, date="2026-05-24", date_uk="24 May 2026", title=None,
                  url="1.html", body_html="<p>Short.</p>", images=[], post_type="note")


class TestRenderNotesPage:

    def test_notes_page_has_h1_notes(self):
        html = render_notes_page_content([_NOTE_POST], 1, 1)
        assert "<h1>Short notes</h1>" in html

    def test_notes_h1_inside_main(self):
        html = render_notes_page_content([_NOTE_POST], 1, 1)
        assert html.index('<main>') < html.index('<h1>Short notes</h1>') < html.index('</main>')

    def test_notes_h1_before_articles(self):
        html = render_notes_page_content([_NOTE_POST], 1, 1)
        assert html.index('<h1>') < html.index('<article')

    def test_notes_page_includes_post_articles(self):
        p2 = Post(id=2, date="2026-05-25", date_uk="25 May 2026", title=None,
                  url="2.html", body_html="<p>Another.</p>", images=[], post_type="note")
        html = render_notes_page_content([_NOTE_POST, p2], 1, 1)
        assert html.count('<article') == 2

    def test_images_per_post_threaded_to_articles(self):
        images = [Image(f"1-image-0{n}.jpg") for n in (1, 2, 3)]
        post = Post(id=1, date="2026-05-24", date_uk="24 May 2026", title=None,
                    url="1.html", body_html="", images=images, post_type="note")
        html = render_notes_page_content([post], 1, 1, images_per_post=3)
        assert html.count("<figure>") == 3

    def test_notes_page_has_back_to_homepage_link(self):
        html = render_notes_page_content([_NOTE_POST], 1, 1)
        assert '<a href="index.html">Blog home</a>' in html

    def test_notes_no_pagination_nav_when_single_page(self):
        html = render_notes_page_content([_NOTE_POST], 1, 1)
        assert 'notes-2.html' not in html

    def test_notes_older_link_present_on_page_1_of_2(self):
        html = render_notes_page_content([_NOTE_POST], 1, 2)
        assert 'href="notes-2.html"' in html

    def test_notes_newer_link_present_on_page_2_of_2(self):
        html = render_notes_page_content([_NOTE_POST], 2, 2)
        assert 'href="notes.html"' in html

    def test_notes_no_newer_link_on_page_1(self):
        html = render_notes_page_content([_NOTE_POST], 1, 2)
        assert 'class="newer"' not in html

    def test_notes_no_older_link_on_last_page(self):
        html = render_notes_page_content([_NOTE_POST], 2, 2)
        assert 'class="older"' not in html


# ---------------------------------------------------------------------------
# gallery_page_url
# ---------------------------------------------------------------------------

class TestGalleryPageUrl:

    def test_first_page_is_gallery_dot_html(self):
        assert gallery_page_url(1) == "gallery.html"

    def test_second_page_has_number_suffix(self):
        assert gallery_page_url(2) == "gallery-2.html"

    def test_third_page_has_number_suffix(self):
        assert gallery_page_url(3) == "gallery-3.html"


# ---------------------------------------------------------------------------
# render_gallery_page_content
# ---------------------------------------------------------------------------

def make_photo(
    post_id=26,
    post_url="26.html",
    full="26-image-01-resized.jpg",
    thumb="26-image-01-thumb.jpg",
    alt="A sunset",
    width=400,
    height=267,
):
    return {
        "post_id": post_id,
        "post_url": post_url,
        "full": full,
        "thumb": thumb,
        "alt": alt,
        "width": width,
        "height": height,
    }


class TestRenderGalleryPage:

    def test_gallery_page_has_h1_photo_archive(self):
        html = render_gallery_page_content([make_photo()], 1, 1)
        assert "<h1>Photo archive</h1>" in html

    def test_gallery_page_has_description(self):
        html = render_gallery_page_content([make_photo()], 1, 1)
        assert "<p>These are all the photos from my blog posts.</p>" in html

    def test_h1_inside_main(self):
        html = render_gallery_page_content([make_photo()], 1, 1)
        assert html.index('<main>') < html.index('<h1>Photo archive</h1>') < html.index('</main>')

    def test_h1_before_gallery_list(self):
        html = render_gallery_page_content([make_photo()], 1, 1)
        assert html.index('<h1>') < html.index('<ul id="gallery">')

    def test_ul_has_gallery_id(self):
        html = render_gallery_page_content([make_photo()], 1, 1)
        assert '<ul id="gallery">' in html

    def test_one_li_per_photo(self):
        photos = [make_photo(post_id=1), make_photo(post_id=2)]
        html = render_gallery_page_content(photos, 1, 1)
        assert html.count('class="gallery-item"') == 2

    def test_li_has_data_post_attribute(self):
        html = render_gallery_page_content([make_photo(post_id=26)], 1, 1)
        assert 'data-post="26"' in html

    def test_anchor_links_to_post(self):
        html = render_gallery_page_content([make_photo(post_id=26, post_url="26.html")], 1, 1)
        assert 'href="26.html"' in html

    def test_anchor_has_data_full_attribute(self):
        html = render_gallery_page_content([make_photo(full="26-image-01-resized.jpg")], 1, 1)
        assert 'data-full="26-image-01-resized.jpg"' in html

    def test_img_src_is_thumbnail(self):
        html = render_gallery_page_content([make_photo(thumb="26-image-01-thumb.jpg")], 1, 1)
        assert 'src="26-image-01-thumb.jpg"' in html

    def test_img_alt_uses_photo_alt(self):
        html = render_gallery_page_content([make_photo(alt="A sunset")], 1, 1)
        assert 'alt="A sunset"' in html

    def test_img_alt_empty_when_no_alt(self):
        html = render_gallery_page_content([make_photo(alt="")], 1, 1)
        assert 'alt=""' in html

    def test_img_alt_is_escaped(self):
        html = render_gallery_page_content([make_photo(alt='A "sunset" & sky')], 1, 1)
        assert 'alt="A &quot;sunset&quot; &amp; sky"' in html

    def test_img_has_width_and_height(self):
        html = render_gallery_page_content([make_photo(width=400, height=267)], 1, 1)
        assert 'width="400"' in html
        assert 'height="267"' in html

    def test_img_has_loading_lazy(self):
        html = render_gallery_page_content([make_photo()], 1, 1)
        assert 'loading="lazy"' in html

    def test_gallery_page_has_back_to_homepage_link(self):
        html = render_gallery_page_content([make_photo()], 1, 1)
        assert '<a href="index.html">Blog home</a>' in html

    def test_no_pagination_nav_when_single_page(self):
        html = render_gallery_page_content([make_photo()], 1, 1)
        assert 'gallery-2.html' not in html

    def test_older_link_present_on_page_1_of_2(self):
        html = render_gallery_page_content([make_photo()], 1, 2)
        assert 'href="gallery-2.html"' in html
        assert 'Older photos' in html

    def test_older_link_has_load_more_class(self):
        html = render_gallery_page_content([make_photo()], 1, 2)
        assert '<li class="older"><a href="gallery-2.html" class="load-more">Older photos</a></li>' in html

    def test_newer_link_present_on_page_2_of_2(self):
        html = render_gallery_page_content([make_photo()], 2, 2)
        assert 'href="gallery.html"' in html
        assert 'Newer photos' in html

    def test_newer_link_has_no_load_more_class(self):
        html = render_gallery_page_content([make_photo()], 2, 2)
        assert '<li class="newer"><a href="gallery.html">Newer photos</a></li>' in html

    def test_no_newer_link_on_page_1(self):
        html = render_gallery_page_content([make_photo()], 1, 2)
        assert 'class="newer"' not in html

    def test_no_older_link_on_last_page(self):
        html = render_gallery_page_content([make_photo()], 2, 2)
        assert 'class="older"' not in html
