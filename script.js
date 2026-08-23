/* Homepage behaviour.
 *
 * Three files load on the homepage, in this order:
 *   lead-capture.js  email validation, the Formsubmit bridge, the gated PDF
 *                    modal, and the nav dropdowns — everything shared with the
 *                    blog and the service pages.
 *   nav.js           navbar scroll state, the mobile drawer, anchor scrolling
 *                    and the fade-in observer.
 *   script.js        this file: the consultation form and the blog strip.
 *
 * The nav code used to live here. It moved to nav.js when the site grew past a
 * single page; note that both files run in the same global scope, so anything
 * re-declared here with `const` would be a SyntaxError, not a shadow.
 */

// ===== SCHEDULED POSTS =====
// Future-dated cards in the "latest from the blog" strip stay hidden until
// their publication date. See hideScheduledCards() in lead-capture.js.
hideScheduledCards();


// ===== ENQUIRY FORM =====
/* One handler for three forms: the homepage consultation form, contact.html
 * and attorney-inquiry.html. They differ only in which fields they carry, which
 * inbox they route to and what the subject line says, so those three things are
 * declared on the <form> element rather than forked in here.
 *
 * data-inbox is a key into LEAD_INBOXES in lead-capture.js, not an address —
 * an address in the markup could be edited into a redirect to somewhere else.
 */
const form = document.getElementById('contactForm');
if (form) {
    // Set the _next redirect to current page
    const nextInput = form.querySelector('input[name="_next"]');
    if (nextInput) nextInput.value = window.location.href;

    form.addEventListener('submit', function (e) {
        e.preventDefault();

        // Validate email first
        const emailInput = document.getElementById('contactEmail');
        const emailResult = validateEmail(emailInput.value);
        if (!emailResult.valid) {
            emailInput.focus();
            const fb = document.getElementById('contactEmailFeedback');
            fb.classList.remove('valid');
            fb.classList.add('invalid');
            fb.textContent = emailResult.message || 'Please enter a valid email';
            return;
        }

        const btn = form.querySelector('button[type="submit"]');
        const originalText = btn.textContent;
        btn.textContent = 'Sending...';
        btn.disabled = true;

        const field = name => {
            const el = form.querySelector('[name="' + name + '"]');
            return el ? el.value.trim() : '';
        };

        const formData = {
            name: field('name'),
            email: emailInput.value.trim(),
            company: field('company'),
            role: field('role'),
            service: field('service'),
            matter: field('matter'),
            parties: field('parties'),
            message: field('message')
        };

        sendToFormsubmit(formData,
                         form.dataset.subject || 'New Enquiry — Flaney Associates',
                         form.dataset.inbox)
            .then(res => {
                if (res.ok) {
                    btn.textContent = 'Request Sent!';
                    btn.style.background = '#22c55e';
                    form.reset();
                    // Clear validation states
                    emailInput.classList.remove('email-valid', 'email-invalid');
                    document.getElementById('contactEmailFeedback').textContent = '';
                } else {
                    btn.textContent = 'Error — Try Again';
                    btn.style.background = '#ef4444';
                }
            })
            .catch(() => {
                btn.textContent = 'Error — Try Again';
                btn.style.background = '#ef4444';
            })
            .finally(() => {
                setTimeout(() => {
                    btn.textContent = originalText;
                    btn.style.background = '';
                    btn.disabled = false;
                }, 3000);
            });
    });

    attachEmailValidation('contactEmail', 'contactEmailFeedback');
}
