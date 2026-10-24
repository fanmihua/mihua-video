// 出片前扫一遍安全区：整片每 0.5 秒 seek 一次，列出压进字幕区（y > 950）和顶部签名导航区（y < 110）的可见字和图。
// 用法：preview 打开 http://localhost:<端口>/api/projects/<工程文件夹名>/preview，视口设成 3840×2160，
//       把这个文件的全部内容贴进 javascript_tool（或浏览器控制台）执行；十分钟的片子约 10 秒扫完，返回分组后的清单。
// 已按父层的 overflow 裁切和 clip-path: inset(...) 算（被窗口裁掉的不算）；透明度 < 0.15 的不算。
// 清单逐条看：甩镜头、钻入那一下的一闪、压暗的小字没碰到字幕文字的可以留；字、截图停在字幕区上的要改（字幕压在白底截图上看不清）。
// 起止秒数、步长、安全区边界改下面四个数。
(async () => {
  const FROM = 0.3, TO = parseFloat(document.querySelector('[data-composition-id="main"]')?.dataset.duration) || 600, STEP = 0.5, SUB_Y = 950, TOP_Y = 110;
  const S = innerWidth / 1920, SUB = SUB_Y * S, TOP = TOP_Y * S;
  const eff = (e) => { let o = 1; for (let n = e; n && n.nodeType === 1; n = n.parentElement) { const cs = getComputedStyle(n); if (cs.display === "none" || cs.visibility === "hidden") return 0; o *= parseFloat(cs.opacity); if (o < 0.12) return o; } return o; };
  const clipRect = (e) => {
    const r = e.getBoundingClientRect(); let x0 = r.left, y0 = r.top, x1 = r.right, y1 = r.bottom;
    for (let n = e.parentElement; n && n.nodeType === 1; n = n.parentElement) {
      const cs = getComputedStyle(n), p = n.getBoundingClientRect();
      if (cs.clipPath && cs.clipPath.startsWith("inset")) {
        const m = cs.clipPath.match(/inset\(([-\d.]+)px(?: ([-\d.]+)px)?(?: ([-\d.]+)px)?(?: ([-\d.]+)px)?/);
        if (m) { const t = +m[1], rr = +(m[2] ?? m[1]), b = +(m[3] ?? m[1]), l = +(m[4] ?? m[2] ?? m[1]), k = p.width / (n.offsetWidth || p.width); x0 = Math.max(x0, p.left + l * k); y0 = Math.max(y0, p.top + t * k); x1 = Math.min(x1, p.right - rr * k); y1 = Math.min(y1, p.bottom - b * k); }
      }
      if (cs.overflow !== "visible") { x0 = Math.max(x0, p.left); y0 = Math.max(y0, p.top); x1 = Math.min(x1, p.right); y1 = Math.min(y1, p.bottom); }
    }
    return { left: x0, top: y0, right: x1, bottom: y1, width: x1 - x0, height: y1 - y0 };
  };
  const hits = [];
  for (let t = FROM; t < TO; t += STEP) {
    const tt = Math.round(t * 100) / 100;
    try { await window.__player.seek(tt); } catch (err) { break; }
    for (const c of document.querySelectorAll('[data-composition-id^="act"]')) {
      if (eff(c) < 0.12) continue;
      for (const e of c.querySelectorAll("*")) {
        const own = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) || e.tagName === "IMG" || e.tagName === "text";
        if (!own) continue;
        const r = clipRect(e);
        if (r.width < 2 || r.height < 2 || r.right < 0 || r.left > innerWidth || r.bottom < 0 || r.top > innerHeight) continue;
        const sub = r.bottom > SUB + 4, top = r.top < TOP - 4;
        if (!sub && !top) continue;
        const o = eff(e); if (o < 0.15) continue;
        hits.push([tt, c.getAttribute("data-composition-id"), sub ? "字幕区" : "顶部", e.tagName === "IMG" ? "图 " + e.getAttribute("src") : e.textContent.trim().slice(0, 24), Math.round(o * 100) / 100, Math.round(r.top / S), Math.round(r.bottom / S)]);
      }
    }
  }
  const g = {};
  for (const [t, act, zone, what, o, y0, y1] of hits) { const k = act + " " + zone + " " + what; (g[k] ||= { from: t, to: t, n: 0, o, y: y0 + "–" + y1 }); g[k].to = t; g[k].n++; }
  return Object.entries(g).map(([k, v]) => `${k} | ${v.from}–${v.to} 秒 ×${v.n} · 透明度 ${v.o} · y ${v.y}`);
})();
