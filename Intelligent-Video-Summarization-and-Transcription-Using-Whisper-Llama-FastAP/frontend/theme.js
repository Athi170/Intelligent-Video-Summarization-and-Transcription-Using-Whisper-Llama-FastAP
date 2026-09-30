/* Light/dark theme: applies the saved (or system) theme immediately, then adds a toggle button. */
(function () {
  var KEY = "theme", root = document.documentElement, saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  var mq = window.matchMedia("(prefers-color-scheme: dark)");
  root.setAttribute("data-theme", saved || (mq.matches ? "dark" : "light"));

  var SUN = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  var MOON = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';

  var css = ".theme-toggle{display:inline-grid;place-items:center;width:40px;height:40px;padding:0;border-radius:50%;cursor:pointer;" +
    "background:var(--card,#fff)!important;color:var(--text,#14192e)!important;border:1px solid var(--line,#dfe3ee)!important;transition:transform .15s}" +
    ".theme-toggle:hover{transform:rotate(18deg)}.theme-toggle:focus-visible{outline:3px solid var(--accent,#3846e8);outline-offset:2px}" +
    ".theme-toggle.fixed{position:fixed;top:16px;right:16px;z-index:50}";
  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  function apply(theme, persist) {
    root.setAttribute("data-theme", theme);
    if (persist) { try { localStorage.setItem(KEY, theme); } catch (e) {} }
    var b = document.getElementById("themeToggle");
    if (b) {
      b.innerHTML = theme === "dark" ? SUN : MOON;
      b.setAttribute("aria-label", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
      b.title = b.getAttribute("aria-label");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var b = document.createElement("button");
    b.type = "button"; b.id = "themeToggle"; b.className = "theme-toggle";
    var bar = document.getElementById("userBar");
    if (bar) { bar.insertBefore(b, bar.firstChild); } else { b.className += " fixed"; document.body.appendChild(b); }
    b.addEventListener("click", function () {
      apply(root.getAttribute("data-theme") === "dark" ? "light" : "dark", true);
    });
    apply(root.getAttribute("data-theme"), false);
  });

  // Follow the system setting until the person makes their own choice.
  mq.addEventListener && mq.addEventListener("change", function (e) {
    var s = null; try { s = localStorage.getItem(KEY); } catch (x) {}
    if (!s) apply(e.matches ? "dark" : "light", false);
  });
})();
