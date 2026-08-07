# Magnetizer

A static site generator for a photo blog. Takes Markdown and image files as input and outputs a ready-to-publish HTML site.

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
| `images_per_post` | Top-level images shown per post on multi-post pages (index, category, notes) — `0` shows none. The post's own page always shows all top-level images regardless. Inline images (`{{ image N }}`) aren't counted; use `<!-- more -->` to control those | `2` |
| `index_meta_description` | `<meta name="description">` content on index pages (via `MAGNETIZER_METADATA` placeholder) | Not set |
| `index_title` | When set, the title of `index.html` becomes `site_name - index_title` | Not set |
| `categories` | Map of category slug to display name, e.g. `{photography: Photography}` | `{}` (no categories) |
| `navigation` | Map of page filename to nav label, e.g. `{index.html: Home}`, in display order | `{}` (no navigation) |
| `special_pages` | List of standalone page names, each backed by a `content/{name}.md` file — see [Special pages](#special-pages) | `[]` (no special pages) |
| `ai_disclosure_html` | Raw HTML (not escaped, so it may include a link) shown in the disclosure banner when a post or special page sets `ai_assisted: true` — see the `ai_assisted` entry in [Frontmatter reference](#frontmatter-reference) | Not set — falls back to a generic disclosure sentence |
| `404-page-input-filename` | `content/` markdown filename for the 404 page, e.g. `error-404.md` — optional, but requires `404-page-output-filename` too — see [404 page](#404-page) | Not set — no 404 page generated |
| `404-page-output-filename` | `dist/` output filename for the 404 page, e.g. `404.html` — optional, but requires `404-page-input-filename` too — see [404 page](#404-page) | Not set — no 404 page generated |

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

Any link in a post body whose host doesn't match `site_url` is treated as external, and automatically gets `target="_blank" rel="noopener"` plus an `external-link` class, so readers leaving the site open it in a new tab. This applies to Markdown links and raw HTML `<a>` tags alike, and merges into any `class`/`target`/`rel` the tag already has rather than duplicating attributes.

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

Notes replace what used to be called microblog posts. The behaviour is the same except there's no length cap any more, and the paginated listing page is `notes.html` (was `microblog.html`). Notes get a `<a href="notes.html" class="notes">Short note</a>` link in their footer, before the category link if any. Notes are excluded from the Atom feed (`feed.xml`) — only Full and Image posts get feed entries.

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
| `favourite` | Posts | `true` / `false` | `false` |
| `ai_assisted` | Posts, special pages | `true` / `false` | `false` |
| `noindex` | Posts, special pages | `true` / `false` | `false` |

- **`date`** — publish date. Required on posts; optional on special pages (omit it and no date footer is rendered). Shown in the footer as `D Month YYYY` and used for the Atom feed, sitemap `lastmod`, and archive month grouping.
- **`title`** — rendered as the page's `<h1>` on its own page, or `<h2>` when shown alongside other posts (index and category pages). Omit it for an Image post or a Note — see [Post types](#post-types).
- **`name`** — fallback label for a post with no `title` (an Image post or a Note), used for the heading and page `<title>`, and as the archive link text immediately after `title` — it wins over an excerpt of the post's own content, not just when there's no content to excerpt. Ignored (with a build warning) if `title` is also set. See [Post types](#post-types).
- **`images`** — alt text for each image file belonging to the post (`{post-id}-image-{nn}.*`), matched to image files in filename order. If the list is absent or has fewer entries than image files, the remaining images get `alt=""` (decorative). An incomplete list triggers a "Missing alt text" build warning.
- **`category`** — assigns the post to a category. Matching against `categories` in `config.yaml` is case-insensitive and the value is normalised to lowercase. Adds a category link to the post's footer and includes the post on that category's page (`{slug}.html`). If `categories` is configured, a build warning is printed for posts with no category or with a category not found in `categories`.
- **`favourite`** — adds an additional `favourite` CSS class to the post's entry in the archive.
- **`ai_assisted`** — inserts a disclosure banner above the post's heading, wherever it's shown (individual page, and index/category excerpts or full body). The banner text comes from `ai_disclosure_html` in `config.yaml` (raw HTML, so it can include a link) — Magnetizer falls back to a generic sentence if `ai_disclosure_html` isn't set. The banner needs the `.container-brown` and `.ai-disclosure` CSS rules to be present in the project's `resources/` directory — the icon itself is a CSS background image, base64-encoded in the project's own stylesheet, same as every other icon on the site.
- **`noindex`** — excludes the page from `sitemap.xml` and adds a `<meta name="robots" content="noindex">` tag via `MAGNETIZER_METADATA`, but is otherwise treated normally (still shown on index pages, category pages, the feed, the archive, and post navigation) — it only affects search indexing. Works the same way on special pages as on posts.

## Comments

Comments are for posting manual updates on a post or special page — e.g. linking to a follow-up once it's published. There's no way for a visitor to leave one; anything here has been added by hand.

A comment is its own Markdown file: `{post-id}-comment-{nn}.md` for a post (`12-comment-01.md`), or `{name}-comment-{nn}.md` for a special page (`about-comment-01.md`). Unlike image numbering, comment numbers don't need to be contiguous or start at `01`.

```markdown
---
date: 2026-08-05
author: Magnus
---

I have now published the [second part](13.html).
```

Both `date` and `author` are required — the build errors if either is missing. The body is Markdown, with the same automatic external-link handling as a post body, but no container blocks, `{{ image N }}` tokens, or `{{ shortcode }}` values.

Comments show up only on the post's or special page's own page, inside `<section class="comments" id="comments">`, oldest first — regardless of the comment's own date. Index, category, and notes pages instead get a `N comment(s)` link in the post's footer, pointing at `{post-id}.html#comments`.

Each comment's author name is slugified into a `class="author author-{slug}"`, shared by its `<h4>` and by a `<div class="avatar author-{slug}" data-initial="{INITIAL}" aria-hidden="true"></div>` placed just before it — `{INITIAL}` is the upper-cased first character of the author's name. Magnetizer renders no avatar styling itself; a project's own CSS decides what that `<div>` looks like, typically the initial shown via `content: attr(data-initial)` on a pseudo-element for a default "no photo" look, with a specific commenter's `author-{slug}` class overridden to show a real image instead.

A comment naming a post that doesn't exist (e.g. `99-comment-01.md` with no `99.md`) produces a build warning, not an error — the comment is simply skipped. Adding, editing, or removing a comment rebuilds its post or special page like an image change would.

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
| `MAGNETIZER_PAGE_ID` | No | The current page's bare id, e.g. `56` for a post, `about` for a special page, `photography` for a category page, `index`/`index-2`/`notes`/`archive` otherwise. Never includes `.html`. Not used by Magnetizer itself — useful for e.g. a per-page tracking pixel. |

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
- Comment files: `{post-id}-comment-{nn}.md` or `{name}-comment-{nn}.md` (e.g. `42-comment-01.md`, `about-comment-01.md`) — see [Comments](#comments)
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

## 404 page

GitHub Pages serves `404.html` at the site root as a custom error page. Post id `404` is always rejected (the build errors if `content/404.md` exists), and you can author a 404 page under a different filename via two config keys — set both, or neither:

```yaml
404-page-input-filename: error-404.md
404-page-output-filename: 404.html
```

`404-page-output-filename` must be a plain filename with no path separators (not `.` or `..` either) — it's used directly as a path inside `dist/`. The `404.md` reservation also can't be dodged by naming the 404 page's own input file `404.md`, or adding `"404"` to `special_pages`.

It behaves just like a special page (same frontmatter/image support, rebuild-on-change, single-file preview builds) except it's also excluded from `sitemap.xml`.

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

"Published posts" means posts with their own page — special pages, index/category/archive pages don't count. The three counts (`post_count`, `word_count`, `image_count`) are drawn only from that set. `{{ ai_post_list }}` is the one exception — a special page with `ai_assisted: true` shows up there too, alongside qualifying posts, even though it's never counted. Numbers 1,000 and above render with a comma thousands-separator (e.g. `12,345`).

Each expanded value is wrapped for styling: scalars in `<span class="post-count">42</span>` (underscores in the name become hyphens in the class); `{{ ai_post_list }}` renders its own `<ul class="ai-post-list">`, or `<ul class="ai-post-list"><li>(none)</li></ul>` if no posts qualify. Put `{{ ai_post_list }}` on its own line (blank lines before and after) so it isn't trapped inside a `<p>`.

An unrecognised shortcode name is left as literal text and produces a build warning naming the shortcode and the file it's in. A `{{ ... }}` with no closing braces is just left as plain text, silently.

Because a page like this can go stale purely from *other* content changing (a new post changes `post_count` everywhere it's shown), a page using a shortcode is rebuilt on any full or partial build where something changed anywhere — not just when its own file changes. A build with no changes at all is still a true no-op, though — nothing is rebuilt "just in case". A single-file preview build (`build.py 42.md`) is the one exception to the whole mechanism — it only rebuilds the page you asked for, using freshly computed values, and leaves everything else as-is.

## Archive page

The archive page (`dist/archive.html`) lists all dated blog posts grouped by month (Notes are excluded from this list). It opens with an `<h1>Archive</h1>` heading, immediately followed by a GitHub-style contribution calendar — a rolling 53-week grid (Monday to Sunday) of every published post (Notes included this time) from the last 12 months, coloured by how many posts fell on each day (`level-0` for none up to `level-5` for five or more). A day later than the build date hasn't happened yet, so it renders as blank space rather than an empty box. Clicking a filled-in day links to the newest post from that day, at its anchor on `index.html` (or whichever paginated index page it falls on); a day with one or more posts carries a `data-tooltip` attribute describing it (plus `aria-label` on its link), e.g. `25 August: 1 post + 2 notes` — deliberately a data attribute rather than `title`, since Magnetizer emits data only and a project's own CSS renders the actual tooltip. A day with no posts has no tooltip. The categories/notes/monthly-list sections described below follow the calendar, in the same order as before:

```html
<section class="contribution-calendar">
  <h2><span class="calendar-count">248</span> posts in the last year</h2>
  <div class="calendar">
    <div class="calendar-months">...</div>
    <div class="calendar-weeks">
      <div class="calendar-week">
        <span class="calendar-day level-0"></span>
        <a href="index.html#post-42" class="calendar-day level-2" data-tooltip="27 May: 2 posts" aria-label="27 May: 2 posts"></a>
        <span class="calendar-day-empty"></span>
        ...
      </div>
      ...
    </div>
  </div>
</section>
```

As with everything else Magnetizer generates, this is bare structure only — no inline styles — so the actual grid layout, sizing, colour scale, and tooltip appearance come entirely from the project's own `resources/` CSS.

```html
<main>
  <h1>Archive</h1>
  <div class="archive-months">
    <section>
      <h3>May 2026</h3>
      <ul>
        <li class="full-post"><span class="day">16</span><a href="42.html">Post title</a></li>
        ...
      </ul>
    </section>
    ...
  </div>
</main>
```

Each month heading is an `<h3>`, one level below the page's own `<h2>Blog Posts</h2>` — it's a subsection of the monthly list, not a sibling heading. Every month `<section>` is wrapped in a single `<div class="archive-months">`, so a project's CSS can flow them across multiple columns on wide viewports via `column-count` — see [Archive column layout](#archive-column-layout) in the spec for the full detail. Magnetizer itself doesn't decide which months land in which column; the browser balances them.

Each `<li>` gets the post's type class (`full-post` or `image-post` — Notes never appear here) and its link text follows the title → `name` → excerpt → generated-fallback priority order described in [Post types](#post-types).

If `categories` is configured and at least one category has a matching post, a categories list is inserted after the contribution calendar. If any Notes exist, a `<h2>Short notes</h2>` section with a link to `notes.html` is inserted after the categories. When either (or both) sections appear, a `<h2>Blog Posts</h2>` heading is shown before the monthly sections:

```html
<main>
  <h1>Archive</h1>
  <div class="archive-columns">
    <div class="archive-categories">
      <h2>Categories</h2>
      <ul>
        <li><a href="photography.html">Photography</a> (34)</li>
        <li><a href="travel.html">Travel</a> (12)</li>
      </ul>
    </div>
    <div class="archive-notes">
      <h2>Short notes</h2>
      <ul>
        <li><a href="notes.html">All short notes</a></li>
      </ul>
    </div>
  </div>
  <h2>Blog Posts</h2>
  ...
</main>
```

Each category link shows the number of posts in that category in parentheses. Categories are listed in descending order of post count, and only if they have at least one matching post.

`archive-categories` and `archive-notes` sit side by side inside `archive-columns` — whichever of the two exist; if only one does, it's the sole child. Like `archive-months`, this is bare structure for a project's CSS to lay out on wide viewports (e.g. a two-column flex row); Magnetizer ships no default column CSS or breakpoint of its own.

## Publishing

Set up `dist/` as a clone of your GitHub Pages repository before using `--push`. Magnetizer stages, commits, and pushes all changes automatically.

If the push is rejected because the remote has changes you don't have locally (e.g. a `CNAME` file added by GitHub), run `git pull --rebase origin main` inside `dist/` first.
