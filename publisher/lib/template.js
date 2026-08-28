/* Article rendering for the publisher — the browser-side twin of generate_blog.py.
 *
 * Both paths must produce the same markup: the publisher writes blog/<slug>.html
 * directly so a post can go live without running Python, but it also appends the
 * post to blog/data/posts.json so `python3 generate_blog.py` reproduces the whole
 * archive from scratch. If the two drift, a regeneration silently rewrites pages
 * the publisher made. Any change to build_post()/card() in generate_blog.py
 * belongs here too.
 */
window.FlaneyTemplate = (function () {
    'use strict';

    const SITE = 'https://jotaigbe2026.github.io/Flaney_Associates';

    // -------------------------------------------------------------- utilities

    function stripTags(html) {
        return String(html || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    }

    function decode(text) {
        const el = document.createElement('textarea');
        el.innerHTML = String(text || '');
        return el.value;
    }

    function esc(text) {
        return String(text || '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    /* Attribute-safe, entity-decoded first — the archive reads these values back
       through dataset, which returns them decoded. See attr() in generate_blog.py. */
    function attr(text) {
        return decode(stripTags(text)).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
    }

    /* Same ASCII folding as generate_blog.py's search_key() and blog.js's fold(),
       so a search for "didn't" matches "didn’t". Keep all three in sync. */
    const FOLD = { '‘': "'", '’': "'", '“': '"', '”': '"', '–': '-', '—': '-', '…': '...', ' ': ' ' };
    function searchKey(text) {
        return decode(stripTags(text))
            .replace(/[‘’“”–—… ]/g, c => FOLD[c])
            .toLowerCase().replace(/&/g, '&amp;').replace(/"/g, '&quot;');
    }

    function slugify(title) {
        return decode(stripTags(title)).toLowerCase()
            .replace(/[‘’'"“”]/g, '')
            .replace(/&/g, ' and ')
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-+|-+$/g, '')
            .slice(0, 80).replace(/-+$/, '');
    }

    const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
        'August', 'September', 'October', 'November', 'December'];

    /* Parse as a local date. new Date("2026-09-01") is UTC midnight, which prints
       as August 31st for anyone west of Greenwich. */
    function parseDate(iso) {
        const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (!m) return new Date(iso);
        return new Date(+m[1], +m[2] - 1, +m[3]);
    }

    function fmtDate(iso) {
        const d = parseDate(iso);
        return MONTHS[d.getMonth()] + ' ' + d.getDate() + ', ' + d.getFullYear();
    }

    function readTime(words) {
        return Math.max(1, Math.round(words / 200));
    }

    function countWords(html) {
        const text = stripTags(html);
        return text ? text.split(/\s+/).length : 0;
    }

    // ------------------------------------------------------------ body parsing

    const BLOCK_TAGS = ['P', 'H2', 'H3', 'H4', 'UL', 'OL', 'LI', 'BLOCKQUOTE', 'TABLE'];

    const STRIP_ATTR = /^(style|class|id|data-[\w-]+|width|height|srcset|sizes|loading|decoding)$/i;

    function looksLikeHeading(line) {
        const t = line.trim();
        if (!(t.length > 3 && t.length <= 80)) return false;
        if (/[,;:\-–—.!?]$/.test(t)) return false;
        if (t.split(/\s+/).length > 12) return false;
        return /^[A-Z0-9]/.test(t);
    }

    function inlineMarkdown(text) {
        return esc(text)
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,;:!?]|$)/g, '$1<em>$2</em>')
            .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
                '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    }

    /* Plain text or light Markdown -> article HTML.
       Handles the two ways an article actually arrives: pasted straight out of a
       word processor (blank-line paragraphs, bare heading lines) or written in
       Markdown. A standalone short line with no terminal punctuation is promoted
       to a heading — the same conservative rule generate_blog.py applies to bold
       runs in the imported WordPress copy. */
    function fromPlainText(input) {
        const raw = String(input).replace(/\r\n?/g, '\n');

        // Markdown separates paragraphs with a blank line; word processors,
        // Google Docs and Canva put one paragraph per line with no blank line
        // between. Requiring blank lines silently glued every heading onto the
        // paragraph below it, producing openings like "BoardGPT — Using AI in
        // the Boardroom Artificial intelligence is changing how organizations…".
        // So: if the text has no blank lines anywhere, every line is its own
        // block. Hard-wrapped text would suffer, but nothing pasted from a
        // modern editor is hard-wrapped.
        const lineIsBlock = !/\n[ \t]*\n/.test(raw);

        const lines = raw.split('\n');
        const out = [];
        let paragraph = [], list = null, quote = [];

        function flushParagraph() {
            if (!paragraph.length) return;
            const text = paragraph.join(' ').trim();
            if (text) {
                if (paragraph.length === 1 && looksLikeHeading(text)) {
                    out.push('<h3>' + inlineMarkdown(text) + '</h3>');
                } else {
                    out.push('<p>' + inlineMarkdown(text) + '</p>');
                }
            }
            paragraph = [];
        }
        function flushList() {
            if (!list) return;
            out.push('<' + list.tag + '>\n' +
                list.items.map(i => '    <li>' + inlineMarkdown(i) + '</li>').join('\n') +
                '\n</' + list.tag + '>');
            list = null;
        }
        function flushQuote() {
            if (!quote.length) return;
            out.push('<blockquote><p>' + inlineMarkdown(quote.join(' ')) + '</p></blockquote>');
            quote = [];
        }
        function flushAll() { flushParagraph(); flushList(); flushQuote(); }

        lines.forEach(function (raw) {
            const line = raw.trim();

            if (!line) { flushAll(); return; }

            let m = line.match(/^(#{1,4})\s+(.*)$/);
            if (m) {
                flushAll();
                const level = Math.min(4, Math.max(2, m[1].length));
                out.push('<h' + level + '>' + inlineMarkdown(m[2].trim()) + '</h' + level + '>');
                return;
            }

            m = line.match(/^[-*•]\s+(.*)$/);
            if (m) {
                flushParagraph(); flushQuote();
                if (!list || list.tag !== 'ul') { flushList(); list = { tag: 'ul', items: [] }; }
                list.items.push(m[1].trim());
                return;
            }

            m = line.match(/^\d+[.)]\s+(.*)$/);
            if (m) {
                flushParagraph(); flushQuote();
                if (!list || list.tag !== 'ol') { flushList(); list = { tag: 'ol', items: [] }; }
                list.items.push(m[1].trim());
                return;
            }

            m = line.match(/^>\s?(.*)$/);
            if (m) {
                flushParagraph(); flushList();
                quote.push(m[1].trim());
                return;
            }

            flushList(); flushQuote();
            paragraph.push(line);
            if (lineIsBlock) flushParagraph();
        });

        flushAll();
        return out.join('\n');
    }

    /* Pasted HTML (Word, Google Docs, the WordPress editor) -> clean article HTML.
       Mirrors clean() in generate_blog.py: drop presentational attributes, unwrap
       containers, normalise b/i, and let wide tables scroll inside their own box. */
    function fromHTML(input) {
        const doc = new DOMParser().parseFromString('<body>' + input + '</body>', 'text/html');
        const body = doc.body;

        body.querySelectorAll('script, style, meta, link, noscript, ' +
            'header, footer, nav, form, input, button, iframe, o\\:p').forEach(el => el.remove());

        // Strip WordPress/WPBakery leftovers and every HTML comment. Word wraps
        // its bullet glyphs in conditional comments —
        //   <li><!--[if !supportLists]-->·&nbsp;&nbsp;<!--[endif]-->Item</li>
        // — which browsers hide in the document but which render as a stray
        // bullet and a run of spaces once the markup is reused.
        body.innerHTML = body.innerHTML
            .replace(/\[\/?(?:vc_|wpb_)[a-z_]*[^\]]*\]/gi, '')
            .replace(/<!--[\s\S]*?-->/g, '');

        // A page break Word emits between sections; meaningless here.
        body.querySelectorAll('br[clear]').forEach(el => el.remove());

        // Mirrors BAD_ATTR in generate_blog.py — strip presentational and loader
        // attributes, keep the rest. An allowlist would be tighter but diverges:
        // dropping the `start` off <ol start="2"> silently renumbers the list
        // back to 1, and Python would have kept it.
        body.querySelectorAll('*').forEach(function (el) {
            Array.from(el.attributes).forEach(function (a) {
                if (STRIP_ATTR.test(a.name)) el.removeAttribute(a.name);
            });
        });

        function unwrap(el) {
            while (el.firstChild) el.parentNode.insertBefore(el.firstChild, el);
            el.remove();
        }
        body.querySelectorAll('div, span, section, article, font').forEach(unwrap);

        body.querySelectorAll('b').forEach(function (el) {
            const s = doc.createElement('strong');
            s.innerHTML = el.innerHTML; el.replaceWith(s);
        });
        body.querySelectorAll('i, u').forEach(function (el) {
            const s = doc.createElement('em');
            s.innerHTML = el.innerHTML; el.replaceWith(s);
        });
        // The page renders the title as its own <h1>; demote any inside the body.
        body.querySelectorAll('h1').forEach(function (el) {
            const s = doc.createElement('h2');
            s.innerHTML = el.innerHTML; el.replaceWith(s);
        });
        body.querySelectorAll('h5, h6').forEach(function (el) {
            const s = doc.createElement('h4');
            s.innerHTML = el.innerHTML; el.replaceWith(s);
        });

        /* Word and Google Docs wrap headings in bookmark anchors for their
           internal table of contents — <a name="augmenting_not_replacing">.
           They are not links, they render as nothing, and they hid every
           heading from the promotion below by sitting between the paragraph
           and its bold run. An anchor with no href is unwrapped. */
        Array.from(body.querySelectorAll('a')).forEach(function (el) {
            if (el.getAttribute('href')) return;
            while (el.firstChild) el.parentNode.insertBefore(el.firstChild, el);
            el.remove();
        });

        body.querySelectorAll('a[href]').forEach(function (el) {
            const href = el.getAttribute('href') || '';
            if (/^https?:/i.test(href) && href.indexOf('flaneyassociates.com') === -1) {
                el.setAttribute('target', '_blank');
                el.setAttribute('rel', 'noopener noreferrer');
            }
        });

        body.querySelectorAll('p').forEach(function (el) {
            if (!el.textContent.trim() && !el.querySelector('img')) el.remove();
        });


        /* Word exports bulleted and numbered lists as ordinary paragraphs with
           the marker glyph inlined — <p class=MsoListParagraph>· Item</p> — so
           without this a list arrives as a run of stray paragraphs each opening
           with a bullet character. Consecutive markers are grouped into one
           list, which is what the author saw in the document. */
        const MARKER = /^\s*(?:[-\u2022\u25AA\u25E6\u00B7*]|\d+[.)])\s+/;
        Array.from(body.querySelectorAll('p')).forEach(function (el) {
            if (!MARKER.test(el.textContent)) return;
            const ordered = /^\s*\d/.test(el.textContent);
            const prev = el.previousElementSibling;
            const tag = ordered ? 'OL' : 'UL';

            const item = doc.createElement('li');
            item.innerHTML = el.innerHTML.replace(/^(\s|&nbsp;)*(?:[-\u2022\u25AA\u25E6\u00B7*]|\d+[.)])(\s|&nbsp;)+/, '');

            if (prev && prev.tagName === tag) {
                prev.appendChild(item);
                el.remove();
            } else {
                const list = doc.createElement(tag.toLowerCase());
                list.appendChild(item);
                el.replaceWith(list);
            }
        });

        /* Promote a standalone short line to a heading. Word only emits <h2>
           when a built-in Heading style was used; a heading made by enlarging
           or bolding the text arrives as an ordinary paragraph, which is how an
           article came through with 38 paragraphs and 1 heading. Both shapes
           are handled — a bare line and a line that is entirely one bold run.

           Runs after the list grouping above, so a numbered item is already an
           <li> and cannot be mistaken for a heading. Conservative by design,
           matching promote_pseudo_headings() in generate_blog.py: at most 12
           words, no terminal punctuation, must start with a capital or digit.
           Whitespace is collapsed because Word wraps long lines mid-heading. */
        Array.from(body.querySelectorAll('p')).forEach(function (el) {
            const boldOnly = el.children.length === 1 &&
                el.children[0].tagName === 'STRONG' &&
                el.textContent.trim() === el.children[0].textContent.trim();
            if (el.children.length !== 0 && !boldOnly) return;

            const text = el.textContent.replace(/\s+/g, ' ').trim();
            if (!looksLikeHeading(text)) return;

            const h = doc.createElement('h3');
            h.textContent = text;
            el.replaceWith(h);
        });

        // Word wraps long lines mid-heading, so a heading that arrived as a real
        // <h2> can still carry a newline through to the page.
        body.querySelectorAll('h2, h3, h4').forEach(function (el) {
            el.innerHTML = el.innerHTML.replace(/\s+/g, ' ').trim();
        });

        /* The marker glyph Word leaves at the front of a real list item, now
           that its surrounding conditional comment is gone. Removing it here
           rather than in the grouping above covers lists that arrived as
           genuine <ul><li> markup as well as those rebuilt from paragraphs. */
        body.querySelectorAll('li').forEach(function (el) {
            el.innerHTML = el.innerHTML
                .replace(/^(?:\s|&nbsp;|\u00a0)*(?:[\u00b7\u2022\u25AA\u25E6*-]|\d+[.)])(?:\s|&nbsp;|\u00a0)+/, '')
                .trim();
        });

        body.querySelectorAll('table').forEach(function (el) {
            const wrap = doc.createElement('div');
            wrap.className = 'table-scroll';
            el.replaceWith(wrap);
            wrap.appendChild(el);
        });

        // Bare text nodes left at the top level need a paragraph of their own.
        Array.from(body.childNodes).forEach(function (node) {
            if (node.nodeType === 3 && node.textContent.trim()) {
                const p = doc.createElement('p');
                p.textContent = node.textContent.trim();
                node.replaceWith(p);
            }
        });

        return Array.from(body.children)
            .map(el => el.outerHTML)
            .join('\n')
            .replace(/[ \t]{2,}/g, ' ')
            .trim();
    }

    function looksLikeHTML(input) {
        return /<(p|div|h[1-6]|ul|ol|li|table|br|strong|em|b|i|span)\b[^>]*>/i.test(input);
    }

    function parseBody(input) {
        const text = String(input || '').trim();
        if (!text) return '';
        const html = looksLikeHTML(text) ? fromHTML(text) : fromPlainText(text);
        // clean() in generate_blog.py collapses runs of spaces and tabs. Doing
        // the same here keeps the stored body identical to what a later
        // `python3 generate_blog.py` would write, so regenerating produces no
        // spurious diff against the page the publisher already built.
        return html.replace(/[ \t]{2,}/g, ' ');
    }

    /* Article HTML -> flat block list for the PDF writer. */
    function toBlocks(html) {
        const doc = new DOMParser().parseFromString('<body>' + html + '</body>', 'text/html');
        const blocks = [];

        function runs(el) {
            const list = [];
            (function walk(node, bold, italic) {
                node.childNodes.forEach(function (child) {
                    if (child.nodeType === 3) {
                        const text = child.textContent;
                        // Keep whitespace-only nodes as a single space: they are
                        // what separates "<strong>a</strong> <em>b</em>", and
                        // dropping them would run the two words together.
                        if (text.trim()) list.push({ text: text, bold: bold, italic: italic });
                        else if (text.length) list.push({ text: ' ', bold: bold, italic: italic });
                        return;
                    }
                    if (child.nodeType !== 1) return;
                    const tag = child.tagName;
                    walk(child, bold || tag === 'STRONG', italic || tag === 'EM');
                });
            })(el, false, false);
            return list.length ? list : [{ text: el.textContent, bold: false, italic: false }];
        }

        (function visit(parent) {
            Array.from(parent.children).forEach(function (el) {
                switch (el.tagName) {
                    case 'H2': blocks.push({ type: 'h2', runs: runs(el) }); break;
                    case 'H3':
                    case 'H4': blocks.push({ type: 'h3', runs: runs(el) }); break;
                    case 'P': blocks.push({ type: 'p', runs: runs(el) }); break;
                    case 'LI': blocks.push({ type: 'li', runs: runs(el) }); break;
                    case 'BLOCKQUOTE': blocks.push({ type: 'quote', runs: runs(el) }); break;
                    case 'UL':
                    case 'OL': visit(el); break;
                    case 'TABLE':
                        // Tables don't survive a text-only PDF; flatten each row.
                        Array.from(el.querySelectorAll('tr')).forEach(function (tr) {
                            const cells = Array.from(tr.children).map(td => td.textContent.trim());
                            blocks.push({ type: 'li', runs: [{ text: cells.join(' — ') }] });
                        });
                        break;
                    default: visit(el);
                }
            });
        })(doc.body);

        return blocks;
    }

    /* Mirrors LOGIN_WALL in generate_blog.py. The Simple Membership plugin
       served this instead of an abstract on a couple of gated posts, and the
       API stored it as the excerpt. It was indexed into the card's data-title,
       so an archive search for "member" or "logged" surfaced them. */
    const LOGIN_WALL = /logged in to view|not a member|please log in/i;

    /* First real paragraph, trimmed to a card-sized summary. Mirrors summarise(). */
    function summarise(html, title, limit) {
        limit = limit || 260;
        const doc = new DOMParser().parseFromString('<body>' + html + '</body>', 'text/html');
        const first = doc.querySelector('p');
        let text = stripTags(first ? first.innerHTML : html);

        const clean = String(title || '').trim().replace(/:$/, '');
        if (clean && text.toLowerCase().indexOf(clean.toLowerCase()) === 0) {
            text = text.slice(clean.length).replace(/^[\s:–—-]+/, '');
        }
        text = text.replace(/^(Introduction|Abstract|Overview)\b[\s:–—-]*/i, '');

        if (text.length > limit) {
            text = text.slice(0, limit - 1).replace(/\s+\S*$/, '').replace(/[,;:.]$/, '') + '…';
        }
        return text;
    }

    // ------------------------------------------------------------- components

    function nav(depth, solid) {
        const up = '../'.repeat(depth);
        const cls = solid ? 'navbar navbar-solid' : 'navbar';
        return `    <nav class="${cls}" id="navbar">
        <div class="container nav-container">
            <a href="${up}index.html" class="logo">
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
                        <li><a href="${up}services/failure-analysis.html">Failure &amp; Root-Cause Analysis<span class="dropdown-note">Why it failed, and what is defensible</span></a></li>
                        <li><a href="${up}services/materials-selection.html">Materials Selection &amp; Qualification<span class="dropdown-note">Choosing and validating a material</span></a></li>
                        <li><a href="${up}services/product-development.html">Product Development &amp; Materials Innovation<span class="dropdown-note">Concept through production</span></a></li>
                        <li><a href="${up}services/process-optimization.html">Manufacturing Process Optimization<span class="dropdown-note">Yield, quality, throughput</span></a></li>
                        <li><a href="${up}services/technical-due-diligence.html">Technical Due Diligence &amp; R&amp;D Strategy<span class="dropdown-note">Technology and investment decisions</span></a></li>
                        <li><a href="${up}services/expert-witness.html">Expert Witness &amp; Litigation Support<span class="dropdown-note">Product liability, IP, technical disputes</span></a></li>
                    </ul>
                </li>
                <li class="has-dropdown">
                    <button type="button" class="nav-trigger">Industries</button>
                    <ul class="dropdown">
                        <li><a href="${up}industries.html#polymers-plastics">Polymers &amp; Plastics</a></li>
                        <li><a href="${up}industries.html#composites">Composites</a></li>
                        <li><a href="${up}industries.html#manufacturing">Manufacturing &amp; Processing</a></li>
                        <li><a href="${up}industries.html#consumer-products">Consumer Products</a></li>
                        <li><a href="${up}industries.html#automotive">Automotive &amp; Transportation</a></li>
                        <li><a href="${up}industries.html#energy">Energy &amp; Oil/Gas</a></li>
                    </ul>
                </li>
                <li class="has-dropdown">
                    <button type="button" class="nav-trigger">Insights</button>
                    <ul class="dropdown">
                        <li><a href="${up}featured.html">Featured This Month<span class="dropdown-note">One article, chosen monthly</span></a></li>
                        <li><a href="${up}blog/index.html" class="active">Blog<span class="dropdown-note">Articles on materials and manufacturing</span></a></li>
                        <li><a href="${up}guides.html">Guides &amp; Briefings<span class="dropdown-note">Checklists and sector briefings</span></a></li>
                    </ul>
                </li>
                <li class="has-dropdown">
                    <button type="button" class="nav-trigger">About</button>
                    <ul class="dropdown">
                        <li><a href="${up}about.html">Joshua U. Otaigbe<span class="dropdown-note">Founder &amp; Principal &middot; credentials and approach</span></a></li>
                        <li><a href="${up}about.html#credentials">Credentials</a></li>
                        <li><a href="${up}about.html#approach">Approach</a></li>
                        <li><a href="${up}about.html#faqs">FAQs</a></li>
                    </ul>
                </li>
                <li class="has-dropdown">
                    <button type="button" class="nav-trigger">Contact</button>
                    <ul class="dropdown">
                        <li><a href="${up}contact.html">Discuss Your Challenge<span class="dropdown-note">Manufacturers and product teams</span></a></li>
                        <li><a href="${up}attorney-inquiry.html">Attorney Conflict Check<span class="dropdown-note">Confidential, no case details</span></a></li>
                    </ul>
                </li>
                <li><a href="${up}contact.html" class="btn btn-nav">Discuss Your Challenge</a></li>
            </ul>
        </div>
    </nav>`;
    }

    function footer(depth) {
        const up = '../'.repeat(depth);
        return `    <footer class="footer">
        <div class="container">
            <div class="footer-grid">
                <div class="footer-brand">
                    <a href="${up}index.html" class="logo">
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
                        <li><a href="${up}services/failure-analysis.html">Failure &amp; Root-Cause Analysis</a></li>
                        <li><a href="${up}services/materials-selection.html">Materials Selection &amp; Qualification</a></li>
                        <li><a href="${up}services/product-development.html">Product Development &amp; Materials Innovation</a></li>
                        <li><a href="${up}services/process-optimization.html">Manufacturing Process Optimization</a></li>
                        <li><a href="${up}services/technical-due-diligence.html">Technical Due Diligence &amp; R&amp;D Strategy</a></li>
                        <li><a href="${up}services/expert-witness.html">Expert Witness &amp; Litigation Support</a></li>
                    </ul>
                </div>
                <div class="footer-links">
                    <h4>Company</h4>
                    <ul>
                        <li><a href="${up}about.html">About Joshua U. Otaigbe</a></li>
                        <li><a href="${up}about.html#credentials">Credentials</a></li>
                        <li><a href="${up}industries.html">Industries</a></li>
                        <li><a href="${up}featured.html">Featured This Month</a></li>
                        <li><a href="${up}blog/index.html">Blog</a></li>
                        <li><a href="${up}guides.html">Guides &amp; Briefings</a></li>
                    </ul>
                </div>
                <div class="footer-links">
                    <h4>Contact</h4>
                    <ul>
                        <li><a href="${up}contact.html">Discuss Your Challenge</a></li>
                        <li><a href="${up}attorney-inquiry.html">Attorney Conflict Check</a></li>
                        <li><a href="mailto:info@flaneyassociates.com">info@flaneyassociates.com</a></li>
                        <li><a href="tel:+16014027282">+1 (601) 402-7282</a></li>
                    </ul>
                </div>
            </div>
            <div class="footer-bottom">
                <p>&copy; 2026 Flaney Associates, LLC. All rights reserved.</p>
            </div>
        </div>
    </footer>`;
    }

    /* The lead-capture modal, identical to the one in index.html. blog.js wires
       it up on article pages; script.js does the same on the homepage. */
    function downloadModal() {
        return `    <div class="modal-overlay" id="downloadModal">
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
    </div>`;
    }

    function head(title, description, depth, extra, assets) {
        const up = '../'.repeat(depth);
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${title}</title>
    <meta name="description" content="${description}">
${extra || ''}    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="${up}styles.css${assets.site}">
    <link rel="stylesheet" href="${up}blog/blog.css${assets.css}">
</head>
<body>
`;
    }

    // ------------------------------------------------------------------ cards

    function card(post, prefix) {
        prefix = prefix || '';
        const media = post.local_image
            ? `<img src="${prefix}images/${post.local_image}" alt="${attr(post.image_alt || post.title)}" loading="lazy">`
            : '<div class="blog-thumb-fallback" aria-hidden="true">&#9670;</div>';

        const cats = (post.categories && post.categories.length)
            ? post.categories : ['Materials Engineering'];
        const stored = (post.summary && !LOGIN_WALL.test(post.summary)) ? post.summary : '';
        const excerpt = stored || summarise(post.content, stripTags(post.title));

        let thumb, heading, action, badge, metaExtra;
        if (post.gated) {
            // The source site is being retired, so these no longer link
            // anywhere. .post-thumb and .post-card h3 are styled by class, not
            // by tag, so dropping the <a> changes nothing visually.
            const contact = prefix ? 'contact.html' : '../contact.html';
            thumb = `<div class="post-thumb">${media}</div>`;
            heading = `<h3>${post.title}</h3>`;
            action = `<a class="card-link" href="${contact}">Request a copy &rarr;</a>`;
            badge = '<span class="post-badge post-badge-locked">&#128196; PDF on request</span>';
            metaExtra = '';
        } else {
            const href = prefix + post.slug + '.html';
            thumb = `<a class="post-thumb" href="${href}">${media}</a>`;
            heading = `<h3><a href="${href}">${post.title}</a></h3>`;
            action = `<a class="card-link" href="${href}">Read full article &rarr;</a>`;
            badge = '';
            metaExtra = `<span class="blog-read">${readTime(post.words)} min read</span>`;
        }

        // Two gated posts have no abstract at all. An empty <p> would leave a
        // gap the card's spacing was not designed for, so it is omitted.
        const summaryEl = excerpt ? `\n                        <p>${excerpt}</p>` : '';

        return `                <article class="post-card" data-title="${searchKey((post.title + ' ' + excerpt).trim())}" data-cats="${attr(cats.join('|'))}" data-publish="${String(post.date).slice(0, 10)}">
                    ${thumb}
                    <div class="post-body">
                        <div class="post-cats">${cats.map(c => `<span class="blog-category">${c}</span>`).join('')}${badge}</div>
                        ${heading}${summaryEl}
                        <div class="blog-meta">
                            <span class="blog-date">${fmtDate(post.date)}</span>
                            ${metaExtra}
                        </div>
                        ${action}
                    </div>
                </article>
`;
    }

    // ----------------------------------------------------------- article page

    function article(post, related, assets) {
        const cats = (post.categories && post.categories.length)
            ? post.categories : ['Materials Engineering'];
        const desc = (post.summary || summarise(post.content, stripTags(post.title), 300))
            .replace(/"/g, '&quot;');
        const canonical = post.link || (SITE + '/blog/' + post.slug + '.html');

        const og = `    <meta property="og:type" content="article">
    <meta property="og:title" content="${attr(post.title)}">
    <meta property="og:description" content="${desc}">
    <meta property="article:published_time" content="${post.date}">
${post.image ? `    <meta property="og:image" content="${post.image}">\n` : ''}    <link rel="canonical" href="${canonical}">
`;

        let html = head(stripTags(post.title) + ' | Flaney Associates', desc, 1, og, assets);
        html += nav(1, true) + '\n';

        const heroImg = post.local_image ? `        <figure class="article-figure">
            <img src="images/${post.local_image}" alt="${attr(post.image_alt || post.title)}">
        </figure>
` : '';

        html += `
    <article class="article-page" data-publish="${String(post.date).slice(0, 10)}">
        <div class="container container-narrow">
            <a class="back-link" href="index.html">&larr; All articles</a>
            <div class="post-cats">${cats.map(c => `<span class="blog-category">${c}</span>`).join('')}</div>
            <h1>${post.title}</h1>
            <div class="article-meta">
                <span>${fmtDate(post.date)}</span>
                <span aria-hidden="true">&middot;</span>
                <span>${readTime(post.words)} min read</span>
                <span aria-hidden="true">&middot;</span>
                <span>${post.author || 'Flaney Associates'}</span>
            </div>
        </div>
${heroImg}        <div class="container container-narrow">
            <div class="article-body">
${post.content}
            </div>
`;

        if (post.pdf) {
            html += `
            <div class="article-download">
                <div class="article-download-text">
                    <h4>&#128196; Download this article as a PDF</h4>
                    <p>Take the full briefing with you — formatted for print, filing and sharing with your team.</p>
                </div>
                <button class="btn btn-primary gated-download" data-pdf="../${post.pdf}" data-title="${attr(post.title)}">&#11015; Get the PDF</button>
            </div>
`;
        }

        if (post.local) {
            html += `
            <div class="article-source">
                <p>Published by Flaney Associates on ${fmtDate(post.date)}.</p>
            </div>
`;
        } else {
            html += `
            <div class="article-source">
                <p>Originally published on <a href="${post.link}" target="_blank" rel="noopener">flaneyassociates.com</a> on ${fmtDate(post.date)}.</p>
            </div>
`;
        }

        html += `
            <div class="article-author">
                <div class="author-avatar" aria-hidden="true">JO</div>
                <div>
                    <h4>Joshua U. Otaigbe, PhD</h4>
                    <p>Materials engineering consultant specialising in polymers, composites and hybrid materials. Get in touch at <a href="mailto:info@flaneyassociates.com">info@flaneyassociates.com</a>.</p>
                </div>
            </div>
        </div>
    </article>
`;

        if (related && related.length) {
            html += `
    <section class="section related-section">
        <div class="container">
            <h2 class="related-heading">Related articles</h2>
            <div class="post-grid">
`;
            related.forEach(function (r) { html += card(r); });
            html += `            </div>
        </div>
    </section>
`;
        }

        html += `
    <section class="section cta-band">
        <div class="container">
            <h2>Need independent input on a materials problem?</h2>
            <p>Failure and root-cause analysis, materials selection, process optimization and expert-witness work — led by Joshua U. Otaigbe, PhD, CEng, FIMMM, Founder and Principal of Flaney Associates.</p>
            <a href="../contact.html" class="btn btn-primary btn-lg">Discuss Your Challenge</a>
        </div>
    </section>

`;
        html += footer(1) + '\n';
        html += downloadModal() + '\n\n';
        html += `    <script src="../lead-capture.js${assets.lead}"><\/script>\n`;
        html += `    <script src="blog.js${assets.js}"><\/script>\n</body>\n</html>\n`;
        return html;
    }

    // ----------------------------------------------------------- archive page

    /* blog/index.html — the twin of build_index(). Regenerated on every publish
       so a new post actually shows up in the archive without running Python. */
    function archive(posts, assets) {
        const allCats = Array.from(new Set(posts.flatMap(p => p.categories || []))).sort();
        const full = posts.filter(p => !p.gated);

        const chips = ['<button class="filter-chip active" data-cat="all">All posts ' +
            '<span class="chip-count">' + posts.length + '</span></button>'];
        allCats.forEach(function (c) {
            const n = posts.filter(p => (p.categories || []).indexOf(c) !== -1).length;
            chips.push('<button class="filter-chip" data-cat="' + attr(c) + '">' + c +
                ' <span class="chip-count">' + n + '</span></button>');
        });

        let html = head(
            'Blog &amp; Publications | Flaney Associates',
            'Materials engineering insights, research notes and publications from ' +
            'Flaney Associates — polymers, composites, nanotechnology, sustainable ' +
            'materials and AI in materials discovery.',
            1, '', assets);
        html += nav(1) + '\n';
        html += `
    <header class="blog-hero">
        <div class="container">
            <div class="hero-badge">Insights &amp; Publications</div>
            <h1>The Flaney Associates Blog</h1>
            <p class="blog-hero-sub">${posts.length} articles and publications on materials engineering — polymers and composites, nanotechnology, sustainable materials, protective coatings, and the growing role of AI in materials discovery.</p>
            <div class="blog-hero-stats">
                <div class="stat"><span class="stat-number" data-total="${posts.length}">${posts.length}</span><span class="stat-label">Articles</span></div>
                <div class="stat"><span class="stat-number">${full.length}</span><span class="stat-label">Read online</span></div>
                <div class="stat"><span class="stat-number">${allCats.length}</span><span class="stat-label">Topics</span></div>
            </div>
        </div>
    </header>

    <div class="blog-toolbar">
        <div class="container">
            <div class="blog-search">
                <input type="search" id="postSearch" placeholder="Search articles by title or keyword…" aria-label="Search articles">
            </div>
            <div class="filter-chips" id="filterChips">
${chips.map(c => '                ' + c).join('\n')}
            </div>
        </div>
    </div>

    <main class="section blog-archive">
        <div class="container">
            <p class="results-count" id="resultsCount"></p>
            <div class="post-grid" id="postGrid">
`;
        posts.forEach(function (p) { html += card(p); });

        html += `            </div>
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

`;
        html += footer(1) + '\n';
        html += `    <script src="../lead-capture.js${assets.lead}"><\/script>\n`;
        html += `    <script src="blog.js${assets.js}"><\/script>\n</body>\n</html>\n`;
        return html;
    }

    // -------------------------------------------------------------- homepage

    const HOME_BEGIN = '            <!-- BEGIN imported-blog (generated by generate_blog.py — do not edit by hand) -->';
    const HOME_END = '            <!-- END imported-blog -->';

    /* Posts kept off the homepage strip. Must stay in step with
       HOMEPAGE_EXCLUDE in generate_blog.py — the two renderers write the same
       block, and a mismatch means regenerating silently changes which posts
       the homepage features. */
    const HOMEPAGE_EXCLUDE = new Set([
        'unlocking-the-healing-power-of-cassava-leaves-simple-extraction-methods-for-everyday-wellness',
        'boardgpt-using-ai-in-the-boardroom',
        'empowering-smarter-corporate-boards-with-ai',
        'how-ai-is-transforming-scientific-research'
    ]);

    /* Swap the insights strip inside the existing index.html. Only the marked
       block is touched, exactly as update_homepage() does. The sector
       briefings that used to follow it now live on guides.html, so the block
       no longer emits a heading for them. */
    function homepage(currentHTML, posts, n) {
        const latest = posts
            .filter(p => !p.gated && !HOMEPAGE_EXCLUDE.has(p.slug))
            .slice(0, n || 6);
        const lines = [HOME_BEGIN,
            '            <div class="blog-subhead">',
            '                <h3>Latest from the Flaney Associates blog</h3>',
            '                <a href="blog/index.html">View all ' + posts.length + ' articles &amp; publications &rarr;</a>',
            '            </div>',
            '            <div class="post-grid">'];
        latest.forEach(function (p) { lines.push(card(p, 'blog/').replace(/\n$/, '')); });
        lines.push('            </div>', HOME_END);
        const block = lines.join('\n') + '\n';

        const start = currentHTML.indexOf(HOME_BEGIN);
        const end = currentHTML.indexOf(HOME_END);
        if (start === -1 || end === -1) return null;
        return currentHTML.slice(0, start) + block + currentHTML.slice(end + HOME_END.length + 1);
    }

    /* Same-category first, then most recent — matches build_post()'s ordering. */
    function pickRelated(post, posts, n) {
        const others = posts.filter(q => q.slug !== post.slug && !q.gated);
        const cats = new Set(post.categories || []);
        const same = others.filter(q => (q.categories || []).some(c => cats.has(c)));
        const sameSlugs = new Set(same.map(q => q.slug));
        return same.concat(others.filter(q => !sameSlugs.has(q.slug))).slice(0, n || 3);
    }

    return {
        SITE: SITE,
        slugify, fmtDate, parseDate, readTime, countWords, stripTags, attr, esc, searchKey,
        parseBody, toBlocks, summarise, card, article, archive, homepage,
        pickRelated, downloadModal
    };
})();
