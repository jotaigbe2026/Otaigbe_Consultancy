/* Flaney Publisher — compose the monthly post, preview it, and download a
 * bundle of files that drop straight into the repository.
 *
 * The site is static and served from GitHub Pages, so nothing here can write to
 * the repo. Instead every file that a publish touches is rebuilt in the browser
 * and handed back: the new article page, the regenerated archive, the homepage
 * strip, the updated posts.json, the image and the gated PDF. Committing that
 * set is equivalent to running generate_blog.py — which stays the source of
 * truth, and can still be re-run at any time to rebuild everything.
 *
 * Requires a local server (fetch is blocked on file://):
 *     python3 -m http.server 8000  ->  http://localhost:8000/publisher/
 */
(function () {
    'use strict';

    const T = window.FlaneyTemplate;
    const TEMPLATE_KEY = 'flaney_publisher_template';
    //: Kept apart from the template on purpose. The template is exported to
    //: publisher/template.json, which is committed and served publicly; a local
    //: filesystem path does not belong in it.
    const PATHS_KEY = 'flaney_publisher_paths';

    const state = {
        posts: [],
        assets: { css: '', js: '' },
        defaults: {},         // publisher/template.json, the committed baseline
        homepageHTML: '',
        categories: [],
        selected: new Set(),
        image: null,          // { name, ext, bytes, url, type }
        pdfUpload: null,      // { name, bytes }
        editing: null,        // the published post being revised, or null
        repoDir: null,        // FileSystemDirectoryHandle, when connected
        pendingDir: null,     // remembered, but awaiting re-approval
        originalImage: '',    // its existing blog/images/ filename
        bundle: null,
        ready: false
    };

    const $ = id => document.getElementById(id);
    const el = {};
    ['titlePattern', 'defaultAuthor', 'publishDay', 'standingByline', 'saveTemplate',
        'exportTemplate', 'repoPath', 'templateStatus', 'editPicker', 'editPost', 'editNotice',
        'slugLockNote', 'dateLockNote', 'title', 'titleError', 'slug', 'slugError', 'slugPreview',
        'categoryChips', 'categoryError', 'pubDate', 'dateHelp', 'author', 'scheduleNotice',
        'body', 'bodyError', 'bodyStats', 'bodyHint', 'summary', 'imageDrop', 'imageInput',
        'imageThumb', 'imagePreview', 'imageName', 'imageSize', 'imageRemove', 'imageAlt',
        'pdfUploadWrap', 'pdfDrop', 'pdfInput', 'pdfTargetName', 'pdfUploadInfo',
        'generate', 'generateFeedback', 'queueList', 'queueHint', 'previewFrame', 'cardFrame',
        'shareUrl', 'shareText', 'fileList', 'bundleActions', 'downloadZip', 'commitBlock',
        'commitCommands', 'toast', 'startNextMonth', 'resetForm',
        'chooseFolder', 'folderStatus', 'deletePost', 'regenSummary', 'jumpPreview'
    ].forEach(id => { el[id] = $(id); });

    // ------------------------------------------------------------------ utils

    function toast(message) {
        el.toast.textContent = message;
        el.toast.classList.add('on');
        clearTimeout(toast.timer);
        toast.timer = setTimeout(() => el.toast.classList.remove('on'), 2600);
    }

    function notice(target, kind, html) {
        target.className = 'notice notice-' + kind;
        target.innerHTML = '<span>' + html + '</span>';
        target.hidden = false;
    }

    function humanSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function todayISO() {
        const d = new Date();
        return [d.getFullYear(),
            String(d.getMonth() + 1).padStart(2, '0'),
            String(d.getDate()).padStart(2, '0')].join('-');
    }

    function readFile(file) {
        return file.arrayBuffer().then(buf => new Uint8Array(buf));
    }

    function download(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 4000);
    }

    // ------------------------------------------------------------ monthly template

    /* Two layers: publisher/template.json is the committed baseline, and
       localStorage is a per-device override on top of it. Keeping the baseline
       in the repo means the template survives a cleared cache and is the same
       on every machine — a monthly template that only exists in one browser
       profile is not much of a template. */
    function currentTemplate() {
        let saved = {};
        try { saved = JSON.parse(localStorage.getItem(TEMPLATE_KEY) || '{}'); } catch (e) {}
        return { merged: Object.assign({}, state.defaults, saved), overridden: !!Object.keys(saved).length };
    }

    function loadTemplate() {
        const { merged, overridden } = currentTemplate();
        el.titlePattern.value = merged.titlePattern || '';
        el.defaultAuthor.value = merged.author || '';
        el.publishDay.value = merged.publishDay || 15;
        // `closing` is the old key for this field, kept so a per-device override
        // saved before the rename still loads.
        el.standingByline.value = merged.byline || merged.closing || '';
        el.templateStatus.textContent = overridden
            ? 'Edited on this device' : 'From template.json';
        return merged;
    }

    function templateFromForm() {
        return {
            titlePattern: el.titlePattern.value.trim(),
            author: el.defaultAuthor.value.trim(),
            publishDay: Math.min(28, Math.max(1, parseInt(el.publishDay.value, 10) || 15)),
            categories: Array.from(state.selected),
            byline: el.standingByline.value.trim()
        };
    }

    function saveTemplate() {
        try {
            localStorage.setItem(TEMPLATE_KEY, JSON.stringify(templateFromForm()));
            el.templateStatus.textContent = 'Edited on this device';
            toast('Saved for this browser');
        } catch (e) {
            toast('Could not save — browser storage is blocked');
        }
    }

    /* Write the template back out so the change can be committed and picked up
       by every other machine, rather than living in one browser forever. */
    function exportTemplate() {
        const data = Object.assign(
            { _comment: state.defaults._comment || '' }, templateFromForm());
        download(new Blob([JSON.stringify(data, null, 2) + '\n'],
            { type: 'application/json' }), 'template.json');
        toast('Replace publisher/template.json with this, then commit');
    }

    const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
        'August', 'September', 'October', 'November', 'December'];

    /* The first slot on or after today that no post already occupies. Lets you
       queue several months in one sitting without picking dates by hand. */
    function nextOpenSlot(day) {
        const taken = new Set(state.posts.map(p => String(p.date).slice(0, 7)));
        const now = new Date();
        let year = now.getFullYear(), month = now.getMonth();
        if (now.getDate() >= day) month += 1;
        for (let i = 0; i < 36; i++) {
            const y = year + Math.floor(month / 12);
            const m = ((month % 12) + 12) % 12;
            const key = y + '-' + String(m + 1).padStart(2, '0');
            if (!taken.has(key)) {
                return { year: y, month: m, iso: key + '-' + String(day).padStart(2, '0') };
            }
            month += 1;
        }
        return { year: year, month: month % 12, iso: todayISO() };
    }

    function startNextMonth() {
        const template = loadTemplate();
        const day = Math.min(28, Math.max(1, parseInt(el.publishDay.value, 10) || 15));
        const slot = nextOpenSlot(day);
        const seriesCount = state.posts.filter(p => p.local).length + 1;
        const pattern = el.titlePattern.value.trim();

        el.pubDate.value = slot.iso;
        el.author.value = el.defaultAuthor.value.trim();

        // An empty pattern is the deliberate setting, not a missing one: it
        // means "write a real headline this month". Everything else is filled
        // in, and the cursor lands on the one field only you can write.
        if (pattern) {
            el.title.value = pattern
                .replace(/\{month\}/g, MONTHS[slot.month])
                .replace(/\{month_short\}/g, MONTHS[slot.month].slice(0, 3))
                .replace(/\{year\}/g, slot.year)
                .replace(/\{n\}/g, seriesCount);
            el.slug.value = T.slugify(el.title.value);
        } else {
            el.title.value = '';
            el.slug.value = '';
        }

        state.selected.clear();
        (template.categories || []).forEach(c => state.selected.add(c));
        renderCategories();

        (pattern ? el.body : el.title).focus();
        toast('Ready for ' + MONTHS[slot.month] + ' ' + slot.year);
        render();
    }

    // ------------------------------------------------------------- edit mode

    /* Only posts whose body actually lives on this site. A gated post has no
       content here — the membership plugin on flaneyassociates.com holds it —
       so offering it for editing would look like the edit silently failed. */
    function editablePosts() {
        return state.posts.filter(p => !p.gated)
            .sort((a, b) => String(b.date).localeCompare(String(a.date)));
    }

    function renderPostPicker() {
        const posts = editablePosts();
        el.editPost.innerHTML = '<option value="">— choose an article —</option>' +
            posts.map(p => `<option value="${T.esc(p.slug)}">${T.esc(T.stripTags(p.title))}` +
                `  (${T.fmtDate(p.date)})</option>`).join('');
    }

    function setMode(mode) {
        const editing = mode === 'edit';
        document.querySelectorAll('#modeTabs .tab').forEach(t =>
            t.classList.toggle('on', t.dataset.mode === mode));
        el.editPicker.hidden = !editing;
        el.startNextMonth.disabled = editing;

        if (!editing) {
            state.editing = null;
            state.originalImage = '';
            el.editPost.value = '';
            el.editNotice.hidden = true;
            el.slug.readOnly = false;
            el.pubDate.readOnly = false;
            el.deletePost.hidden = true;
            el.slugLockNote.hidden = true;
            el.dateLockNote.hidden = true;
            el.generate.textContent = 'Generate the publish bundle';
            clearForm();
        }
        render();
    }

    /* Load a published post back into the form.
       The URL and the date stay put: changing a live slug breaks every link
       already pointing at it and strands the old page, and a correction is not
       a republication — bumping the date would shove a typo fix to the top of
       the archive and the homepage. */
    /* The body to edit is the one on the published page, not posts.json's.
       posts.json stores the raw WordPress markup — shortcodes, editor cruft and
       all — and generate_blog.py runs clean() over it at render time. Loading
       that raw source would show you markup you never wrote and, on saving,
       replace the cleaned article with a differently-cleaned one. The rendered
       page is the authoritative cleaned text. */
    function loadBody(post) {
        return fetch('../blog/' + post.slug + '.html?x=' + Date.now())
            .then(r => r.ok ? r.text() : Promise.reject(new Error('page not found')))
            .then(function (html) {
                const doc = new DOMParser().parseFromString(html, 'text/html');
                const el = doc.querySelector('.article-body');
                if (!el) throw new Error('no article body');
                return el.innerHTML.trim();
            })
            .catch(() => T.parseBody(post.content || ''));
    }

    function loadPostForEditing(slug) {
        const post = state.posts.find(p => p.slug === slug);
        if (!post) return;

        state.editing = post;
        state.originalImage = post.local_image || '';
        clearImage();
        state.pdfUpload = null;

        el.title.value = T.stripTags(post.title);
        el.slug.value = post.slug;
        el.pubDate.value = String(post.date).slice(0, 10);
        el.author.value = post.author || '';
        el.body.value = '';
        loadBody(post).then(function (body) {
            el.body.value = body;
            render();
        });
        el.summary.value = post.summary || post.excerpt || '';
        el.imageAlt.value = post.image_alt || '';

        el.slug.readOnly = true;
        el.pubDate.readOnly = true;
        el.deletePost.hidden = false;
        el.slugLockNote.hidden = false;
        el.dateLockNote.hidden = false;
        el.generate.textContent = 'Rebuild the bundle for this post';

        state.selected.clear();
        (post.categories || []).forEach(c => state.selected.add(c));
        renderCategories();

        // The PDF is rebuilt from the edited text so the download can never
        // contradict the corrected page.
        const wanted = post.pdf ? 'auto' : 'none';
        document.querySelectorAll('input[name=pdfSource]').forEach(function (radio) {
            radio.checked = radio.value === wanted;
            radio.dispatchEvent(new Event('change', { bubbles: true }));
        });

        const bits = [];
        if (post.local) bits.push('Written in the publisher.');
        else bits.push('Imported from flaneyassociates.com — saving marks it as edited here, ' +
            'so a later <code>extract_blog.py</code> refresh will not undo your change.');
        if (state.originalImage) {
            bits.push('It already has an image (<code>' + T.esc(state.originalImage) +
                '</code>). Leave the image box empty to keep it.');
        }
        notice(el.editNotice, 'warn', bits.join(' '));

        toast('Loaded — the URL and date stay as published');
        render();
    }

    function clearForm() {
        ['title', 'slug', 'body', 'summary', 'imageAlt'].forEach(id => { el[id].value = ''; });
        clearImage();
        state.pdfUpload = null;
        state.bundle = null;
        el.pdfUploadInfo.hidden = true;
        el.generateFeedback.innerHTML = '';
        el.fileList.innerHTML = '<li><span class="path">Nothing generated yet</span></li>';
        el.bundleActions.hidden = true;
        el.commitBlock.hidden = true;
        state.selected.clear();
        (currentTemplate().merged.categories || []).forEach(c => state.selected.add(c));
        renderCategories();
    }

    // -------------------------------------------------------------- categories

    function renderCategories() {
        el.categoryChips.innerHTML = '';
        state.categories.forEach(function (name) {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'chip' + (state.selected.has(name) ? ' on' : '');
            chip.textContent = name;
            chip.addEventListener('click', function () {
                if (state.selected.has(name)) state.selected.delete(name);
                else state.selected.add(name);
                renderCategories();
                render();
            });
            el.categoryChips.appendChild(chip);
        });

        const add = document.createElement('button');
        add.type = 'button';
        add.className = 'chip chip-add';
        add.textContent = '+ New category';
        add.addEventListener('click', function () {
            const name = (prompt('Category name') || '').trim();
            if (!name) return;
            if (state.categories.indexOf(name) === -1) {
                state.categories.push(name);
                state.categories.sort();
            }
            state.selected.add(name);
            renderCategories();
            render();
        });
        el.categoryChips.appendChild(add);
    }

    // ----------------------------------------------------------- post assembly

    function currentPost() {
        const editing = state.editing;
        const title = el.title.value.trim();
        const slug = editing ? editing.slug : (el.slug.value.trim() || T.slugify(title));
        const byline = el.standingByline.value.trim();

        let content = T.parseBody(el.body.value);
        // Only sign a new post. An edited body already carries whatever sign-off
        // it was published with, so appending again would duplicate it.
        if (!editing && byline && content) {
            // <em> rather than a class: clean() in generate_blog.py strips class
            // attributes, so styling that way would vanish on the first
            // regeneration. An inline tag survives, and toBlocks() carries the
            // italics through to the PDF as well.
            content += '\n<p><em>' + T.esc(byline) + '</em></p>';
        }

        const cats = Array.from(state.selected);
        const words = T.countWords(content);
        const summary = el.summary.value.trim() || T.summarise(content, title);
        const wantsPdf = document.querySelector('input[name=pdfSource]:checked').value !== 'none';

        // A replacement image reuses extract_blog.py's naming, so the file lands
        // exactly where the rest of the pipeline expects it. With no new upload,
        // an edited post keeps the image it already has.
        let localImage = editing ? (editing.local_image || '') : '';
        let socialImage = editing ? (editing.image || '') : '';
        if (state.image) {
            localImage = slug.slice(0, 80) + state.image.ext;
            socialImage = T.SITE + '/blog/images/' + localImage;
        }

        return Object.assign({}, editing || {}, {
            id: editing ? editing.id
                : state.posts.reduce((max, p) => Math.max(max, p.id || 0), 16000) + 1,
            slug: slug,
            // Keep a published post's date verbatim — a correction is not a
            // republication, and re-dating it would shove a typo fix to the top
            // of the archive and into the homepage strip.
            date: editing ? editing.date : (el.pubDate.value || todayISO()) + 'T09:00:00',
            modified: todayISO() + 'T09:00:00',
            link: editing ? editing.link : T.SITE + '/blog/' + slug + '.html',
            title: title,
            excerpt: summary,
            content: content,
            gated: false,
            words: words,
            categories: cats,
            author: el.author.value.trim() || 'Joshua Otaigbe',
            image: socialImage,
            image_alt: el.imageAlt.value.trim(),
            local_image: localImage,
            pdf: wantsPdf ? 'articles/' + slug + '.pdf' : '',
            summary: summary,
            local: editing ? !!editing.local : true,
            // Tells extract_blog.py this post is owned here now, so a refresh
            // from the WordPress API will not quietly undo the edit.
            edited: editing ? true : undefined
        });
    }

    // ---------------------------------------------------------------- preview

    /* An iframe written with srcdoc resolves relative URLs against this page,
       so blog-relative paths land in publisher/ and 404. Repoint them, then
       swap the post's own image for the blob it only exists as until the
       bundle is unpacked. */
    function fixPreviewPaths(html, post) {
        html = html.split('src="images/').join('src="../blog/images/');
        if (state.image) {
            html = html.split('../blog/images/' + post.local_image).join(state.image.url);
        }
        return html;
    }

    /* An empty form renders an empty article — a date, the PDF box and the
       author bio, with no headline and no text. That reads as a broken preview
       rather than an empty one, and cost a real author a long detour looking
       for a preview that was in front of them the whole time. Say so instead. */
    function previewPlaceholder() {
        el.previewFrame.srcdoc = `<!DOCTYPE html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="publisher.css"></head>
<body style="background:#f7f9fc">
  <div style="display:grid;place-items:center;min-height:70vh;padding:40px;text-align:center">
    <div style="max-width:34ch">
      <div style="font-size:2.2rem;color:#2d8cf0">&#9670;</div>
      <h3 style="color:#1a3a5c;margin:12px 0 8px">Your article will appear here</h3>
      <p style="color:#555;font-size:0.92rem;line-height:1.65">
        This panel shows the finished page as you write it, using the real
        stylesheet &mdash; what you see here is what publishes.
      </p>
      <p style="color:#888;font-size:0.86rem;line-height:1.65;margin-top:14px">
        Add a title and paste the article in steps 2 and 3, or switch to
        <strong>Edit published</strong> to load a post you have already written.
      </p>
    </div>
  </div>
</body></html>`;
    }

    function previewArticle(post) {
        // Nothing written yet, and no post loaded to edit.
        if (!post.title && !T.stripTags(post.content)) {
            previewPlaceholder();
            return;
        }
        const related = T.pickRelated(post, state.posts, 3);
        let html = fixPreviewPaths(T.article(post, related, state.assets), post);
        // blog.js sits one directory over and would 404 too; it has nothing to
        // do in a preview anyway.
        html = html.replace(/<script src="blog\.js[^"]*"><\/script>/, '');
        el.previewFrame.srcdoc = html;
    }

    function previewCard(post) {
        const card = fixPreviewPaths(T.card(post), post);
        el.cardFrame.srcdoc = `<!DOCTYPE html><html><head>
<link rel="stylesheet" href="../styles.css">
<link rel="stylesheet" href="../blog/blog.css${state.assets.css}">
<style>body{background:transparent;padding:2px}.post-grid{display:block}</style>
</head><body><div class="post-grid">${card}</div></body></html>`;
    }

    const HASHTAGS = {
        'Advanced Materials Engineering': '#MaterialsEngineering',
        'Materials Engineering Innovations': '#MaterialsInnovation',
        'Glasses and Optical Devices': '#Photonics',
        'Sustainable Materials': '#SustainableMaterials',
        'Polymers': '#Polymers',
        'Composites': '#Composites',
        'Nanotechnology': '#Nanotechnology'
    };

    function previewShare(post) {
        const url = T.SITE + '/blog/' + post.slug + '.html';
        el.shareUrl.textContent = url;

        const tags = post.categories
            .map(c => HASHTAGS[c] || '#' + c.replace(/[^A-Za-z0-9]/g, ''))
            .filter((t, i, a) => t.length > 2 && a.indexOf(t) === i)
            .slice(0, 4);

        const parts = [];
        parts.push(post.title || 'Your headline goes here');
        parts.push('');
        parts.push(post.summary || 'A one-paragraph hook — this is what stops the scroll.');
        parts.push('');
        if (post.pdf) {
            parts.push('The full article is on our site, and you can download it as a PDF at the bottom of the page.');
        } else {
            parts.push('The full article is on our site:');
        }
        parts.push('');
        parts.push(url);
        parts.push('');
        parts.push(tags.concat(['#FlaneyAssociates']).join(' '));

        el.shareText.textContent = parts.join('\n');
    }

    function renderStats(post) {
        const scheduled = T.parseDate(post.date) > new Date(todayISO() + 'T23:59:59');
        el.bodyStats.innerHTML =
            `<span class="stat-pill"><strong>${post.words}</strong> words</span>` +
            `<span class="stat-pill"><strong>${T.readTime(post.words)}</strong> min read</span>` +
            `<span class="stat-pill"><strong>${(post.content.match(/<h[234]/g) || []).length}</strong> headings</span>` +
            `<span class="stat-pill"><strong>${(post.content.match(/<li>/g) || []).length}</strong> list items</span>`;
        el.bodyHint.textContent = post.words ? T.readTime(post.words) + ' min read' : 'Paste and go';

        if (state.editing) {
            notice(el.scheduleNotice, 'ok',
                'Revising a published article. It keeps its address and its date of <strong>' +
                T.fmtDate(post.date) + '</strong>, so it stays where it is in the archive ' +
                'rather than being promoted as new. The change is live once you commit.');
        } else if (!el.pubDate.value) {
            el.scheduleNotice.hidden = true;
        } else if (scheduled) {
            notice(el.scheduleNotice, 'info',
                'Scheduled for <strong>' + T.fmtDate(post.date) + '</strong>. Commit the bundle whenever you like — ' +
                'the card stays hidden on the archive and homepage until that morning, then appears on its own. ' +
                'The page itself is reachable at its URL straight away, so you can check it before it goes public.');
        } else {
            notice(el.scheduleNotice, 'ok',
                'Goes live as soon as you commit and push. Dated <strong>' + T.fmtDate(post.date) + '</strong>.');
        }
    }

    let renderTimer;
    function render() {
        if (!state.ready) return;
        clearTimeout(renderTimer);
        renderTimer = setTimeout(function () {
            const post = currentPost();
            renderStats(post);
            previewArticle(post);
            previewCard(post);
            previewShare(post);
            el.slugPreview.innerHTML = 'Page URL: ' + T.SITE + '/blog/<strong>' +
                T.esc(post.slug || '…') + '</strong>.html';
            el.pdfTargetName.textContent = 'articles/' + (post.slug || '<slug>') + '.pdf';
        }, 250);
    }

    // ------------------------------------------------------------- validation

    function validate(post) {
        const problems = [];
        const flag = (input, errorEl, message) => {
            if (message) {
                input.classList.add('invalid');
                errorEl.textContent = message;
                errorEl.hidden = false;
                problems.push(message);
            } else {
                input.classList.remove('invalid');
                errorEl.hidden = true;
            }
        };

        flag(el.title, el.titleError, post.title ? '' : 'Give the article a title.');

        let slugProblem = '';
        if (!post.slug) slugProblem = 'A URL slug is required.';
        else if (!/^[a-z0-9-]+$/.test(post.slug)) slugProblem = 'Use lower-case letters, numbers and hyphens only.';
        else if (!state.editing && state.posts.some(p => p.slug === post.slug)) {
            slugProblem = 'That slug is already used by another post — change it.';
        }
        flag(el.slug, el.slugError, slugProblem);

        flag(el.pubDate, el.categoryError, '');
        if (!post.categories.length) {
            el.categoryError.textContent = 'Choose at least one category.';
            el.categoryError.hidden = false;
            problems.push('category');
        } else {
            el.categoryError.hidden = true;
        }

        flag(el.body, el.bodyError,
            post.words >= 50 ? '' : 'Paste the article — at least a few paragraphs.');

        if (document.querySelector('input[name=pdfSource]:checked').value === 'upload' && !state.pdfUpload) {
            problems.push('Attach the PDF, or switch to generating one.');
            notice(el.pdfUploadInfo, 'err', 'Attach a PDF, or switch back to generating one.');
        }

        return problems;
    }

    // ------------------------------------------------------------ bundle build

    function buildBundle() {
        const post = currentPost();
        const problems = validate(post);
        if (problems.length) {
            notice(el.generateFeedback, 'err',
                'Not ready yet: ' + problems[0] + (problems.length > 1 ? ' (and ' + (problems.length - 1) + ' more above)' : ''));
            return null;
        }

        const files = [];
        const editing = !!state.editing;

        // 1. the article page
        const related = T.pickRelated(post, state.posts, 3);
        files.push({
            name: 'blog/' + post.slug + '.html',
            data: T.article(post, related, state.assets),
            status: editing ? 'replace' : 'new'
        });

        // 2. the featured image
        if (state.image) {
            files.push({
                name: 'blog/images/' + post.local_image,
                data: state.image.bytes,
                status: state.originalImage === post.local_image ? 'replace' : 'new'
            });
        }

        // 3. the gated PDF
        const mode = document.querySelector('input[name=pdfSource]:checked').value;
        let pdfPromise = Promise.resolve(null);
        if (mode === 'upload' && state.pdfUpload) {
            pdfPromise = Promise.resolve(state.pdfUpload.bytes);
        } else if (mode === 'auto') {
            const blob = window.FlaneyPDF.build({
                title: post.title,
                categories: post.categories,
                date: T.fmtDate(post.date),
                dateISO: post.date,
                author: post.author,
                blocks: T.toBlocks(post.content)
            });
            pdfPromise = blob.arrayBuffer().then(b => new Uint8Array(b));
        }

        return pdfPromise.then(function (pdfBytes) {
            if (pdfBytes) {
                files.push({
                    name: post.pdf, data: pdfBytes,
                    status: (editing && state.editing.pdf) ? 'replace' : 'new'
                });
            }

            // 4. posts.json — the entry replaced in place when editing, so the
            // post keeps its position rather than appearing twice.
            const merged = (editing
                ? state.posts.map(p => (p.slug === post.slug ? post : p))
                : state.posts.concat([post])
            ).sort((a, b) => String(b.date).localeCompare(String(a.date)));
            files.push({
                name: 'blog/data/posts.json',
                data: JSON.stringify(merged, null, 1),
                status: 'replace'
            });

            // 5. the regenerated archive
            files.push({
                name: 'blog/index.html',
                data: T.archive(merged, state.assets),
                status: 'replace'
            });

            // 6. the homepage "latest posts" strip
            if (state.homepageHTML) {
                const updated = T.homepage(state.homepageHTML, merged, 6);
                if (updated) {
                    files.push({ name: 'index.html', data: updated, status: 'replace' });
                }
            }

            return { post: post, files: files };
        });
    }

    function renderBundle(bundle) {
        state.bundle = bundle;

        el.fileList.innerHTML = '';
        bundle.files.forEach(function (file) {
            const bytes = typeof file.data === 'string'
                ? new TextEncoder().encode(file.data).length : file.data.length;
            const li = document.createElement('li');
            li.innerHTML = `<span class="tag ${file.status === 'replace' ? 'replace' : ''}">${file.status}</span>` +
                `<span class="path">${T.esc(file.name)}</span>` +
                `<span class="size">${humanSize(bytes)}</span>`;
            const btn = document.createElement('button');
            btn.className = 'btn btn-outline btn-sm';
            btn.type = 'button';
            btn.textContent = 'Save';
            btn.addEventListener('click', function () {
                const blob = typeof file.data === 'string'
                    ? new Blob([file.data], { type: 'text/plain;charset=utf-8' })
                    : new Blob([file.data]);
                download(blob, file.name.split('/').pop());
            });
            li.appendChild(btn);
            el.fileList.appendChild(li);
        });

        el.bundleActions.hidden = false;
        el.commitBlock.hidden = false;
        el.commitCommands.innerHTML = publishCommand();

        document.querySelector('.tab[data-view=files]').click();
    }

    // --------------------------------------------------- direct folder access

    /* Chrome and Edge can grant a page write access to one folder the user
       picks. That removes the whole download-find-unzip dance: pressing
       Generate puts the files where they belong and the only step left is the
       publish script. Safari has no equivalent, so the zip stays as the
       fallback and this whole section simply never activates there. */
    const CAN_WRITE_FOLDER = typeof window.showDirectoryPicker === 'function';

    /* The handle is stored in IndexedDB — it is a live object, not a path, and
       cannot be serialised to localStorage. */
    function idb(mode, fn) {
        return new Promise(function (resolve, reject) {
            const open = indexedDB.open('flaney_publisher', 1);
            open.onupgradeneeded = () => open.result.createObjectStore('handles');
            open.onerror = () => reject(open.error);
            open.onsuccess = function () {
                const db = open.result;
                const store = db.transaction('handles', mode).objectStore('handles');
                const req = fn(store);
                req.onsuccess = () => { resolve(req.result); db.close(); };
                req.onerror = () => { reject(req.error); db.close(); };
            };
        });
    }

    const saveHandle = h => idb('readwrite', s => s.put(h, 'repo'));
    const readHandle = () => idb('readonly', s => s.get('repo')).catch(() => null);

    /* Refuse anything that is not obviously this repository. Writing five files
       into the wrong folder would scatter them somewhere harmless but confusing,
       and the mistake is easy to make in a folder picker. */
    async function looksLikeRepo(dir) {
        const wanted = [['index.html', 'file'], ['blog', 'directory'], ['publisher', 'directory']];
        for (const [name, kind] of wanted) {
            try {
                if (kind === 'file') await dir.getFileHandle(name);
                else await dir.getDirectoryHandle(name);
            } catch (e) {
                return name;
            }
        }
        return null;
    }

    async function ensurePermission(handle) {
        const opts = { mode: 'readwrite' };
        if (await handle.queryPermission(opts) === 'granted') return true;
        return await handle.requestPermission(opts) === 'granted';
    }

    async function chooseFolder() {
        // A remembered folder only needs re-approval after a browser restart —
        // Chrome will not carry write permission across sessions. Ask for that
        // first, so the common case is one click rather than navigating the
        // folder picker again.
        if (state.pendingDir) {
            if (await ensurePermission(state.pendingDir)) {
                state.repoDir = state.pendingDir;
                state.pendingDir = null;
                showFolderStatus();
                toast('Reconnected');
                return;
            }
        }

        let dir;
        try {
            dir = await window.showDirectoryPicker({ mode: 'readwrite' });
        } catch (e) {
            return;   // the picker was dismissed
        }
        const missing = await looksLikeRepo(dir);
        if (missing) {
            notice(el.folderStatus, 'err', 'That folder has no <code>' + T.esc(missing) +
                '</code> in it, so it is not the site repository. Choose the folder that ' +
                'contains <code>index.html</code>, <code>blog</code> and <code>publisher</code>.');
            return;
        }
        if (!await ensurePermission(dir)) {
            notice(el.folderStatus, 'err', 'Chrome did not grant write access, so the files cannot be written for you.');
            return;
        }
        await saveHandle(dir);
        state.repoDir = dir;
        showFolderStatus();
        toast('Connected — Generate now writes straight into the folder');
    }

    async function writeBundleToFolder(files) {
        const dir = state.repoDir;
        if (!dir || !await ensurePermission(dir)) return null;

        for (const file of files) {
            const parts = file.name.split('/');
            const filename = parts.pop();
            let target = dir;
            for (const part of parts) {
                target = await target.getDirectoryHandle(part, { create: true });
            }
            const handle = await target.getFileHandle(filename, { create: true });
            const writable = await handle.createWritable();
            await writable.write(typeof file.data === 'string'
                ? new Blob([file.data], { type: 'text/plain' })
                : new Blob([file.data]));
            await writable.close();
        }
        return files.length;
    }

    function showFolderStatus() {
        if (!CAN_WRITE_FOLDER) {
            notice(el.folderStatus, 'info',
                'This browser cannot write to a folder \u2014 that is Chrome and Edge only. ' +
                'Use <strong>Download all as .zip</strong> instead; the publish script unpacks it for you.');
            el.chooseFolder.hidden = true;
            return;
        }
        if (state.repoDir) {
            notice(el.folderStatus, 'ok', 'Connected to <strong>' + T.esc(state.repoDir.name) +
                '</strong>. Generate writes the files straight in \u2014 no download, no unzipping.');
            el.chooseFolder.textContent = 'Choose a different folder';
        } else if (state.pendingDir) {
            notice(el.folderStatus, 'warn',
                '<strong>' + T.esc(state.pendingDir.name) + '</strong> is remembered, but Chrome ' +
                'drops write permission when it restarts. One click to reconnect \u2014 you will not ' +
                'have to find the folder again.');
            el.chooseFolder.textContent = '\uD83D\uDD11 Reconnect ' + state.pendingDir.name;
        } else {
            notice(el.folderStatus, 'info',
                'Connect your <strong>Flaney_Associates</strong> folder once and Generate will write ' +
                'the files straight into it, with no zip to download or unpack.');
            el.chooseFolder.textContent = '\uD83D\uDCC1 Connect repository folder';
        }
    }

    // ----------------------------------------------------------- deleting

    /* Removing a post needs files deleted, and neither a zip nor a folder write
       can express "delete this". So the bundle carries a manifest that
       publish.sh acts on: it removes the listed paths, then regenerates the
       whole site with generate_blog.py — necessary because other articles carry
       "Related articles" cards pointing at the deleted one, and leaving those
       behind would litter the site with links to a 404. */
    function buildDeleteBundle() {
        const post = state.editing;
        const remaining = state.posts.filter(p => p.slug !== post.slug);

        const doomed = ['blog/' + post.slug + '.html'];
        if (post.local_image) doomed.push('blog/images/' + post.local_image);
        if (post.pdf) doomed.push(post.pdf);

        const files = [
            { name: 'blog/data/posts.json', data: JSON.stringify(remaining, null, 1), status: 'replace' },
            { name: 'blog/index.html', data: T.archive(remaining, state.assets), status: 'replace' }
        ];
        if (state.homepageHTML) {
            const updated = T.homepage(state.homepageHTML, remaining, 6);
            if (updated) files.push({ name: 'index.html', data: updated, status: 'replace' });
        }
        files.push({
            name: '.publish-delete',
            data: doomed.join('\n') + '\n',
            status: 'delete'
        });

        return { post: post, files: files, deleting: doomed };
    }

    function confirmDelete() {
        const post = state.editing;
        if (!post) return;
        const title = T.stripTags(post.title);
        if (!confirm('Delete "' + title + '" permanently?\n\n' +
                'Its page, image and PDF are removed and the URL stops working — ' +
                'any link to it from LinkedIn or Google will 404.\n\n' +
                'Nothing is deleted until you run ./publish.sh.')) return;

        const bundle = buildDeleteBundle();
        renderBundle(bundle);
        notice(el.generateFeedback, 'warn',
            'Ready to delete <strong>' + T.esc(title) + '</strong>. ' +
            (state.repoDir ? 'Files written. ' : 'Download the zip. ') +
            'Nothing is removed until <code>./publish.sh</code> runs.');
        if (state.repoDir) writeBundleToFolder(bundle.files);
        toast('Delete prepared — run ./publish.sh to apply it');
    }

    // ------------------------------------------------------- publish command

    function loadPaths() {
        try { return JSON.parse(localStorage.getItem(PATHS_KEY) || '{}'); } catch (e) { return {}; }
    }

    function savePaths(paths) {
        try { localStorage.setItem(PATHS_KEY, JSON.stringify(paths)); } catch (e) {}
    }

    /* One paste that does the lot: unzip the bundle into the repository, commit
       and push.

       Double-clicking the zip in Finder does NOT work — macOS extracts it into a
       new folder rather than merging it into the repo, so the files land in the
       wrong place. `unzip -o` merges and overwrites without prompting.

       `ls -t | head -1` picks the newest matching download because a second
       download of the same post lands as flaney-<slug>-1.zip, and unzipping the
       older one would quietly publish a stale bundle. */
    function publishCommand() {
        const repo = loadPaths().repo || '<your-repo-folder>';
        const command = 'cd ' + JSON.stringify(repo) + ' && ./publish.sh';

        const hint = loadPaths().repo ? ''
            : '<span class="c"># fill in "Repository folder" in step 1 and this completes itself</span>\n';
        return hint + T.esc(command);
    }

    // ------------------------------------------------------------------ wiring

    function wire() {
        ['title', 'slug', 'pubDate', 'author', 'body', 'summary', 'imageAlt', 'standingByline']
            .forEach(id => el[id].addEventListener('input', render));

        // Keep the slug following the title until the slug is edited by hand.
        let slugTouched = false;
        el.slug.addEventListener('input', () => { slugTouched = true; });
        el.title.addEventListener('input', function () {
            // Never in edit mode: the slug is the published address.
            if (!slugTouched && !state.editing) el.slug.value = T.slugify(el.title.value);
        });

        el.repoPath.value = loadPaths().repo || '';
        el.repoPath.addEventListener('input', function () {
            savePaths({ repo: el.repoPath.value.trim() });
            if (state.bundle) el.commitCommands.innerHTML = publishCommand(state.bundle);
        });

        /* An edited post keeps the excerpt it was published with, which is
           right for a hand-written one and wrong after a rewrite — the card,
           the Google result and the LinkedIn preview all keep the old text. */
        el.regenSummary.addEventListener('click', function () {
            const content = T.parseBody(el.body.value);
            if (!content) { toast('Paste the article first'); return; }
            el.summary.value = T.summarise(content, el.title.value.trim());
            render();
            toast('Excerpt rebuilt from the article');
        });

        /* Capture the formatted clipboard, not the flattened text.
           A <textarea> only ever receives text/plain, and Word, Google Docs and
           most web pages put no line breaks in that flavour — which is how an
           article arrived as two paragraphs of 2,102 and 3,401 characters with
           its headings stranded mid-sentence. The text/html flavour carries the
           real structure: headings, paragraphs, lists, bold, links. fromHTML()
           already knows how to clean it. */
        el.body.addEventListener('paste', function (e) {
            const html = e.clipboardData && e.clipboardData.getData('text/html');
            if (!html || !html.trim()) return;      // plain text: paste normally

            e.preventDefault();
            const cleaned = T.parseBody(html);
            if (!cleaned) return;

            const start = el.body.selectionStart, end = el.body.selectionEnd;
            const value = el.body.value;
            el.body.value = value.slice(0, start) + cleaned + value.slice(end);
            el.body.selectionStart = el.body.selectionEnd = start + cleaned.length;
            el.body.dispatchEvent(new Event('input', { bubbles: true }));

            const headings = (cleaned.match(/<h[234]>/g) || []).length;
            const paras = (cleaned.match(/<p>/g) || []).length;
            notice(el.bodyError, 'ok', 'Formatting kept from your document \u2014 <strong>' +
                headings + ' headings</strong>, ' + paras + ' paragraphs, ' +
                (cleaned.match(/<li>/g) || []).length + ' bullets. The box shows the underlying ' +
                'markup; check the preview on the right, which is what publishes.');
            el.bodyError.hidden = false;
            toast('Kept ' + headings + ' headings from the document');
        });

        el.deletePost.addEventListener('click', confirmDelete);
        el.jumpPreview.addEventListener('click', function () {
            document.querySelector('.preview-column').scrollIntoView({ behavior: 'smooth', block: 'start' });
        });

        el.chooseFolder.addEventListener('click', chooseFolder);
        if (CAN_WRITE_FOLDER) {
            readHandle().then(function (handle) {
                if (!handle) { showFolderStatus(); return; }
                handle.queryPermission({ mode: 'readwrite' }).then(function (p) {
                    // A stored handle needs re-approval after a browser restart;
                    // treat it as connected only once permission is actually held,
                    // but keep it aside so reconnecting is a single click.
                    if (p === 'granted') state.repoDir = handle;
                    else state.pendingDir = handle;
                    showFolderStatus();
                });
            });
        } else {
            showFolderStatus();
        }

        el.saveTemplate.addEventListener('click', saveTemplate);
        el.exportTemplate.addEventListener('click', exportTemplate);
        el.startNextMonth.addEventListener('click', function () {
            slugTouched = false;
            startNextMonth();
        });

        el.resetForm.addEventListener('click', function () {
            if (!confirm('Clear the form? The saved monthly template is kept.')) return;
            slugTouched = false;
            setMode('new');
        });

        document.querySelectorAll('#modeTabs .tab').forEach(function (tab) {
            tab.addEventListener('click', function () {
                if (tab.dataset.mode === 'edit' && !state.editing && el.body.value.trim() &&
                    !confirm('Switch to editing a published post? The draft in the form is lost.')) {
                    return;
                }
                slugTouched = false;
                setMode(tab.dataset.mode);
            });
        });

        el.editPost.addEventListener('change', function () {
            if (el.editPost.value) loadPostForEditing(el.editPost.value);
        });

        // --- tabs
        document.querySelectorAll('.tab').forEach(function (tab) {
            tab.addEventListener('click', function () {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('on'));
                tab.classList.add('on');
                document.querySelectorAll('.viewport').forEach(function (v) {
                    v.classList.toggle('on', v.dataset.view === tab.dataset.view);
                });
            });
        });

        // --- copy buttons
        document.querySelectorAll('[data-copy]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const text = $(btn.dataset.copy).textContent;
                navigator.clipboard.writeText(text)
                    .then(() => toast('Copied to clipboard'))
                    .catch(() => toast('Copy failed — select the text instead'));
            });
        });

        // --- image
        el.imageInput.addEventListener('change', e => acceptImage(e.target.files[0]));
        el.imageRemove.addEventListener('click', function (e) {
            e.preventDefault();
            clearImage();
            render();
        });
        dropTarget(el.imageDrop, acceptImage);

        // --- pdf
        document.querySelectorAll('input[name=pdfSource]').forEach(function (radio) {
            radio.addEventListener('change', function () {
                document.querySelectorAll('.choice-option').forEach(function (opt) {
                    opt.classList.toggle('on', opt.querySelector('input').checked);
                });
                el.pdfUploadWrap.hidden = radio.value !== 'upload';
                render();
            });
        });
        el.pdfInput.addEventListener('change', e => acceptPdf(e.target.files[0]));
        dropTarget(el.pdfDrop, acceptPdf);

        // --- generate
        el.generate.addEventListener('click', function () {
            el.generateFeedback.innerHTML = '';
            el.generate.disabled = true;
            el.generate.textContent = 'Building…';

            Promise.resolve()
                .then(buildBundle)
                .then(function (bundle) {
                    if (!bundle) return;
                    renderBundle(bundle);
                    if (!state.repoDir) {
                        notice(el.generateFeedback, 'ok',
                            'Bundle ready — <strong>' + bundle.files.length + ' files</strong>. ' +
                            'Open the <strong>Files</strong> tab to download them.');
                        toast('Bundle ready');
                        return;
                    }
                    // Folder connected: put the files where they belong instead
                    // of making the author download and unpack them.
                    return writeBundleToFolder(bundle.files).then(function (written) {
                        if (written === null) {
                            notice(el.generateFeedback, 'warn',
                                'Could not write to the folder — permission was withdrawn. ' +
                                'Reconnect it, or use <strong>Download all as .zip</strong>.');
                            return;
                        }
                        notice(el.generateFeedback, 'ok',
                            '<strong>' + written + ' files written</strong> into ' +
                            T.esc(state.repoDir.name) + '. Now run <code>./publish.sh</code> ' +
                            'in Terminal — that is the whole last step.');
                        toast(written + ' files written into the folder');
                    });
                })
                .catch(function (err) {
                    notice(el.generateFeedback, 'err', 'Something went wrong: ' + T.esc(err.message));
                    console.error(err);
                })
                .finally(function () {
                    el.generate.disabled = false;
                    el.generate.textContent = 'Generate the publish bundle';
                });
        });

        el.downloadZip.addEventListener('click', function () {
            if (!state.bundle) return;
            const blob = window.FlaneyZip.build(state.bundle.files.map(f => ({ name: f.name, data: f.data })));
            download(blob, 'flaney-' + state.bundle.post.slug + '.zip');
            toast('Downloaded — unzip over the repository root');
        });
    }

    function dropTarget(node, accept) {
        ['dragenter', 'dragover'].forEach(type => node.addEventListener(type, function (e) {
            e.preventDefault();
            node.classList.add('over');
        }));
        ['dragleave', 'drop'].forEach(type => node.addEventListener(type, function (e) {
            e.preventDefault();
            node.classList.remove('over');
        }));
        node.addEventListener('drop', function (e) {
            if (e.dataTransfer.files.length) accept(e.dataTransfer.files[0]);
        });
    }

    const IMAGE_EXT = { 'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'image/gif': '.gif' };

    //: The article renders its hero image in a 760px column, so anything wider
    //: than this buys nothing on screen and costs load time. 1600 keeps it sharp
    //: on a retina display at 2x.
    const MAX_IMAGE_WIDTH = 1600;
    const JPEG_QUALITY = 0.85;

    /* Photographs saved as PNG are enormous — the first image published through
       this dashboard was 1.8 MB, over three times the size of anything else on
       the blog, and it was a photo in a PNG wrapper. Re-encoding it as JPEG at
       1600px brought it to 254 KB with no visible difference at display size.

       JPEG cannot represent transparency, so a PNG that uses it stays a PNG. */
    function hasTransparency(ctx, w, h) {
        const data = ctx.getImageData(0, 0, w, h).data;
        for (let i = 3; i < data.length; i += 4) {
            if (data[i] < 250) return true;
        }
        return false;
    }

    function optimiseImage(file, bytes) {
        // An animated GIF would be flattened to its first frame, so leave it be.
        if (file.type === 'image/gif') return Promise.resolve(null);

        return new Promise(function (resolve) {
            const url = URL.createObjectURL(new Blob([bytes], { type: file.type }));
            const img = new Image();

            img.onload = function () {
                const scale = Math.min(1, MAX_IMAGE_WIDTH / img.naturalWidth);
                const w = Math.round(img.naturalWidth * scale);
                const h = Math.round(img.naturalHeight * scale);

                const canvas = document.createElement('canvas');
                canvas.width = w;
                canvas.height = h;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, w, h);

                const keepAlpha = file.type === 'image/png' && hasTransparency(ctx, w, h);
                const type = keepAlpha ? 'image/png' : 'image/jpeg';

                canvas.toBlob(function (blob) {
                    URL.revokeObjectURL(url);
                    // Re-encoding can make a small flat graphic bigger. Never
                    // hand back something worse than what was given.
                    if (!blob || blob.size >= bytes.length) { resolve(null); return; }
                    blob.arrayBuffer().then(function (buf) {
                        resolve({
                            bytes: new Uint8Array(buf),
                            type: type,
                            ext: type === 'image/png' ? '.png' : '.jpg',
                            width: w, height: h,
                            from: bytes.length,
                            fromWidth: img.naturalWidth
                        });
                    });
                }, type, JPEG_QUALITY);
            };

            img.onerror = function () { URL.revokeObjectURL(url); resolve(null); };
            img.src = url;
        });
    }

    function acceptImage(file) {
        if (!file) return;
        if (!IMAGE_EXT[file.type]) { toast('Use a JPG, PNG, WebP or GIF'); return; }

        readFile(file)
            .then(bytes => optimiseImage(file, bytes).then(better => ({ bytes, better })))
            .then(function (result) {
                const better = result.better;
                const bytes = better ? better.bytes : result.bytes;
                const type = better ? better.type : file.type;
                const ext = better ? better.ext : IMAGE_EXT[file.type];

                if (state.image) URL.revokeObjectURL(state.image.url);
                state.image = {
                    name: file.name,
                    ext: ext,
                    type: type,
                    bytes: bytes,
                    url: URL.createObjectURL(new Blob([bytes], { type: type }))
                };

                el.imagePreview.src = state.image.url;
                el.imageName.textContent = file.name;
                el.imageSize.textContent = better
                    ? humanSize(better.from) + ' \u2192 ' + humanSize(bytes.length)
                    : humanSize(bytes.length);
                el.imageThumb.classList.add('on');
                if (!el.imageAlt.value.trim()) el.imageAlt.value = el.title.value.trim();

                if (better) {
                    toast('Resized to ' + better.width + 'px \u2014 ' +
                        humanSize(better.from) + ' down to ' + humanSize(bytes.length));
                }
                render();
            });
    }

    function clearImage() {
        if (state.image) URL.revokeObjectURL(state.image.url);
        state.image = null;
        el.imageInput.value = '';
        el.imagePreview.removeAttribute('src');
        el.imageThumb.classList.remove('on');
    }

    function acceptPdf(file) {
        if (!file) return;
        if (file.type !== 'application/pdf') { toast('That is not a PDF'); return; }
        readFile(file).then(function (bytes) {
            state.pdfUpload = { name: file.name, bytes: bytes };
            notice(el.pdfUploadInfo, 'ok',
                'Using <strong>' + T.esc(file.name) + '</strong> (' + humanSize(bytes.length) + ').');
            render();
        });
    }

    // -------------------------------------------------------------- the queue

    function renderQueue() {
        const today = todayISO();
        const upcoming = state.posts
            .filter(p => String(p.date).slice(0, 10) > today)
            .sort((a, b) => String(a.date).localeCompare(String(b.date)));

        el.queueList.innerHTML = '';
        if (!upcoming.length) {
            el.queueList.innerHTML = '<li><span class="empty">Nothing scheduled — the next post you date in the future will show up here.</span></li>';
            el.queueHint.textContent = '';
            return;
        }
        el.queueHint.textContent = upcoming.length + ' waiting';
        upcoming.forEach(function (p) {
            const li = document.createElement('li');
            li.innerHTML = `<span class="when">${T.fmtDate(p.date)}</span>` +
                `<span class="what">${T.esc(T.stripTags(p.title))}</span>`;
            el.queueList.appendChild(li);
        });
    }

    // ------------------------------------------------------------------- boot

    /* Always re-fetch the site's own data. These files change every time a post
       is published, and a cached copy means the dashboard quietly works from a
       stale archive — offering a slug that is already taken, or leaving a
       just-published post out of the edit list.

       `cache: 'reload'`, not `'no-cache'`. The latter only revalidates, and a
       conditional request answered with 304 hands back the cached body: measured
       against this site, 'no-cache' returned 55 posts where the file held 56.
       'reload' bypasses the cache outright, which is what is actually wanted for
       a file that is small and changes on every publish. */
    function fresh(url) {
        return fetch(url, { cache: 'reload' });
    }

    /* Reuse whatever ?v= the deployed archive is already using. Recomputing a
       hash here would disagree with generate_blog.py's md5 and churn the URLs
       on every publish. */
    function readAssetVersions(html) {
        const css = html.match(/blog\.css(\?v=[a-z0-9]+)?/);
        const js = html.match(/blog\.js(\?v=[a-z0-9]+)?/);
        const lead = html.match(/lead-capture\.js(\?v=[a-z0-9]+)?/);
        // styles.css is stamped too — head() in generate_blog.py appends
        // asset_version("styles.css"), and a bundle written without it would be
        // rewritten by the next Python run. Anchored on the slash so it cannot
        // match publisher.css or any other *styles.css.
        const site = html.match(/\/styles\.css(\?v=[a-z0-9]+)?/);
        return {
            css: (css && css[1]) || '',
            js: (js && js[1]) || '',
            lead: (lead && lead[1]) || '',
            site: (site && site[1]) || ''
        };
    }

    function boot() {
        Promise.all([
            fresh('../blog/data/posts.json').then(r => r.json()),
            fresh('../blog/index.html').then(r => r.text()),
            fresh('../index.html').then(r => r.text()),
            // Optional: the dashboard still works on localStorage alone.
            fresh('template.json').then(r => r.ok ? r.json() : {}).catch(() => ({})),
            // Required, unlike template.json: a missing base URL would put the
            // wrong canonical into every article page this dashboard writes.
            // Same barrier as posts.json, so nothing renders before it lands.
            fresh('../site.json').then(r => r.json())
        ]).then(function (results) {
            T.setSite(results[4].base_url);
            state.posts = results[0];
            state.assets = readAssetVersions(results[1]);
            state.homepageHTML = results[2];
            state.defaults = results[3] || {};

            state.categories = Array.from(new Set(
                state.posts.flatMap(p => p.categories || [])
                    .concat(state.defaults.categories || [])
            )).sort();

            const template = loadTemplate();
            (template.categories || []).forEach(c => state.selected.add(c));
            renderCategories();
            renderQueue();
            renderPostPicker();

            el.author.value = el.defaultAuthor.value;
            el.pubDate.value = nextOpenSlot(
                Math.min(28, Math.max(1, parseInt(el.publishDay.value, 10) || 15))).iso;
            el.dateHelp.textContent = 'Posts dated ahead stay hidden until that day.';

            state.ready = true;
            render();
        }).catch(function (err) {
            state.ready = false;
            notice(el.generateFeedback, 'err',
                'Could not read the site files. The dashboard needs a local server — run ' +
                '<code>python3 -m http.server 8000</code> in the repository root and open ' +
                '<code>http://localhost:8000/publisher/</code>. (' + T.esc(err.message) + ')');
            console.error(err);
        });
    }

    loadTemplate();
    wire();
    boot();
})();
