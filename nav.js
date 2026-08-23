/* Shared page chrome: navbar scroll state, the mobile drawer, anchor scrolling
 * and the fade-in observer.
 *
 * Split out of script.js when the site grew from one page to fourteen. The
 * homepage loads this and then script.js, which now holds only what is unique
 * to it (the consultation form and the scheduled-post strip). Blog article
 * pages keep their own copy inside blog/blog.js and do not load this file —
 * binding both would toggle the drawer twice per tap and leave it shut.
 *
 * Dropdown menus are not here: they are in lead-capture.js, which every page
 * including the blog loads. See initNavDropdowns().
 */

// ===== NAVBAR =====
const navbar = document.getElementById('navbar');
if (navbar && !navbar.classList.contains('navbar-solid')) {
    window.addEventListener('scroll', () => {
        navbar.classList.toggle('scrolled', window.scrollY > 50);
    });
}

// ===== MOBILE DRAWER =====
const navToggle = document.getElementById('navToggle');
const navLinks = document.getElementById('navLinks');

if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => navLinks.classList.toggle('active'));

    // A dropdown parent opens its own submenu inside the drawer, so closing the
    // drawer on that tap would shut the menu the visitor just opened.
    navLinks.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => navLinks.classList.remove('active'));
    });

    document.addEventListener('click', e => {
        if (!navToggle.contains(e.target) && !navLinks.contains(e.target)) {
            navLinks.classList.remove('active');
        }
    });
}

// ===== ANCHOR SCROLLING =====
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const href = this.getAttribute('href');

        // querySelector('#') throws, so a bare hash is handled before it is
        // ever used as a selector — it means "back to the top".
        if (!href || href === '#') {
            e.preventDefault();
            window.scrollTo({ top: 0, behavior: 'smooth' });
            return;
        }

        const target = document.querySelector(href);
        if (!target) return;   // let the browser deal with an anchor we don't have
        e.preventDefault();
        window.scrollTo({ top: target.getBoundingClientRect().top + window.scrollY - 80,
                          behavior: 'smooth' });
    });
});

// ===== SCROLL ANIMATIONS =====
const revealObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
        revealObserver.unobserve(entry.target);
    });
}, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

document.querySelectorAll(
    '.service-card, .expertise-card, .industry-card, .process-step, .blog-card,' +
    '.problem-card, .cred-card, .audience-card'
).forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    revealObserver.observe(el);
});
