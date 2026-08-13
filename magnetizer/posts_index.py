import json


def render_posts_index(entries):
    """entries: iterable of (id, title, category, date) — one per published
    page of every kind (posts, index/category/notes pages, archive, special
    pages). Rendered id-keyed rather than as an array so a consumer can do
    O(1) lookups by page_id without building its own map first."""
    data = {
        str(id_): {"title": title, "category": category, "date": date}
        for id_, title, category, date in entries
    }
    return json.dumps(data, indent=2)
