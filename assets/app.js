/* course-exam-review — 交互 */
(function () {
  "use strict";

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  /* ------------------------------------------------------------ print mode */
  const params = new URLSearchParams(location.search);
  const printMode = params.get("print") === "1";
  if (printMode) {
    document.documentElement.classList.add("printing");
    $$("details").forEach((d) => { d.open = true; });
  }

  /* ------------------------------------------------------------ progress */
  const progress = $("#progress");
  const toTop = $("#to-top");
  function onScroll() {
    const h = document.documentElement;
    const max = h.scrollHeight - h.clientHeight;
    const pct = max > 0 ? (h.scrollTop / max) * 100 : 0;
    if (progress) progress.style.width = pct + "%";
    if (toTop) toTop.classList.toggle("show", h.scrollTop > 600);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  if (toTop) {
    toTop.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
  }

  /* ------------------------------------------------------------ toc active */
  const tocLinks = new Map();
  $$("#toc a[href^='#']").forEach((a) => {
    const id = a.getAttribute("href").slice(1);
    if (!tocLinks.has(id)) tocLinks.set(id, []);
    tocLinks.get(id).push(a);
  });

  const targets = $$(".chapter-title, .content h2");
  if ("IntersectionObserver" in window) {
    const visible = new Set();
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) visible.add(e.target.id);
          else visible.delete(e.target.id);
        });
        // pick the first visible target in document order
        let activeId = null;
        for (const t of targets) {
          if (visible.has(t.id)) { activeId = t.id; break; }
        }
        if (!activeId && targets.length) {
          // fallback: nearest above viewport
          for (const t of targets) {
            if (t.getBoundingClientRect().top < 120) activeId = t.id;
          }
        }
        $$("#toc a.active").forEach((a) => a.classList.remove("active"));
        if (activeId && tocLinks.has(activeId)) {
          tocLinks.get(activeId).forEach((a) => a.classList.add("active"));
          const first = tocLinks.get(activeId)[0];
          if (first) {
            const box = first.closest(".toc");
            if (box && first.offsetTop < box.scrollTop) box.scrollTop = first.offsetTop - 20;
          }
        }
      },
      { rootMargin: "-12% 0px -72% 0px", threshold: 0 }
    );
    targets.forEach((t) => io.observe(t));
  }

  /* ------------------------------------------------------------ search */
  const search = $("#search");
  if (search) {
    const groups = $$(".toc-group");
    const apply = () => {
      const q = search.value.trim().toLowerCase();
      groups.forEach((g) => {
        const links = $$("a", g);
        let any = false;
        links.forEach((a) => {
          a.classList.remove("search-hit");
          const hit = !q || a.textContent.toLowerCase().includes(q);
          if (a.classList.contains("toc-sub-link")) {
            a.classList.toggle("hidden", !hit);
          }
          if (hit) any = true;
          if (q && hit && a.classList.contains("toc-sub-link")) a.classList.add("search-hit");
        });
        // chapter link: match on its own text, or any visible sub-link
        const chapter = $(".toc-chapter", g);
        const chapterHit = chapter && (!q || chapter.textContent.toLowerCase().includes(q));
        g.classList.toggle("hidden", !!q && !chapterHit && !any);
        if (chapter) chapter.classList.toggle("hidden", !!q && !chapterHit && !any);
      });
      // dim non-matching chapters
      $$(".chapter").forEach((ch) => {
        if (!q) { ch.classList.remove("search-dim"); return; }
        const text = ch.textContent.toLowerCase();
        ch.classList.toggle("search-dim", !text.includes(q));
      });
    };
    search.addEventListener("input", apply);
    search.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const first = $(".toc-group:not(.hidden) .toc-sub-link:not(.hidden), .toc-group:not(.hidden) .toc-chapter");
        if (first) first.click();
      }
      if (e.key === "Escape") { search.value = ""; apply(); search.blur(); }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "/" && document.activeElement !== search && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        search.focus();
      }
    });
  }

  /* ------------------------------------------------------------ answers */
  const answersBtn = $("#answers-btn");
  if (answersBtn) {
    answersBtn.addEventListener("click", () => {
      const all = $$("details.answer");
      const anyClosed = all.some((d) => !d.open);
      all.forEach((d) => { d.open = anyClosed; });
      answersBtn.textContent = anyClosed ? "收起全部答案" : "展开全部答案";
    });
  }

  /* ------------------------------------------------------------ print */
  const printBtn = $("#print-btn");
  if (printBtn) printBtn.addEventListener("click", () => window.print());

  let reopened = [];
  window.addEventListener("beforeprint", () => {
    reopened = [];
    $$("details.answer").forEach((d) => {
      if (!d.open) { d.open = true; reopened.push(d); }
    });
  });
  window.addEventListener("afterprint", () => {
    reopened.forEach((d) => { d.open = false; });
    reopened = [];
  });
})();
