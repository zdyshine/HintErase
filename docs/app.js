/* HintErase project page.
 * Every case is ONE video with its rows (Input, Hint, HintErase, baselines...)
 * stacked vertically. A Player draws two of those rows side by side on a
 * canvas, with the two chosen rows drawn side by side, so compared views are always in sync.
 */
(function () {
  "use strict";
  const M = window.HINTERASE_MANIFEST || { cases: [], categories: [] };
  const byId = Object.fromEntries(M.cases.map((c) => [c.id, c]));
  // Language helpers from i18n.js; without it the page stays in English.
  const I = window.HE_I18N || {
    lang: "en", t: (k) => ({ divider: "Comparison divider", play: "Play", pause: "Pause", prevFrame: "Previous frame",
      nextFrame: "Next frame", frameSlider: "Frame", frame: "frame", left: "Left", right: "Right", leftView: "Left view",
      rightView: "Right view", shotCut: "shot cut", copy: "Copy", copied: "Copied", selected: "Selected",
      overviewTitle: "HintErase overview video" })[k] || k,
    row: (l) => l, field: (o, n) => (o && o[n]) || "", onChange: () => {},
  };
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const ICON = {
    play: '<svg viewBox="0 0 16 16"><path d="M4 2.5v11l9-5.5z"/></svg>',
    pause: '<svg viewBox="0 0 16 16"><path d="M3.5 2.5h3v11h-3zM9.5 2.5h3v11h-3z"/></svg>',
    prev: '<svg viewBox="0 0 16 16"><path d="M3 2.5h2v11H3zM13 2.5v11L6 8z"/></svg>',
    next: '<svg viewBox="0 0 16 16"><path d="M11 2.5h2v11h-2zM3 2.5v11L10 8z"/></svg>',
  };
  const pad = (n, w) => String(n).padStart(w, "0");
  function timecode(frame, fps) {
    const f = Math.round(fps) || 25;
    const s = Math.floor(frame / f);
    return `${pad(Math.floor(s / 3600), 2)}:${pad(Math.floor(s / 60) % 60, 2)}:${pad(s % 60, 2)}:${pad(frame % f, 2)}`;
  }
  function el(tag, attrs, html) {
    const e = document.createElement(tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (html != null) e.innerHTML = html;
    return e;
  }

  class Player {
    constructor(root, opts) {
      this.opts = Object.assign({ autoplay: true, intro: false }, opts);
      this.split = 0.5;
      this.root = root;
      root.classList.add("player");
      root.innerHTML = "";
      // Side-by-side comparison: the two chosen views are drawn next to each other on one canvas.
      this.stage = el("div", { class: "stage sbs", tabindex: "0", role: "group" });
      this.canvas = el("canvas");
      this.ctx = this.canvas.getContext("2d");
      this.lblL = el("span", { class: "lbl l" });
      this.lblR = el("span", { class: "lbl r" });
      this.big = el("button", { class: "bigplay", type: "button" }, ICON.play);
      this.stage.append(this.canvas, this.lblL, this.lblR, this.big);

      const controls = el("div", { class: "controls" });
      this.btnPlay = el("button", { class: "ctl", type: "button" }, ICON.play);
      this.btnPrev = el("button", { class: "ctl step", type: "button" }, ICON.prev);
      this.btnNext = el("button", { class: "ctl step", type: "button" }, ICON.next);
      this.scrub = el("input", { class: "scrub", type: "range", min: "0", max: "0", value: "0", step: "1" });
      this.setAria();
      this.tc = el("div", { class: "tc", "aria-live": "off" });
      controls.append(this.btnPlay, this.btnPrev, this.btnNext, this.scrub, this.tc);

      this.pairs = el("div", { class: "pairs" });
      root.append(this.stage, controls, this.pairs);

      this.video = document.createElement("video");
      Object.assign(this.video, { muted: true, loop: true, playsInline: true, preload: "none" });
      this.video.setAttribute("muted", "");
      this.video.setAttribute("playsinline", "");
      this.poster = new Image();
      this.poster.onload = () => this.draw();

      this.bind();
    }

    bind() {
      this.stage.addEventListener("keydown", (e) => {
        if (e.key === " " || e.key === "k") { this.toggle(); e.preventDefault(); }
        else if (e.key === ",") this.step(-1);
        else if (e.key === ".") this.step(1);
      });
      this.big.addEventListener("click", () => this.play());
      this.stage.addEventListener("click", (e) => { if (!e.target.closest(".bigplay")) this.toggle(); });
      this.btnPlay.addEventListener("click", () => this.toggle());
      this.btnPrev.addEventListener("click", () => this.step(-1));
      this.btnNext.addEventListener("click", () => this.step(1));
      this.scrub.addEventListener("input", () => {
        this.ensureSrc(); this.pause();
        this.video.currentTime = (Number(this.scrub.value) + 0.5) / this.c.fps;
      });
      const v = this.video;
      v.addEventListener("loadeddata", () => { this.root.classList.remove("loading"); this.draw(); });
      v.addEventListener("seeked", () => this.draw());
      v.addEventListener("play", () => { this.syncButtons(); this.loop(); });
      v.addEventListener("pause", () => this.syncButtons());

      if ("IntersectionObserver" in window) {
        new IntersectionObserver((ents) => {
          ents.forEach((en) => {
            this.visible = en.isIntersecting;
            if (en.isIntersecting && this.opts.autoplay && !reduceMotion && !this.userPaused) this.play();
            else if (!en.isIntersecting) this.video.pause();
          });
        }, { threshold: 0.35 }).observe(this.root);
      }
    }

    setAria() {
      this.stage.setAttribute("aria-label", I.t("divider"));
      this.big.setAttribute("aria-label", I.t("play"));
      this.btnPrev.setAttribute("aria-label", I.t("prevFrame"));
      this.btnNext.setAttribute("aria-label", I.t("nextFrame"));
      this.scrub.setAttribute("aria-label", I.t("frameSlider"));
    }

    // Re-render every piece of text after a language switch, without reloading the video.
    relabel() {
      this.setAria();
      if (!this.c) return;
      this.renderPairs();
      this.syncButtons();
      this.updateTc();
    }

    load(c) {
      this.c = c;
      this.video.pause();
      this.video.removeAttribute("src");
      this.video.load();
      this.srcSet = false;
      this.userPaused = false;
      this.gap = Math.max(4, Math.round(c.w * 0.012));
      this.canvas.width = 2 * c.w + this.gap; this.canvas.height = c.h;
      this.scrub.max = String(Math.max(0, c.frames - 1));
      this.scrub.value = "0";
      this.left = c.left; this.right = c.right;
      this.poster.src = c.poster;
      this.renderPairs();
      this.lblR.style.left = `calc(${((c.w + this.gap) / (2 * c.w + this.gap)) * 100}% + 10px)`;
      this.draw();
      this.syncButtons();
      this.updateTc();
      if (this.visible && this.opts.autoplay && !reduceMotion) this.play();
    }

    ensureSrc() {
      if (this.srcSet) return;
      this.srcSet = true;
      this.root.classList.add("loading");
      this.video.preload = "auto";
      this.video.src = this.c.video;
    }

    play() {
      this.ensureSrc();
      this.userPaused = false;
      const p = this.video.play();
      if (p && p.catch) p.catch(() => this.syncButtons());
    }
    pause() { this.video.pause(); }
    toggle() {
      if (this.video.paused) this.play();
      else { this.userPaused = true; this.pause(); }
    }
    step(d) {
      this.ensureSrc(); this.userPaused = true; this.pause();
      const f = Math.min(this.c.frames - 1, Math.max(0, this.frame() + d));
      this.video.currentTime = (f + 0.5) / this.c.fps;
    }
    frame() { return Math.min(this.c.frames - 1, Math.floor(this.video.currentTime * this.c.fps)); }

    syncButtons() {
      const playing = !this.video.paused;
      this.btnPlay.innerHTML = playing ? ICON.pause : ICON.play;
      this.btnPlay.setAttribute("aria-label", I.t(playing ? "pause" : "play"));
      this.big.hidden = playing || (this.srcSet && this.video.currentTime > 0);
    }

    loop() {
      const v = this.video;
      if (v.requestVideoFrameCallback) {
        const cb = () => { this.draw(); if (!v.paused) v.requestVideoFrameCallback(cb); };
        v.requestVideoFrameCallback(cb);
      } else {
        const cb = () => { this.draw(); if (!v.paused) requestAnimationFrame(cb); };
        requestAnimationFrame(cb);
      }
    }

    draw() {
      const c = this.c;
      if (!c) return;
      const src = this.video.readyState >= 2 ? this.video : (this.poster.complete && this.poster.naturalWidth ? this.poster : null);
      const { w, h } = c;
      const li = Math.max(0, c.rows.indexOf(this.left));
      const ri = Math.max(0, c.rows.indexOf(this.right));
      const W = this.canvas.width, g = this.gap;
      if (!src) { this.ctx.fillStyle = "#0d0f13"; this.ctx.fillRect(0, 0, W, h); return; }
      this.ctx.fillStyle = "#0d0f13"; this.ctx.fillRect(w, 0, g, h);
      this.ctx.drawImage(src, 0, li * h, w, h, 0, 0, w, h);
      this.ctx.drawImage(src, 0, ri * h, w, h, w + g, 0, w, h);
      this.updateTc();
    }

    updateTc() {
      const c = this.c;
      const f = this.srcSet ? Math.max(0, this.frame()) : 0;
      if (document.activeElement !== this.scrub) this.scrub.value = String(f);
      const src = (c.src_frame || 0) + f;
      this.tc.innerHTML = `<b>${timecode(src, c.fps)}</b><br><span class="tc-frame">${I.t("frame")} ${pad(src, 6)}</span>`;
    }

    renderPairs() {
      const c = this.c;
      this.pairs.innerHTML = "";
      // Row labels stay in English internally (they index the stacked video); only the display is translated.
      const group = (side, label, view) => {
        const g = el("div", { class: "pair", role: "group", "aria-label": view });
        g.append(el("span", null, label));
        c.rows.forEach((r) => {
          const b = el("button", { class: "chip" + (r === "Hint" ? " is-hint" : ""), type: "button" });
          b.textContent = I.row(r);
          b.setAttribute("aria-pressed", String(this[side] === r));
          b.addEventListener("click", () => {
            this[side] = r;
            g.querySelectorAll(".chip").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
            this.updateLabels(); this.draw();
          });
          g.append(b);
        });
        return g;
      };
      this.pairs.append(group("left", I.t("left"), I.t("leftView")), group("right", I.t("right"), I.t("rightView")));
      this.updateLabels();
    }
    updateLabels() {
      this.lblL.textContent = I.row(this.left);
      this.lblR.textContent = I.row(this.right);
      this.lblL.classList.toggle("hint", this.left === "Hint");
      this.lblR.classList.toggle("hint", this.right === "Hint");
    }
  }

  /* ---------------------------------------------------------------- page */
  if (M.placeholder) document.getElementById("placeholder-banner").hidden = false;

  const players = [];
  const heroCase = byId[M.hero] || M.cases[0];
  if (heroCase) {
    const hero = new Player(document.getElementById("hero-player"), { intro: true });
    hero.load(heroCase);
    players.push(hero);
  }

  // The Ultra-HD section is text-only unless a case is configured: the sample footage shows
  // identifiable people, so it is not published. With `uhd` set in cases.json and a
  // #uhd-player container in the page, the player comes back without any change here.
  const uhdCase = M.uhd && byId[M.uhd];
  const uhdHost = document.getElementById("uhd-player");
  if (uhdCase && uhdHost) {
    const uhd = new Player(uhdHost);
    uhd.load(uhdCase);
    players.push(uhd);
  }

  const gallery = new Player(document.getElementById("gallery-player"));
  players.push(gallery);
  const tabs = document.getElementById("cat-tabs");
  const list = document.getElementById("case-list");
  let currentCat = null;
  let currentCase = null;

  function showCase(c) {
    currentCase = c;
    document.getElementById("case-title").textContent = I.field(c, "title");
    document.getElementById("case-note").textContent = I.field(c, "note");
    list.querySelectorAll(".case-btn").forEach((b) => b.setAttribute("aria-current", String(b.dataset.id === c.id)));
    gallery.load(c);
  }
  function showCat(cat, caseId) {
    currentCat = cat.id;
    tabs.querySelectorAll(".tab").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.id === cat.id)));
    document.getElementById("cat-blurb").textContent = I.field(cat, "blurb");
    const cases = M.cases.filter((c) => c.category === cat.id && c.gallery !== false);
    list.innerHTML = "";
    cases.forEach((c) => {
      const li = el("li");
      const b = el("button", { class: "case-btn", type: "button", "data-id": c.id });
      b.append(el("img", { src: c.thumb, alt: "", loading: "lazy", width: "360", height: "203" }), el("span", null, ""));
      b.lastChild.textContent = I.field(c, "title");
      b.addEventListener("click", () => showCase(c));
      li.append(b);
      list.append(li);
    });
    showCase(byId[caseId] || cases[0]);
  }
  M.categories.forEach((cat) => {
    const t = el("button", { class: "tab", type: "button", role: "tab", "data-id": cat.id, "aria-selected": "false" }, "");
    t.textContent = I.field(cat, "label");
    t.addEventListener("click", () => showCat(cat));
    tabs.append(t);
  });
  const catById = Object.fromEntries(M.categories.map((c) => [c.id, c]));
  function openCase(id, scroll) {
    const c = byId[id];
    if (!c) return false;
    if (currentCat !== c.category) showCat(catById[c.category], id); else showCase(c);
    if (scroll) document.getElementById("results").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
    return true;
  }
  const initial = location.hash.slice(1);
  if (!(initial && openCase(initial, true)) && M.categories[0]) showCat(M.categories[0]);
  window.addEventListener("hashchange", () => openCase(location.hash.slice(1), true));
  document.querySelectorAll('a.more[href^="#"]').forEach((a) => {
    const id = a.getAttribute("href").slice(1);
    if (!byId[id] || byId[id].gallery === false) { a.hidden = true; return; }   // case not on the page yet
    a.addEventListener("click", (e) => { e.preventDefault(); openCase(id, true); });
  });
  const failBtn = document.getElementById("open-failures");   // absent when the page has no limitations section
  if (failBtn) {
    if (!catById.failures) failBtn.hidden = true;
    failBtn.addEventListener("click", () => {
      const cat = catById.failures;
      if (cat) { showCat(cat); document.getElementById("results").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" }); }
    });
  }

  /* overview video embed: Bilibili for the Chinese page, YouTube for the English one (falls back to whichever is set) */
  const ov = M.overview_video || {};
  const slot = document.getElementById("overview-slot");
  let ovSrc = null;
  if (!ov.bilibili && !ov.youtube) {   // no overview video yet: hide the section and its button
    document.getElementById("overview").hidden = true;
    document.querySelectorAll('a[href="#overview"]').forEach((a) => (a.hidden = true));
  }
  function embedOverview() {
    if (!ov.bilibili && !ov.youtube) return;
    const useBili = ov.bilibili && (I.lang === "zh" || !ov.youtube);
    const src = useBili
      ? `https://player.bilibili.com/player.html?bvid=${encodeURIComponent(ov.bilibili)}&autoplay=0&high_quality=1`
      : `https://www.youtube-nocookie.com/embed/${encodeURIComponent(ov.youtube)}`;
    if (src === ovSrc) {
      const f = slot.querySelector("iframe");
      if (f) f.title = I.t("overviewTitle");
      return;
    }
    ovSrc = src;
    slot.innerHTML = "";
    slot.classList.remove("is-empty");
    slot.append(el("iframe", { src, title: I.t("overviewTitle"), allow: "fullscreen; picture-in-picture", allowfullscreen: "", loading: "lazy" }));
  }
  embedOverview();

  /* method diagram: windows along a timeline, two shots.
     Order follows the long-video planner: in each shot the window with the most visible
     background goes first, then its left neighbours back to the shot start, then its right
     neighbours to the shot end; each finished window is context for the next one. */
  let shotLabel = null;
  const g = document.getElementById("dg-windows");
  if (g) {
    const NS = "http://www.w3.org/2000/svg";
    const mk = (tag, a) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); return e; };
    const vis = [0.35, 0.9, 0.55, 0.2, 0.7, 0.45, 0.8];
    const shots = [[0, 1, 2, 3], [4, 5, 6]];
    const rank = [], arrows = [];
    let k = 0;
    shots.forEach((s) => {
      const a = s.reduce((best, i) => (vis[i] > vis[best] ? i : best), s[0]);
      const order = [a];
      for (let i = a - 1; i >= s[0]; i--) { order.push(i); arrows.push([i + 1, i]); }
      for (let i = a + 1; i <= s[s.length - 1]; i++) { order.push(i); arrows.push([i - 1, i]); }
      order.forEach((i) => (rank[i] = ++k));
    });
    const W0 = 118, GAP = 14;
    vis.forEach((v, i) => {
      const x = i * (W0 + GAP);
      g.append(mk("rect", { x, y: 18, width: W0, height: 48, rx: 4, style: `fill: color-mix(in srgb, var(--accent) ${Math.round(25 + v * 70)}%, var(--stage))` }));
      const t = mk("text", { x: x + W0 / 2, y: 48, "text-anchor": "middle", class: "d-win-n" }); t.textContent = rank[i]; g.append(t);
    });
    arrows.forEach(([a, b]) => {
      const xa = a * (W0 + GAP) + W0 / 2, xb = b * (W0 + GAP) + W0 / 2;
      g.append(mk("path", { d: `M${xa} 70 Q${(xa + xb) / 2} 98 ${xb} 70`, class: "d-ctx", "marker-end": "url(#arr)" }));
    });
    const sx = shots[1][0] * (W0 + GAP) - GAP / 2;
    g.append(mk("line", { x1: sx, y1: 6, x2: sx, y2: 78, class: "d-shot" }));
    shotLabel = mk("text", { x: sx + 6, y: 10, class: "d-shot-t" }); shotLabel.textContent = I.t("shotCut"); g.append(shotLabel);
  }

  /* BibTeX copy */
  const copyBtn = document.getElementById("copy-bib");
  copyBtn.textContent = I.t("copy");
  copyBtn.addEventListener("click", () => {
    const text = document.getElementById("bibtex").textContent;
    const done = () => { copyBtn.textContent = I.t("copied"); setTimeout(() => (copyBtn.textContent = I.t("copy")), 1600); };
    const fallback = () => {
      const r = document.createRange(); r.selectNodeContents(document.getElementById("bibtex"));
      const s = getSelection(); s.removeAllRanges(); s.addRange(r); copyBtn.textContent = I.t("selected");
    };
    try { navigator.clipboard.writeText(text).then(done, fallback); } catch (e) { fallback(); }
  });

  /* language switch: static text is handled by i18n.js; here everything built from the manifest */
  I.onChange(() => {
    tabs.querySelectorAll(".tab").forEach((t) => { t.textContent = I.field(catById[t.dataset.id], "label"); });
    if (currentCat) document.getElementById("cat-blurb").textContent = I.field(catById[currentCat], "blurb");
    list.querySelectorAll(".case-btn").forEach((b) => { b.lastChild.textContent = I.field(byId[b.dataset.id], "title"); });
    if (currentCase) {
      document.getElementById("case-title").textContent = I.field(currentCase, "title");
      document.getElementById("case-note").textContent = I.field(currentCase, "note");
    }
    players.forEach((p) => p.relabel());
    if (shotLabel) shotLabel.textContent = I.t("shotCut");
    copyBtn.textContent = I.t("copy");
    embedOverview();
  });
})();
