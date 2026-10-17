/* AIPrOoHub site features: dark mode, mobile menu, search, widgets */
(function () {
  "use strict";
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };

  /* ---- Dark mode ---- */
  var themeBtn = $("#theme-toggle");
  function setTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    try { localStorage.setItem("aiproohub-theme", t); } catch (e) {}
    if (themeBtn) themeBtn.textContent = t === "dark" ? "☀️" : "🌙";
  }
  var saved = null;
  try { saved = localStorage.getItem("aiproohub-theme"); } catch (e) {}
  setTheme(saved || "light");
  if (themeBtn) themeBtn.addEventListener("click", function () {
    setTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark");
  });

  /* ---- Mobile menu ---- */
  var burger = $("#menu-toggle"), navLinks = $(".nav-links");
  if (burger && navLinks) burger.addEventListener("click", function () {
    navLinks.classList.toggle("open");
    burger.setAttribute("aria-expanded", navLinks.classList.contains("open") ? "true" : "false");
  });

  /* ---- Scroll progress + back to top ---- */
  var prog = $("#scroll-progress"), toTop = $("#back-to-top");
  function onScroll() {
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    var pct = max > 0 ? (h.scrollTop / max) * 100 : 0;
    if (prog) prog.style.width = pct + "%";
    if (toTop) toTop.classList.toggle("show", h.scrollTop > 600);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  if (toTop) toTop.addEventListener("click", function () {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  /* ---- Fade-in on scroll ---- */
  var faders = $$(".fade-in");
  if ("IntersectionObserver" in window && faders.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("visible"); io.unobserve(e.target); }
      });
    }, { threshold: 0.08 });
    faders.forEach(function (el) { io.observe(el); });
  } else {
    faders.forEach(function (el) { el.classList.add("visible"); });
  }

  /* ---- Site search ---- */
  var overlay = $("#search-overlay"), searchInput = $("#search-input"), resultsBox = $("#search-results");
  var index = null;
  function openSearch() { if (overlay) { overlay.classList.add("open"); if (searchInput) { searchInput.value = ""; renderResults(""); searchInput.focus(); } } }
  function closeSearch() { if (overlay) overlay.classList.remove("open"); }
  var searchBtn = $("#search-toggle");
  if (searchBtn) searchBtn.addEventListener("click", openSearch);
  if (overlay) overlay.addEventListener("click", function (e) { if (e.target === overlay) closeSearch(); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeSearch();
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openSearch(); }
  });
  function renderResults(q) {
    if (!resultsBox) return;
    q = q.trim().toLowerCase();
    if (!index) { resultsBox.innerHTML = '<p class="search-hint">Loading…</p>'; return; }
    if (!q) { resultsBox.innerHTML = '<p class="search-hint">Type to search 30 guides and the prompt pack. Tip: press Ctrl+K anywhere.</p>'; return; }
    var hits = index.filter(function (p) {
      return (p.title + " " + p.desc + " " + p.keywords).toLowerCase().indexOf(q) !== -1;
    }).slice(0, 8);
    if (!hits.length) { resultsBox.innerHTML = '<p class="search-hint">No matches — try "listing", "ads", or "email".</p>'; return; }
    resultsBox.innerHTML = hits.map(function (p) {
      return '<a href="' + p.url + '"><span class="sr-title">' + p.title + '</span><br><span class="sr-desc">' + p.desc + '</span></a>';
    }).join("");
  }
  if (searchInput) {
    searchInput.addEventListener("input", function () { renderResults(searchInput.value); });
    fetch("/search-index.json").then(function (r) { return r.json(); }).then(function (d) {
      index = d; renderResults(searchInput.value || "");
    }).catch(function () {
      if (resultsBox) resultsBox.innerHTML = '<p class="search-hint">Search is unavailable right now.</p>';
    });
  }

  /* ---- Newsletter signup (success state; ESP wiring pending) ---- */
  $$(".newsletter-form").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var email = form.querySelector('input[type="email"]');
      if (!email || !email.value || email.value.indexOf("@") < 0) {
        email.focus();
        return;
      }
      /* TODO: POST to ESP endpoint (e.g. MailerLite) when connected. */
      var wrap = form.closest(".newsletter-wrap") || form.parentElement;
      var ok = wrap ? wrap.querySelector(".newsletter-success") : null;
      if (ok) { form.style.display = "none"; ok.classList.add("show"); }
    });
  });

  /* ---- Copy buttons for code snippets (present + future) ---- */
  $$("pre").forEach(function (pre) {
    if (pre.querySelector(".copy-btn")) return;
    var btn = document.createElement("button");
    btn.className = "copy-btn";
    btn.type = "button";
    btn.textContent = "Copy";
    btn.addEventListener("click", function () {
      var code = pre.querySelector("code");
      var text = code ? code.innerText : pre.innerText.replace(/^Copy/, "");
      function done() { btn.textContent = "Copied ✓"; setTimeout(function () { btn.textContent = "Copy"; }, 1500); }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(done);
      } else {
        var ta = document.createElement("textarea");
        ta.value = text; document.body.appendChild(ta); ta.select();
        try { document.execCommand("copy"); } catch (e) {}
        document.body.removeChild(ta); done();
      }
    });
    pre.insertBefore(btn, pre.firstChild);
  });
})();
