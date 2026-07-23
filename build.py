#!/usr/bin/env python3
import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from magnetizer.builder import build
from magnetizer.config import load_config
from magnetizer.publisher import publish


_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_RESET = "\033[0m"


def _c(code, text):
    if sys.stdout.isatty():
        return f"{code}{text}{_RESET}"
    return text


def _post_entries(log):
    return [e for e in log if len(e) >= 6 and e[1].endswith(".html") and e[1][:-5].isdigit()]


def _page_entries(log):
    def is_page(e):
        name = e[1]
        return (
            not (name.endswith(".html") and name[:-5].isdigit())
            and not name.startswith("resources/")
            and e[0] in ("UPDATED", "REMOVED")
        )
    return [e for e in log if is_page(e)]


def _resource_entries(log):
    return [e for e in log if e[1].startswith("resources/")]


def _post_id(entry):
    return int(entry[1][:-5])


def _category_page_names(names, categories):
    if not categories:
        return []
    matched = []
    for slug in categories:
        pattern = re.compile(rf'^{re.escape(slug)}(-\d+)?\.html$')
        matched.extend(n for n in names if pattern.match(n))
    return matched


def _pages_summary(log, verbose, special_pages=(), categories=None):
    entries = _page_entries(log)
    if not entries:
        return None

    names = [e[1] for e in entries]
    index_pages = [n for n in names if n == "index.html" or n.startswith("index-")]
    non_index = [n for n in names if n not in index_pages]

    boilerplate = {"archive.html", "sitemap.xml", "robots.txt"}
    if not verbose:
        non_index = [n for n in non_index if n not in boilerplate]

    parts = []
    for name in special_pages:
        html_name = f"{name}.html"
        if html_name in non_index:
            parts.append(name)
            non_index.remove(html_name)

    if index_pages:
        n = len(index_pages)
        parts.append(f"index(+{n})" if n > 1 else "index")

    category_pages = _category_page_names(non_index, categories)
    if category_pages:
        parts.append(f"categories({len(category_pages)})")
        for name in category_pages:
            non_index.remove(name)

    if "feed.xml" in non_index:
        parts.append("feed.xml")
        non_index.remove("feed.xml")

    if verbose:
        for name in ("archive.html", "sitemap.xml", "robots.txt"):
            if name in non_index:
                parts.append(name)
                non_index.remove(name)

    parts.extend(non_index)
    return ", ".join(parts) if parts else None


def _non_post_warning_files(warns_by_file, posts):
    post_names = {e[1] for e in posts}
    return sorted(name for name in warns_by_file if name not in post_names)


def _print_non_post_warnings(warns_by_file, posts):
    for name in _non_post_warning_files(warns_by_file, posts):
        print(_c(_YELLOW, f"  {name}   ⚠ {', '.join(warns_by_file[name])}"))


def _print_output(outcome, config, dist_path, verbose):
    log = outcome["log"]
    warnings_list = outcome.get("warnings", [])

    warns_by_file = {}
    for filename, msg in warnings_list:
        warns_by_file.setdefault(filename, []).append(msg)

    if not log:
        print("No changes.")
        if warns_by_file:
            print()
            _print_non_post_warnings(warns_by_file, [])
        return bool(warns_by_file)

    posts = _post_entries(log)
    resources = _resource_entries(log)

    if verbose:
        print()
        if posts:
            ids = [_post_id(e) for e in posts]
            id_w = max(3, max(len(str(i)) for i in ids))

            def display_name(e):
                return f"+{e[1]}" if e[5] else e[1]

            name_w = max(len(display_name(e)) for e in posts)

            for entry in sorted(posts, key=_post_id):
                pid = _post_id(entry)
                _, name, _, _, n_imgs, is_draft = entry
                dname = f"+{name}" if is_draft else name
                post_warns = warns_by_file.get(name, [])

                line = f"  {pid:0{id_w}d}   {dname:<{name_w}}"
                if n_imgs:
                    img_label = f"[{n_imgs} img{'s' if n_imgs > 1 else ''}]"
                    line += f"   {img_label}"
                if post_warns:
                    line += f"   ⚠ {', '.join(post_warns)}"
                    print(_c(_YELLOW, line.rstrip()))
                else:
                    print(line.rstrip())
        _print_non_post_warnings(warns_by_file, posts)
        print()
    else:
        posts_with_warns = [e for e in posts if e[1] in warns_by_file]
        if posts_with_warns:
            ids = [_post_id(e) for e in posts_with_warns]
            id_w = max(3, max(len(str(i)) for i in ids))
            name_w = max(len(f"+{e[1]}" if e[5] else e[1]) for e in posts_with_warns)
            for entry in sorted(posts_with_warns, key=_post_id):
                pid = _post_id(entry)
                name = entry[1]
                dname = f"+{name}" if entry[5] else name
                post_warns = warns_by_file.get(name, [])
                print(_c(_YELLOW, f"  {pid:0{id_w}d}   {dname:<{name_w}}   ⚠ {', '.join(post_warns)}"))
        _print_non_post_warnings(warns_by_file, posts)

    c, u, d = outcome["created"], outcome["updated"], outcome["deleted"]
    print(f"{c} created · {u} updated · {d} deleted")

    has_warnings = bool(warns_by_file)

    if verbose:
        if has_warnings:
            w_files = sorted(warns_by_file.keys())
            label = "warning" if len(w_files) == 1 else "warnings"
            print(f"⚠ {len(w_files)} {label}: {', '.join(w_files)}")
        print()

        pages = _pages_summary(log, verbose=True, special_pages=config["special_pages"], categories=config["categories"])
        if pages:
            print(f"{'Pages updated':<16}{pages}")
        if resources:
            names = ", ".join(sorted(e[1][len("resources/"):] for e in resources))
            print(f"{'Resources':<16}{names}")
        print()  # blank line before DONE in verbose
    else:
        pages = _pages_summary(log, verbose=False, special_pages=config["special_pages"], categories=config["categories"])
        if pages:
            print(f"{'updated':<11}{pages}")
        if resources:
            names = ", ".join(sorted(e[1][len("resources/"):] for e in resources))
            print(f"{'resources':<11}{names}")

    return has_warnings


def main():
    parser = argparse.ArgumentParser(
        prog="build.py",
        description="Generate static web pages from the content in ./content.",
    )
    parser.add_argument("filename", nargs="?", metavar="FILENAME")
    parser.add_argument("--flush", action="store_true")
    parser.add_argument("--resources", action="store_true")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.filename and any([args.flush, args.resources, args.push]):
        print("Error: FILENAME cannot be used together with other options.", file=sys.stderr)
        sys.exit(1)

    config = load_config(Path.cwd() / "config.yaml")
    dist_path = (Path.cwd() / "dist").resolve()

    if args.verbose:
        print(f"Generating {config['site_name']} → {dist_path}/")

    dot_count = 0

    def _on_progress():
        nonlocal dot_count
        dot_count += 1
        if sys.stdout.isatty():
            print(".", end="", flush=True)

    def _finish_dots():
        if not sys.stdout.isatty() or dot_count == 0:
            return
        if args.verbose:
            print()
        else:
            # Dots are printed with no newlines, so once dot_count exceeds the
            # terminal width the line wraps onto multiple rows — a single "\r"
            # only rewinds to the start of the last row, so each wrapped row
            # needs to be cleared individually.
            width = shutil.get_terminal_size((80, 24)).columns
            rows = -(-dot_count // width)  # ceil division
            for i in range(rows):
                sys.stdout.write("\r\033[K")
                if i < rows - 1:
                    sys.stdout.write("\033[A")
            sys.stdout.flush()

    try:
        outcome = build(
            Path.cwd(),
            filename=args.filename,
            flush=args.flush,
            resources=args.resources,
            on_progress=_on_progress,
        )
    except Exception as e:
        _finish_dots()
        print(f"  {e}", file=sys.stderr)
        print(_c(_RED, "ERROR"), file=sys.stderr)
        sys.exit(1)

    _finish_dots()

    has_warnings = _print_output(outcome, config, dist_path, verbose=args.verbose)

    if args.push:
        if args.verbose:
            print()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("Pushing to GitHub...", end=" ", flush=True)
        try:
            publish(Path.cwd() / "dist", timestamp)
        except RuntimeError as e:
            print()
            print(f"  {e}", file=sys.stderr)
            print(_c(_RED, "ERROR"), file=sys.stderr)
            sys.exit(1)
        print("DONE.")

    if has_warnings:
        print(_c(_YELLOW, "DONE") + " with warnings")
    elif outcome["log"]:
        print(_c(_GREEN, "DONE"))
    else:
        print(_c(_GREEN, "DONE"))


if __name__ == "__main__":
    main()
