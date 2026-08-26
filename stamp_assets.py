#!/usr/bin/env python3
"""Stamp publisher/index.html's own asset URLs with a content hash.

The blog has always done this — asset_version() in generate_blog.py appends a
hash to blog.css/blog.js — but publisher/index.html is hand-written, so its own
stylesheet and scripts were loaded bare:

    <script src="publisher.js"></script>

A browser that has the file cached then keeps using it. The symptom is nasty
because it is silent and looks like a broken feature rather than a stale file:
index.html is small and revalidates, so you get the *new* markup running against
the *old* script — buttons that exist but do nothing.

Appending the hash means the URL changes whenever the file does, so a stale copy
can never be reused.

    python3 stamp_assets.py

Idempotent, and run automatically at the end of generate_blog.py.
"""
import hashlib
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))

#: (page, directory the assets sit in, pattern matching just those assets).
#: Anything not matched is left alone — notably the Google Fonts URL, which is
#: not ours to version, and blog/blog.css, which generate_blog.py already
#: stamps through update_homepage().
PAGES = [
    (os.path.join(ROOT, "publisher", "index.html"),
     os.path.join(ROOT, "publisher"),
     r'(publisher\.css|publisher\.js|lib/[a-z0-9_-]+\.js)'),
    (os.path.join(ROOT, "index.html"),
     ROOT,
     r'(styles\.css|script\.js|nav\.js|featured\.js|lead-capture\.js)'),
]


def digest(directory, relative):
    with open(os.path.join(directory, relative), "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]


def stamp_page(page, directory, pattern):
    label = os.path.relpath(page, ROOT)
    try:
        html = open(page).read()
    except OSError:
        print("%-22s not found — skipped" % label)
        return

    assets = re.compile(r'(href|src)="%s(?:\?v=[a-f0-9]+)?"' % pattern)
    seen = []

    def stamp(m):
        attr, asset = m.group(1), m.group(2)
        version = digest(directory, asset)
        seen.append((asset, version))
        return '%s="%s?v=%s"' % (attr, asset, version)

    updated = assets.sub(stamp, html)

    if updated == html:
        print("%-22s already current (%d assets)" % (label, len(seen)))
        return

    with open(page, "w") as f:
        f.write(updated)
    print("%-22s stamped %d assets" % (label, len(seen)))
    for asset, version in seen:
        print("    %-20s v=%s" % (asset, version))


def main():
    for page, directory, pattern in PAGES:
        stamp_page(page, directory, pattern)


if __name__ == "__main__":
    main()
