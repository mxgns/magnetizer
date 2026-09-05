# Changelog

> [!NOTE]
> This changelog is primarily authored and maintained by Claude Code.

## Released changes

### 5/9/26

- Exclude noindex pages from the Pagefind search index
- Generate search.html on full builds; Pagefind reindexes every build
- Archive calendar summary now also states the current weekly streak

### 3/9/26

- Inline post images now link to the post on index/category pages

### 2/9/26

- Strip EXIF metadata from resized images; fix lost orientation
- Strip script tags from the Atom feed
- Cut Atom feed entries at the Read more marker
- Added feed_max_posts config option to cap Atom feed length

### 31/8/26

- Added image thumbnails and a paginated gallery page

### 26/8/26

- Added support for tables

### 16/8/26

- Reverted the Atom feed to also include notes.

### 13/8/26

- Added posts.json for looking up title and category from a post id.
- Extracted `archive_display_text()` for reuse by `posts.json`

### 7/8/26

- Added a GitHub-style contribution calendar to the archive page
- Fixed archive month headings using `<h2>` instead of `<h3>`
- Wrapped archive categories/notes/months in column-layout containers

### 6/8/26

- Added comments, published manually using .md

### 2/8/26

- Atom feed entry links now carry a `?src=atom` tracking param
- Short notes excluded from the Atom feed

### 1/8/26

- AI disclosure banner now renders above the post heading

### 29/7/26

- Renamed "Notes" to "Short notes" in headings/links
- New `MAGNETIZER_PAGE_ID` template placeholder

### 28/7/26

- Added 404 page support

### 26/7/26

- External post links now open in a new tab
- Simplified "Back to homepage" links to a single "Blog home" link

### 23/7/26

- Removed the unused `draft` feature
- New `images_per_post` config

### 22/7/26

- New post types: Full post, Image post, and Note
- `name` frontmatter field: fallback label for untitled posts
- Untitled posts now always get a heading and meta title
- Renamed microblog posts to Notes; removed the length cap
- Archive link text now falls back through title → name → excerpt
- New build error/warnings for invalid, title+name, and title-only posts
- Renamed `micro_posts_per_page` config to `notes_per_page`

### 19/7/26

- New `noindex` frontmatter key
- Refactored `<head>` metadata into `MAGNETIZER_METADATA` placeholder
- Removed `{{ days_since_last_post }}` shortcode
- Smart typography also converts dashes and ellipses
- Split `build()` into named phase functions
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
- Article heading hierarchy: h1 on posts, h2 on index

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

- New `MAGNETIZER_BUILD_ID` cache-busting placeholder
- Archive page listing all blogposts
- Image alt texts via frontmatter with build warning when missing

### 31/5/26

- Atom feed generation
- 'Newer' and 'Older' links on individual post pages
- Post excerpts with 'Read more' links on index pages
- 'About' page

### 24/5/26

- Initial launch
