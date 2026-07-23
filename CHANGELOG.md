# Changelog

> [!NOTE]
> This changelog is primarily authored and maintained by Claude Code.

## Released changes

### 23/7/26

- Removed the unused `draft` frontmatter key and everything built on it: the index/category/feed/sitemap/archive/navigation exclusion and the `+` build-output prefix. Every post now always gets the neighbour-aware newer/older navigation and anchored back-link that non-draft posts already used.

### 22/7/26

- Post types: every post is now a Full post (has a title), Image post (no title, has images), or Note (no title, no images, has content) — replacing the old title/photo-based archive classification
- New `name` frontmatter field: a fallback label for untitled posts, used in the heading, meta title, and archive link text
- Every post now gets a heading and meta title (title → `name` → generated label, e.g. "Photo posted 22 July 2026"), instead of omitting it when untitled
- Notes replace microblog posts: no more length cap, and the paginated page is `notes.html` instead of `microblog.html`
- Archive link text now falls back through title → `name` → a 40-character excerpt → generated label, replacing the old 36-character/"Untitled" behaviour
- Build now errors on a post with no title, no images, and no content; warns if `title` and `name` are both set, or if `title` is set with neither images nor content
- Renamed `micro_posts_per_page` config to `notes_per_page`; removed `micro_post_max_length`

### 19/7/26

- `noindex` frontmatter key: excludes a page from `sitemap.xml` and adds a noindex meta tag
- Refactored page `<head>` metadata into a single `MAGNETIZER_METADATA` template placeholder
- Removed `{{ days_since_last_post }}` shortcode
- Smart typography now also converts `--`/`---` to en/em dashes and `...` to an ellipsis
- Split `build()` into named phase functions in `builder.py` (no behaviour change)
- Consolidated config and frontmatter reference docs
- Fixed category pages never appearing in the build log

### 18/7/26

- Dynamic shortcodes, e.g. `post_count` and `ai_post_list`

### 17/7/26

- Inline post images
- AI disclosure banners, triggered from frontmatter

### 15/7/26

- Bug fix microblog character counts

### 14/7/26

- `:::` fenced containers / special divs

### 10/7/26

- Active navigation accessibility improvements

### 9/7/26

- Removed unused archive statistics block
- Configurable special pages, replacing fixed 'About' and 'Cookies'

### 8/7/26

- Configurable site navigation

### 7/7/26

- Updated untitled individual page meta titles to `Post N - site_name`
- Dedicated microblog pages
- Added SVG image support

### 6/7/26

- Improved console output + build fixes
- Added post counts to categories in the archive, ordering by count

### 17/6/26

- Added category pages to the sitemap
- Draft posts, generating individual post pages but not showing anywhere else
- Code and specification tidy-up, test clean up and improved resource syncing

### 16/6/26

- Post categories and category pages
- Article heading hierarchy, using h1 on individual post pages and h2 on index pages

### 15/6/26

- More-photos link to appear below post body

### 14/6/26

- Render quotation marks and apostrophes as typographic versions
- Favourite posts in Archive using frontmatter

### 13/6/26

- Meta description for index pages via config
- Photo-only posts as "Untitled" rather than “Photo” in archive
- Include images in Atom feed

### 11/6/26

- `MAGNETIZER_CANONICAL_URL` template placeholder
- 'More photos' link + removing archive stats
- `==highlighted text==` Markdown syntax rendered as `<mark>`

### 8/6/26

- Archive improvements (styling, structure & statistics)

### 7/6/26

- Reduce image sizes
- Configurable max length for microblog posts
- `sitemap.xml` and `robots.txt` file

### 6/6/26

- Cookies page
- Fixed post navigation when building individual post pages
- Verbose build output

### 5/6/26

- Micro-posts
- Tweaked article names for title-less posts on Archive page

### 3/6/26

- Tweaked untitled article names on Archive page
- Atom feed bug fixes (escaping titles, etc)

### 1/6/26

- `MAGNETIZER_BUILD_ID` template placeholder busting the cache for resource files on build
- Archive page listing all blogposts
- Image alt texts via frontmatter with build warning when missing

### 31/5/26

- Atom feed generation
- 'Newer' and 'Older' links on individual post pages
- Post excerpts with 'Read more' links on index pages
- 'About' page

### 24/5/26

- Initial launch
