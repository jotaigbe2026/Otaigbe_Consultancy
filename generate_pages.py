#!/usr/bin/env python3
"""Render the static interior pages: services, about, industries, guides, the
checklist landing page and the two contact intakes.

Why a generator rather than fourteen hand-written files: every page carries the
same navbar and footer, and the navbar now has five dropdowns in it. Kept by
hand, one of them would be out of date within a month — which is exactly the
problem the site had before, where every service "Learn more" pointed at the
contact form because nothing else existed to point at.

    python3 generate_pages.py        # rewrite every page under PAGES

index.html is deliberately NOT generated here. It has a unique structure and it
carries the <!-- BEGIN imported-blog --> block that generate_blog.py rewrites;
two generators editing one file is a merge conflict waiting to happen.

Nav and footer markup therefore exists in four places — here, index.html,
generate_blog.py and publisher/lib/template.js. Changing one means changing all
four. See CLAUDE.md, "Site chrome lives in four places".
"""

import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))

SITE = "https://jotaigbe2026.github.io/Flaney_Associates"

# Two inboxes, deliberately. The general address is a shared mailbox and is what
# the site has always used; the principal's address is for the attorney conflict
# check, where the enquiry names opposing parties and should reach one person.
EMAIL_GENERAL = "info@flaneyassociates.com"
EMAIL_PRINCIPAL = "jotaigbe@flaneyassociates.com"
PHONE_GENERAL = "+1 (601) 402-7282"
PHONE_GENERAL_TEL = "+16014027282"
PHONE_PRINCIPAL = "+1 (601) 451-8452"
PHONE_PRINCIPAL_TEL = "+16014518452"
LINKEDIN = ("https://www.linkedin.com/in/"
            "joshua-otaigbe-ceng-fimmm-faeng-22751322")

# Two forms of the name, deliberately.
#
# An academic title answers "what is he"; a role title answers "what will he do
# for me". Manufacturers buy the second, and to a buyer deciding whether this
# practice can take their problem this quarter, "Professor ... Emeritus" reads
# as retired. So client-facing chrome — nav, footers, service pages, the
# homepage hero — leads with the role.
#
# Attorneys are the opposite case: under FRE 702 the qualifications are
# litigated, and academic rank is an admissibility asset. The full academic
# framing therefore stays on about.html and the expert-witness page, where the
# reader is looking for exactly that.
#
# The short postnominal set stops at three. Past that they read as insecurity
# rather than authority, and few buyers can decode CSci, FAEng or FSPE. CEng
# and FIMMM are the two that earn their place: CEng says licensed and
# accountable to a professional body rather than merely educated, and FIMMM is
# peer-elected and specific to materials.
PRINCIPAL = "Joshua U. Otaigbe"                  # client-facing
PRINCIPAL_ACADEMIC = "Professor Joshua U. Otaigbe"   # about + expert witness
ROLE = "Principal, Flaney Associates"
LETTERS = "PhD, CEng, FIMMM"                     # client-facing
LETTERS_FULL = "PhD, CEng, FIMMM, CSci, FAEng, FSPE"  # credentials in full

CHECKLIST_PDF = "articles/materials-failure-cost-checklist.pdf"
CHECKLIST_TITLE = ("The Executive&#8217;s 12-Question Materials Failure "
                   "&amp; Manufacturing Cost Checklist")


# ------------------------------------------------------------------ assets

def asset_version(name):
    """Content hash for cache busting — md5, matching asset_version() in
    generate_blog.py and stamp_assets.py so one file never carries two different
    version strings depending on which page loaded it.

    Without it a returning visitor gets new markup against a cached stylesheet,
    and the symptom — an unstyled dropdown — looks like a broken page rather
    than a stale file.
    """
    import hashlib
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        return "1"
    return hashlib.md5(open(path, "rb").read()).hexdigest()[:8]


# ------------------------------------------------------------------- chrome

def head(title, description, depth=0, canonical=""):
    up = "../" * depth
    canon = ('    <link rel="canonical" href="%s/%s">\n' % (SITE, canonical)
             if canonical else "")
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="{desc}">
    <meta property="og:type" content="website">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{desc}">
{canon}    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="{up}styles.css?v={cssv}">
    <link rel="stylesheet" href="{up}blog/blog.css?v={blogv}">
</head>
<body>
""".format(title=title, desc=description, up=up, canon=canon,
           cssv=asset_version("styles.css"),
           blogv=asset_version(os.path.join("blog", "blog.css")))


# How We Help. The order is the order a problem usually arrives in: something
# broke, then what do we use instead, then how do we build the next one.
SERVICE_NAV = [
    ("failure-analysis", "Failure &amp; Root-Cause Analysis",
     "Why it failed, and what is defensible"),
    ("materials-selection", "Materials Selection &amp; Qualification",
     "Choosing and validating a material"),
    ("product-development", "Product Development &amp; Materials Innovation",
     "Concept through production"),
    ("process-optimization", "Manufacturing Process Optimization",
     "Yield, quality, throughput"),
    ("technical-due-diligence", "Technical Due Diligence &amp; R&amp;D Strategy",
     "Technology and investment decisions"),
    ("expert-witness", "Expert Witness &amp; Litigation Support",
     "Product liability, IP, technical disputes"),
]

INDUSTRY_NAV = [
    ("polymers-plastics", "Polymers &amp; Plastics"),
    ("composites", "Composites"),
    ("manufacturing", "Manufacturing &amp; Processing"),
    ("consumer-products", "Consumer Products"),
    ("automotive", "Automotive &amp; Transportation"),
    ("energy", "Energy &amp; Oil/Gas"),
]


def nav(depth=0, active=""):
    """Site navbar.

    `active` is a page key ("services/failure-analysis", "about", ...) used to
    mark the current entry. Interior pages open on a light background, so the
    navbar is always solid here — the transparent treatment is for the
    homepage's dark hero only.
    """
    up = "../" * depth

    def mark(key):
        return ' class="active"' if active == key else ""

    services = "\n".join(
        '                        <li><a href="{up}services/{slug}.html"{m}>{name}'
        '<span class="dropdown-note">{note}</span></a></li>'.format(
            up=up, slug=slug, name=name, note=note, m=mark("services/" + slug))
        for slug, name, note in SERVICE_NAV)

    industries = "\n".join(
        '                        <li><a href="{up}industries.html#{anchor}">{name}</a></li>'.format(
            up=up, anchor=anchor, name=name)
        for anchor, name in INDUSTRY_NAV)

    return """    <nav class="navbar navbar-solid" id="navbar">
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
{services}
                    </ul>
                </li>
                <li class="has-dropdown">
                    <button type="button" class="nav-trigger">Industries</button>
                    <ul class="dropdown">
{industries}
                    </ul>
                </li>
                <li class="has-dropdown">
                    <button type="button" class="nav-trigger">Insights</button>
                    <ul class="dropdown">
                        <li><a href="{up}featured.html"{fm}>Featured This Month<span class="dropdown-note">One article, chosen monthly</span></a></li>
                        <li><a href="{up}blog/index.html">Blog<span class="dropdown-note">Articles on materials and manufacturing</span></a></li>
                        <li><a href="{up}guides.html"{gm}>Guides &amp; Briefings<span class="dropdown-note">Checklists and sector briefings</span></a></li>
                    </ul>
                </li>
                <li class="has-dropdown">
                    <button type="button" class="nav-trigger">About</button>
                    <ul class="dropdown">
                        <li><a href="{up}about.html"{am}>{principal}<span class="dropdown-note">Principal &middot; credentials and approach</span></a></li>
                        <li><a href="{up}about.html#credentials">Credentials</a></li>
                        <li><a href="{up}about.html#approach">Approach</a></li>
                        <li><a href="{up}about.html#faqs">FAQs</a></li>
                    </ul>
                </li>
                <li class="has-dropdown">
                    <button type="button" class="nav-trigger">Contact</button>
                    <ul class="dropdown">
                        <li><a href="{up}contact.html"{cm}>Discuss Your Challenge<span class="dropdown-note">Manufacturers and product teams</span></a></li>
                        <li><a href="{up}attorney-inquiry.html"{lm}>Attorney Conflict Check<span class="dropdown-note">Confidential, no case details</span></a></li>
                    </ul>
                </li>
                <li><a href="{up}contact.html" class="btn btn-nav">Discuss Your Challenge</a></li>
            </ul>
        </div>
    </nav>""".format(up=up, services=services, industries=industries,
                     principal=PRINCIPAL, gm=mark("guides"), am=mark("about"),
                     cm=mark("contact"), lm=mark("attorney"),
                     fm=mark("featured"))


def footer(depth=0):
    up = "../" * depth
    services = "\n".join(
        '                        <li><a href="{up}services/{slug}.html">{name}</a></li>'.format(
            up=up, slug=slug, name=name)
        for slug, name, _ in SERVICE_NAV)

    return """    <footer class="footer">
        <div class="container">
            <div class="footer-grid">
                <div class="footer-brand">
                    <a href="{up}index.html" class="logo">
                        <span class="logo-icon">&#9670;</span>
                        Flaney<span class="logo-accent">Associates</span>
                    </a>
                    <p>Independent materials-science and engineering expertise for manufacturers, product teams and attorneys. Led by {principal}, {letters} &mdash; {role}.</p>
                    <div class="footer-social">
                        <a href="{linkedin}" target="_blank" rel="noopener noreferrer" class="social-link" aria-label="LinkedIn">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
                        </a>
                        <a href="tel:{phonetel}" class="social-link" aria-label="Phone">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z"/></svg>
                        </a>
                    </div>
                </div>
                <div class="footer-links">
                    <h4>How We Help</h4>
                    <ul>
{services}
                    </ul>
                </div>
                <div class="footer-links">
                    <h4>Company</h4>
                    <ul>
                        <li><a href="{up}about.html">About {principal}</a></li>
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
                        <li><a href="mailto:{email}">{email}</a></li>
                        <li><a href="tel:{phonetel}">{phone}</a></li>
                    </ul>
                </div>
            </div>
            <div class="footer-bottom">
                <p>&copy; 2026 Flaney Associates, LLC. All rights reserved.</p>
            </div>
        </div>
    </footer>""".format(up=up, services=services, principal=PRINCIPAL,
                        letters=LETTERS, role=ROLE, linkedin=LINKEDIN,
                        email=EMAIL_GENERAL, phone=PHONE_GENERAL,
                        phonetel=PHONE_GENERAL_TEL)


def scripts(depth=0):
    """lead-capture.js first — nav.js and the pages rely on what it defines.

    Both carry a content hash for the same reason the stylesheets do: a cached
    lead-capture.js against new markup means the download gate quietly stops
    working, which reads as a broken button rather than a stale file.
    """
    up = "../" * depth
    return ('    <script src="%slead-capture.js?v=%s"></script>\n'
            '    <script src="%snav.js?v=%s"></script>\n'
            % (up, asset_version("lead-capture.js"),
               up, asset_version("nav.js")))


def download_modal():
    """Lead-capture modal for gated PDFs — identical to the one in index.html
    and the one generate_blog.py writes onto article pages. lead-capture.js
    wires up any .gated-download button on the page against it."""
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


def page_hero(title, lede, crumbs, depth=0, primary=None, secondary=None):
    """Compact solid hero for interior pages.

    `crumbs` is a list of (label, href-or-None); the last entry is the current
    page and is rendered without a link.
    """
    up = "../" * depth
    parts = []
    for i, (label, href) in enumerate(crumbs):
        if i:
            parts.append('<span aria-hidden="true">/</span>')
        if href:
            parts.append('<a href="%s%s">%s</a>' % (up, href, label))
        else:
            parts.append('<span>%s</span>' % label)
    trail = "\n                    ".join(parts)

    cta = ""
    if primary or secondary:
        buttons = []
        if primary:
            buttons.append('<a href="%s%s" class="btn btn-primary btn-lg">%s</a>'
                           % (up, primary[1], primary[0]))
        if secondary:
            buttons.append('<a href="%s%s" class="btn btn-outline btn-lg">%s</a>'
                           % (up, secondary[1], secondary[0]))
        cta = ('\n                <div class="page-hero-cta">\n                    '
               + "\n                    ".join(buttons)
               + '\n                </div>')

    return """    <header class="page-hero">
        <div class="container">
            <div class="page-hero-inner">
                <nav class="breadcrumb" aria-label="Breadcrumb">
                    {trail}
                </nav>
                <h1>{title}</h1>
                <p class="lede">{lede}</p>{cta}
            </div>
        </div>
    </header>""".format(trail=trail, title=title, lede=lede, cta=cta)


def closing_cta(depth=0):
    """The two-door close, repeated at the foot of every interior page."""
    up = "../" * depth
    return """    <section class="section section-alt">
        <div class="container">
            <div class="section-header">
                <span class="section-tag">Next Step</span>
                <h2>Get Clarity Before the Next Costly Decision</h2>
                <p class="section-subtitle">A short conversation is usually enough to tell whether independent technical review is worth it — and if it is not, you will be told so.</p>
            </div>
            <div class="audience-split">
                <div class="audience-card">
                    <span class="audience-tag">Manufacturers &amp; product teams</span>
                    <h3>Discuss Your Challenge</h3>
                    <p>Describe what is happening, what it is costing and what decision is waiting on it. You will get a direct assessment of whether and how this can be investigated.</p>
                    <a href="{up}contact.html" class="btn btn-primary btn-lg">Discuss Your Challenge</a>
                </div>
                <div class="audience-card">
                    <span class="audience-tag">Attorneys</span>
                    <h3>Request a Confidential Conflict Check</h3>
                    <p>Send the parties and the technical subject matter only — no case details, no documents. Conflicts are cleared before any substantive discussion takes place.</p>
                    <a href="{up}attorney-inquiry.html" class="btn btn-outline btn-lg">Request a Conflict Check</a>
                </div>
            </div>
        </div>
    </section>""".format(up=up)


def write(relpath, html):
    path = os.path.join(ROOT, relpath)
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    with open(path, "w") as fh:
        fh.write(html)
    print("  %-46s %6d bytes" % (relpath, len(html)))


# =========================================================================
# SERVICES
#
# Every claim below traces to something Flaney Associates can evidence: the
# principal's own record, the material systems and process areas the practice
# actually covers, or the working method. Nothing here asserts a client result,
# a project count or a named customer — see CLAUDE.md, "Proof discipline".
# =========================================================================

MATERIALS = ["Engineering plastics", "Polyurethanes", "Polyamides",
             "Biodegradable plastics", "Polyesters &amp; polycarbonates",
             "Styrenics", "Polyolefins", "Thermosetting plastics", "FRP/GRP",
             "Carbon &amp; aramid fibre composites", "Biomaterials",
             "Magnetic materials", "Nanomaterials &amp; nanocomposites",
             "Glasses &amp; ceramics"]

PROCESSES = ["Extrusion", "Injection moulding", "Compounding &amp; formulation",
             "Coatings &amp; films", "Adhesives", "Polymer reaction engineering",
             "Rheology", "Materials processing", "Materials testing",
             "Properties of materials"]


def tags(items):
    return ('<ul class="tag-list">\n'
            + "\n".join("                    <li>%s</li>" % i for i in items)
            + "\n                </ul>")


SERVICES = {}

SERVICES["failure-analysis"] = dict(
    name="Failure &amp; Root-Cause Analysis",
    short="Failure Analysis",
    title="Failure &amp; Root-Cause Analysis | Flaney Associates",
    meta=("Independent materials failure analysis for manufacturers and "
          "attorneys. Determine why a material, component or product failed "
          "and what corrective action is defensible."),
    lede=("Determine why a material, component or product failed &mdash; and "
          "what action is most defensible."),
    body="""
                <h2>When this comes up</h2>
                <p>Failure analysis is rarely commissioned out of curiosity. It is commissioned because something is already costing money and a decision is waiting on the answer.</p>
                <ul>
                    <li>Parts are cracking, warping, discolouring, embrittling or leaking in service.</li>
                    <li>Returns, warranty claims or a customer complaint are escalating.</li>
                    <li>A batch is out of specification and the cause is disputed between you and a supplier.</li>
                    <li>A material or supplier change was made and failures started afterwards.</li>
                    <li>An insurer, a customer or an attorney is asking for cause, and the answer needs to hold up.</li>
                </ul>

                <div class="callout">
                    <p><strong>Before anything else: preserve the evidence.</strong> Do not clean, cut, re-dry or re-process failed parts. Keep the failed items, unused retains of the same material lot, packaging and labels, process data and machine settings from the period in question, and any photographs taken as found.</p>
                    <p>More investigations are weakened by well-intentioned handling than by anything that happens in a laboratory. If the matter could become a dispute, that handling record becomes part of the evidence too.</p>
                </div>

                <h2>How the investigation runs</h2>
                <h3>1. Fix the decision the answer has to serve</h3>
                <p>&ldquo;Why did it fail&rdquo; has many true answers at different depths. Whether you need to release a held batch, defend a claim, requalify a supplier or redesign a part determines how deep the investigation has to go and what standard of proof it has to meet. That is settled first, because it decides the cost of everything after it.</p>

                <h3>2. Review the evidence and the process history</h3>
                <p>Failed parts, unfailed parts from the same run, material certificates, drying and moisture records, thermal and residence-time history, regrind practice, tooling and gate design, changes to the resin lot, the additive package or the supplier, and what was different about the period when failures began.</p>

                <h3>3. Form and rank the candidate mechanisms</h3>
                <p>Polymeric and composite parts fail through a limited set of mechanisms, and they leave different signatures: creep, fatigue, impact, molecular degradation, hydrolysis, oxidative or UV attack, environmental stress cracking, chemical attack, filler or fibre debonding, weld-line weakness, residual stress, moisture at the point of processing, and incompatibility introduced by a formulation change. Candidates are ranked before any test is ordered, so testing is used to discriminate between them rather than to produce a general survey.</p>

                <h3>4. Test only what discriminates</h3>
                <p>Analysis is commissioned through an established network of university and industry laboratory partners, with government national laboratories available through collaborators where a specialised resource is needed. Being independent of any one laboratory is deliberate: the instrument is chosen to answer the question, not because it is the one in the building.</p>

                <h3>5. Report what the evidence supports &mdash; and what it does not</h3>
                <p>Findings are separated from inference. You are told the mechanism, the contributing factors, the evidence behind each conclusion, the confidence attached to it, and what new evidence would change it. A conclusion presented without its limits is not usable in a dispute and is not much use in a plant either.</p>

                <h2>What you receive</h2>
                <ul>
                    <li>The failure mechanism and the contributing factors, ranked by the strength of the supporting evidence.</li>
                    <li>Whether the cause sits in the material, the process, the design, the service conditions, or a combination.</li>
                    <li>Corrective and preventive actions, in the order that removes the most risk for the least disruption.</li>
                    <li>An assessment of how the conclusion would stand up if the matter became a formal dispute.</li>
                    <li>Findings written to be read by executives and engineers, not only by specialists.</li>
                </ul>

                <div class="callout">
                    <p><strong>If litigation is possible, say so at the outset.</strong> Work commissioned as a plant investigation and later repurposed as evidence is weaker than work scoped for that purpose from the start. See <a href="expert-witness.html">Expert Witness &amp; Litigation Support</a>.</p>
                </div>

                <h2>Material systems covered</h2>
                """ + tags(MATERIALS) + """
""",
)

SERVICES["materials-selection"] = dict(
    name="Materials Selection &amp; Qualification",
    short="Materials Selection",
    title="Materials Selection &amp; Qualification | Flaney Associates",
    meta=("Independent materials selection and qualification. Select and "
          "validate materials for performance, manufacturability, cost and "
          "real service conditions."),
    lede=("Select and validate materials for performance, manufacturability, "
          "cost and real service conditions."),
    body="""
                <h2>When this comes up</h2>
                <ul>
                    <li>Purchasing has been offered an &ldquo;equivalent&rdquo; grade at a lower price.</li>
                    <li>A supplier is discontinuing a grade, or a resin has gone on allocation.</li>
                    <li>A cost-reduction target has landed on a part that is currently working.</li>
                    <li>A new application needs a material and the shortlist is being argued from datasheets.</li>
                    <li>A sustainability, regulatory or end-of-life requirement has changed what is acceptable.</li>
                </ul>

                <div class="callout">
                    <p><strong>Datasheet equivalence is not service equivalence.</strong> Two grades can match on tensile strength, melt flow index and density and still behave differently in your part &mdash; because the additive and filler package differs, because the molecular weight distribution differs, because one tolerates regrind and the other does not, or because the difference only appears after two years of thermal cycling in the field.</p>
                    <p>The failures that follow a substitution usually arrive months later, well after the saving has been booked and the decision has stopped being reviewed.</p>
                </div>

                <h2>How selection is done</h2>
                <h3>1. Establish the real service conditions</h3>
                <p>Not the nominal ones. Peak and sustained temperature, load type and duration, chemical and UV exposure, humidity, cycling, assembly stresses, cleaning regime, expected service life and what failure would actually cost. Most poor selections trace back to a requirement that was never written down.</p>

                <h3>2. Screen systematically, not by habit</h3>
                <p>Screening uses the Granta Design Cambridge Engineering Selector<sup>&reg;</sup> alongside four decades of experience across the material classes below. The database widens the field beyond what is familiar; the experience is what keeps the shortlist realistic about processing, supply and cost.</p>

                <h3>3. Shortlist against manufacturability, not just properties</h3>
                <p>A material that meets every performance requirement and cannot be moulded reliably in your tool, on your line, at your cycle time is not a candidate. Processing window, drying sensitivity, shrinkage and warpage behaviour, weld-line strength, regrind tolerance and colour stability are assessed alongside performance.</p>

                <h3>4. Qualify by targeted testing</h3>
                <p>Testing is specified to close the specific gaps between what is known and what the decision needs, using university and industry laboratory partners. The point is a decision you can defend, reached at the lowest cost that still supports it.</p>

                <h3>5. Document the rationale</h3>
                <p>A written selection record &mdash; what was considered, what was rejected and why &mdash; is what makes the decision reviewable later, and what protects it if the part is ever the subject of a claim.</p>

                <h2>What you receive</h2>
                <ul>
                    <li>A ranked shortlist with the reasoning behind each position, including the candidates that were rejected.</li>
                    <li>A qualification test plan scoped to the risk, not to a standard panel.</li>
                    <li>The specific risks attached to each candidate and what would retire them.</li>
                    <li>A documented selection rationale suitable for design review and for the record.</li>
                </ul>

                <h2>Material systems covered</h2>
                """ + tags(MATERIALS) + """
""",
)

SERVICES["product-development"] = dict(
    name="Product Development &amp; Materials Innovation",
    short="Product Development",
    title="Product Development &amp; Materials Innovation | Flaney Associates",
    meta=("Reduce materials risk in product development, from concept through "
          "scale-up and production, with senior independent materials-science "
          "expertise."),
    lede="Reduce development risk from concept through production.",
    body="""
                <h2>When this comes up</h2>
                <ul>
                    <li>A development programme is slipping, and the open questions are materials questions.</li>
                    <li>What works at bench or pilot scale is not reproducing in production.</li>
                    <li>The concept needs a material that does not exist off the shelf, or a formulation that has to be built.</li>
                    <li>A performance target is being pursued without agreement on whether it is physically reachable.</li>
                    <li>The programme needs a senior technical view without hiring a full in-house materials group.</li>
                </ul>

                <div class="callout">
                    <p>The commercial argument for outside expertise here is narrow and specific: it avoids having to hire a number of PhD scientists and engineers to obtain creativity and problem-solving capability that a programme needs intensively for a period and then does not need at that level again.</p>
                </div>

                <h2>Where the work concentrates</h2>
                <h3>Formulation and structure&ndash;property relationships</h3>
                <p>The through-line of this practice is the relationship between formulation, structure, processing, morphology, properties and performance &mdash; across all classes of materials. That chain is where development programmes usually stall, because a change made at one end produces an unexplained result at the other.</p>

                <h3>Scale-up</h3>
                <p>Bench-to-pilot-to-production transitions fail for reasons that are predictable in advance: shear and thermal history differ, residence-time distributions differ, mixing quality differs, and a formulation tuned to a laboratory process can be intolerant of the production one. Identifying which of those a given formulation is sensitive to, before the capital is committed, is usually the highest-value point in the programme.</p>

                <h3>Materials innovation</h3>
                <p>Where an off-the-shelf material will not reach the target, the route may be a blend, a hybrid, a nanocomposite, a modified surface or a reformulated system. Direct research experience across organic&ndash;inorganic hybrids, nanocomposites, biomaterials, magnetic materials and glass&ndash;polymer systems informs whether a proposed route is promising or a known dead end.</p>

                <h3>Intellectual property</h3>
                <p>Where development produces something protectable, support is available for patent applications and for positioning the work so that it can be protected &mdash; drawing on direct experience as a named inventor and on prior-art and patentability work. See <a href="expert-witness.html">Expert Witness &amp; Litigation Support</a>.</p>

                <h2>How a programme is supported</h2>
                <ul>
                    <li><strong>Technology and market opportunity assessment</strong> &mdash; is this route worth taking, and what does the literature and patent landscape already say about it.</li>
                    <li><strong>Ideation and concept shaping</strong> &mdash; turning a performance target into candidate material and process routes.</li>
                    <li><strong>Design, prototyping and testing</strong> &mdash; specified through university and industry laboratory partners.</li>
                    <li><strong>Production transition</strong> &mdash; identifying the process sensitivities that will decide whether it scales.</li>
                    <li><strong>Cross-functional technical project management</strong> &mdash; forming and running the team, including identifying university research groups and national laboratories that can be brought in cost-effectively.</li>
                </ul>

                <h2>Process areas covered</h2>
                """ + tags(PROCESSES) + """
""",
)

SERVICES["process-optimization"] = dict(
    name="Manufacturing Process Optimization",
    short="Process Optimization",
    title="Manufacturing Process Optimization | Flaney Associates",
    meta=("Improve yield, quality, throughput and process consistency in "
          "extrusion, injection moulding, compounding and coating operations."),
    lede="Improve yield, quality, throughput and process consistency.",
    body="""
                <h2>When this comes up</h2>
                <ul>
                    <li>Scrap has been climbing and no single change explains it.</li>
                    <li>Quality drifts across shifts, machines or lots that are nominally identical.</li>
                    <li>Cycle time is capped, and pushing it produces defects.</li>
                    <li>A new tool, line or material has never settled into a stable window.</li>
                    <li>The process worked until a material, supplier or regrind practice changed.</li>
                </ul>

                <div class="callout">
                    <p><strong>Rising scrap is a diagnostic, not just a cost.</strong> A scrap rate that climbs gradually while operators, tooling and settings stay the same is usually telling you that the process window has narrowed &mdash; and a window narrows when the material has changed, when moisture or thermal history has changed, or when the process was always running close to an edge that something has now pushed it over.</p>
                    <p>Treating that as an operator or a maintenance problem is the most common reason it persists for months.</p>
                </div>

                <h2>How the work runs</h2>
                <h3>1. Establish what is actually happening</h3>
                <p>Scrap by defect type rather than by total, sorted by machine, shift, tool, cavity and material lot. Most of the diagnosis is in that breakdown, and it is often the first time it has been assembled in one place.</p>

                <h3>2. Map the current window against the material</h3>
                <p>Drying and residence time, melt and mould temperatures, shear history, screw and barrel configuration, gate and runner design, regrind fraction and its thermal history, hold and cooling profiles &mdash; assessed against what the specific grade in use can tolerate, not against a generic processing guide.</p>

                <h3>3. Run designed trials, not sequential tweaks</h3>
                <p>Changing one parameter at a time on a running line is slow and interacts badly with the variation you are trying to explain. Trials are designed to separate the factors that matter from the ones that only appear to.</p>

                <h3>4. Confirm and document the window</h3>
                <p>A setting that fixes the problem is worth much less than a documented window with known edges, because the second one survives the next material lot, the next tool change and the next shift.</p>

                <h2>Where this typically applies</h2>
                <ul>
                    <li><strong>Extrusion</strong> &mdash; melt homogeneity, degradation, gauge variation, die and screw design effects.</li>
                    <li><strong>Injection moulding</strong> &mdash; warpage, sink, weld-line strength, short shots, dimensional drift, cavity-to-cavity variation.</li>
                    <li><strong>Compounding and formulation</strong> &mdash; dispersion quality, additive and filler distribution, batch-to-batch consistency.</li>
                    <li><strong>Coatings and films</strong> &mdash; adhesion, cure, barrier performance, surface defects.</li>
                    <li><strong>Rheology</strong> &mdash; understanding flow behaviour as the link between formulation and what the machine can do with it.</li>
                </ul>

                <h2>What you receive</h2>
                <ul>
                    <li>The factors driving the loss, distinguished from the ones that correlate with it.</li>
                    <li>A documented processing window with its edges identified.</li>
                    <li>Changes ranked by the yield or quality they recover against the disruption they cost.</li>
                    <li>Where the cause is the material rather than the process, a clear statement of that &mdash; and what to do about it.</li>
                </ul>

                <h2>Process areas covered</h2>
                """ + tags(PROCESSES) + """
""",
)

SERVICES["technical-due-diligence"] = dict(
    name="Technical Due Diligence &amp; R&amp;D Strategy",
    short="Technical Due Diligence",
    title="Technical Due Diligence &amp; R&amp;D Strategy | Flaney Associates",
    meta=("Independent technology assessment and R&D strategy. Make better "
          "technology, supplier and development-investment decisions with "
          "senior materials-science expertise."),
    lede=("Make better technology, supplier and development-investment "
          "decisions."),
    body="""
                <h2>When this comes up</h2>
                <ul>
                    <li>A technology, licence or acquisition is being evaluated and the technical claims need independent testing.</li>
                    <li>A supplier or start-up is presenting a breakthrough, and nobody in the room can assess it.</li>
                    <li>Two or three development paths are competing for the same budget.</li>
                    <li>A decision is pending on whether to build capability in-house, partner, or buy it.</li>
                    <li>The company is entering a materials area it has no history in.</li>
                </ul>

                <h2>Technology assessment</h2>
                <p>The scientific, patent and trade literature in any active materials area grows faster than a technical team with a day job can read it. A technology assessment does three things: identifies what actually matters in that volume of information, converts it into reliable and specific recommendations, and presents the findings in writing and in person to the people making the decision.</p>
                <p>These assessments are most valuable early &mdash; at the point of entry into a new technology area, when the output is still able to shape the strategy rather than justify one already chosen.</p>

                <h2>Diligence on a technical claim</h2>
                <ul>
                    <li>Is the underlying science sound, and is the claimed mechanism the one actually operating?</li>
                    <li>Does the prior art already cover it, and is the IP position defensible?</li>
                    <li>What has been demonstrated, at what scale, and what remains unproven between there and production?</li>
                    <li>What are the known failure modes of this class of material or process, and have they been addressed or simply not yet encountered?</li>
                    <li>What would it take to manufacture at volume, and who can currently supply it?</li>
                </ul>

                <h2>R&amp;D strategy</h2>
                <p>The strategic question is usually not which projects are interesting but which ones the organisation should be doing itself. Industries stay competitive by remaining focused on their own core competencies and strengths while still moving quickly on innovation &mdash; which means being deliberate about what is developed internally, what is partnered, and what is bought.</p>
                <p>One of the most valuable pieces of this is identifying university-based research groups, national government laboratories and other external resources that can be used to form productive, cost-efficient partnerships. Problems that sit at the boundaries between established disciplines &mdash; which is where most materials problems now sit &mdash; are frequently solved faster this way than by expanding an internal team.</p>

                <h2>What you receive</h2>
                <ul>
                    <li>A written assessment with the recommendation stated plainly and the reasoning behind it available.</li>
                    <li>A technology roadmap for the area under consideration.</li>
                    <li>The technical risks, separated into those that are resolvable and those that are inherent.</li>
                    <li>Where relevant, a shortlist of university, national-laboratory or industry partners and what each would contribute.</li>
                    <li>A briefing delivered to the decision-makers directly, in language that does not require a materials background.</li>
                </ul>
""",
)

SERVICES["expert-witness"] = dict(
    name="Expert Witness &amp; Litigation Support",
    short="Expert Witness",
    title="Expert Witness &amp; Litigation Support | Flaney Associates",
    meta=("Independent materials-science expert witness and litigation support "
          "for product liability, intellectual property and technical "
          "disputes. Confidential conflict checks."),
    lede=("Independent materials-science expertise for product liability, IP "
          "and technical disputes."),
    body="""
                <h2>Matters this covers</h2>
                <ul>
                    <li><strong>Product liability</strong> &mdash; whether a material, component or product failed, why, and whether the failure was foreseeable or preventable.</li>
                    <li><strong>Intellectual property</strong> &mdash; infringement and invalidity analysis, prior-art searching, patentability research, and support on initial filings, valuations and prosecution or defence before the U.S. Patent and Trademark Office.</li>
                    <li><strong>Manufacturing and supply disputes</strong> &mdash; specification conformance, materials substitution, process deviation and batch quality.</li>
                    <li><strong>Insurance and subrogation</strong> &mdash; independent determination of cause where a materials question sits at the centre of the loss.</li>
                </ul>

                <div class="callout">
                    <p><strong>Start with a conflict check.</strong> Send the party names and the technical subject matter only. Do not send case details, documents, samples or privileged material before an engagement agreement is in place.</p>
                    <p><a href="../attorney-inquiry.html">Request a confidential conflict check &rarr;</a></p>
                </div>

                <h2>What is provided</h2>
                <h3>Independent technical determination</h3>
                <p>The engagement is to reach the conclusion the evidence supports. An opinion that bends to the retaining party is worth nothing under cross-examination, and counsel is better served by knowing early where the technical weaknesses are than by discovering them in deposition.</p>

                <h3>Data acquisition, analysis, interpretation and presentation</h3>
                <p>Investigations run from inception through to litigation-related expert testimony. Where the product under evaluation cannot be assessed with standard equipment, custom test equipment can be acquired or built to suit it &mdash; which is often what produces the measurement that actually decides an infringement or a causation question.</p>

                <h3>Testing through independent laboratories</h3>
                <p>Analysis is commissioned through an established network of university and industry laboratory partners, with government national laboratories available through collaborators where a specialised resource is required. Not being tied to a single in-house laboratory means the method is chosen for the question rather than for the equipment already owned.</p>

                <h3>Explanation a jury can follow</h3>
                <p>Molecular degradation, environmental stress cracking and fibre debonding decide cases, and they have to be explained to people with no technical background without being distorted in the process. Four decades of teaching graduate and undergraduate engineering, and of presenting technical findings to boards and non-specialist audiences, is directly applicable here.</p>

                <h2>Credentials relevant to admissibility</h2>
                <ul>
                    <li>PhD in polymer science and engineering, University of Manchester (UMIST), England.</li>
                    <li>Professor Emeritus of Polymer Science &amp; Engineering, The University of Southern Mississippi; formerly professor of chemical engineering and of materials science and engineering, Iowa State University.</li>
                    <li>Registered Chartered Engineer (UK) and Registered Chartered Scientist (UK).</li>
                    <li>Fellow of the Institute of Materials, Minerals &amp; Mining (UK), the Society of Plastics Engineers, and the Nigerian Academy of Engineering.</li>
                    <li>Holder of seven patents; author of more than 150 publications in refereed archival scientific and engineering journals and books.</li>
                    <li>Senior industrial experience, including as Senior Project Leader and Engineer at Corning Incorporated.</li>
                </ul>
                <p>The full record, including awards and appointments, is set out on the <a href="../about.html#credentials">credentials page</a>.</p>

                <h2>Material systems and technical subject matter</h2>
                """ + tags(MATERIALS) + """
""",
)


# ------------------------------------------------------------ service pages

def service_aside(current):
    """Sticky rail: the call to action, then the other five services.

    Every service page links to every other one, which is the whole reason
    these pages exist — before them, each "Learn more" went to the contact
    form and a visitor with a slightly different problem had nowhere to go.
    """
    others = "\n".join(
        '                        <li><a href="{slug}.html"{cur}>{name}</a></li>'.format(
            slug=slug, name=name,
            cur=' aria-current="page"' if slug == current else "")
        for slug, name, _ in SERVICE_NAV)

    return """            <aside class="svc-aside">
                <div class="aside-card aside-dark">
                    <h3>Discuss Your Challenge</h3>
                    <p>Describe what is happening, what it is costing and what decision is waiting on it. You speak with the principal, not an account manager.</p>
                    <a href="../contact.html" class="btn btn-primary btn-full">Discuss Your Challenge</a>
                </div>
                <div class="aside-card">
                    <h3>How We Help</h3>
                    <ul class="aside-list">
{others}
                    </ul>
                </div>
                <div class="aside-card">
                    <h3>Not sure it needs an outside view?</h3>
                    <p>Twelve questions that separate a problem worth reviewing independently from one your own team should keep.</p>
                    <a href="../checklist.html" class="btn btn-outline btn-full">Get the Checklist</a>
                </div>
            </aside>""".format(others=others)


def build_service(slug):
    s = SERVICES[slug]
    html = head(s["title"], s["meta"], depth=1,
                canonical="services/%s.html" % slug)
    html += nav(depth=1, active="services/" + slug) + "\n"
    html += page_hero(s["name"], s["lede"],
                      [("Home", "index.html"), ("How We Help", None),
                       (s["short"], None)],
                      depth=1,
                      primary=("Discuss Your Challenge", "contact.html"),
                      secondary=("Get the Checklist", "checklist.html")) + "\n"
    html += """    <section class="section">
        <div class="container">
            <div class="svc-layout">
                <div class="prose">%s                </div>
%s
            </div>
        </div>
    </section>
""" % (s["body"], service_aside(slug))
    html += closing_cta(depth=1) + "\n"
    html += footer(depth=1) + "\n"
    html += scripts(depth=1)
    html += "</body>\n</html>\n"
    return html


# -------------------------------------------------------------- about page

CREDENTIALS = [
    ("U.S. National Science Foundation CAREER Award", "Awarded for early-career research and education excellence"),
    ("Jefferson Science Fellow", "U.S. National Academies of Sciences, Engineering, and Medicine"),
    ("Fellow, Institute of Materials, Minerals &amp; Mining", "United Kingdom"),
    ("Fellow, Society of Plastics Engineers", "SPE"),
    ("Fellow, Nigerian Academy of Engineering", "FAEng"),
    ("Tocqueville-Fulbright Distinguished Chair", "Professor in Engineering, University of Lyon, France, 2013&ndash;2014"),
    ("Registered Chartered Engineer (UK)", "CEng"),
    ("Registered Chartered Scientist (UK)", "CSci"),
    ("Cooper Distinguished Lectureship Award", "Glass and Optical Materials Division, American Ceramic Society"),
    ("Seven patents", "Including U.S. Patent 6,171,433, recognised by the Iowa State University College of Engineering, 2001"),
    ("150+ publications", "Refereed archival scientific and engineering journals and books"),
    ("Best Paper &mdash; Polyolefins", "Society of Plastics Engineers, ANTEC&rsquo;97"),
]

APPOINTMENTS = [
    "Visiting Professor (invited), Department of Materials, Institute for Polymers, Swiss Federal Institute of Technology (ETH Zurich), Switzerland",
    "Visiting Professor (invited), INSA de Lyon, Polymer Materials Engineering, LMM, UMR CNRS 5223, Lyon, France (sabbatical leave, 2009&ndash;2010)",
    "Visiting Professor (invited), Universit&eacute; Jean Monnet, Facult&eacute; de Sciences et Techniques, Rheology &amp; Polymer Materials Engineering, Saint-&Eacute;tienne, France",
    "Visiting professorship, University of Alberta, Canada",
    "Elected to the Board of Directors, Society of Plastics Engineers &mdash; Engineering Properties and Structure Division",
]

FAQS = [
    ("Who will actually do the work?",
     "<p>The principal. Flaney Associates is a principal-led practice: the person you speak with first is the person who reviews the evidence, specifies the testing and signs the findings. Laboratory analysis is commissioned through university and industry partners, and the choice of laboratory and method is made for the question at hand.</p>"),
    ("Do you have your own laboratory?",
     "<p>No, and that is deliberate. Testing is specified through an established network of university and industry laboratory partners, with government national laboratories available through collaborators where a specialised resource is required. Independence from any one facility means the method is selected to answer the question rather than to fill the instrument that is already owned.</p>"),
    ("What size of problem is worth bringing to you?",
     "<p>The useful test is not the size of the company but the cost of the decision. If a failure, a substitution, a scrap rate or a dispute carries enough financial or legal consequence that being wrong is expensive, it is worth an independent view. If it does not, you will be told that in the first conversation.</p>"),
    ("How do engagements usually start?",
     "<p>With a short conversation about what is happening, what it is costing and what decision is waiting on it. That is normally enough to establish whether independent technical review is warranted, what it would involve and roughly what it would take. A written scope follows before any work begins.</p>"),
    ("Can you work with our existing suppliers and laboratories?",
     "<p>Yes. Where you already have testing arrangements or a relationship with a resin supplier&rsquo;s technical service group, that work can be specified, reviewed and interpreted rather than duplicated.</p>"),
    ("We are an attorney&rsquo;s office. How should we make first contact?",
     "<p>Through the <a href=\"attorney-inquiry.html\">conflict check form</a>, with the party names and the technical subject matter only. Do not send case details, documents, samples or privileged material before an engagement agreement is in place.</p>"),
    ("Is the initial conversation confidential?",
     "<p>Enquiries are treated as confidential. That said, please do not send confidential samples, files or evidence before an engagement agreement is in place &mdash; for your protection as much as anything else, particularly where a matter may become contested.</p>"),
]


def build_about():
    creds = "\n".join(
        '                <div class="cred-card"><strong>%s</strong><span>%s</span></div>'
        % (title, note) for title, note in CREDENTIALS)
    appointments = "\n".join("                    <li>%s</li>" % a
                             for a in APPOINTMENTS)
    faqs = "\n".join(
        '                <details class="faq-item">\n'
        '                    <summary>%s</summary>\n'
        '                    %s\n'
        '                </details>' % (q, a) for q, a in FAQS)

    html = head("About %s, %s | Flaney Associates" % (PRINCIPAL, LETTERS_FULL),
                "Professor Joshua U. Otaigbe, PhD, CEng, FIMMM, CSci, FAEng, "
                "FSPE — Founder and Principal Partner of Flaney Associates, "
                "LLC, and Professor Emeritus of Polymer Science & Engineering.",
                depth=0, canonical="about.html")
    html += nav(active="about") + "\n"
    html += page_hero(
        PRINCIPAL,
        "Founder and Principal Partner of Flaney Associates, LLC. Professor "
        "Emeritus of Polymer Science &amp; Engineering. Forty years of "
        "materials science and engineering across industry and academia in "
        "North America, Europe and Africa.",
        [("Home", "index.html"), ("About", None)],
        primary=("Discuss Your Challenge", "contact.html")) + "\n"

    html += """    <section class="section">
        <div class="container">
            <div class="bio-layout">
                <div class="bio-card">
                    <div class="bio-mark">JO</div>
                    <h3>{principal}</h3>
                    <p class="bio-letters">{letters}</p>
                    <p class="bio-post">Founder &amp; Principal Partner, Flaney Associates, LLC<br>Professor Emeritus, The University of Southern Mississippi</p>
                    <ul>
                        <li>PhD, polymer science and engineering, University of Manchester (UMIST), England, 1984</li>
                        <li>Formerly Senior Project Leader and Engineer, Corning Incorporated</li>
                        <li>Registered Chartered Engineer and Chartered Scientist (UK)</li>
                        <li>7 patents &middot; 150+ refereed publications</li>
                    </ul>
                    <p style="margin-top:22px"><a href="{linkedin}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-full">View LinkedIn profile</a></p>
                </div>
                <div class="prose">
                    <h2>Biography</h2>
                    <p>I have had a professional career of more than forty years spanning the North American, European and African continents. I am the Founder and Principal Partner of Flaney Associates, LLC, a technical consulting company that provides value-added materials engineering solutions and innovations to industry, and I am Professor Emeritus of Polymer Science &amp; Engineering at The University of Southern Mississippi.</p>
                    <p>I specialise in polymer engineering and materials science, and I have held senior appointments in both industry and academia &mdash; including Senior Project Leader and Engineer at Corning Incorporated, and the Fulbright-Tocqueville Distinguished Chair Professor in Engineering in France for 2013&ndash;2014, an appointment reserved for international scholars with substantial experience and publications in their fields.</p>
                    <p>I earned my PhD in polymer science and engineering from the University of Manchester (UMIST) in England in 1984. I joined The University of Southern Mississippi in 2002 as a professor of polymer engineering and science, following a career at Iowa State University as professor of chemical engineering and of materials science and engineering. From 2003 to 2012 I held invited visiting professorships at the Swiss Federal Institute of Technology (ETH Zurich) and at the Institut National des Sciences Appliqu&eacute;es (INSA) in Lyon, France, among other universities.</p>
                    <p>I hold seven patents and have authored more than 150 publications in refereed archival scientific and engineering journals and books. I am a registered Chartered Engineer, and my work is directed at translating strategic, value-added materials ideas into practice.</p>

                    <h2 id="approach">Approach</h2>
                    <p>Large firms offer scale. This practice offers something different and narrower: direct, principal-level attention to the decision sitting behind the technical problem.</p>
                    <h3>Break down complex concepts</h3>
                    <p>Technical advice is only useful if the person who has to act on it can follow it. Findings are explained to the background and knowledge of the people receiving them &mdash; executives, engineers, or a court &mdash; without being diluted in the process.</p>
                    <h3>Understand the goal, not just the question</h3>
                    <p>Recommendations have to be financially and practically feasible with the resources you actually have. Understanding the objective and the constraints behind a request is what separates advice that gets implemented from advice that gets filed.</p>
                    <h3>Avoid miscommunication</h3>
                    <p>Technical advice communicated imprecisely leads to expensive decisions made on a misreading. Findings are stated with their limits attached, including what would change the conclusion.</p>
                    <h3>Independence</h3>
                    <p>No laboratory to keep busy, no product line to favour, no material to sell. Where the answer is that the problem does not need outside help, that is the answer you get.</p>

                    <h2 id="credentials">Credentials, awards and honours</h2>
                </div>
            </div>
        </div>
    </section>

    <section class="section section-alt">
        <div class="container">
            <div class="cred-grid">
{creds}
            </div>
        </div>
    </section>

    <section class="section">
        <div class="container">
            <div class="prose" style="max-width:820px">
                <h2>Academic appointments</h2>
                <ul>
{appointments}
                </ul>
                <h2 id="faqs">Frequently asked questions</h2>
            </div>
        </div>
    </section>

    <section class="section section-alt">
        <div class="container" style="max-width:860px">
{faqs}
        </div>
    </section>
""".format(principal=PRINCIPAL, letters=LETTERS_FULL, linkedin=LINKEDIN,
           creds=creds, appointments=appointments, faqs=faqs)

    html += closing_cta() + "\n"
    html += footer() + "\n"
    html += scripts()
    html += "</body>\n</html>\n"
    return html


# ------------------------------------------------- sector briefings (gated)
#
# Lifted verbatim out of index.html, where twelve of these sat below the blog
# strip and buried the homepage. They are downloads, so they belong on the
# guides page; the homepage now links to it instead. The "Read full article"
# link each card used to carry pointed at #contact — there was no article — and
# has been dropped rather than re-pointed.

BRIEFINGS = [
    dict(cat='Aerospace &amp; Defense',
         title='Next-Gen Composite Materials: How Carbon Fiber Thermoplastics Are Reshaping Aircraft Design',
         desc='The aerospace industry is undergoing a materials revolution. New carbon fiber-reinforced thermoplastic composites offer 20-40% weight savings over traditional aluminum structures while enabling faster manufacturing cycles. We explore how these advanced materials are meeting stringent FAA certification requirements and what it means for the future of lightweight aircraft components.',
         pdf='articles/aerospace-composite-materials.pdf', dtitle='Aerospace Composite Materials', read='6 min read'),
    dict(cat='Automotive',
         title='The Lightweighting Imperative: How EV Manufacturers Are Cutting Vehicle Mass by 15% With Multi-Material Strategies',
         desc='Electric vehicle range anxiety is driving a materials transformation. Automakers are adopting hybrid material approaches — combining high-strength steel, aluminum alloys, and engineering polymers — to shed hundreds of pounds per vehicle. We break down the most effective lightweighting strategies and the failure analysis pitfalls to avoid during material substitution.',
         pdf='articles/automotive-lightweighting-ev.pdf', dtitle='Automotive Lightweighting', read='7 min read'),
    dict(cat='Energy &amp; Oil/Gas',
         title='Corrosion-Resistant Alloys for Deepwater Pipelines: Selecting Materials That Survive 30+ Years Subsea',
         desc='Subsea pipeline failures cost the energy industry billions annually. Choosing the right corrosion-resistant alloys (CRAs) — from duplex stainless steels to nickel-based superalloys — is critical for long-term integrity. This article examines the latest advances in material selection for high-pressure, high-temperature deepwater environments and the testing protocols that ensure decades of reliable service.',
         pdf='articles/energy-corrosion-resistant-alloys.pdf', dtitle='Energy Corrosion-Resistant Alloys', read='8 min read'),
    dict(cat='Biomedical',
         title='Biocompatible Polymers for Implantable Devices: Navigating FDA Material Requirements in 2026',
         desc='The medical device industry demands materials that perform flawlessly inside the human body. From PEEK spinal implants to bioresorbable polymer scaffolds, material selection directly impacts patient safety and regulatory approval timelines. We walk through the latest ISO 10993 biocompatibility testing standards and share how smart material choices can accelerate your path to FDA clearance.',
         pdf='articles/biomedical-biocompatible-polymers.pdf', dtitle='Biomedical Biocompatible Polymers', read='7 min read'),
    dict(cat='Construction',
         title='Fiber-Reinforced Concrete: How Advanced Additives Are Extending Infrastructure Lifespan by Decades',
         desc='Aging infrastructure is a trillion-dollar global challenge. Fiber-reinforced concrete and self-healing cementitious materials are emerging as game-changers — reducing crack propagation by up to 90% and dramatically extending service life. We explore the materials science behind these innovations and their real-world impact on bridges, tunnels, and commercial structures.',
         pdf='articles/construction-fiber-reinforced-concrete.pdf', dtitle='Construction Fiber-Reinforced Concrete', read='5 min read'),
    dict(cat='Consumer Products',
         title='Sustainable Packaging Materials: Moving Beyond Single-Use Plastics Without Sacrificing Performance',
         desc='Consumer brands are under mounting pressure to eliminate single-use plastics, but finding alternatives that match conventional materials in barrier properties, shelf life, and cost is no easy feat. We examine the latest bio-based polymers, compostable films, and recycled-content solutions that are making sustainable packaging commercially viable — and how to test them rigorously before launch.',
         pdf='articles/consumer-sustainable-packaging.pdf', dtitle='Consumer Sustainable Packaging', read='6 min read'),
    dict(cat='Aerospace &amp; Defense',
         title='Metal 3D Printing in Aerospace: How Additive Manufacturing Is Reinventing Aircraft Components',
         desc='From jet engine brackets to satellite structures, metal additive manufacturing enables topology-optimized designs, part consolidation, and internal cooling channels that are impossible to machine. We explore the alloys, processes, and certification pathways driving this shift across the aerospace industry.',
         pdf='articles/aerospace-additive-manufacturing.pdf', dtitle='Aerospace Additive Manufacturing', read='7 min read'),
    dict(cat='Automotive',
         title='Engineering Polymers in EV Battery Systems: Materials That Keep Your Battery Safe and Efficient',
         desc='The battery pack in a modern EV is a sophisticated materials system — thermal interface pads, composite enclosures, flame-retardant cell holders, and runaway barriers all play critical roles. We break down the polymer science keeping high-voltage packs safe, efficient, and durable for the life of the vehicle.',
         pdf='articles/automotive-ev-battery-materials.pdf', dtitle='EV Battery Materials', read='7 min read'),
    dict(cat='Energy',
         title='Materials for the Energy Transition: What Wind Turbines and Solar Panels Are Really Made Of',
         desc='Behind every megawatt of clean energy is a story of demanding materials engineering. Wind blade composites fighting leading-edge erosion, solar encapsulants stabilizing over 30 years of UV exposure — we examine the materials science powering the renewable revolution and the challenges that still need solving.',
         pdf='articles/energy-renewable-materials.pdf', dtitle='Renewable Energy Materials', read='8 min read'),
    dict(cat='Biomedical',
         title='3D-Printed Implants: How Additive Manufacturing Is Personalizing Orthopedic Medicine',
         desc='Patient-specific titanium implants printed from CT scan data are already being used in thousands of surgeries annually. We explain the materials science of osseointegration through engineered porosity, the regulatory pathway for printed implants, and what the next frontier of bioprinting means for orthopedic medicine.',
         pdf='articles/biomedical-3d-printed-implants.pdf', dtitle='3D-Printed Implants', read='6 min read'),
    dict(cat='Construction',
         title='Smart Coatings for Infrastructure Protection: How Nanotechnology Is Defeating Corrosion',
         desc='Corrosion costs the global economy $2.5 trillion annually. A new generation of smart coatings — with microencapsulated inhibitors, nanoparticle barrier enhancement, and pH-responsive release systems — is fighting back. We explore how these materials are extending bridge and infrastructure coating life by 30 to 50 percent.',
         pdf='articles/construction-smart-coatings.pdf', dtitle='Smart Coatings for Infrastructure', read='6 min read'),
    dict(cat='Consumer Products',
         title='Engineering Plastics vs. Metals: The Smart Material Substitution Strategy Reshaping Product Design',
         desc='Modern consumer products increasingly use high-performance polymers where metal was once the default — but metal-to-plastic substitution has hidden pitfalls. We cover the key engineering plastics, where they outperform metals, and the creep, weld-line, and stress-cracking traps that catch designers off guard.',
         pdf='articles/consumer-engineering-plastics.pdf', dtitle='Engineering Plastics vs Metals', read='6 min read'),
]


# --------------------------------------------------------- industries page
#
# Six sectors, each one traceable to the industrial application areas the
# practice actually lists. Sectors with no supporting evidence behind them are
# not here — the old homepage claimed six industries with a one-line boast
# apiece and nothing underneath.

INDUSTRIES = [
    dict(anchor="polymers-plastics", icon="&#9883;", name="Polymers &amp; Plastics",
         lede="The core discipline of the practice: a PhD and forty years in polymer science and engineering, and the material class behind most of the failures, substitutions and process problems that arrive here.",
         points=[
             "Engineering plastics, polyolefins, polyamides, polyesters and polycarbonates, styrenics, polyurethanes and thermosets.",
             "Degradation and ageing &mdash; hydrolysis, oxidation, UV attack, environmental stress cracking.",
             "Formulation and additive-package effects on performance and processability.",
             "Biodegradable and bio-derived plastics, and the end-of-life questions that come with them.",
         ]),
    dict(anchor="composites", icon="&#129704;", name="Composites",
         lede="Fibre-reinforced and hybrid systems, where performance depends as much on the interface and the process as on the constituents.",
         points=[
             "Carbon and aramid fibre composites, FRP and GRP.",
             "Nanocomposites and organic&ndash;inorganic hybrid systems &mdash; a direct research specialism.",
             "Fibre&ndash;matrix debonding, delamination and interface failure.",
             "Cellulose-nanocrystal and other bio-derived reinforcement systems.",
         ]),
    dict(anchor="manufacturing", icon="&#9881;", name="Manufacturing &amp; Processing",
         lede="Where a material meets a machine. Most quality and scrap problems are decided here rather than in the specification.",
         points=[
             "Extrusion and injection moulding &mdash; window definition, defects, dimensional stability.",
             "Compounding and formulation &mdash; dispersion, distribution, batch consistency.",
             "Coatings and films &mdash; adhesion, cure, barrier performance.",
             "Rheology and polymer reaction engineering as the link between formulation and processability.",
         ]),
    dict(anchor="consumer-products", icon="&#128230;", name="Consumer Products",
         lede="High-volume plastic products, packaging and consumer goods, where a small per-part materials decision multiplies into a large commercial one.",
         points=[
             "Consumer plastic products and consumer materials science and engineering.",
             "Packaging materials, barrier performance and sustainable alternatives.",
             "Paints, thin films and surface finish durability.",
             "Sports and recreation products; computers and wearable electronics housings.",
         ]),
    dict(anchor="automotive", icon="&#128663;", name="Automotive &amp; Transportation",
         lede="Materials substitution and lightweighting decisions with warranty exposure attached, plus the aerospace-grade requirements that increasingly follow them.",
         points=[
             "Metal-to-polymer and metal-to-composite substitution and its failure modes.",
             "Under-bonnet and battery-system polymers &mdash; thermal, chemical and electrical service conditions.",
             "Aircraft and aerospace structures and components.",
             "Durability, creep and fatigue over a design life measured in years, not test cycles.",
         ]),
    dict(anchor="energy", icon="&#9889;", name="Energy &amp; Oil/Gas",
         lede="Long-service-life assets in aggressive environments, where a materials failure is rarely cheap and frequently contested.",
         points=[
             "Chemicals and petrochemicals; oil and gas service environments.",
             "Petroleum underground storage tanks (USTs) and flexible piping &mdash; a specific area of experience.",
             "Protective and corrosion-resistant coatings.",
             "Materials for renewable-energy systems and the sustainability constraints attached to them.",
         ]),
]


def build_industries():
    blocks = []
    for ind in INDUSTRIES:
        fields = dict(ind)
        fields["points"] = "\n".join(
            "                        <li>%s</li>" % p for p in ind["points"])
        blocks.append("""            <div class="prose" id="{anchor}" style="max-width:820px;margin-bottom:64px">
                <h2><span aria-hidden="true">{icon}</span> {name}</h2>
                <p>{lede}</p>
                <ul>
{points}
                </ul>
            </div>""".format(**fields))

    html = head("Industries | Flaney Associates",
                "Materials-science and engineering expertise across polymers "
                "and plastics, composites, manufacturing, consumer products, "
                "automotive and transportation, and energy and oil/gas.",
                canonical="industries.html")
    html += nav(active="industries") + "\n"
    html += page_hero(
        "Industries",
        "Sectors where this practice can point to real experience &mdash; in "
        "the material systems, the process areas and the failure modes that "
        "define them. Listed here only where that is true.",
        [("Home", "index.html"), ("Industries", None)],
        primary=("Discuss Your Challenge", "contact.html")) + "\n"
    html += """    <section class="section">
        <div class="container">
%s
        </div>
    </section>

    <section class="section section-alt">
        <div class="container">
            <div class="section-header">
                <span class="section-tag">Coverage</span>
                <h2>Material Systems and Process Areas</h2>
                <p class="section-subtitle">The classes of material and the processes this practice works in directly.</p>
            </div>
            <div class="prose" style="max-width:900px;margin:0 auto">
                <h3>Material systems</h3>
                %s
                <h3>Process areas</h3>
                %s
            </div>
        </div>
    </section>
""" % ("\n".join(blocks), tags(MATERIALS), tags(PROCESSES))
    html += closing_cta() + "\n"
    html += footer() + "\n"
    html += scripts()
    html += "</body>\n</html>\n"
    return html


# -------------------------------------------------------------- guides page

def build_guides():
    cards = []
    for b in BRIEFINGS:
        cards.append("""                <article class="blog-card">
                    <div class="blog-category">{cat}</div>
                    <h3>{title}</h3>
                    <p>{desc}</p>
                    <div class="blog-meta">
                        <span class="blog-read">{read}</span>
                    </div>
                    <div class="blog-actions">
                        <button class="btn-download gated-download" data-pdf="{pdf}" data-title="{dtitle}">&#11015; Download PDF</button>
                    </div>
                </article>""".format(**b))

    html = head("Guides &amp; Briefings | Flaney Associates",
                "Downloadable guides and sector briefings on materials "
                "selection, failure, processing and manufacturing decisions.",
                canonical="guides.html")
    html += nav(active="guides") + "\n"
    html += page_hero(
        "Guides &amp; Briefings",
        "Written for the people who have to make the decision, not for the "
        "people who run the tests.",
        [("Home", "index.html"), ("Insights", None), ("Guides &amp; Briefings", None)],
        primary=("Get the Checklist", "checklist.html"),
        secondary=("Read the blog", "blog/index.html")) + "\n"

    html += """    <section class="section">
        <div class="container">
            <!-- Featured article of the month. Filled in by featured.js from
                 content/featured/featured.json, which .github/workflows/featured.yml
                 rewrites on the 1st. Ships hidden; revealed only once loaded. -->
            <div class="featured-band" id="featuredBand" data-src="content/featured/featured.json" hidden>
                <div>
                    <a class="featured-tag" href="featured.html">Featured this month &middot; <span data-field="month"></span> &rarr;</a>
                    <h3><a data-field="link" href="blog/index.html"><span data-field="title"></span></a></h3>
                    <p class="featured-excerpt" data-field="excerpt"></p>
                    <p class="featured-why" data-field="summary"></p>
                </div>
                <div>
                    <a class="btn btn-primary btn-full" data-field="link" href="blog/index.html">Read the article</a>
                </div>
            </div>
            <div class="magnet">
                <div>
                    <span class="audience-tag" style="color:var(--accent)">Featured guide</span>
                    <h2>{ctitle}</h2>
                    <p>Twelve questions that separate a product failure, quality problem, material change or process issue that needs independent technical review from one your own team should keep.</p>
                    <ul>
                        <li>What the problem is actually costing, in terms your finance team recognises</li>
                        <li>Which evidence has to be preserved before anyone touches a failed part</li>
                        <li>When a materials question has become a legal exposure</li>
                    </ul>
                </div>
                <div>
                    <a href="{up}checklist.html" class="btn btn-primary btn-lg btn-full">Send Me the Checklist</a>
                </div>
            </div>
        </div>
    </section>

    <section class="section section-alt">
        <div class="container">
            <div class="section-header">
                <span class="section-tag">Sector briefings</span>
                <h2>Twelve Briefings by Sector</h2>
                <p class="section-subtitle">Short technical briefings on materials decisions in aerospace, automotive, energy, biomedical, construction and consumer products. Each downloads as a PDF.</p>
            </div>
            <div class="blog-grid">
{cards}
            </div>
        </div>
    </section>

    <section class="section">
        <div class="container">
            <div class="section-header">
                <span class="section-tag">Blog</span>
                <h2>Articles on Materials and Manufacturing</h2>
                <p class="section-subtitle">The full archive of articles and publications, including members-only papers hosted on flaneyassociates.com.</p>
            </div>
            <div style="text-align:center">
                <a href="{up}blog/index.html" class="btn btn-primary btn-lg">Browse the blog</a>
            </div>
        </div>
    </section>
""".format(cards="\n".join(cards), ctitle=CHECKLIST_TITLE, up="")

    html += closing_cta() + "\n"
    html += footer() + "\n"
    html += download_modal() + "\n"
    html += scripts()
    html += ('    <script src="featured.js?v=%s"></script>\n'
             % asset_version("featured.js"))
    html += "</body>\n</html>\n"
    return html


def form_scripts(depth=0):
    """Pages carrying an enquiry form also load script.js, which wires it up.

    hideScheduledCards() runs from there too and is a no-op on a page with no
    post cards, so there is nothing to guard against.
    """
    up = "../" * depth
    return scripts(depth) + ('    <script src="%sscript.js?v=%s"></script>\n'
                             % (up, asset_version("script.js")))


# ----------------------------------------------------------- checklist page

CHECKLIST_POINTS = [
    ("What is this actually costing?",
     "Scrap, rework, returns, warranty reserve, expedited freight, held inventory and the engineering hours already spent. Most problems are escalated on the visible number and turn out to be several times larger."),
    ("Has the evidence been preserved?",
     "Failed parts left as found, retains from the same material lot, process data from the period, and photographs. Almost nothing else in an investigation is recoverable once this is lost."),
    ("Did anything change before it started?",
     "Resin lot, supplier, additive package, regrind practice, tooling, drying, an operator, a shift pattern, a season. The date the problem started is usually the most informative fact available."),
    ("Is this one failure mode or several?",
     "A single mechanism and three unrelated ones look identical on a scrap report and need completely different responses."),
    ("Could this become a legal matter?",
     "If there is any prospect of a product-liability, IP or supply dispute, the investigation should be scoped for that from the start &mdash; work repurposed as evidence later is weaker."),
]


def build_checklist():
    points = "\n".join(
        """                <div class="problem-card">
                    <h4>{q}</h4>
                    <p>{a}</p>
                </div>""".format(q=q, a=a) for q, a in CHECKLIST_POINTS)

    html = head("The Executive&#8217;s Materials Failure &amp; Manufacturing Cost Checklist | Flaney Associates",
                "A 12-question checklist for deciding whether a product "
                "failure, quality problem, material change or process issue "
                "requires independent technical review.",
                canonical="checklist.html")
    html += nav(active="checklist") + "\n"
    html += page_hero(
        CHECKLIST_TITLE,
        "A short guide for deciding whether a product failure, quality "
        "problem, material change or process issue requires independent "
        "technical review &mdash; or whether your own team should keep it.",
        [("Home", "index.html"), ("Insights", None), ("Guides &amp; Briefings", "guides.html"),
         ("Checklist", None)]) + "\n"

    html += """    <section class="section">
        <div class="container">
            <div class="svc-layout">
                <div class="prose">
                    <h2>Who this is for</h2>
                    <p>Operations directors, engineering and quality leaders, and general managers who have a materials or manufacturing problem in front of them and have to decide what to do about it &mdash; usually without a materials specialist in the building.</p>
                    <p>It is not a sales document. Several of the twelve questions are designed to establish that a problem does <em>not</em> need outside help, which is the correct answer more often than a consultancy&rsquo;s website normally admits.</p>

                    <h2>What is inside</h2>
                    <p>Twelve questions in four groups &mdash; cost, evidence, cause and exposure &mdash; each with a short note on what the answer tells you and what to do next. Five of them, in outline:</p>
                </div>
                <aside class="svc-aside">
                    <div class="aside-card aside-dark">
                        <h3>Send me the checklist</h3>
                        <p>Enter your details and the PDF downloads immediately. No follow-up call unless you ask for one.</p>
                        <button class="btn btn-primary btn-full gated-download" data-pdf="{pdf}" data-title="Materials Failure &amp; Manufacturing Cost Checklist" data-modal-heading="Send Me the Checklist" data-modal-subtitle="Enter your details and the checklist downloads immediately. No follow-up call unless you ask for one." data-modal-submit="&amp;#11015; Send Me the Checklist">&#11015; Send Me the Checklist</button>
                    </div>
                    <div class="aside-card">
                        <h3>Already know what you need?</h3>
                        <p>Skip the guide and describe the problem directly.</p>
                        <a href="contact.html" class="btn btn-outline btn-full">Discuss Your Challenge</a>
                    </div>
                </aside>
            </div>
        </div>
    </section>

    <section class="section section-alt">
        <div class="container">
            <div class="problem-grid">
{points}
            </div>
            <div style="text-align:center;margin-top:44px">
                <button class="btn btn-primary btn-lg gated-download" data-pdf="{pdf}" data-title="Materials Failure &amp; Manufacturing Cost Checklist" data-modal-heading="Send Me the Checklist" data-modal-subtitle="Enter your details and the checklist downloads immediately. No follow-up call unless you ask for one." data-modal-submit="&amp;#11015; Send Me the Checklist">&#11015; Send Me the Checklist</button>
            </div>
        </div>
    </section>
""".format(points=points, pdf=CHECKLIST_PDF)

    html += closing_cta() + "\n"
    html += footer() + "\n"
    html += download_modal() + "\n"
    html += scripts()
    html += "</body>\n</html>\n"
    return html


# ------------------------------------------------------------ contact pages

CONFIDENTIALITY = ('                        <div class="intake-note">\n'
                   '                            <strong>Please do not send confidential samples, files or evidence '
                   'before an engagement agreement is in place.</strong> A short description of the problem is all '
                   'that is needed to start.\n'
                   '                        </div>')


def build_contact():
    html = head("Discuss Your Challenge | Flaney Associates",
                "Describe your materials, product-performance or "
                "manufacturing problem and get a direct assessment from the "
                "principal. Attorneys should use the conflict-check form.",
                canonical="contact.html")
    html += nav(active="contact") + "\n"
    html += page_hero(
        "Discuss Your Challenge",
        "Tell us what is happening, what it is costing and what decision is "
        "waiting on it. You will get a direct answer on whether independent "
        "technical review is warranted &mdash; including when it is not.",
        [("Home", "index.html"), ("Contact", None), ("Discuss Your Challenge", None)]) + "\n"

    html += """    <section class="section">
        <div class="container">
            <div class="cta-layout">
                <div class="cta-content">
                    <h2>What happens next</h2>
                    <ul class="why-list" style="margin-top:24px">
                        <li><strong>You hear back within one business day.</strong> From the principal, not from a scheduler.</li>
                        <li><strong>A short conversation, around twenty minutes.</strong> Enough to establish what the problem is and whether it needs an outside view.</li>
                        <li><strong>A written scope before any work starts.</strong> What would be investigated, how, and what it would take.</li>
                        <li><strong>An honest answer if the answer is no.</strong> Some problems belong with your own team or your resin supplier&rsquo;s technical service group, and you will be told so.</li>
                    </ul>
                    <div class="prose" style="margin-top:36px">
                        <h3>Direct contact</h3>
                        <p><a href="mailto:{email}">{email}</a><br>
                        <a href="tel:{phonetel}">{phone}</a></p>
                        <h3>Attorneys</h3>
                        <p>Please use the <a href="attorney-inquiry.html">confidential conflict-check form</a> rather than this one, and send party names and technical subject matter only.</p>
                    </div>
                </div>
                <div class="cta-form-wrapper">
                    <form class="contact-form" id="contactForm" data-inbox="general" data-subject="New Enquiry — Flaney Associates" action="https://formsubmit.co/{email}" method="POST">
                        <input type="hidden" name="_subject" value="New Enquiry — Flaney Associates">
                        <input type="hidden" name="_captcha" value="false">
                        <input type="hidden" name="_template" value="table">
                        <input type="hidden" name="_next" value="">
                        <input type="text" name="_honey" style="display:none">
                        <h3>Describe your challenge</h3>
{note}
                        <div class="form-row">
                            <div class="form-group">
                                <input type="text" name="name" placeholder="Your name" required>
                            </div>
                            <div class="form-group">
                                <input type="text" name="role" placeholder="Your role">
                            </div>
                        </div>
                        <div class="form-group">
                            <input type="email" name="email" id="contactEmail" placeholder="Work email" required>
                            <span class="email-feedback" id="contactEmailFeedback"></span>
                        </div>
                        <div class="form-group">
                            <input type="text" name="company" placeholder="Company">
                        </div>
                        <div class="form-group">
                            <select name="service" required>
                                <option value="" disabled selected>Which area is closest?</option>
                                <option value="failure-analysis">Failure &amp; root-cause analysis</option>
                                <option value="materials-selection">Materials selection &amp; qualification</option>
                                <option value="product-development">Product development &amp; materials innovation</option>
                                <option value="process-optimization">Manufacturing process optimization</option>
                                <option value="technical-due-diligence">Technical due diligence &amp; R&amp;D strategy</option>
                                <option value="expert-witness">Expert witness &amp; litigation support</option>
                                <option value="other">Not sure yet</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <textarea name="message" rows="4" placeholder="Briefly: what is happening, roughly what it is costing, and what decision is waiting on it." required></textarea>
                        </div>
                        <button type="submit" class="btn btn-primary btn-lg btn-full">Send Enquiry</button>
                        <p class="form-note">Response within one business day. Your details are not shared or sold.</p>
                    </form>
                </div>
            </div>
        </div>
    </section>
""".format(email=EMAIL_GENERAL, phone=PHONE_GENERAL,
           phonetel=PHONE_GENERAL_TEL, note=CONFIDENTIALITY)

    html += footer() + "\n"
    html += form_scripts()
    html += "</body>\n</html>\n"
    return html


def build_attorney():
    html = head("Attorney Conflict Check | Flaney Associates",
                "Request a confidential conflict check for materials-science "
                "expert witness and litigation support. Party names and "
                "technical subject matter only.",
                canonical="attorney-inquiry.html")
    html += nav(active="attorney") + "\n"
    html += page_hero(
        "Request a Confidential Conflict Check",
        "Send the parties and the technical subject matter only. Conflicts "
        "are cleared before any substantive discussion of the matter takes "
        "place.",
        [("Home", "index.html"), ("Contact", None), ("Attorney Conflict Check", None)]) + "\n"

    html += """    <section class="section">
        <div class="container">
            <div class="cta-layout">
                <div class="cta-content">
                    <h2>Before you write</h2>
                    <ul class="why-list" style="margin-top:24px">
                        <li><strong>Party names and technical subject only.</strong> No case details, no theory of the case, no documents, no samples, no privileged or work-product material.</li>
                        <li><strong>The check itself is quick.</strong> You will normally hear back within one business day on whether a conflict exists.</li>
                        <li><strong>Substantive discussion follows clearance.</strong> Only once conflicts are cleared and an engagement agreement is in place.</li>
                        <li><strong>The opinion follows the evidence.</strong> If the technical picture does not support the position, you will be told before it costs anything.</li>
                    </ul>
                    <div class="prose" style="margin-top:36px">
                        <h3>Direct contact</h3>
                        <p>This route reaches the principal directly rather than a shared mailbox.</p>
                        <p><a href="mailto:{pemail}">{pemail}</a><br>
                        <a href="tel:{ptel}">{pphone}</a></p>
                        <h3>Scope of expert work</h3>
                        <p>Product liability, IP infringement and invalidity, manufacturing and supply disputes, and insurance or subrogation matters. See <a href="services/expert-witness.html">Expert Witness &amp; Litigation Support</a>.</p>
                    </div>
                </div>
                <div class="cta-form-wrapper">
                    <form class="contact-form" id="contactForm" data-inbox="principal" data-subject="Attorney Conflict Check — Flaney Associates" action="https://formsubmit.co/{pemail}" method="POST">
                        <input type="hidden" name="_subject" value="Attorney Conflict Check — Flaney Associates">
                        <input type="hidden" name="_captcha" value="false">
                        <input type="hidden" name="_template" value="table">
                        <input type="hidden" name="_next" value="">
                        <input type="text" name="_honey" style="display:none">
                        <h3>Conflict check request</h3>
                        <div class="intake-note">
                            <strong>Do not include case details, documents, samples or privileged material.</strong> Party names and the technical subject matter are all that is needed to run the check.
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <input type="text" name="name" placeholder="Your name" required>
                            </div>
                            <div class="form-group">
                                <input type="text" name="role" placeholder="Your role">
                            </div>
                        </div>
                        <div class="form-group">
                            <input type="email" name="email" id="contactEmail" placeholder="Work email" required>
                            <span class="email-feedback" id="contactEmailFeedback"></span>
                        </div>
                        <div class="form-group">
                            <input type="text" name="company" placeholder="Firm" required>
                        </div>
                        <div class="form-group">
                            <select name="matter" required>
                                <option value="" disabled selected>Matter type</option>
                                <option value="product-liability">Product liability</option>
                                <option value="ip-infringement">IP &mdash; infringement</option>
                                <option value="ip-invalidity">IP &mdash; invalidity / prior art</option>
                                <option value="manufacturing-dispute">Manufacturing or supply dispute</option>
                                <option value="insurance-subrogation">Insurance / subrogation</option>
                                <option value="other">Other</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <textarea name="parties" rows="3" placeholder="Parties involved (names only)" required></textarea>
                        </div>
                        <div class="form-group">
                            <textarea name="message" rows="3" placeholder="Technical subject matter — e.g. &quot;failure of a glass-filled nylon housing&quot;. No case details." required></textarea>
                        </div>
                        <button type="submit" class="btn btn-primary btn-lg btn-full">Request Conflict Check</button>
                        <p class="form-note">Response within one business day. Treated as confidential.</p>
                    </form>
                </div>
            </div>
        </div>
    </section>
""".format(pemail=EMAIL_PRINCIPAL, pphone=PHONE_PRINCIPAL, ptel=PHONE_PRINCIPAL_TEL)

    html += footer() + "\n"
    html += form_scripts()
    html += "</body>\n</html>\n"
    return html


# ------------------------------------------------------ featured this month
#
# A real page, not just the band on the homepage. The band sits two thirds of
# the way down index.html with nothing linking to it, which made the monthly
# pick effectively invisible; this gives it a stable URL that can be linked
# from a newsletter or a LinkedIn post and does not move as the homepage grows.
#
# The content is filled in by featured.js from content/featured/featured.json,
# so the month's article changes without regenerating any HTML — the workflow
# commits one JSON file and this page follows it.

def build_featured():
    html = head("Featured This Month | Flaney Associates",
                "One article from the Flaney Associates archive, selected each "
                "month for readers facing a materials, product-performance or "
                "manufacturing decision.",
                canonical="featured.html")
    html += nav(active="featured") + "\n"
    html += page_hero(
        "Featured This Month",
        "One article from the archive, chosen each month for readers facing a "
        "materials, product-performance or manufacturing decision &mdash; with "
        "a note on why it is worth your time.",
        [("Home", "index.html"), ("Insights", None), ("Featured This Month", None)]) + "\n"

    html += """    <section class="section">
        <div class="container">
            <div class="featured-page" id="featuredBand" data-src="content/featured/featured.json" hidden>
                <span class="featured-tag">Featured this month &middot; <span data-field="month"></span></span>
                <h2><a data-field="link" href="blog/index.html"><span data-field="title"></span></a></h2>
                <p class="featured-excerpt" data-field="excerpt"></p>
                <div class="featured-why-block">
                    <h3>Why this one</h3>
                    <p data-field="summary"></p>
                </div>
                <div class="featured-meta">
                    <span>Published <span data-field="published"></span></span>
                    <span data-field="themes"></span>
                </div>
                <div class="featured-actions">
                    <a class="btn btn-primary btn-lg" data-field="link" href="blog/index.html">Read the article</a>
                    <a class="btn btn-outline btn-lg" href="blog/index.html">Browse all articles</a>
                </div>
            </div>

            <!-- Shown only if the JSON is missing or unreadable. On the homepage
                 the band simply hides; a dedicated page cannot do that, because
                 hiding everything would leave a blank page under a heading that
                 promises an article. -->
            <div class="featured-empty" id="featuredEmpty" hidden>
                <h2>No featured article just yet</h2>
                <p>This month&rsquo;s selection has not been published. The full archive is available in the meantime.</p>
                <a href="blog/index.html" class="btn btn-primary btn-lg">Browse all articles</a>
            </div>
        </div>
    </section>

    <section class="section section-alt">
        <div class="container">
            <div class="prose" style="max-width:760px;margin:0 auto">
                <h2>How this is chosen</h2>
                <p>One article is selected on the first of each month from those published on this site that fall within the practice&rsquo;s material and manufacturing areas. The note above says which areas the article touches and which kind of engagement it relates to.</p>
                <p>Nothing is removed from the archive when an article is featured, and past selections stay exactly where they were. If you are looking for something specific, the <a href="blog/index.html">full archive</a> is searchable by title and filterable by topic.</p>
            </div>
        </div>
    </section>
"""
    html += closing_cta() + "\n"
    html += footer() + "\n"
    html += scripts()
    html += ('    <script src="featured.js?v=%s"></script>\n'
             % asset_version("featured.js"))
    html += "</body>\n</html>\n"
    return html


# ------------------------------------------------------------------- main

def main():
    print("Rendering interior pages...")
    for slug in SERVICES:
        write(os.path.join("services", slug + ".html"), build_service(slug))
    write("about.html", build_about())
    write("industries.html", build_industries())
    write("guides.html", build_guides())
    write("featured.html", build_featured())
    write("checklist.html", build_checklist())
    write("contact.html", build_contact())
    write("attorney-inquiry.html", build_attorney())
    print("Done. index.html and blog/ are generated elsewhere — see CLAUDE.md.")


if __name__ == "__main__":
    main()
