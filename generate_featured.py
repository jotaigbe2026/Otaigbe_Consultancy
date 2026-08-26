#!/usr/bin/env python3
"""Pick one blog article to feature for the current month.

    python3 generate_featured.py                      # write this month's pick
    python3 generate_featured.py --month 2026-11      # preview another month
    python3 generate_featured.py --dry-run            # print, write nothing
    python3 generate_featured.py --all-months 12      # show the next year's rota

Writes content/featured/featured.json, overwriting the previous month's file.
Reads blog/data/posts.json and never writes to blog/ — every post stays in the
archive exactly as it was, and the archive page is untouched.

There is no /content/blog/ directory of Markdown here; the blog lives in
blog/data/posts.json, whose records already carry title, slug, categories,
summary and excerpt. That file is the frontmatter.

Run monthly by .github/workflows/featured.yml. See CLAUDE.md, "Featured
article of the month".
"""

import argparse
import datetime
import hashlib
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "blog", "data", "posts.json")
OUT = os.path.join(ROOT, "content", "featured", "featured.json")
BASE_URL = "https://jotaigbe2026.github.io/Flaney_Associates"

MAX_EXCERPT_WORDS = 40

# The exclusion list is imported rather than copied: it already encodes the
# editorial judgement about which posts belong in the archive but not on the
# front of the site, and two copies would drift.
sys.path.insert(0, ROOT)
from generate_blog import HOMEPAGE_EXCLUDE          # noqa: E402


# ---------------------------------------------------------------- relevance
#
# A category maps to the service areas it speaks to. This is both the relevance
# filter and the source of the summary text, so the reason a post was chosen is
# always the reason stated in the JSON — they cannot disagree.

CATEGORY_THEMES = {
    "Advanced Materials Engineering": [
        "materials selection",
        "product development"],
    "Polymers and Composites": [
        "failure analysis",
        "materials selection"],
    "Sustainable Materials Technology": [
        "materials selection",
        "technical due diligence"],
    "Organic-Inorganic Hybrid Materials": [
        "product development"],
    "Nanotechnology": [
        "product development",
        "technical due diligence"],
    "Protective Coatings": [
        "process optimization",
        "failure analysis"],
    "Glasses and Optical Devices": [
        "materials selection"],
    "Materials Engineering Innovations": [
        "product development"],
}

# Two posts carry only "Board Room Governance" but are squarely about
# materials-science expertise in litigation — which is a core service, not a
# governance topic. Their categories understate them, so they are named here
# rather than the whole category being admitted (which would also let in the
# boardroom-AI posts).
THEME_OVERRIDE = {
    "bridging-science-and-law-how-prof-joshua-otaigbe-helps-science-win-in-court":
        ["expert witness work"],
    "from-lab-to-courtroom-the-impact-of-materials-science-experts-in-patent-disputes":
        ["expert witness work"],
}


def themes_for(post):
    """Service areas this post speaks to, or [] if it is off-theme."""
    if post["slug"] in THEME_OVERRIDE:
        return list(THEME_OVERRIDE[post["slug"]])
    found = []
    for cat in post.get("categories") or []:
        for theme in CATEGORY_THEMES.get(cat, []):
            if theme not in found:
                found.append(theme)
    return found


def matched_categories(post):
    if post["slug"] in THEME_OVERRIDE:
        return list(post.get("categories") or [])
    return [c for c in (post.get("categories") or []) if c in CATEGORY_THEMES]


# ------------------------------------------------------------------- pool

def eligible(posts, today):
    """The posts that may be featured, oldest-stable order.

    Four gates, each for a concrete reason:

    * **not gated** — a gated post's link goes to a members-only login on
      flaneyassociates.com, which is a dead end for a reader arriving cold.
    * **the page exists** — the JSON carries records the site does not render,
      so the URL is checked against the file rather than assumed.
    * **not future-dated** — scheduled posts are committed early and hidden by
      hideScheduledCards() until their morning. Featuring one would publish it
      ahead of its date and quietly break that contract.
    * **on theme, and not excluded** — see themes_for() and HOMEPAGE_EXCLUDE.
    """
    out = []
    for p in posts:
        if p.get("gated"):
            continue
        if not os.path.exists(os.path.join(ROOT, "blog", p["slug"] + ".html")):
            continue
        if p.get("date", "")[:10] > today:
            continue
        if p["slug"] in HOMEPAGE_EXCLUDE:
            continue
        if not themes_for(p):
            continue
        out.append(p)
    # Sorted so the pool order never depends on how posts.json happens to be
    # written; the selection below does not need it, but the logs do.
    return sorted(out, key=lambda p: (p.get("date", ""), p["slug"]), reverse=True)


# -------------------------------------------------------------- selection

def _rendezvous(pool, month):
    """Lowest sha256(month|slug) wins."""
    return min(pool, key=lambda post: hashlib.sha256(
        (month + "|" + post["slug"]).encode("utf-8")).hexdigest())


def previous_month(month):
    y, m = int(month[:4]), int(month[5:])
    return "%04d-%02d" % ((y - 1, 12) if m == 1 else (y, m - 1))


def choose(pool, month):
    """Deterministic pick for `month` ("YYYY-MM").

    Rendezvous hashing: every candidate is hashed together with the month and
    the lowest hash wins. Two properties matter.

    Re-running the workflow — a retried job, a manual dispatch, a local
    preview — reproduces the same article, so what shipped can always be
    checked. A plain random.choice() would silently change the pick on a retry.

    And adding a post only changes a month's pick if that new post happens to
    win it, rather than reshuffling every month the way `hash(month) %
    len(pool)` would. That matters because the publisher adds a post most
    months, so the pool grows between runs.

    The one-month look-back is the exception to "independent per month".
    Independent draws collide: with 16 candidates, August and September landed
    on the same article, which looks broken rather than random. Excluding only
    the previous month's winner fixes the case anyone would notice, and stays
    reproducible because that winner is recomputed rather than remembered.
    Repeats at wider spacing are left alone — they are the accepted cost of not
    keeping a state file.
    """
    if len(pool) < 2:
        return pool[0]
    last = _rendezvous(pool, previous_month(month))["slug"]
    candidates = [p for p in pool if p["slug"] != last]
    return _rendezvous(candidates, month)


# ---------------------------------------------------------------- content

TAGS = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")


def plain(text):
    return WS.sub(" ", html.unescape(TAGS.sub(" ", text or ""))).strip()


SHORTCODE = re.compile(r"\[/?(?:vc_|wpb_)[a-z_]*[^\]]*\]", re.I)
HEADING = re.compile(r"(?is)<h[1-6][^>]*>.*?</h[1-6]>")
PARA = re.compile(r"(?is)<p[^>]*>(.*?)</p>")

# Every article closes with the same contact block and byline. They are prose
# in a <p>, so nothing structural marks them as not-the-article.
BOILERPLATE = re.compile(
    r"(?i)(for more information|contact the author|all rights reserved"
    r"|flaneyassociates\.com|^joshua u\. otaigbe)")


def first_paragraph(post):
    """The article's opening prose, skipping headings and the repeated title.

    The stored `summary` is built from the body by summarise(), which does not
    strip section headings — so for a post that opens with one it reads
    "A New Era in Construction The buildings we live and work in...", a
    heading welded to a sentence. Most posts also repeat their own title as the
    first paragraph.

    Taking the first real paragraph instead avoids both. `excerpt` and
    `summary` remain as fallbacks: several WordPress excerpts carry shortcodes,
    repeat the title, or describe a different article entirely (see
    summarise() in generate_blog.py), so neither is trusted first.
    """
    body = HEADING.sub(" ", SHORTCODE.sub(" ", post.get("content") or ""))
    title = plain(html.unescape(post.get("title") or "")).rstrip(":.")
    collected, count = [], 0
    for match in PARA.findall(body):
        text = plain(match)

        # Most posts repeat their own title at the top. Sometimes it is its own
        # paragraph and sometimes the body runs on from it inside the same <p>,
        # so the prefix is stripped rather than the paragraph discarded —
        # discarding it threw away a 317-word body and left the contact-details
        # footer as the excerpt.
        if title and text.lower().startswith(title.lower()):
            text = text[len(title):].lstrip(" :.\u2013\u2014-")

        if BOILERPLATE.search(text):
            continue
        if len(text.split()) < 6:
            continue

        collected.append(text)
        count += len(text.split())
        # Some articles open with a one-line hook. Keep taking paragraphs until
        # there is enough to fill a highlight, rather than shipping 13 words.
        if count >= MAX_EXCERPT_WORDS:
            break
    return " ".join(collected)


def highlight_excerpt(post, limit=MAX_EXCERPT_WORDS):
    """At most `limit` words, cut on a word boundary.

    The body's opening paragraph first; `excerpt` and `summary` cover the case
    the spec calls "auto-generate if no excerpt exists".
    """
    for text in (first_paragraph(post), plain(post.get("excerpt")),
                 plain(post.get("summary"))):
        if not text:
            continue
        words = text.split()
        if len(words) <= limit:
            return text
        return " ".join(words[:limit]).rstrip(",;:.—-") + "…"
    return ""


def relevance_summary(post, themes, cats):
    """Two or three sentences on why this article was selected.

    Written from the same map that admitted the post, so the stated reason is
    the actual reason. Nothing here is invented about the article's contents.
    """
    def join(items):
        items = list(items)
        if len(items) == 1:
            return items[0]
        return ", ".join(items[:-1]) + " and " + items[-1]

    tail = ("one of the material and manufacturing areas" if len(cats) == 1
            else "which are among the material and manufacturing areas")
    first = ("This article sits in %s, %s this practice works in directly."
             % (join(c.lower() for c in cats), tail))
    second = ("It speaks to %s, so it reaches readers already facing the kind "
              "of decision Flaney Associates is engaged to support."
              % join(themes[:3]))
    third = ("Selected for %s from %s eligible on-site articles."
             % (post["_month_label"], post["_pool_size"]))
    return " ".join([first, second, third])


def build(post, month, month_label, pool_size):
    post = dict(post)
    post["_month_label"] = month_label
    post["_pool_size"] = pool_size
    cats = matched_categories(post) or (post.get("categories") or [])
    themes = themes_for(post)

    return {
        # Titles arrive entity-encoded from the WordPress API ("Pglass &#038;
        # PET"), so they are decoded before going into JSON — JSON has no HTML
        # context, and whatever renders this would show the raw entity.
        "title": html.unescape(post["title"]),
        "slug": post["slug"],
        "url": "%s/blog/%s.html" % (BASE_URL, post["slug"]),
        "summary": relevance_summary(post, themes, cats),
        "highlight_excerpt": highlight_excerpt(post),
        # No wall-clock timestamp here on purpose: the output is a pure
        # function of (month, posts.json), so re-running inside the same month
        # produces a byte-identical file and the workflow's "nothing to commit"
        # check actually works. A generated_at would make every retry a commit.
        "_meta": {
            "month": month,
            "pool_size": pool_size,
            "matched_categories": cats,
            "themes": themes,
            "published": post.get("date", "")[:10],
            "selection": "sha256 rendezvous hash of month|slug, lowest wins",
        },
    }


# ------------------------------------------------------------------- main

def month_label(month):
    y, m = month.split("-")
    return datetime.date(int(y), int(m), 1).strftime("%B %Y")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--month", help='Month to select for, "YYYY-MM". '
                                    "Defaults to the current month.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the object; write nothing.")
    ap.add_argument("--all-months", type=int, metavar="N",
                    help="Print the picks for the next N months and exit.")
    args = ap.parse_args()

    today = datetime.date.today()
    month = args.month or today.strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        ap.error('--month must look like 2026-11, got %r' % month)

    posts = json.load(open(DATA))
    pool = eligible(posts, today.isoformat())
    if not pool:
        # Better to leave last month's file in place than to write an empty one
        # and blank the band on the site.
        print("! no eligible articles — featured.json left unchanged")
        return 1

    if args.all_months is not None:
        start = datetime.date(int(month[:4]), int(month[5:]), 1)
        print("%d eligible articles\n" % len(pool))
        for i in range(args.all_months):
            m = start.month - 1 + i
            d = datetime.date(start.year + m // 12, m % 12 + 1, 1)
            key = d.strftime("%Y-%m")
            print("  %s  %s" % (key, html.unescape(choose(pool, key)["title"])))
        return 0

    chosen = choose(pool, month)
    obj = build(chosen, month, month_label(month), len(pool))

    text = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"

    if args.dry_run:
        print(text, end="")
        return 0

    folder = os.path.dirname(OUT)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    with open(OUT, "w") as fh:
        fh.write(text)
    print("%s  ->  %s" % (os.path.relpath(OUT, ROOT),
                          html.unescape(chosen["title"])))
    print("   %s, %d eligible of %d posts" % (month, len(pool), len(posts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
