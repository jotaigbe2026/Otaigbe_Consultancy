#!/usr/bin/env python3
"""Build the blog from content extracted off flaneyassociates.com.

Reads blog/data/posts.json (produced by extract_blog.py) and writes:

    blog/index.html      archive of all 55 posts, searchable + filterable
    blog/<slug>.html     one page per post whose full text is public
    blog/blog.css        styles layered on top of the site-wide styles.css

Posts still gated behind the source site's membership plugin are listed on
the archive with their real title, date, category and abstract, and link out
to flaneyassociates.com. No body text is invented for them.

    python3 generate_blog.py
"""
import hashlib
import html as htmlmod
import json
import os
import re
from datetime import datetime

import stamp_assets

ROOT = os.path.dirname(os.path.abspath(__file__))
BLOG = os.path.join(ROOT, "blog")
DATA = os.path.join(BLOG, "data", "posts.json")
# The retired WordPress origin. This is NOT a site base URL: its only job is
# resolving the protocol-relative and root-relative image paths that came back
# in the imported post bodies (see resolve() below). It must not be merged with
# BASE_URL — that one follows the domain move, this one is frozen history.
SOURCE_SITE = "https://flaneyassociates.com"

# The canonical origin of this site, and the single place it is written down.
# Three Python generators and publisher.js all read site.json, so moving the
# domain is a one-line edit there rather than four edits across four files.
with open(os.path.join(ROOT, "site.json")) as _f:
    BASE_URL = json.load(_f)["base_url"]

# ---------------------------------------------------------------- sanitising

SHORTCODE = re.compile(r"\[/?(?:vc_|wpb_)[a-z_]*(?:[^\]]*)\]", re.I)
BAD_ATTR = re.compile(
    r'\s(?:style|class|id|data-[\w-]+|width|height|srcset|sizes|loading|decoding)="[^"]*"', re.I
)
WRAPPER_DIV = re.compile(r"</?div[^>]*>", re.I)
EMPTY_P = re.compile(r"<p>(?:\s|&nbsp;|<br\s*/?>)*</p>", re.I)


def promote_pseudo_headings(html):
    """WPBakery collapsed section headings into inline <strong> inside long <p>.

    Split those paragraphs so a bold run that genuinely acts as a heading
    becomes an <h3>. Deliberately conservative — a bold run is only promoted
    when it begins a new block, reads like a short title, and the text after
    it starts a fresh sentence. Inline emphasis is left alone.
    """

    def looks_like_heading(t):
        t = t.strip()
        if not (3 < len(t) <= 80):
            return False
        if t[-1] in ",;:-–—.":
            return False
        return len(t.split()) <= 12

    def fix_paragraph(m):
        parts = re.split(r"(<strong>(?:(?!</strong>).)*</strong>)", m.group(1), flags=re.S)
        if len(parts) < 3:
            return m.group(0)
        out, buf = [], ""

        def flush():
            nonlocal buf
            if re.sub(r"<[^>]+>", "", buf).strip():
                out.append("<p>%s</p>" % buf.strip())
            buf = ""

        for i, part in enumerate(parts):
            sm = re.fullmatch(r"<strong>((?:(?!</strong>).)*)</strong>", part, flags=re.S)
            if sm:
                text = re.sub(r"<[^>]+>", "", sm.group(1)).strip()
                pending = re.sub(r"<[^>]+>", "", buf).strip()
                starts_block = (not pending) or pending[-1] in ".!?”\"'"
                after = re.sub(r"<[^>]+>", "", "".join(parts[i + 1:])).strip()
                opens_new = (not after) or after[0].isupper() or after[0].isdigit()
                prev_was_heading = bool(out) and out[-1].startswith("<h3>")
                if looks_like_heading(text) and starts_block and opens_new and not prev_was_heading:
                    flush()
                    out.append("<h3>%s</h3>" % text)
                    continue
            buf += part
        flush()
        return "".join(out) if out else m.group(0)

    return re.sub(r"<p>(.*?)</p>", fix_paragraph, html, flags=re.S)


INLINE = "em|strong|i|b|u"


def _norm(s):
    """Comparison key: entities decoded, tags and punctuation dropped.

    Titles arrive entity-encoded from the API ("Pglass &#038; PET"), so they
    must be decoded before matching against body text that renders the same.
    """
    return re.sub(r"[^a-z0-9]", "", htmlmod.unescape(strip_tags(s)).lower())


def drop_leading_title(html, title):
    """Remove the article title from the top of the body.

    Most posts open by repeating their own title — either as a heading or as a
    bold/italic run at the start of the first paragraph. The page already
    renders the title as its <h1>, so left in place it shows up twice.
    """
    want = _norm(title)
    if len(want) < 12:
        return html

    # case 1: a leading heading that is just the title
    m = re.match(r"\s*<(h[1-6])>(.*?)</\1>\s*", html, flags=re.S)
    if m and _norm(m.group(2)) == want:
        return html[m.end():]

    # case 2: a leading emphasis run at the start of the first paragraph
    m = re.match(r"(\s*<p>\s*)((?:<(?:%s)>\s*)+)(.*?)((?:\s*</(?:%s)>)+)\s*"
                 % (INLINE, INLINE), html, flags=re.S)
    if m and _norm(m.group(3)) == want:
        return m.group(1) + html[m.end():]

    return html


def balance_inline_tags(html):
    """Drop inline close tags with no matching open tag, and empty inline pairs.

    Promoting a bold run to a heading discards the tags inside it, which can
    orphan an <em> that opened just outside the run.
    """
    open_counts = {}

    def fix(m):
        tag = m.group(2).lower()
        closing = m.group(1) == "/"
        if closing:
            if open_counts.get(tag, 0) == 0:
                return ""
            open_counts[tag] -= 1
        else:
            open_counts[tag] = open_counts.get(tag, 0) + 1
        return m.group(0)

    html = re.sub(r"<(/?)(%s)>" % INLINE, fix, html)
    # any tag left open at the end never closes — drop those openers
    for tag, n in open_counts.items():
        for _ in range(n):
            html = re.sub(r"<%s>" % tag, "", html, count=1)
    # collapse pairs that now wrap nothing
    for _ in range(3):
        html = re.sub(r"<(%s)>\s*</\1>" % INLINE, " ", html)
    return html


def absolutize(html):
    """Point every link at the source site and make outbound links safe."""

    def fix(m):
        url = m.group(1)
        if url.startswith("/"):
            url = SOURCE_SITE + url
        if url.startswith("http") and "flaneyassociates.com" not in url:
            return 'href="%s" target="_blank" rel="noopener noreferrer"' % url
        if url.startswith("http"):
            return 'href="%s" target="_blank" rel="noopener"' % url
        return 'href="%s"' % url

    return re.sub(r'href="([^"]*)"', fix, html)


def clean(html, title=None):
    if not html:
        return ""
    html = html.replace("&#8221;", '"').replace("&#8220;", '"')
    html = SHORTCODE.sub("", html)
    # Gutenberg block delimiters (<!-- wp:paragraph -->) ship in the API output
    html = re.sub(r"<!--\s*/?\s*wp:.*?-->", "", html, flags=re.S)
    html = BAD_ATTR.sub("", html)
    html = WRAPPER_DIV.sub("", html)
    html = re.sub(r"</?span>", "", html)
    html = re.sub(r"<(/?)u>", r"<\1em>", html)
    html = html.replace("<b>", "<strong>").replace("</b>", "</strong>")
    html = EMPTY_P.sub("", html)
    html = promote_pseudo_headings(html)
    if title:
        html = drop_leading_title(html, title)
    html = balance_inline_tags(html)
    html = EMPTY_P.sub("", html)
    html = absolutize(html)
    # wide tables scroll inside their own box so the page body never does
    html = re.sub(r"(?is)<table.*?</table>",
                  lambda m: '<div class="table-scroll">%s</div>' % m.group(0), html)
    return re.sub(r"[ \t]{2,}", " ", html).strip()


def strip_tags(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def attr(text):
    """Escape a (possibly entity-encoded) string for use in an attribute.

    Decode first: source titles and excerpts arrive entity-encoded, and the
    archive's search reads these values back through `dataset`, which returns
    them decoded. Leaving "&#8217;" in place would mean a search for "didn't"
    never matched. Re-escape only the characters an attribute actually needs.
    """
    text = htmlmod.unescape(strip_tags(text))
    return text.replace("&", "&amp;").replace('"', "&quot;")


#: typographic characters folded to ASCII so a search for "didn't" matches
#: "didn’t". blog.js applies the same folding to the query.
TYPOGRAPHIC = {"‘": "'", "’": "'", "“": '"', "”": '"',
               "–": "-", "—": "-", "…": "...", " ": " "}


def search_key(text):
    """Lowercased, ASCII-folded haystack for the archive's client-side search."""
    text = htmlmod.unescape(strip_tags(text))
    for src, dst in TYPOGRAPHIC.items():
        text = text.replace(src, dst)
    return text.lower().replace("&", "&amp;").replace('"', "&quot;")


def _tidy_summary(text, title):
    text = re.sub(r'^\s*(?:css=)?"*\s*', "", strip_tags(text))
    title = (title or "").strip().rstrip(":")
    if title and text.lower().startswith(title.lower()):
        text = text[len(title):].lstrip(" :–—-")
    # drop a leading section label the text may have swallowed
    text = re.sub(r"^(Introduction|Abstract|Overview)\b[\s:–—-]*", "", text, flags=re.I)
    text = re.sub(r"\s*\[(?:…|\.\.\.)\]\s*$", "", text)
    # stripping inline tags leaves gaps before punctuation
    text = re.sub(r"\s+([,.;:!?%])", r"\1", text)
    return re.sub(r"\(\s+|\s+\)", lambda m: m.group(0).strip(), text).strip()


# The Simple Membership plugin served this in place of an abstract on a couple
# of gated posts, and the API returned it as the excerpt. It is not a summary:
# it was indexed into the card's data-title, so searching the archive for
# "member" or "logged" surfaced those posts. summarise() returns "" for it and
# card() then omits the <p> entirely, which also leaves data-title as the title
# alone. Two posts are affected today; the guard covers any future one.
LOGIN_WALL = re.compile(r"logged in to view|not a member|please log in", re.I)


def summarise(p, limit=260):
    """A clean one-paragraph summary for cards and meta descriptions.

    A stored `summary` always wins. Every post carries one: it is what this
    function computed the first time, and for posts written in publisher/ it is
    whatever the author typed. Storing it means the archive, the homepage strip
    and the article page agree no matter which renderer produced them — the
    publisher builds those pages in JavaScript, and re-deriving this from the
    body in two languages is the one thing guaranteed to drift.

    Falling back, prefer the article's own opening: several of the source site's
    WordPress excerpts carry WPBakery shortcodes, repeat the title, or — on a
    handful of posts — describe an entirely different article. Where the body is
    available it is the only trustworthy summary. Gated posts have no body, so
    their published abstract is used as-is once cleaned.
    """
    if p.get("summary") and not LOGIN_WALL.search(p["summary"]):
        return p["summary"]

    title = strip_tags(p["title"])
    text = ""

    if not p["gated"]:
        text = _tidy_summary(strip_tags(clean(p["content"], title)), title)

    if len(text.split()) < 8:
        raw = (p["excerpt"] or "").replace("&#8221;", '"').replace("&#8220;", '"')
        text = _tidy_summary(SHORTCODE.sub("", raw), title) or text

    if len(text) > limit:
        text = text[:limit - 1].rsplit(" ", 1)[0].rstrip(",;:.") + "…"

    # The login wall reaches this point by two routes — the stored summary and
    # the WordPress excerpt carry the same string — so it is rejected at the
    # exit rather than at each source. Returning "" also keeps this in step
    # with template.js, whose summarise() only ever sees the (empty) body of a
    # gated post and so returns "" here regardless.
    if LOGIN_WALL.search(text):
        return ""
    return text


# ---------------------------------------------------------------- assets

def asset_version(name, base=None):
    """Short content hash appended to asset URLs.

    Without it, browsers keep serving a cached blog.css/blog.js after a deploy,
    so returning visitors can get new markup with the old stylesheet or an old
    search index with the new script. `base` selects the directory the asset
    lives in — lead-capture.js sits at the repository root, not in blog/.
    """
    try:
        with open(os.path.join(base or BLOG, name), "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    except OSError:
        return "1"


# ---------------------------------------------------------------- components

def nav(depth=1, solid=False):
    """Site navbar. `solid` is for pages with no dark hero behind it, where the
    default transparent/white-text treatment would be invisible."""
    up = "../" * depth
    cls = "navbar navbar-solid" if solid else "navbar"
    return """    <nav class="{cls}" id="navbar">
        <div class="container nav-container">
            <a href="{up}index.html" class="logo">
                <span class="logo-icon">&#9670;</span>
                Flaney<span class="logo-accent">Associates</span>
            </a>
            <button class="nav-toggle" id="navToggle" aria-label="Toggle navigation">
                <span></span><span></span><span></span>
            </button>
            <ul class="nav-links" id="navLinks">
                <li class="has-dropdown">
                    <button type="button" class="nav-trigger">How We Help</button>
                    <ul class="dropdown">
                        <li><a href="{up}services/failure-analysis.html">Failure &amp; Root-Cause Analysis<span class="dropdown-note">Why it failed, and what is defensible</span></a></li>
                        <li><a href="{up}services/materials-selection.html">Materials Selection &amp; Qualification<span class="dropdown-note">Choosing and validating a material</span></a></li>
                        <li><a href="{up}services/product-development.html">Product Development &amp; Materials Innovation<span class="dropdown-note">Concept through production</span></a></li>
                        <li><a href="{up}services/process-optimization.html">Manufacturing Process Optimization<span class="dropdown-note">Yield, quality, throughput</span></a></li>
                        <li><a href="{up}services/technical-due-diligence.html">Technical Due Diligence &amp; R&amp;D Strategy<span class="dropdown-note">Technology and investment decisions</span></a></li>
                        <li><a href="{up}services/expert-witness.html">Expert Witness &amp; Litigation Support<span class="dropdown-note">Product liability, IP, technical disputes</span></a></li>
                    </ul>
                </li>
                <li class="has-dropdown">
                    <button type="button" class="nav-trigger">Industries</button>
                    <ul class="dropdown">
                        <li><a href="{up}industries.html#polymers-plastics">Polymers &amp; Plastics</a></li>
                        <li><a href="{up}industries.html#composites">Composites</a></li>
                        <li><a href="{up}industries.html#manufacturing">Manufacturing &amp; Processing</a></li>
                        <li><a href="{up}industries.html#consumer-products">Consumer Products</a></li>
                        <li><a href="{up}industries.html#automotive">Automotive &amp; Transportation</a></li>
                        <li><a href="{up}industries.html#energy">Energy &amp; Oil/Gas</a></li>
                    </ul>
                </li>
                <li class="has-dropdown">
                    <button type="button" class="nav-trigger">Insights</button>
                    <ul class="dropdown">
                        <li><a href="{up}featured.html">Featured This Month<span class="dropdown-note">One article, chosen monthly</span></a></li>
                        <li><a href="{up}blog/index.html" class="active">Blog<span class="dropdown-note">Articles on materials and manufacturing</span></a></li>
                        <li><a href="{up}guides.html">Guides &amp; Briefings<span class="dropdown-note">Checklists and sector briefings</span></a></li>
                    </ul>
                </li>
                <li class="has-dropdown">
                    <button type="button" class="nav-trigger">About</button>
                    <ul class="dropdown">
                        <li><a href="{up}about.html">Joshua U. Otaigbe<span class="dropdown-note">Founder &amp; Principal &middot; credentials and approach</span></a></li>
                        <li><a href="{up}about.html#credentials">Credentials</a></li>
                        <li><a href="{up}about.html#approach">Approach</a></li>
                        <li><a href="{up}about.html#faqs">FAQs</a></li>
                    </ul>
                </li>
                <li class="has-dropdown">
                    <button type="button" class="nav-trigger">Contact</button>
                    <ul class="dropdown">
                        <li><a href="{up}contact.html">Discuss Your Challenge<span class="dropdown-note">Manufacturers and product teams</span></a></li>
                        <li><a href="{up}attorney-inquiry.html">Attorney Conflict Check<span class="dropdown-note">Confidential, no case details</span></a></li>
                    </ul>
                </li>
                <li><a href="{up}contact.html" class="btn btn-nav">Discuss Your Challenge</a></li>
            </ul>
        </div>
    </nav>""".format(up=up, cls=cls)


def footer(depth=1):
    up = "../" * depth
    return """    <footer class="footer">
        <div class="container">
            <div class="footer-grid">
                <div class="footer-brand">
                    <a href="{up}index.html" class="logo">
                        <span class="logo-icon">&#9670;</span>
                        Flaney<span class="logo-accent">Associates</span>
                    </a>
                    <p>Independent materials-science and engineering expertise for manufacturers, product teams and attorneys. Led by Joshua U. Otaigbe, PhD, CEng, FIMMM &mdash; Founder &amp; Principal, Flaney Associates.</p>
                    <div class="footer-social">
                        <a href="https://www.linkedin.com/in/joshua-otaigbe-ceng-fimmm-faeng-22751322" target="_blank" rel="noopener noreferrer" class="social-link" aria-label="LinkedIn">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
                        </a>
                        <a href="tel:+16014027282" class="social-link" aria-label="Phone">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z"/></svg>
                        </a>
                    </div>
                </div>
                <div class="footer-links">
                    <h4>How We Help</h4>
                    <ul>
                        <li><a href="{up}services/failure-analysis.html">Failure &amp; Root-Cause Analysis</a></li>
                        <li><a href="{up}services/materials-selection.html">Materials Selection &amp; Qualification</a></li>
                        <li><a href="{up}services/product-development.html">Product Development &amp; Materials Innovation</a></li>
                        <li><a href="{up}services/process-optimization.html">Manufacturing Process Optimization</a></li>
                        <li><a href="{up}services/technical-due-diligence.html">Technical Due Diligence &amp; R&amp;D Strategy</a></li>
                        <li><a href="{up}services/expert-witness.html">Expert Witness &amp; Litigation Support</a></li>
                    </ul>
                </div>
                <div class="footer-links">
                    <h4>Company</h4>
                    <ul>
                        <li><a href="{up}about.html">About Joshua U. Otaigbe</a></li>
                        <li><a href="{up}about.html#credentials">Credentials</a></li>
                        <li><a href="{up}industries.html">Industries</a></li>
                        <li><a href="{up}featured.html">Featured This Month</a></li>
                        <li><a href="{up}blog/index.html">Blog</a></li>
                        <li><a href="{up}guides.html">Guides &amp; Briefings</a></li>
                    </ul>
                </div>
                <div class="footer-links">
                    <h4>Contact</h4>
                    <ul>
                        <li><a href="{up}contact.html">Discuss Your Challenge</a></li>
                        <li><a href="{up}attorney-inquiry.html">Attorney Conflict Check</a></li>
                        <li><a href="mailto:info@flaneyassociates.com">info@flaneyassociates.com</a></li>
                        <li><a href="tel:+16014027282">+1 (601) 402-7282</a></li>
                    </ul>
                </div>
            </div>
            <div class="footer-bottom">
                <p>&copy; 2026 Flaney Associates, LLC. All rights reserved.</p>
            </div>
        </div>
    </footer>""".format(up=up)


def download_modal():
    """Lead-capture modal for gated PDFs — identical to the one in index.html.

    lead-capture.js wires it up wherever it appears, so article pages get the
    same gate the homepage briefings use.
    """
    return """    <div class="modal-overlay" id="downloadModal">
        <div class="modal-card">
            <button class="modal-close" id="modalClose" aria-label="Close">&times;</button>
            <div class="modal-icon">&#128218;</div>
            <h3>Get Your Free Article</h3>
            <p class="modal-subtitle">Enter your details below and the PDF will download instantly. No spam — just expert insights.</p>
            <form class="modal-form" id="downloadForm">
                <div class="form-group">
                    <input type="text" id="dlName" name="name" placeholder="Your Name" required>
                </div>
                <div class="form-group">
                    <input type="email" id="dlEmail" name="email" placeholder="Work Email" required>
                    <span class="email-feedback" id="dlEmailFeedback"></span>
                </div>
                <div class="form-group">
                    <input type="text" id="dlCompany" name="company" placeholder="Company (optional)">
                </div>
                <input type="hidden" id="dlArticle" name="article" value="">
                <button type="submit" class="btn btn-primary btn-lg btn-full">&#11015; Download Now — Free</button>
                <p class="form-note">We respect your privacy. Unsubscribe anytime.</p>
            </form>
        </div>
    </div>"""


def scripts(depth=1):
    """lead-capture.js first: blog.js calls hideScheduledCards() from it.

    Both carry a content hash for the same reason blog.css does — a cached
    lead-capture.js against new markup means the download gate silently stops
    working, which looks like a broken button rather than a stale file.
    """
    up = "../" * depth
    return ('    <script src="%slead-capture.js?v=%s"></script>\n'
            '    <script src="blog.js?v=%s"></script>\n'
            % (up, asset_version("lead-capture.js", ROOT), asset_version("blog.js")))


def head(title, description, depth=1, extra=""):
    up = "../" * depth
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="{desc}">
{extra}    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="{up}styles.css?v={sitev}">
    <link rel="stylesheet" href="{up}blog/blog.css?v={cssv}">
</head>
<body>
""".format(title=title, desc=description, up=up, extra=extra,
               cssv=asset_version("blog.css"),
               sitev=asset_version("styles.css", base=ROOT))


# ------------------------------------------------------------------- helpers

def fmt_date(iso):
    d = datetime.strptime(iso[:10], "%Y-%m-%d")
    return "%s %d, %d" % (d.strftime("%B"), d.day, d.year)


def read_time(words):
    return max(1, round(words / 200))


def card(p, prefix=""):
    """Render one archive card. Gated posts link out to the source site.

    `prefix` is prepended to blog-relative URLs so the same card works from
    the homepage (prefix="blog/") as from inside blog/ (prefix="").
    """
    img = p.get("local_image")
    if img:
        media = '<img src="{pre}images/{f}" alt="{alt}" loading="lazy">'.format(
            pre=prefix, f=img, alt=attr(p["image_alt"] or p["title"]))
    else:
        media = '<div class="blog-thumb-fallback" aria-hidden="true">&#9670;</div>'

    cats = p["categories"] or ["Materials Engineering"]
    excerpt = summarise(p)

    if p["gated"]:
        # The source site is being retired, so these no longer link anywhere.
        # The thumbnail and title become inert — .post-thumb and .post-card h3
        # are styled by class, not by tag, so dropping the <a> changes nothing
        # visually. The paper itself is supplied on request.
        contact = "contact.html" if prefix else "../contact.html"
        thumb = '<div class="post-thumb">%s</div>' % media
        heading = "<h3>%s</h3>" % p["title"]
        action = '<a class="card-link" href="%s">Request a copy &rarr;</a>' % contact
        badge = ('<span class="post-badge post-badge-locked">'
                 "&#128196; PDF on request</span>")
        meta_extra = ""
    else:
        href = "%s%s.html" % (prefix, p["slug"])
        thumb = '<a class="post-thumb" href="%s">%s</a>' % (href, media)
        heading = '<h3><a href="%s">%s</a></h3>' % (href, p["title"])
        action = '<a class="card-link" href="%s">Read full article &rarr;</a>' % href
        badge = ""
        meta_extra = '<span class="blog-read">%d min read</span>' % read_time(p["words"])

    # Two gated posts have no abstract at all — see LOGIN_WALL. An empty <p>
    # would leave a gap the card's spacing was not designed for, so the element
    # is omitted rather than rendered blank.
    summary_el = ("\n                        <p>%s</p>" % excerpt) if excerpt else ""

    return """                <article class="post-card" data-title="{search}" data-cats="{catattr}" data-publish="{publish}">
                    {thumb}
                    <div class="post-body">
                        <div class="post-cats">{cats}{badge}</div>
                        {heading}{summary_el}
                        <div class="blog-meta">
                            <span class="blog-date">{date}</span>
                            {meta_extra}
                        </div>
                        {action}
                    </div>
                </article>
""".format(
        search=search_key((p["title"] + " " + excerpt).strip()),
        catattr=attr("|".join(cats)), publish=p["date"][:10],
        thumb=thumb, heading=heading, summary_el=summary_el,
        cats="".join('<span class="blog-category">%s</span>' % c for c in cats),
        badge=badge,
        date=fmt_date(p["date"]), meta_extra=meta_extra, action=action)


# -------------------------------------------------------------- page writers

def build_index(posts):
    all_cats = sorted({c for p in posts for c in (p["categories"] or [])})
    full = [p for p in posts if not p["gated"]]

    chips = ['<button class="filter-chip active" data-cat="all">All posts '
             '<span class="chip-count">%d</span></button>' % len(posts)]
    for c in all_cats:
        n = sum(1 for p in posts if c in p["categories"])
        chips.append('<button class="filter-chip" data-cat="%s">%s <span class="chip-count">%d</span></button>'
                     % (attr(c), c, n))

    html = head(
        "Blog &amp; Publications | Flaney Associates",
        "Materials engineering insights, research notes and publications from "
        "Flaney Associates — polymers, composites, nanotechnology, sustainable "
        "materials and AI in materials discovery.",
        depth=1,
    )
    html += nav(1) + "\n"
    html += """
    <header class="blog-hero">
        <div class="container">
            <div class="hero-badge">Insights &amp; Publications</div>
            <h1>The Flaney Associates Blog</h1>
            <p class="blog-hero-sub">{total} articles and publications on materials engineering — polymers and composites, nanotechnology, sustainable materials, protective coatings, and the growing role of AI in materials discovery.</p>
            <div class="blog-hero-stats">
                <div class="stat"><span class="stat-number" data-total="{total}">{total}</span><span class="stat-label">Articles</span></div>
                <div class="stat"><span class="stat-number">{full}</span><span class="stat-label">Read online</span></div>
                <div class="stat"><span class="stat-number">{cats}</span><span class="stat-label">Topics</span></div>
            </div>
        </div>
    </header>

    <div class="blog-toolbar">
        <div class="container">
            <div class="blog-search">
                <input type="search" id="postSearch" placeholder="Search articles by title or keyword…" aria-label="Search articles">
            </div>
            <div class="filter-chips" id="filterChips">
{chips}
            </div>
        </div>
    </div>

    <main class="section blog-archive">
        <div class="container">
            <p class="results-count" id="resultsCount"></p>
            <div class="post-grid" id="postGrid">
""".format(total=len(posts), full=len(full), cats=len(all_cats),
           chips="\n".join("                " + c for c in chips))

    for p in posts:
        html += card(p)

    html += """            </div>
            <p class="no-results" id="noResults" hidden>No articles match that search. <button class="link-btn" id="clearFilters">Clear filters</button></p>

            <div class="archive-note">
                <h4>About this archive</h4>
                <p>Articles marked <strong>&#128196; PDF on request</strong> are published papers and trade articles. They are listed here by title, date and abstract; the full text and a PDF copy are available on request. <a href="../contact.html">Ask for a copy</a> and name the article you want.</p>
            </div>
        </div>
    </main>

    <section class="section cta-band">
        <div class="container">
            <h2>Have a materials challenge of your own?</h2>
            <p>Describe what is happening, what it is costing and what decision is waiting on it. You speak with the principal directly.</p>
            <a href="../contact.html" class="btn btn-primary btn-lg">Discuss Your Challenge</a>
        </div>
    </section>

"""
    html += footer(1) + "\n"
    html += scripts(1) + "</body>\n</html>\n"
    with open(os.path.join(BLOG, "index.html"), "w") as f:
        f.write(html)
    return len(posts)


def build_post(p, posts):
    # clean() sanitises the WordPress import — shortcodes, editor attributes,
    # bold runs standing in for headings. Content written or edited in
    # publisher/ has already been through the equivalent and is stored clean,
    # so running it again is not a no-op: promote_pseudo_headings() is not
    # idempotent, and a second pass promotes bold runs the first pass left
    # alone. Re-cleaning would rewrite the article on every regeneration.
    if p.get("local") or p.get("edited"):
        body = p["content"]
    else:
        body = clean(p["content"], strip_tags(p["title"]))
    cats = p["categories"] or ["Materials Engineering"]
    desc = summarise(p).replace('"', "&quot;")

    og = """    <meta property="og:type" content="article">
    <meta property="og:title" content="{t}">
    <meta property="og:description" content="{d}">
    <meta property="article:published_time" content="{pub}">
{img}    <link rel="canonical" href="{canon}">
""".format(t=attr(p["title"]), d=desc, pub=p["date"],
           # Self-referential. This used to echo p["link"], the URL the
           # WordPress API reported, which pointed at a site now being retired —
           # so 19 of the 20 article pages were telling search engines that the
           # authoritative copy lived somewhere that will stop resolving.
           canon="%s/blog/%s.html" % (BASE_URL, p["slug"]),
           img=('    <meta property="og:image" content="%s">\n' % p["image"]) if p["image"] else "")

    html = head("%s | Flaney Associates" % strip_tags(p["title"]), desc, depth=1, extra=og)
    html += nav(1, solid=True) + "\n"

    hero_img = ""
    if p.get("local_image"):
        hero_img = """        <figure class="article-figure">
            <img src="images/{f}" alt="{alt}">
        </figure>
""".format(f=p["local_image"], alt=attr(p["image_alt"] or p["title"]))

    # Gated PDF, when the post has one. Posts authored in publisher/ carry a
    # `pdf` path; the imported WordPress archive does not.
    download_block = ""
    if p.get("pdf"):
        download_block = """
            <div class="article-download">
                <div class="article-download-text">
                    <h4>&#128196; Download this article as a PDF</h4>
                    <p>Take the full briefing with you — formatted for print, filing and sharing with your team.</p>
                </div>
                <button class="btn btn-primary gated-download" data-pdf="../{pdf}" data-title="{t}">&#11015; Get the PDF</button>
            </div>
""".format(pdf=p["pdf"], t=attr(p["title"]))

    if p.get("local"):
        source_block = ("""
            <div class="article-source">
                <p>Published by Flaney Associates on %s.</p>
            </div>
""" % fmt_date(p["date"]))
    else:
        source_block = ("""
            <div class="article-source">
                <p>Originally published on <a href="%s" target="_blank" rel="noopener">flaneyassociates.com</a> on %s.</p>
            </div>
""" % (p["link"], fmt_date(p["date"])))

    html += """
    <article class="article-page" data-publish="{publish}">
        <div class="container container-narrow">
            <a class="back-link" href="index.html">&larr; All articles</a>
            <div class="post-cats">{cats}</div>
            <h1>{title}</h1>
            <div class="article-meta">
                <span>{date}</span>
                <span aria-hidden="true">&middot;</span>
                <span>{mins} min read</span>
                <span aria-hidden="true">&middot;</span>
                <span>{author}</span>
            </div>
        </div>
{img}        <div class="container container-narrow">
            <div class="article-body">
{body}
            </div>
{download}{source}
            <div class="article-author">
                <div class="author-avatar" aria-hidden="true">JO</div>
                <div>
                    <h4>Joshua U. Otaigbe, PhD</h4>
                    <p>Materials engineering consultant specialising in polymers, composites and hybrid materials. Get in touch at <a href="mailto:info@flaneyassociates.com">info@flaneyassociates.com</a>.</p>
                </div>
            </div>
        </div>
    </article>
""".format(cats="".join('<span class="blog-category">%s</span>' % c for c in cats),
           title=p["title"], date=fmt_date(p["date"]), mins=read_time(p["words"]),
           author=p["author"] or "Flaney Associates", img=hero_img, body=body,
           publish=p["date"][:10], download=download_block, source=source_block)

    # related — same category first, then most recent, full-text only
    others = [q for q in posts if q["slug"] != p["slug"] and not q["gated"]]
    same = [q for q in others if set(q["categories"]) & set(p["categories"])]
    same_slugs = {q["slug"] for q in same}
    related = (same + [q for q in others if q["slug"] not in same_slugs])[:3]
    if related:
        html += """
    <section class="section related-section">
        <div class="container">
            <h2 class="related-heading">Related articles</h2>
            <div class="post-grid">
"""
        for q in related:
            html += card(q)
        html += """            </div>
        </div>
    </section>
"""

    html += """
    <section class="section cta-band">
        <div class="container">
            <h2>Need independent input on a materials problem?</h2>
            <p>Failure and root-cause analysis, materials selection, process optimization and expert-witness work — led by Joshua U. Otaigbe, PhD, CEng, FIMMM, Founder and Principal of Flaney Associates.</p>
            <a href="../contact.html" class="btn btn-primary btn-lg">Discuss Your Challenge</a>
        </div>
    </section>

"""
    html += footer(1) + "\n"
    html += download_modal() + "\n\n"
    html += scripts(1) + "</body>\n</html>\n"

    with open(os.path.join(BLOG, "%s.html" % p["slug"]), "w") as f:
        f.write(html)


BEGIN = "            <!-- BEGIN imported-blog (generated by generate_blog.py — do not edit by hand) -->"
END = "            <!-- END imported-blog -->"


# Posts kept off the homepage. The blog covers materials engineering, board
# governance and general-interest science, and all three belong in the archive
# — but the homepage has one job, which is to tell a visitor with an expensive
# materials problem that they are in the right place. A wellness article or a
# general boardroom-AI piece in that strip works against it.
#
# New posts are featured by default; this list names the exceptions. Keep it in
# step with HOMEPAGE_EXCLUDE in publisher/lib/template.js.
HOMEPAGE_EXCLUDE = {
    "unlocking-the-healing-power-of-cassava-leaves-simple-extraction-methods-for-everyday-wellness",
    "boardgpt-using-ai-in-the-boardroom",
    "empowering-smarter-corporate-boards-with-ai",
    "how-ai-is-transforming-scientific-research",
}


def featured(posts, n=6):
    """The posts that appear in the homepage strip, newest first."""
    return [p for p in posts
            if not p["gated"] and p["slug"] not in HOMEPAGE_EXCLUDE][:n]


def update_homepage(posts, n=6):
    """Inject the insights strip into index.html's #blog section.

    Re-running the generator replaces only the marked block, so this is safe to
    run repeatedly. The twelve sector briefings that used to sit below this
    strip now live on guides.html; the block no longer emits a heading for them.
    """
    path = os.path.join(ROOT, "index.html")
    page = open(path).read()

    latest = featured(posts, n)
    block = [BEGIN,
             '            <div class="blog-subhead">',
             '                <h3>Latest from the Flaney Associates blog</h3>',
             '                <a href="blog/index.html">View all %d articles &amp; publications &rarr;</a>'
             % len(posts),
             "            </div>",
             '            <div class="post-grid">']
    for p in latest:
        block.append(card(p, prefix="blog/").rstrip("\n"))
    block += ["            </div>", END]
    block = "\n".join(block) + "\n"

    if BEGIN in page:
        page = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n",
                      lambda _: block, page, flags=re.S)
        action = "replaced"
    else:
        anchor = '            <div class="blog-grid">'
        if anchor not in page:
            print("! index.html: could not find .blog-grid anchor — homepage not updated")
            return
        page = page.replace(anchor, block + anchor, 1)
        action = "inserted"

    # the imported cards rely on blog.css
    css = '<link rel="stylesheet" href="blog/blog.css?v=%s">' % asset_version("blog.css")
    if 'href="blog/blog.css' in page:
        page = re.sub(r'<link rel="stylesheet" href="blog/blog\.css[^"]*">', css, page)
    else:
        page = page.replace('<link rel="stylesheet" href="styles.css">',
                            '<link rel="stylesheet" href="styles.css">\n    ' + css, 1)

    # point the nav/footer "Blog" entries at the full archive
    page = page.replace('<li><a href="#blog">Blog</a></li>',
                        '<li><a href="blog/index.html">Blog</a></li>')

    open(path, "w").write(page)
    print("index.html               %s latest-posts strip (%d cards)" % (action, len(latest)))


def main():
    posts = json.load(open(DATA))
    posts.sort(key=lambda p: p["date"], reverse=True)
    os.makedirs(BLOG, exist_ok=True)

    build_index(posts)
    full = [p for p in posts if not p["gated"]]
    for p in full:
        build_post(p, posts)

    print("blog/index.html          %d posts listed" % len(posts))
    print("blog/<slug>.html         %d full-text article pages" % len(full))
    print("gated (abstract + link)  %d" % (len(posts) - len(full)))
    update_homepage(posts)
    stamp_assets.main()


if __name__ == "__main__":
    main()
