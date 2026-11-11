/* Chinese / English switch for the HintErase page.
 *
 * Static text:  index.html is the English source. Elements carry data-i18n / data-i18n-html /
 *               data-i18n-attr keys; ZH below holds the Chinese for the same keys. English is
 *               read back from the page on first use, so it is written in one place only.
 * Dynamic text: player controls, row labels and other strings built by app.js use UI below.
 * Case titles / notes and category labels come from manifest.js (title_zh, note_zh,
 *               label_zh, blurb_zh, written by tools/build_site.py from cases.json).
 *
 * Language: ?lang=zh|en in the URL, else the last choice (localStorage), else English by
 * default (the browser's own language is not used to pick the default). A missing Chinese
 * string falls back to English.
 */
(function () {
  "use strict";

  const ZH = {
    "nav.label": "页面导航",
    "nav.results": "结果",
    "nav.hints": "提示",
    "nav.delivery": "落地",
    "nav.uhd": "超高清",
    "nav.cite": "引用",
    "banner": "预览版本：本页所有视频均为合成占位素材，正式发布时将替换为真实结果。",

    "hero.eyebrow": "技术报告 · 视频叠加层擦除",
    "hero.title": "是提示，不是洞。",
    "hero.lede": "HintErase 能从完整长视频中擦除硬字幕、卡拉OK歌词、片头标题、演职员表和台标。它根据一个“提示”得知叠加层大致在哪里，即使提示不准，也能擦干净。",
    "hero.authors": "<span class=\"aff\">马栏山音视频实验室</span>",
    "hero.report": "技术报告 <small>PDF</small>",
    "hero.soonTitle": "即将发布",
    "hero.overview": "概览视频",
    "hero.playerLabel": "擦除前后对比",

    "facts.label": "适用范围",
    "facts.types": "叠加层类型",
    "facts.typesVal": "字幕、歌词、标题、演职员表、台标",
    "facts.hint": "提示",
    "facts.hintVal": "框、像素级 mask，或粗略估计",
    "facts.length": "时长",
    "facts.lengthVal": "整集剧集与 MV，多镜头",
    "facts.sources": "片源",
    "facts.sourcesVal": "480p 到 1080p 片源，可超高清交付",

    "results.eyebrow": "结果",
    "results.title": "每段视频都可以左右并排对比。",
    "results.sub": "每个播放器同步显示同一帧的两个画面，左右两侧可以分别选择：原始输入、我们给出的提示或我们的结果。",
    "results.tabsLabel": "叠加层类型",
    "results.listLabel": "该类别下的视频",

    "overview.eyebrow": "概览视频",
    "overview.title": "三分钟看完整长视频结果。",
    "overview.empty": "概览视频将嵌入在这里。",
    "overview.howto": "在 cases.json 中设置 <code>overview_video.bilibili</code> 或 <code>overview_video.youtube</code>。",

    "hints.eyebrow": "为什么是提示，而不是洞",
    "hints.title": "检测器会在两个方向上出错。",
    "hints.sub": "大多数擦除方法把 mask 当成“洞”：洞里全部重新生成，洞外原样复制。于是 mask 漏掉的笔画会留在结果里，mask 多盖住的背景会被重画。HintErase 把 mask 当作线索，同时看整幅画面。",
    "hints.complete": "擦得完整",
    "hints.completeText": "擦掉整个叠加层，包括提示漏掉的笔画、光晕和描边。",
    "hints.completeLink": "查看漏检笔画的例子",
    "hints.faithful": "保得忠实",
    "hints.faithfulText": "保留每一个干净像素，包括被宽松的框误盖住的背景。",
    "hints.faithfulLink": "查看宽松框的例子",
    "hints.selective": "擦得有选择",
    "hints.selectiveText": "即使提示落在场景文字上，也会把它保留下来。店招、书封等属于画面本身的文字都不会被擦掉。",

    "why.regionAlt": "红色区域 mask 盖住片头标题卡的整行文字",
    "why.regionTag": "常见做法：整块分割 mask",
    "why.regionTitle": "洞太大",
    "why.regionText": "mask 盖住整行文字，连同字与字之间、文字周围的背景。把它当作洞的擦除方法会把这些区域全部重画，原本干净的纹理也一起丢失。",
    "why.charAlt": "红色字幕级 mask 紧贴每个笔画",
    "why.charTag": "改进做法：字幕级分割 mask",
    "why.charTitle": "洞太小",
    "why.charText": "mask 紧贴每个笔画。紧挨在 mask 外面的描边、光晕和压缩痕迹会留在结果里，分割漏掉的笔画也会原样保留。",
    "why.hintAlt": "完整画面上，红框框住文字区域，蓝框框住唱片公司标志",
    "why.hintTag": "HintErase：提示",
    "why.hintTitle": "一个框就够",
    "why.hintText": "每个文字区域（红框）、每个标志（蓝框）各给一个框，模型看到的仍是保留叠加层的完整画面。它会擦掉框内所有笔画、描边和光晕，同时保留字与字之间的背景。",
    "why.complete": "<strong>擦得完整。</strong>提示漏掉的笔画、描边、光晕也一并擦掉。",
    "why.faithful": "<strong>保得忠实。</strong>宽松的框误盖住的背景原样保留。",
    "why.selective": "<strong>擦得有选择。</strong>框落在场景文字上，场景文字也不会被擦掉。",



    "deliv.eyebrow": "从模型到落地",
    "deliv.title": "模型只看短窗口，落地要处理完整的长视频。",
    "deliv.gap1": "短窗口 → 长视频",
    "deliv.gap1s": "模型每次只处理几秒，长视频却有成千上万帧，必须拆成窗口处理，再无缝拼回。",
    "deliv.gap2": "单镜头 → 频繁切换",
    "deliv.gap2s": "窗口一旦跨过镜头切换，前后两个镜头的画面就会相互串扰。",
    "deliv.gap3": "精确 mask → 漏检与抖动",
    "deliv.gap3s": "检测漏掉一帧，那一帧就会残留文字；mask 抖动会让结果闪烁。",
    "deliv.note": "这些问题在几秒的短片段上很难显现，只有处理完整长视频时才会集中暴露；下面任何一环出错，成片都无法使用。",
    "deliv.problemLabel": "难点",
    "deliv.fixLabel": "解法",
    "deliv.input": "① 输入预处理",
    "deliv.inputP": "片源格式多样：隔行扫描、压缩失真、非方形像素。",
    "deliv.inputS": "自动检测并反交错，按原始比例在原尺度上裁取处理窗口。",
    "deliv.shots": "② 镜头切分",
    "deliv.shotsP": "窗口跨越镜头切换会串画面；淡入淡出、闪白容易产生假切点。",
    "deliv.shotsS": "先做镜头检测，按镜头切分处理区间；跨转场的假切点自动合并。",
    "deliv.hint": "③ 擦除提示",
    "deliv.hintP": "检测会漏帧、框位置抖动，台标等小目标容易漏检。",
    "deliv.hintS": "分割与定位相结合，并在时间上膨胀提示，补齐漏检帧。",
    "deliv.plan": "④ 推理规划",
    "deliv.planP": "长视频放不进显存，而且大部分帧上根本没有叠加内容。",
    "deliv.planS": "只处理带叠加内容的片段，逐窗口流式推理，显存占用固定，与视频长度无关。",
    "deliv.paste": "⑤ 贴回",
    "deliv.pasteP": "整帧替换会让非擦除区域变软；暗场中的残字不易察觉。",
    "deliv.pasteS": "只替换真正有变化的像素，判定阈值随画面亮度自适应。",
    "deliv.output": "⑥ 整片输出",
    "deliv.outputP": "丢帧或重复帧，音画不同步。",
    "deliv.outputS": "输出帧数与原片严格对齐，并合入原始音轨。",
    "deliv.uhd": "⑦ 超高清交付（可选）",
    "deliv.uhdP": "老片分辨率低，而重新发行常要求超高清；基于大模型的生成式超分容易改变色彩、人物和细节。",
    "deliv.uhdS": "擦除完成后，用自研高保真超分模型将干净视频放大 4 倍，保持原片的色彩、人物和细节。",
    "uhd.eyebrow": "超高清交付",
    "uhd.title": "老片擦除后，以超高清交付。",
    "uhd.sub": "很多重新发行的片源只有低分辨率母版。HintErase 先在原始分辨率上擦除叠加内容，再由自研超分模型将干净视频放大 4 倍。基于大模型的生成式超分常会偏色、改变人物面貌、凭空生成细节；我们的模型以高保真为目标，色彩、人物和细节都忠于原片。该环节的示例片段涉及可识别的人物，故此处不作展示。",
    "uhd.playerLabel": "原片与超高清成片对比",


    "cite.eyebrow": "引用",
    "footer": "本页所有视频均已获得版权方授权展示，请勿下载或转载。",
  };

  // Strings built in app.js.
  const UI = {
    en: {
      divider: "Side-by-side comparison", play: "Play", pause: "Pause",
      prevFrame: "Previous frame", nextFrame: "Next frame", frameSlider: "Frame", frame: "frame",
      left: "Left", right: "Right", leftView: "Left view", rightView: "Right view",
      shotCut: "shot cut", copy: "Copy", copied: "Copied", selected: "Selected",
      overviewTitle: "HintErase overview video",
      toggle: "中文", toggleLabel: "切换到中文", toggleLang: "zh-CN",
    },
    zh: {
      divider: "左右并排对比", play: "播放", pause: "暂停",
      prevFrame: "上一帧", nextFrame: "下一帧", frameSlider: "帧位置", frame: "帧",
      left: "左", right: "右", leftView: "左侧画面", rightView: "右侧画面",
      shotCut: "镜头切换", copy: "复制", copied: "已复制", selected: "已选中",
      overviewTitle: "HintErase 概览视频",
      toggle: "EN", toggleLabel: "Switch to English", toggleLang: "en",
    },
  };

  // Row labels shown on the player chips. Method names are not translated.
  const ROWS_ZH = {
    "Input": "输入",
    "Hint": "提示",
    "Independent windows": "独立窗口",
    "Hole": "挖洞模式",
    "Box hint": "框提示",
    "No hint": "无提示",
    "HintErase (hole)": "HintErase（挖洞）",
    "HintErase + 4x SR": "HintErase + 4倍超分",
  };

  const KEY = "hinterase-lang";
  const listeners = [];

  function initial() {
    const q = new URLSearchParams(location.search).get("lang");
    if (q === "zh" || q === "en") return q;
    try {
      const s = localStorage.getItem(KEY);
      if (s === "zh" || s === "en") return s;
    } catch (e) { /* storage blocked */ }
    return "en"; // default language for first-time visitors, regardless of browser locale
  }

  // English is taken from the page the first time an element is touched.
  function original(node, slot, read) {
    const a = "data-i18n-en-" + slot;
    if (!node.hasAttribute(a)) node.setAttribute(a, read());
    return node.getAttribute(a);
  }

  const I = {
    lang: initial(),
    t(key) {
      const d = UI[I.lang] || UI.en;
      return key in d ? d[key] : (UI.en[key] != null ? UI.en[key] : key);
    },
    row(label) { return I.lang === "zh" ? (ROWS_ZH[label] || label) : label; },
    // obj.title / obj.title_zh etc. from the manifest
    field(obj, name) { return (obj && ((I.lang === "zh" && obj[name + "_zh"]) || obj[name])) || ""; },
    apply(root) {
      const zh = I.lang === "zh";
      (root || document).querySelectorAll("[data-i18n]").forEach((n) => {
        const en = original(n, "text", () => n.textContent);
        const v = zh ? ZH[n.getAttribute("data-i18n")] : null;
        n.textContent = v != null ? v : en;
      });
      (root || document).querySelectorAll("[data-i18n-html]").forEach((n) => {
        const en = original(n, "html", () => n.innerHTML);
        const v = zh ? ZH[n.getAttribute("data-i18n-html")] : null;
        n.innerHTML = v != null ? v : en;
      });
      (root || document).querySelectorAll("[data-i18n-attr]").forEach((n) => {
        n.getAttribute("data-i18n-attr").split(";").forEach((pair) => {
          const [attr, key] = pair.split(":").map((s) => s.trim());
          if (!attr || !key) return;
          const en = original(n, attr, () => n.getAttribute(attr) || "");
          const v = zh ? ZH[key] : null;
          n.setAttribute(attr, v != null ? v : en);
        });
      });
      document.documentElement.lang = zh ? "zh-CN" : "en";
      const b = document.getElementById("lang-toggle");
      if (b) {
        b.textContent = I.t("toggle");
        b.setAttribute("aria-label", I.t("toggleLabel"));
        b.setAttribute("lang", I.t("toggleLang"));
      }
    },
    set(lang) {
      if (lang !== "zh" && lang !== "en") return;
      I.lang = lang;
      try { localStorage.setItem(KEY, lang); } catch (e) { /* storage blocked */ }
      const u = new URL(location.href);
      u.searchParams.set("lang", lang);
      history.replaceState(history.state, "", u.pathname + u.search + u.hash);
      I.apply(document);
      listeners.forEach((f) => f(lang));
    },
    onChange(f) { listeners.push(f); },
  };

  window.HE_I18N = I;
  I.apply(document);
  const b = document.getElementById("lang-toggle");
  if (b) b.addEventListener("click", () => I.set(I.lang === "zh" ? "en" : "zh"));
})();
