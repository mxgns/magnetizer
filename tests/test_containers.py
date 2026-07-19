"""Tests for magnetizer/containers.py — ::: fenced container Markdown extension"""

import markdown as _markdown
from magnetizer.containers import ContainerExtension


def render(text):
    return _markdown.markdown(text, extensions=[ContainerExtension()])


class TestContainerBlocks:

    def test_bare_fence_gets_default_class(self):
        html = render(":::\nMy container content\n:::")
        assert '<div class="container">' in html

    def test_bare_fence_wraps_content_in_paragraph(self):
        html = render(":::\nMy container content\n:::")
        assert "<p>My container content</p>" in html

    def test_custom_class_appended_to_default(self):
        html = render("::: my-container-class\nContent\n:::")
        assert '<div class="container my-container-class">' in html

    def test_markdown_rendered_inside_container(self):
        html = render("::: my-class\nSome **bold** text\n:::")
        assert "<strong>bold</strong>" in html

    def test_multiple_paragraphs_inside_container(self):
        html = render("::: my-class\nFirst paragraph.\n\nSecond paragraph.\n:::")
        assert html.count('<div class="container my-class">') == 1
        assert "<p>First paragraph.</p>" in html
        assert "<p>Second paragraph.</p>" in html

    def test_content_before_and_after_container_not_nested(self):
        html = render("Before.\n\n::: my-class\nInside.\n:::\n\nAfter.")
        assert "<p>Before.</p>" in html
        assert "<p>After.</p>" in html
        assert html.index("</div>") < html.index("<p>After.</p>")

    def test_unpaired_opening_fence_treated_as_literal_text(self):
        html = render(":::\nJust text, no closing fence.")
        assert "<div" not in html
        assert "Just text, no closing fence." in html

    def test_unpaired_fence_with_class_treated_as_literal_text(self):
        html = render("::: my-class\nJust text, no closing fence.")
        assert "<div" not in html
        assert "my-class" in html

    def test_two_separate_containers_render_independently(self):
        html = render("::: first\nOne\n:::\n\n::: second\nTwo\n:::")
        assert '<div class="container first">' in html
        assert '<div class="container second">' in html
