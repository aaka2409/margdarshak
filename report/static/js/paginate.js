/* Lays the report out into fixed A4 pages inside the browser, before printing.
 *
 * The template emits two kinds of things:
 *   <div class="page">            a finished page (cover, charts, cards ...)
 *   <section class="flow">        running text that has to be poured into as many
 *                                 pages as it needs, two columns per page
 *
 * A flow is  <template class="flow-first"> (what sits on its first page: the
 * section header and anything above the columns)  +  <div class="flow-source">
 * (the blocks to pour).  Blocks are placed one by one and measured, so a page
 * is never over- or under-filled; paragraphs are split between columns and
 * pages on word boundaries, headings stay with the text that follows them.
 *
 * When everything is placed: pages are numbered, the contents page gets its
 * page numbers, fixed pages are checked for overflow, and window.__report
 * tells the Python side what happened.
 */
(function () {
  "use strict";
  const PT = 96 / 72;                       // CSS px per pt
  const COL_BOTTOM = 763.2;                   // pt from page top: lowest edge of body text
  const CONT_TOP = 65.2;                    // pt: top of the columns on continuation pages
  const problems = [];

  const px = (pt) => pt * PT;
  const pagePt = (el, page) => (el.getBoundingClientRect().bottom - page.getBoundingClientRect().top) / PT;

  /* ---------------------------------------------------------------- page shell */
  function newPage(flow, first) {
    const shell = document.getElementById("page-shell").content.firstElementChild.cloneNode(true);
    shell.querySelector(".running .txt").textContent = flow.dataset.running || "";
    if (flow.dataset.pageClass) shell.classList.add(...flow.dataset.pageClass.split(" "));
    const cols = document.createElement("div");
    cols.className = "cols prose " + (flow.dataset.cols === "1" ? "one " : "") + (flow.dataset.textClass || "");
    const count = flow.dataset.cols === "1" ? 1 : 2;
    for (let i = 0; i < count; i++) {
      const c = document.createElement("div");
      c.className = "col";
      cols.appendChild(c);
    }
    let top = CONT_TOP;
    if (first) {
      const head = flow.querySelector("template.flow-first");
      if (head) shell.appendChild(head.content.cloneNode(true));
    }
    shell.appendChild(cols);
    flow.parentNode.insertBefore(shell, flow);
    if (first) {
      const pre = shell.querySelector(".pre");
      if (pre) top = pagePt(pre, shell);
    }
    cols.style.top = top + "pt";
    cols.style.height = (COL_BOTTOM - top) + "pt";
    return { page: shell, cols, columns: Array.from(cols.children), top };
  }

  /* ---------------------------------------------------------------- paragraph splitting */
  function tokenize(html) {                  // words and tags, in order
    return html.match(/<[^>]+>|[^<\s]+|\s+/g) || [];
  }
  function joinUpTo(tokens, wordCount) {     // first `wordCount` words, tags balanced
    let out = "", words = 0, open = [], i = 0;
    for (; i < tokens.length; i++) {
      const t = tokens[i];
      if (t[0] === "<") {
        if (t[1] === "/") open.pop(); else if (!/\/>$/.test(t)) open.push(t);
        out += t;
      } else if (/^\s+$/.test(t)) {
        out += " ";
      } else {
        if (words === wordCount) break;
        out += t; words++;
      }
    }
    const closing = open.slice().reverse().map((t) => "</" + t.replace(/^<(\w+).*$/, "$1") + ">").join("");
    const rest = open.join("") + tokens.slice(i).join("");
    return { head: out.replace(/\s+$/, "") + closing, rest: rest.replace(/^\s+/, ""), open };
  }
  function countWords(tokens) {
    return tokens.filter((t) => t[0] !== "<" && !/^\s+$/.test(t)).length;
  }
  function lineHeight(el) {
    const lh = parseFloat(getComputedStyle(el).lineHeight);
    return isNaN(lh) ? parseFloat(getComputedStyle(el).fontSize) * 1.5 : lh;
  }

  /* Try to keep the start of paragraph `p` (already appended to `col`) within `limit` (px from
     the column top).  Returns the remainder element, or null when not even the minimum fits. */
  function splitParagraph(p, col, limit, keep) {
    if (p.dataset.nosplit !== undefined || p.tagName !== "P") return null;
    const full = p.innerHTML;
    const tokens = tokenize(full);
    const total = countWords(tokens);
    const lh = lineHeight(p);
    const colTop = col.getBoundingClientRect().top;
    const topOf = () => p.getBoundingClientRect().top - colTop;
    const bottomWith = (k) => { p.innerHTML = joinUpTo(tokens, k).head; return p.getBoundingClientRect().bottom - colTop; };
    const minLines = p.classList.contains("has-dc") ? 4 : 2;   // fewest lines left behind (orphans)
    const room = Math.floor((limit - topOf() + 0.5) / lh);
    if (room < minLines) { p.innerHTML = full; return null; }

    let lo = 1, hi = total - 1, best = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (bottomWith(mid) <= limit + 0.5) { best = mid; lo = mid + 1; } else hi = mid - 1;
    }
    if (!best) { p.innerHTML = full; return null; }
    // lines left for the remainder; if it would be a single line, pull one line back
    const linesOf = (k) => Math.round((bottomWith(k) - topOf()) / lh);
    let headLines = linesOf(best);
    const restEl = () => {
      const r = p.cloneNode(false);
      r.classList.remove("has-dc");
      r.classList.add("cont");
      r.innerHTML = joinUpTo(tokens, best).rest;
      return r;
    };
    const probe = restEl();
    p.innerHTML = joinUpTo(tokens, best).head;
    col.appendChild(probe);
    const restLines = Math.round(probe.getBoundingClientRect().height / lh);
    col.removeChild(probe);
    if (restLines < keep) {
      const target = headLines - (keep - restLines);
      if (target < minLines) { p.innerHTML = full; return null; }
      while (best > 1 && linesOf(best) > target) best--;
      headLines = target;
    }
    if (headLines < minLines) { p.innerHTML = full; return null; }
    const parts = joinUpTo(tokens, best);
    p.innerHTML = parts.head;
    p.classList.add("split-head");            // last line of a split paragraph is justified like the rest
    const rest = p.cloneNode(false);
    rest.classList.remove("has-dc", "split-head");
    rest.classList.add("cont");
    rest.innerHTML = parts.rest;
    return rest;
  }

  /* ---------------------------------------------------------------- filling */
  /* `keep` = fewest lines of a paragraph carried over a break (widows): 3 into the next column of
     the same page, 2 across a page turn, as in the approved design. */
  function fillColumn(col, queue, limit, keep) {
    const colTop = () => col.getBoundingClientRect().top;
    while (queue.length) {
      const node = queue[0];
      col.appendChild(node);
      if (node.getBoundingClientRect().bottom - colTop() <= limit + 0.5) { queue.shift(); continue; }
      const rest = splitParagraph(node, col, limit, keep);
      if (rest) queue[0] = rest; else col.removeChild(node);
      // a heading must not be left alone at the foot of a column
      if (col.children.length && Array.from(col.children).every((c) => c.dataset.keep !== undefined)) {
        return "overflow";                    // only headings are here and the next block fits nowhere
      }
      while (col.lastElementChild && col.lastElementChild.dataset.keep !== undefined) {
        queue.unshift(col.lastElementChild);
        col.removeChild(col.lastElementChild);
      }
      if (!col.children.length) {             // nothing fits even in an empty column: place it and report
        const forced = queue.shift();
        col.appendChild(forced);
        if (forced.getBoundingClientRect().bottom - colTop() > limit + 0.5) return "overflow";
        continue;
      }
      return "full";
    }
    return "done";
  }
  function fillPage(columns, queue, limit) {
    let state = "done";
    for (let i = 0; i < columns.length; i++) {
      const col = columns[i];
      state = fillColumn(col, queue, limit, i === columns.length - 1 ? 2 : 3);
      if (state === "overflow") return state;
      if (!queue.length) return "done";
    }
    return queue.length ? "full" : "done";
  }
  const cloneAll = (nodes) => nodes.map((x) => x.cloneNode(true));
  const empty = (columns) => columns.forEach((c) => { c.textContent = ""; });

  /* Pour one flow at a given body-text scale.  Returns the pages it made. */
  function pourOnce(flow, scale) {
    const source = flow.querySelector(".flow-source");
    let queue = cloneAll(Array.from(source.children));
    const balance = flow.dataset.balance !== "off" && flow.dataset.cols !== "1";
    let first = true, guard = 0;
    const made = [], issues = [];
    while (queue.length && guard++ < 60) {
      const pg = newPage(flow, first);
      if (scale !== 1) pg.cols.style.setProperty("--tight", String(scale));
      first = false;
      made.push(pg);
      const limit = px(COL_BOTTOM - pg.top);
      const snapshot = cloneAll(queue);
      const state = fillPage(pg.columns, queue, limit);
      if (state === "overflow") issues.push("a block is taller than a page column in “" + (flow.dataset.running || "") + "”");
      if (!queue.length && balance && pg.columns.length === 2) {
        // last page of the flow: even out the two columns
        let lo = px(24), hi = limit, bestH = limit;
        for (let i = 0; i < 12 && hi - lo > 2; i++) {
          const mid = (lo + hi) / 2;
          empty(pg.columns);
          const q = cloneAll(snapshot);
          const s = fillPage(pg.columns, q, mid);
          if (s === "done" && !q.length) { bestH = mid; hi = mid; } else lo = mid;
        }
        empty(pg.columns);
        fillPage(pg.columns, cloneAll(snapshot), bestH);
      }
    }
    if (guard >= 60) issues.push("flow “" + (flow.dataset.running || "") + "” did not finish paginating");
    return { made, issues };
  }

  /* A section that runs a few lines onto an extra page is reset slightly smaller (2%, 4%, at most 6%)
     when that brings it back onto one page fewer, as the approved design does.  Headings keep
     their size; nothing is ever cut. */
  function pourFlow(flow) {
    let best = pourOnce(flow, 1);
    if (best.made.length > 1 && flow.dataset.tighten !== "off") {
      const pages = best.made.length;
      const used = (pg) => pg.columns.reduce((sum, c) => sum + (c.lastElementChild
        ? c.lastElementChild.getBoundingClientRect().bottom - c.getBoundingClientRect().top : 0), 0);
      const spill = used(best.made[pages - 1]);
      const before = best.made.slice(0, -1).reduce((sum, pg) => sum + used(pg), 0);
      // text set s times smaller needs about s*s of the height (less where columns had slack); only try what can plausibly work
      const scales = [0.98, 0.96, 0.94].filter((s) => spill <= before * (1 - s * s) * 2.2);
      if (scales.length) {
        const drop = (r) => r.made.forEach((pg) => pg.page.remove());
        drop(best);
        best = null;
        for (const scale of scales) {
          const attempt = pourOnce(flow, scale);
          if (attempt.made.length < pages && !attempt.issues.length) { best = attempt; break; }
          drop(attempt);
        }
        if (!best) best = pourOnce(flow, 1);
      }
    }
    problems.push(...best.issues);
    if (best.made.length) addTail(flow, best.made[best.made.length - 1]);
    flow.remove();
  }

  /* Ornament in the empty space under the last column, as in the design. */
  function addTail(flow, pg) {
    if (flow.dataset.tail === "none") return;
    let end = 0;
    pg.columns.forEach((c) => { if (c.lastElementChild) end = Math.max(end, pagePt(c.lastElementChild, pg.page)); });
    const floor = 783;                       // footer rule
    const gap = floor - end;
    let tpl = null;
    if (gap >= 150) tpl = document.getElementById("tail-moon");
    else if (gap >= 70) tpl = document.getElementById("tail-star");
    if (!tpl) return;
    const el = tpl.content.firstElementChild.cloneNode(true);
    pg.page.appendChild(el);
    const h = el.getBoundingClientRect().height / PT;
    const centre = gap > 300 ? end + gap * 0.55 : end + gap / 2;
    el.style.top = (centre - h / 2) + "pt";
  }

  /* ---------------------------------------------------------------- fixed pages */
  function fitFixedPages() {
    document.querySelectorAll(".page[data-fit]").forEach((page) => {
      const checks = Array.from(page.querySelectorAll("[data-within],[data-max-bottom]"));
      const ok = () => checks.every((el) => {
        const r = el.getBoundingClientRect();
        if (el.dataset.maxBottom) return pagePt(el, page) <= parseFloat(el.dataset.maxBottom) + 0.5;
        const box = el.closest(el.dataset.within).getBoundingClientRect();
        const pad = px(parseFloat(el.dataset.pad || "8"));
        return r.top >= box.top + pad - 0.5 && r.bottom <= box.bottom - pad + 0.5;
      });
      /* a block marked data-own-fit shrinks alone first, so one long intro does not shrink the whole page */
      const one = (el) => {
        const r = el.getBoundingClientRect();
        if (el.dataset.maxBottom) return pagePt(el, page) <= parseFloat(el.dataset.maxBottom) + 0.5;
        return true;
      };
      checks.filter((el) => el.hasAttribute("data-own-fit")).forEach((el) => {
        let f = 1;
        while (!one(el) && f > 0.74) { f -= 0.02; el.style.setProperty("--fit", f.toFixed(2)); }
      });
      let fit = 1;
      while (!ok() && fit > 0.74) { fit -= 0.02; page.style.setProperty("--fit", fit.toFixed(2)); }
      if (!ok()) problems.push("text does not fit on the “" + (page.dataset.fit || "fixed") + "” page");
    });
  }

  /* ---------------------------------------------------------------- numbering */
  function numberPages() {
    const pages = Array.from(document.querySelectorAll(".page"));
    const first = {};
    pages.forEach((p, i) => {
      const folio = p.querySelector(".footer .folio");
      if (folio) folio.textContent = String(i + 1).padStart(2, "0");
      if (p.dataset.toc && !(p.dataset.toc in first)) first[p.dataset.toc] = i + 1;
    });
    document.querySelectorAll("[data-toc-ref]").forEach((el) => {
      const pg = first[el.dataset.tocRef];
      if (pg) el.textContent = pg; else problems.push("contents entry “" + el.dataset.tocRef + "” has no page");
    });
    return pages.length;
  }

  async function run() {
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await Promise.all(Array.from(document.images).map((img) => img.complete ? null :
      new Promise((res) => { img.onload = img.onerror = res; })));
    document.querySelectorAll("section.flow").forEach(pourFlow);
    fitFixedPages();
    const count = numberPages();
    // artwork cloned into the poured pages starts loading only now
    await Promise.all(Array.from(document.images).map((img) => img.complete ? null :
      new Promise((res) => { img.onload = img.onerror = res; })));
    document.querySelectorAll("img").forEach((img) => { if (!img.naturalWidth) problems.push("image failed to load: " + img.getAttribute("src")); });
    const fontsOk = ["400 12px 'Cormorant Garamond'", "400 12px 'DM Sans'", "500 12px 'Noto Serif Devanagari'"]
      .every((f) => document.fonts.check(f, f.indexOf("Devanagari") > 0 ? "म" : "a"));
    if (!fontsOk) problems.push("a report font failed to load");
    window.__report = { pages: count, problems };
  }
  window.__paginate = run().catch((e) => { window.__report = { pages: 0, problems: ["layout script error: " + e.message] }; });
})();
