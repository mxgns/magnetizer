# Magnetizer

A static site generator for a personal photo blog. Takes Markdown and image files as input and outputs a ready-to-publish HTML site.

## Project structure

Your blog lives in its own directory with the following layout:

```
content/       Markdown and image files
templates/     HTML templates
resources/     CSS, JS, fonts, icons, etc.
dist/          Generated output (publish this to the web)
config.yaml    Site configuration
manifest.json  Build state (created automatically)
```

`dist/` should be a cloned GitHub Pages repository. Magnetizer assumes this is already set up.

## Configuration

`config.yaml` supports the following options — this table is the single reference for all of them:

| Option | Description | Default |
|---|---|---|
| `site_name` | Used in page `<title>` tags | `My Blog` |
| `site_url` | Absolute base URL of the published site, e.g. `https://example.github.io` — used for canonical links, the Atom feed, and the sitemap | **Required** — build exits with an error if absent or empty |
| `image_max_dimension` | Long-edge pixel limit when resizing images | `1600` |
| `image_quality` | JPEG quality for resized images (0–95) | `75` |
| `posts_per_page` | Posts shown per index page | `12` |
| `notes_per_page` | Notes shown per notes page (`notes.html`, `notes-2.html`, …) | `20` |
| `index_meta_description` | `<meta name="description">` content on index pages (via `MAGNETIZER_METADATA` placeholder) | Not set |
| `index_title` | When set, the title of `index.html` becomes `site_name - index_title` | Not set |
| `categories` | Map of category slug to display name, e.g. `{photography: Photography}` | `{}` (no categories) |
| `navigation` | Map of page filename to nav label, e.g. `{index.html: Home}`, in display order | `{}` (no navigation) |
| `special_pages` | List of standalone page names, each backed by a `content/{name}.md` file — see [Special pages](#special-pages) | `[]` (no special pages) |
| `ai_disclosure_html` | Raw HTML (not escaped, so it may include a link) shown in the disclosure banner when a post or special page sets `ai_assisted: true` — see the `ai_assisted` entry in [Frontmatter reference](#frontmatter-reference) | Not set — falls back to a generic disclosure sentence |

Example:

```yaml
site_name: My Blog
site_url: https://example.github.io
posts_per_page: 12
image_max_dimension: 1600
image_quality: 75
categories:
  photography: Photography
  travel: Travel
navigation:
  index.html: Home
  archive.html: Archive
special_pages:
  - about
```

Use the `MAGNETIZER_NAVIGATION` template placeholder to render `navigation` as a `<ul>` of links. Each link gets its own `nav-{slug}` class derived from its filename (e.g. `archive.html` → `nav-archive`), and the link matching the page currently being generated additionally gets `current` appended to its class and an `aria-current="page"` attribute.

## Creating a post

Run `new-post.py` from your project directory:

```
new-post.py                                     Empty post
new-post.py photo.jpg                           Post with one image
new-post.py "Post title"                        Post with a title
new-post.py photo1.jpg photo2.jpg "Post title"  Post with images and a title
```

This creates a numbered `.md` file in `content/` and copies any images alongside it. Open the `.md` file in your editor to add content.

Post files use a simple frontmatter format:

```markdown
---
date: 2026-05-24
title: My post title
---

Post body goes here. Standard Markdown is supported.
```

The `title` field is optional — see [Frontmatter reference](#frontmatter-reference) below for `title` and every other supported key.

The post's heading is rendered as the page's `<h1>` on an individual post page, or `<h2>` when shown alongside other posts (index and category pages). Use `###` (`<h3>`) or lower for any headings inside the post body — the build prints a warning if a post contains a `#` or `##` heading, since those levels are already used by the post's own heading. See [Post types](#post-types) below for what the heading contains when the post has no `title`.

Wrap part of a post body in a `<div>` with a fenced container:

```markdown
::: my-container-class
My container content
:::
```

This renders `<div class="container my-container-class"><p>My container content</p></div>`. The class name is optional — a bare `:::` fence renders `<div class="container">`. Content between the fences is parsed as Markdown, and an opening `:::` with no matching closing `:::` is left as ordinary text.

Place a specific image inline in the body with `{{ image N }}`, where `N` is the image's number from its filename (`{{ image 3 }}` → `{post-id}-image-03.{ext}`):

```markdown
Some text.

{{ image 3 }}

More text.
```

It must be on its own line with a blank line before and after (its own paragraph, not just its own line within one) — used inline with other text, or referencing an image number that doesn't exist for the post, is a build error. The image is rendered as `<figure><img src="..." alt="..."></figure>` using its frontmatter alt text, and is excluded from the top-of-post image strip since it's already shown in the body. On index pages, if it falls after a `<!-- more -->` marker (so isn't part of the shown excerpt), it's counted into the "Read more (+N photo(s))" link text — see below.

## Post types

Every post is one of three types, based on its `title`, top-level images, and body content:

| Type | Type class | Criteria |
|---|---|---|
| Full post | `full-post` | Has a `title` |
| Image post | `image-post` | No `title`, one or more top-level images |
| Note | `note` | No `title`, no top-level images, has body content |

The type class is appended to the `<article>` alongside its existing `single-post`/`multiple-posts` layout class, not instead of it — e.g. `class="single-post note"` on an individual Note's own page, or `class="multiple-posts image-post"` for an Image post shown on the index.

A blank or whitespace-only `title`, `name`, or body counts as unset for all of this — classification, the warnings/errors below, and the heading/title/archive fallback text. `title: "   "` behaves exactly like no `title` at all.

Images placed inline via `{{ image N }}` don't count as top-level images for this — a post with only inline images and no title is a Note, not an Image post. All in-post features (`<!-- more -->`, `{{ image N }}`, container blocks, dynamic values) work the same way across all three types; Magnetizer doesn't restrict any of them by post type.

Notes replace what used to be called microblog posts. The behaviour is the same except there's no length cap any more, and the paginated listing page is `notes.html` (was `microblog.html`). Notes get a `<a href="notes.html" class="notes">Notes</a>` link in their footer, before the category link if any.

A post with no `title`, no images and no content is invalid — the build exits with an error. A post with a `title` but no images and no content triggers a build warning (it doesn't make much use of its own page), as does a post with both `title` and `name` set — the `title` wins and `name` is ignored. ("Images" here means any image, including one used only inline via `{{ image N }}` — unlike the Full/Image/Note classification above, these two checks don't distinguish top-level from inline.)

Every post gets a non-empty heading and page `<title>`, built from the same priority order:

1. `title`, if set
2. `name`, if set — a frontmatter field used only as a fallback label when there's no `title`
3. Otherwise, a generated fallback based on post type and top-level image count: `Note posted {date}`, `Photo posted {date}` (one image), or `Photos posted {date}` (more than one)

For an Image post or Note, the heading exists in the HTML (for the document outline and screen readers, since the index/category pages mix titled and untitled posts) but isn't shown visually — hiding it is left to your own `resources/` CSS, keyed off the `full-post`/`image-post`/`note` class on the `<article>`; Magnetizer itself never hides it.

The archive's link text for each post follows the same priority order, except it falls back to an excerpt of the post's own first paragraph (plaintext, tags stripped, truncated to 40 characters after the last full word) before reaching the generated fallback text — see [Archive page](#archive-page).

## Frontmatter reference

This is the single reference for every frontmatter key a post or special page can set. Any other key produces a build warning naming the post and the unknown key.

| Key | Applies to | Format | Default |
|---|---|---|---|
| `date` | Posts (required), special pages (optional) | `YYYY-MM-DD` | — |
| `title` | Posts, special pages | Plain text | Not set |
| `name` | Posts, special pages | Plain text | Not set |
| `images` | Posts, special pages | List of alt text strings, one per image file, in file order | `[]` |
| `category` | Posts | A slug from `categories` in `config.yaml` | Not set |
| `draft` | Posts | `true` / `false` | `false` |
| `favourite` | Posts | `true` / `false` | `false` |
| `ai_assisted` | Posts, special pages | `true` / `false` | `false` |
| `noindex` | Posts, special pages | `true` / `false` | `false` |

- **`date`** — publish date. Required on posts; optional on special pages (omit it and no date footer is rendered). Shown in the footer as `D Month YYYY` and used for the Atom feed, sitemap `lastmod`, and archive month grouping.
- **`title`** — rendered as the page's `<h1>` on its own page, or `<h2>` when shown alongside other posts (index and category pages). Omit it for an Image post or a Note — see [Post types](#post-types).
- **`name`** — fallback label for a post with no `title` (an Image post or a Note), used for the heading and page `<title>`, and as the archive link text immediately after `title` — it wins over an excerpt of the post's own content, not just when there's no content to excerpt. Ignored (with a build warning) if `title` is also set. See [Post types](#post-types).
- **`images`** — alt text for each image file belonging to the post (`{post-id}-image-{nn}.*`), matched to image files in filename order. If the list is absent or has fewer entries than image files, the remaining images get `alt=""` (decorative). An incomplete list triggers a "Missing alt text" build warning.
- **`category`** — assigns the post to a category. Matching against `categories` in `config.yaml` is case-insensitive and the value is normalised to lowercase. Adds a category link to the post's footer and includes the post on that category's page (`{slug}.html`). If `categories` is configured, a build warning is printed for posts with no category or with a category not found in `categories`.
- **`draft`** — generates the post's HTML page as usual, but excludes it from index pages, category pages, the Atom feed, the sitemap, the archive, and next/previous navigation. A draft post is only reachable via its direct URL.
- **`favourite`** — adds an additional `favourite` CSS class to the post's entry in the archive.
- **`ai_assisted`** — inserts a disclosure banner at the top of the content, wherever it's shown (individual page, and index/category excerpts or full body). The banner text comes from `ai_disclosure_html` in `config.yaml` (raw HTML, so it can include a link) — Magnetizer falls back to a generic sentence if `ai_disclosure_html` isn't set. The banner needs the `.container-brown` and `.ai-disclosure` CSS rules to be present in the project's `resources/` directory — the icon itself is a CSS background image, base64-encoded in the project's own stylesheet, same as every other icon on the site.
- **`noindex`** — excludes the page from `sitemap.xml` and adds a `<meta name="robots" content="noindex">` tag via `MAGNETIZER_METADATA`, but is otherwise treated normally (still shown on index pages, category pages, the feed, the archive, and post navigation). Unlike `draft`, it doesn't hide the page anywhere except search indexing. Works the same way on special pages as on posts.

## Building the site

Run `build.py` from your project directory.

| Command | What it does |
|---|---|
| `build.py` | Build anything that has changed since the last build, including resource files |
| `build.py --flush` | Delete all output and rebuild everything from scratch |
| `build.py --resources` | Force-replace all of `dist/resources/` with the current `resources/` |
| `build.py --push` | Build, then push `dist/` to GitHub Pages |
| `build.py --verbose` | Build and print a detailed post log plus summarised pages/resources sections |
| `build.py 1.md` | Preview a single post or special page (does not update index pages) |

Use `--flush` after editing templates. Resource file changes (CSS, JS) are picked up automatically on the next build. A `.` is printed for each file generated so you can see progress — in normal mode the dots are erased when the build finishes; in `--verbose` mode they remain. Warnings (missing alt text, missing category, etc.) are always shown inline next to the affected post, with the whole row coloured yellow in a terminal for visibility, e.g. `037   37.html   ⚠ Missing alt text`. Fatal errors are prefixed with a red `ERROR` label.

Every full build also generates `dist/sitemap.xml` (all published posts, index, category, notes, special, and archive pages with `lastmod` dates) and `dist/robots.txt` (pointing to the sitemap). These are not generated on single-file preview builds.

## Templates

Magnetizer uses a single template file: `templates/index.html`. It must contain two required placeholders, plus optional ones:

| Placeholder | Required | Replaced with |
|---|---|---|
| `MAGNETIZER_METADATA` | Yes | A block of `<head>` metadata tags: `<title>`, an optional `<meta name="description">` (index pages only, from `index_meta_description`), a `<link rel="canonical">`, and — for posts or special pages with `noindex: true` — a `<meta name="robots" content="noindex">`. Each line is present only when applicable. |
| `MAGNETIZER_CONTENT` | Yes | The generated page content |
| `MAGNETIZER_BUILD_ID` | No | A Unix timestamp, useful for cache-busting: `style.css?v=MAGNETIZER_BUILD_ID` |

Example `templates/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    MAGNETIZER_METADATA
    <link rel="stylesheet" href="resources/style.css?v=MAGNETIZER_BUILD_ID">
  </head>
  <body>
    <header><a href="/">My site</a></header>
    MAGNETIZER_CONTENT
  </body>
</html>
```

## Content files

All files live flat in `content/` — no subdirectories.

- Markdown files: `{post-id}.md` (e.g. `42.md`)
- Image files: `{post-id}-image-{nn}.jpg/jpeg/png/svg` (e.g. `42-image-01.jpg`) — numbering must start at `01` with no gaps; the build errors out otherwise
- One `{name}.md` per entry in `special_pages` (e.g. `about.md`, `cookies.md`) — see [Special pages](#special-pages)

Posts are displayed in reverse order by post ID — a higher ID means a newer post.

## Special pages

Configure standalone pages — an about page, a cookies policy, a now page, etc. — via `special_pages` in `config.yaml`:

```yaml
special_pages:
  - about
  - cookies
  - now
```

For each name listed, Magnetizer requires a matching `content/{name}.md` and generates `dist/{name}.html` — the build errors out if the `.md` file is missing. Each special page supports the same frontmatter and images as a regular post (`date` is optional; omit it and no date footer is rendered), and is rebuilt whenever its `.md` or images change on a full or partial build. Single-file preview builds work too, e.g. `build.py about.md` — and only touch that one page, never any other special page.

Special pages are never linked to automatically — add them to `navigation` if you want a link in your template — and they're excluded from index pages, category pages, the archive, the feed, and post navigation.

## Dynamic values

Posts and special pages can include shortcode-style placeholders that are computed at build time and inserted into the rendered HTML:

```text
{{ post_count }}
```

Whitespace inside the braces is optional (`{{post_count}}` and `{{ post_count }}` are equivalent). Shortcodes are only expanded in ordinary text — not inside `` <code> ``, `<pre>`, `<script>`, `<style>`, HTML comments, or tag attributes — so the syntax can be shown literally in a post (e.g. inside backticks) without being expanded.

| Shortcode | Renders |
| --- | --- |
| `{{ post_count }}` | Total number of published posts |
| `{{ word_count }}` | Total word count across all published posts |
| `{{ image_count }}` | Total number of images across all published posts |
| `{{ today }}` | The build date, as `D/M/YY` (e.g. `17/7/26`) |
| `{{ ai_post_list }}` | A `<ul>` of posts with `ai_assisted: true`, newest first |

"Published posts" means non-draft posts with their own page — special pages, index/category/archive pages don't count. The three counts (`post_count`, `word_count`, `image_count`) are drawn only from that set. `{{ ai_post_list }}` is the one exception — a special page with `ai_assisted: true` shows up there too, alongside qualifying posts, even though it's never counted. Numbers 1,000 and above render with a comma thousands-separator (e.g. `12,345`).

Each expanded value is wrapped for styling: scalars in `<span class="post-count">42</span>` (underscores in the name become hyphens in the class); `{{ ai_post_list }}` renders its own `<ul class="ai-post-list">`, or `<ul class="ai-post-list"><li>(none)</li></ul>` if no posts qualify. Put `{{ ai_post_list }}` on its own line (blank lines before and after) so it isn't trapped inside a `<p>`.

An unrecognised shortcode name is left as literal text and produces a build warning naming the shortcode and the file it's in. A `{{ ... }}` with no closing braces is just left as plain text, silently.

Because a page like this can go stale purely from *other* content changing (a new post changes `post_count` everywhere it's shown), a page using a shortcode is rebuilt on any full or partial build where something changed anywhere — not just when its own file changes. A build with no changes at all is still a true no-op, though — nothing is rebuilt "just in case". A single-file preview build (`build.py 42.md`) is the one exception to the whole mechanism — it only rebuilds the page you asked for, using freshly computed values, and leaves everything else as-is.

## Archive page

The archive page (`dist/archive.html`) lists all dated blog posts grouped by month (Notes are excluded from this list). It opens with an `<h1>Archive</h1>` heading:

```html
<main>
  <h1>Archive</h1>
  <section>
    <h2>May 2026</h2>
    <ul>
      <li class="full-post"><span class="day">16</span><a href="42.html">Post title</a></li>
      ...
    </ul>
  </section>
  ...
</main>
```

Each `<li>` gets the post's type class (`full-post` or `image-post` — Notes never appear here) and its link text follows the title → `name` → excerpt → generated-fallback priority order described in [Post types](#post-types).

If `categories` is configured and at least one category has a matching post, a categories list is inserted after the `<h1>`. If any Notes exist, a `<h2>Notes</h2>` section with a link to `notes.html` is inserted after the categories. When either (or both) sections appear, a `<h2>Blog Posts</h2>` heading is shown before the monthly sections:

```html
<main>
  <h1>Archive</h1>
  <h2>Categories</h2>
  <ul>
    <li><a href="photography.html">Photography</a> (34)</li>
    <li><a href="travel.html">Travel</a> (12)</li>
  </ul>
  <h2>Notes</h2>
  <ul>
    <li><a href="notes.html">All notes</a></li>
  </ul>
  <h2>Blog Posts</h2>
  ...
</main>
```

Each category link shows the number of posts in that category in parentheses. Categories are listed in descending order of post count, and only if they have at least one matching post.

## Publishing

Set up `dist/` as a clone of your GitHub Pages repository before using `--push`. Magnetizer stages, commits, and pushes all changes automatically.

If the push is rejected because the remote has changes you don't have locally (e.g. a `CNAME` file added by GitHub), run `git pull --rebase origin main` inside `dist/` first.
