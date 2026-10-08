# `ingest.py` specification (planning document)

This is a full design spec for `ingest.py`, written ahead of implementation so the design can be reviewed as a whole. It is **not** part of `spec/specification.md` — that gets updated alongside the actual implementation, per this project's usual spec-first convention.

`ingest.py`'s underscore-filename convention sets `draft: true` in frontmatter. The core generator behaviour that key drives (excluded from listings, still reachable at its own URL, etc.) is already implemented and tested in `magnetizer` itself, independently of `ingest.py` — see `d6847d2` ("Reintroduce draft posts").

### Purpose

Turns a drop-folder (`inbox/`) into a real, numbered post in `content/`, so posting from a device with no Python (the iPad) needs no manual filename/frontmatter rules.

### CLI

```
ingest.py [--inbox inbox] [--content content] [--max-edge 2000] [--quality 90] [--dry-run]
```

Run from the project root, same convention as `build.py`/`new-post.py`.

### What counts as "the post"

- `inbox/` holds the files for exactly **one** post, as loose files directly inside it — no subfolders.
- Dotfiles (`.gitkeep`, `.DS_Store`, etc.) are ignored when scanning `inbox/`.

### Draft trigger

If the `.md` filename starts with `_` (e.g. `_my-post.md`), the resulting post gets `draft: true` added to its frontmatter (alongside the other frontmatter normalisation below). The leading underscore is a signal, not part of the post — it is never reflected in the output filename (`{id}.md`, not `_{id}.md`) or anywhere else.

No `.md` at all means never a draft (there's nothing to name `_...`) — only an explicit underscore-prefixed markdown file triggers it.

### Validation (before any image processing)

- At most one `.md` in `inbox/` (regardless of underscore prefix) — more than one is an error.
- Every other file must be a recognised image extension (`.jpg .jpeg .png .svg .heic .heif`, case-insensitive) — anything else (e.g. a `.txt`, a video) is an error.
- Zero images and no usable `.md` is an error — no silent no-op beyond the genuinely empty-inbox case (see Output below).
- `default_category` in `config.yaml`, if set, must match a configured `categories` slug — checked up front (via `validate_default_category`) rather than deferred to the next `build.py` run, since by then the bad value would already be baked into the ingested post.

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
  - Add `category:` if absent, set to `default_category` from `config.yaml` (empty if not configured).
- If no `.md` was supplied: generate the same skeleton `new-post.py` would (reusing `build_markdown`), with `draft: true` impossible in this case (see Draft trigger above).

### Numbering and atomicity

- id = `get_next_post_id(content_dir)` (reused from `new-post.py`'s code, not duplicated).
- Everything is written to a **temporary staging directory** first.
- `validate_content` (reused from `magnetizer/validate.py`) runs against a merged view of the real `content/` plus the staged addition, before anything real changes.
- Only if validation passes: move staged files into the real `content/`, then delete the processed source files from `inbox/` (keeping `inbox/.gitkeep`).
- Any failure aborts the whole run — `inbox/` and `content/` are left exactly as they started. Nothing partial.

### Output

- Empty `inbox/` (nothing but dotfiles): exit 0, print `Nothing to ingest.`, no changes.
- Success: delete processed source files, print `Post {id} created`.
- `--dry-run`: runs validation and processing into the temp dir, reports what *would* be created (e.g. `Would create post 113`), discards the temp dir. `inbox/` and `content/` untouched either way.
- Failure: non-zero exit, clear error message, nothing touched.

### Test plan

HEIC→JPEG; orientation applied; GPS EXIF gone; downscale only, never upscale; natural sort of images within a post; id continues correctly from existing `content/`; markdown-merge cases (date/images/category padding); multiple `.md` in `inbox/` errors; an unsupported file type errors; an empty/unusable inbox errors; a failure leaves `inbox/` and `content/` completely untouched; SVG passthrough; `--dry-run` changes nothing; empty inbox is a clean no-op; underscore-prefixed `.md` produces `draft: true`; non-underscore-prefixed doesn't; no `.md` is never a draft; the leading underscore never leaks into the output filename.

---

## Status

Ready for implementation.
