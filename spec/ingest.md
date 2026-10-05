# `ingest.py` specification (planning document)

This is a full design spec for `ingest.py`, written ahead of implementation so the design can be reviewed as a whole. It is **not** part of `spec/specification.md` — that gets updated alongside the actual implementation, per this project's usual spec-first convention. This document also specifies a prerequisite change to magnetizer's core (draft posts), since `ingest.py`'s draft trigger is meaningless without it.

Decisions already confirmed before writing this:
- Loose files directly in `inbox/` sort **last**, after all named subfolders, when a run has both.
- A subfolder with no usable content (no images, no valid `.md`, or only unsupported file types) **errors out the whole run** — no silent per-folder skipping.

---

## Part 1 — Prerequisite: draft posts (magnetizer core)

`ingest.py`'s underscore-filename convention just sets `draft: true` in frontmatter. The actual behaviour that key must drive is a **core generator feature**, implemented and tested in `magnetizer` itself, independently of `ingest.py`. This section specifies that feature; Part 2 covers `ingest.py` itself.

### History

A `draft: true` frontmatter key existed before, added in `b63daa3` (17/6/26) and removed in `e9da5f8` (23/7/26) for being unused — no real content had ever set it, not because the design was wrong. Its removal commit describes the exact prior scope:

> Draft posts are excluded from index pages, category pages, the Atom feed, the sitemap, the archive, and next/previous post navigation. They can only be reached by navigating directly to their individual post URL. The HTML page for a draft post is still generated on every build.

That scope predates several features that didn't exist yet at the time (gallery, notes pages, `posts.json`, Pagefind search, dynamic shortcode counts, the archive's photo/calendar sections) — so reintroducing the key means re-auditing every current listing surface, not just restoring the old code.

### Frontmatter

```
---
date: 2026-05-21
draft: true
---
```

- Add `'draft'` to `_ALLOWED_FRONTMATTER_KEYS` in `magnetizer/content.py` (currently `{'date', 'title', 'name', 'images', 'favourite', 'category', 'ai_assisted', 'noindex', 'description'}`), or it's rejected as an unknown key.
- Parsed the same way as `favourite`/`ai_assisted`/`noindex` already are: `draft_raw = fm.get('draft', 'false'); is_draft = isinstance(draft_raw, str) and draft_raw.lower() == 'true'`.
- Absent or `false` → published, same as today (no behaviour change for existing content).

### What "draft" means, surface by surface

The generator already has one central hook for "which posts count as real, listable posts": `published_post_ids_sorted_desc` / `published_posts_sorted_desc`, computed once in `_load_content` (`magnetizer/builder.py`) and threaded into nearly everything downstream. Today it means "has a `.md` file".

**This needs to become two lists, not one — confirmed by tracing every call site, not assumed:**

- `buildable_post_ids_sorted_desc` / `buildable_posts_sorted_desc` — every real post, **draft or not** (today's current, unfiltered meaning of `published_*`). Used for build mechanics that must still treat a draft as a real post: `_check_no_invalid_posts` (no draft exemption from the invalid-post check, matching the removal commit's own reasoning for dropping that exemption last time), `_orphan_comment_warnings` (a comment on a draft post isn't orphaned), and the `--refresh` scope (`refresh_ids` in `build()`) — without this, a draft's unchanged page would never get re-rendered on `--refresh`, since that scope is drawn from whichever list excludes drafts.
- `published_post_ids_sorted_desc` / `published_posts_sorted_desc` — narrows to **exclude drafts**, becoming "has a `.md` file and is not a draft". Used for every public-facing listing surface (table below) and for next/previous navigation.

```python
buildable_post_ids_sorted_desc = [
    pid for pid in all_post_ids_sorted_desc if pid in posts_cache
]
published_post_ids_sorted_desc = [
    pid for pid in buildable_post_ids_sorted_desc if not posts_cache[pid].is_draft
]
```

**Two call sites need an explicit guard, not just a list swap**, because `_adjacent_post_urls` does a plain `.index()` lookup with no fallback (unlike `_neighbor_post_ids`, which already handles "not in the list"). Building or refreshing a draft's own page must skip neighbor computation entirely — both because a draft gets no prev/next nav by design, and because calling `_adjacent_post_urls(draft_id, published_post_ids_sorted_desc)` would otherwise raise `ValueError` (the draft id is never in that list). Both `_build_changed_posts` and `_refresh_posts` need: `newer_url, older_url = (None, None) if post.is_draft else _adjacent_post_urls(post_id, published_post_ids_sorted_desc)`.

With that in place, confirmed by reading the current call sites that the `published_*` list change alone covers:

| Surface | Confirmed excluded via | 
|---|---|
| Index pages (`index.html`, …) | built from `published_posts_sorted_desc` |
| Category pages | same |
| Notes pages | same (filtered from the same list) |
| Atom feed (`feed.xml`) | `render_feed(published_posts_sorted_desc, …)` |
| Gallery page | `_gallery_photos(published_posts_sorted_desc, …)` |
| Sitemap (`sitemap.xml`) | loop is already `for pid in published_post_ids_sorted_desc`, same place `is_noindex` is already skipped |
| Archive page | built from the same list |
| `{{ post_count }}`, `{{ word_count }}`, `{{ image_count }}`, `{{ ai_post_list }}` | `_compute_dynamic_values(published_posts_sorted_desc, …)` |
| Next/previous navigation | `_neighbor_post_ids` is computed against `published_post_ids_sorted_desc`, the same mechanism that already correctly skips a *deleted* post's old slot |
| Category post counts (archive) | derived from the same filtered list |

Surfaces that need an **explicit, separate check** — confirmed these do *not* currently derive from the published list:

- **Pagefind search (`data-pagefind-ignore`) and the `noindex` robots meta tag.** Confirmed via the README: `data-pagefind-ignore` on a post's own page is driven by `post.is_noindex` specifically in `render_post_page_content` (`magnetizer/render.py`), as its own condition — not by list membership. The `<meta name="robots" content="noindex">` tag is separately driven by the `is_noindex` parameter passed into `render_template` from `_write_post_html` (`magnetizer/builder.py`). **Decided (goes beyond the original removed feature, and beyond the plain brief):** `is_draft` triggers both of these the same way `is_noindex` does — `main_attrs = ' data-pagefind-ignore' if (post.is_noindex or post.is_draft) else ''`, and `is_noindex=(post.is_noindex or post.is_draft)` at the `_write_post_html` call site. Otherwise a draft would be hidden from every listing but still fully indexable by a search engine that finds the URL some other way — "hidden" should mean hidden. The two frontmatter keys stay independent; a draft doesn't need its own separate `noindex: true`.
- **`posts.json`.** Confirmed: no code change needed at all — `_write_posts_index` already takes `published_posts_sorted_desc` directly, so it inherits the exclusion for free once that list's definition changes.
- **Orphan-comment warning, the invalid-post check, and `--refresh`'s scope.** These must use the *unfiltered* `buildable_post_ids_sorted_desc` (see above), not `published_post_ids_sorted_desc` — a draft is still a real, buildable post for all of these purposes, just excluded from the public-facing listing surfaces in the table above.

### What stays the same

- The HTML page for a draft post is still generated on every build, at its normal URL (`{id}.html`) — reachable directly, just not linked from anywhere generated.
- The invalid-post check (no title, no images, no content) still applies to drafts — no draft exemption, matching the removal commit's own reasoning for why that exemption was dropped last time.
- **Decided: no prev/next nav on a draft's own page** — matches the original removed feature, and is also required to avoid the `_adjacent_post_urls` crash described above.
- **Decided: build console output must show drafts, in verbose mode.** Not the original feature's bare `+` prefix (which needs a legend to understand) — instead a bracketed `[draft]` label, matching the existing `[N imgs]` convention already used in verbose output (`build.py`'s `_print_output`). Requires a 6th element on the post log tuple (`is_draft`) — the original feature had exactly this 6th slot for its own `+` marker, removed along with everything else; reintroducing it the same way, just with a clearer label.

### Not affected (confirmed no change needed)

- `--refresh`'s dynamic-rebuild-forcing logic (`forced_dynamic_ids`), comment handling, image resizing, footnotes — all operate per-post regardless of draft status, same as today.

---

## Part 2 — `ingest.py`

### Purpose

Turns a drop-folder (`inbox/`) into real, numbered posts in `content/`, so posting from a device with no Python (the iPad) needs no manual filename/frontmatter rules.

### CLI

```
ingest.py [--inbox inbox] [--content content] [--max-edge 2000] [--quality 90] [--dry-run]
```

Run from the project root, same convention as `build.py`/`new-post.py`.

### What counts as "one post" (a group)

- Each immediate **subfolder** of `inbox/` is one group.
- All **loose files** directly in `inbox/` (ignoring dotfiles) together form one more group, if any exist.
- Groups are ordered by natural sort of their folder name (so `trip-2` sorts before `trip-10`); the loose-files group, if present, is always **last**.
- Dotfiles (`.gitkeep`, `.DS_Store`, etc.) are ignored everywhere this scans, both at the `inbox/` root and inside every subfolder.

### Draft trigger

If a group's `.md` filename starts with `_` (e.g. `_my-post.md`), the resulting post gets `draft: true` added to its frontmatter (alongside the other frontmatter normalisation below). The leading underscore is a signal, not part of the post — it is never reflected in the output filename (`{id}.md`, not `_{id}.md`) or anywhere else.

A group with no `.md` at all is never a draft (there's nothing to name `_...`) — only an explicit underscore-prefixed markdown file triggers it.

### Per-group validation (before any image processing)

- At most one `.md` per group (regardless of underscore prefix) — more than one is an error for the **whole run**.
- Every other file in the group must be a recognised image extension (`.jpg .jpeg .png .svg .heic .heif`, case-insensitive) — anything else (e.g. a `.txt`, a video) is an error for the whole run.
- A group with zero images and no usable `.md` is an error for the whole run (confirmed above — no silent skip).

### Image processing

In natural-sort order of filename (`IMG_2` before `IMG_10`):

- Raster (`.jpg/.jpeg/.png/.heic/.heif`): apply EXIF orientation, strip all metadata, downscale so the long edge is at most `--max-edge` (never upscale), save at `--quality`. `.heic`/`.heif` → `.jpg`. `.png` stays `.png`. Extensions normalised to lowercase in the output filename.
- `.svg`: copied as-is, no processing.
- Output: `{id}-image-{NN}.{ext}`, contiguous from `01`.

Implementation note: factor the orientation-fix + metadata-strip step out of `magnetizer/image.py`'s `resize_image` into a small shared helper, since `ingest.py` needs that same step but a different output shape (one downscaled content-original per image, not a dist-ready resized+thumbnail pair) — avoids duplicating the EXIF-handling logic between the two. `pillow-heif`'s HEIF opener is registered once at import time so `Image.open()` can read `.heic`/`.heif` directly.

### Markdown handling

- If a `.md` was supplied: body and existing frontmatter are kept verbatim, then:
  - Add `date:` (today, `Europe/London`, via `zoneinfo`) if absent.
  - Add `draft: true` if the filename was underscore-prefixed (see above).
  - Pad `images:` with generic `Image N` placeholders up to the image count, if the existing list is shorter. Warn (don't error, don't truncate) if the existing list is already longer than the image count.
  - Add an empty `category:` if absent.
- If no `.md` was supplied: generate the same skeleton `new-post.py` would (reusing `build_markdown`), with `draft: true` impossible in this case (see Draft trigger above).

### Numbering and atomicity

- Starting id = `get_next_post_id(content_dir)` (reused from `new-post.py`'s code, not duplicated), computed **once**, before anything is touched. Each subsequent group gets the next consecutive integer — never re-queried mid-run.
- Everything is written to a **temporary staging directory** first.
- `validate_content` (reused from `magnetizer/validate.py`) runs against a merged view of the real `content/` plus the staged additions, before anything real changes.
- Only if every group succeeds and validation passes: move staged files into the real `content/`, then delete the processed source files from `inbox/` (keeping `inbox/.gitkeep`).
- Any failure anywhere aborts the whole run — `inbox/` and `content/` are left exactly as they started. Nothing partial.

### Output

- Empty `inbox/` (nothing but dotfiles): exit 0, print `Nothing to ingest.`, no changes.
- Success: delete processed source files, print `Post {id} created from {source}` per group (where `{source}` is the subfolder name, or e.g. `inbox/` for the loose-files group).
- `--dry-run`: runs validation and processing into the temp dir, reports what *would* be created (e.g. `Would create post 113 from trip-2/`), discards the temp dir. `inbox/` and `content/` untouched either way.
- Failure: non-zero exit, clear error message, nothing touched.

### Test plan

From the original brief, unchanged: HEIC→JPEG; orientation applied; GPS EXIF gone; downscale only, never upscale; natural sort of images within a post; natural sort of groups across a run (loose files last); several posts in one run get consecutive ids; id continues correctly from existing `content/`; markdown-merge cases (date/images/category padding); multiple `.md` in one group errors; an unsupported file type errors; an empty/unusable group errors; a failure anywhere leaves `inbox/` and `content/` completely untouched; SVG passthrough; `--dry-run` changes nothing; empty inbox is a clean no-op.

Added for drafts: underscore-prefixed `.md` produces `draft: true`; non-underscore-prefixed doesn't; a group with no `.md` is never a draft regardless of folder name; the leading underscore never leaks into the output filename.

For the core draft feature (magnetizer, separate from `ingest.py`'s own tests): a draft post is excluded from index/category/notes pages, the Atom feed, the sitemap, the archive, dynamic post/word/image counts, and `ai_post_list`; it's still reachable at its own URL; its own page still builds and still gets rebuilt when its content changes; it gets `data-pagefind-ignore`; it has no prev/next navigation on its own page; it does not get a draft exemption from the invalid-post check; a non-draft post's neighbours correctly skip over an adjacent draft (reusing the same mechanism already proven correct for a deleted post).

---

## Status

Both open items are resolved: `posts.json` excludes drafts; verbose build output must show drafts (a `[draft]` label, not the old bare `+` prefix). Full call-site audit done — see the two-list design and guard fixes above. Ready for implementation: core draft feature in `magnetizer` first, `ingest.py` after.
