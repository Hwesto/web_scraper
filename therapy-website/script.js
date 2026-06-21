/* Progressive enhancement — the site works fully without JS. */
(function () {
  "use strict";

  // Mobile navigation toggle
  var toggle = document.querySelector(".nav-toggle");
  var menu = document.getElementById("nav-menu");
  if (toggle && menu) {
    toggle.addEventListener("click", function () {
      var open = menu.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    // Close the menu after choosing a link (mobile)
    menu.addEventListener("click", function (e) {
      if (e.target.tagName === "A" && menu.classList.contains("open")) {
        menu.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  // Current year in footer
  var yearEl = document.getElementById("year");
  if (yearEl) { yearEl.textContent = String(new Date().getFullYear()); }

  // Contact form — client-side validation + friendly status message.
  // NOTE: wire `action` to a real handler (Formspree, Netlify Forms, etc.)
  // before going live. Until then this just confirms the message locally.
  var form = document.querySelector(".contact-form");
  if (form) {
    var status = form.querySelector(".form-status");
    form.addEventListener("submit", function (e) {
      if (!form.checkValidity()) { return; } // let the browser show native errors
      if (form.getAttribute("action") === "#") {
        e.preventDefault();
        if (status) {
          status.textContent =
            "Thanks — your message is ready. Connect this form to your email/form service to start receiving enquiries.";
        }
        form.reset();
      }
    });
  }
})();
