/* "Featured this month" band.
 *
 * Reads content/featured/featured.json — written monthly by
 * generate_featured.py via .github/workflows/featured.yml — and fills in the
 * band. Loaded only by the pages that have one (the homepage and guides).
 *
 * The band ships hidden and is revealed only once real content is in it, so
 * every failure mode is the same: no band at all, and the page reads as though
 * the section was never there. That covers the month before the first run, a
 * file that has not been committed yet, a fetch blocked on file:// URLs, and
 * malformed JSON. A half-rendered card with an empty heading would be worse
 * than nothing on a page whose whole argument is that this practice is careful.
 */
(function () {
    const band = document.getElementById('featuredBand');
    if (!band) return;

    // The path is on the element rather than hardcoded here, so a page at a
    // different depth can carry the band without this file knowing about it.
    const src = band.dataset.src;
    if (!src) return;

    const set = (sel, value) => {
        const el = band.querySelector(sel);
        if (el) el.textContent = value;
    };

    fetch(src, { cache: 'no-cache' })
        .then(r => r.ok ? r.json() : Promise.reject(r.status))
        .then(data => {
            if (!data || !data.title || !data.url) return;

            set('[data-field="title"]', data.title);
            set('[data-field="summary"]', data.summary || '');
            set('[data-field="excerpt"]', data.highlight_excerpt || '');

            // The heading and the button are both links to the article, so
            // every one of them is set, not just the first.
            band.querySelectorAll('[data-field="link"]')
                .forEach(a => { a.href = data.url; });

            const month = band.querySelector('[data-field="month"]');
            if (month && data._meta && data._meta.month) {
                // "2026-08" -> "August 2026". Parsed as UTC and formatted in
                // UTC: new Date('2026-08') is midnight UTC, which is the
                // previous month for anyone west of Greenwich.
                const d = new Date(data._meta.month + '-01T00:00:00Z');
                month.textContent = d.toLocaleDateString('en-GB', {
                    month: 'long', year: 'numeric', timeZone: 'UTC'
                });
            }

            band.hidden = false;
        })
        .catch(() => { /* no file yet, or unreadable — leave the band hidden */ });
})();
