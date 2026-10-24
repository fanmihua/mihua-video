// ─────────────────────────────────────────────────────────────────────────────
// AI 讲解视频 · 封面工具（只是工具，不管排版）
// 箭头、卡片高度按元素在页面上的真实位置算，不手摆坐标——手摆的 SVG 箭头一眼就看得出歪了。
// 用法（放在页面最后）：
//   <script src="cover.js"></script>
//   <script>coverDone(() => { coverFit(); coverArrow(coverPt("#from"), coverCorner("#target", "left")); });</script>
// coverDone 等字体加载完再执行，最后设 window.__placed = true；render.mjs / measure.mjs 等到它才截图。
// ─────────────────────────────────────────────────────────────────────────────

const coverEl = (s) => (typeof s === "string" ? document.querySelector(s) : s);

// 元素外包盒上的一个点：fx / fy 是比例（0 左/上 → 1 右/下）
function coverPt(sel, fx = 0.5, fy = 0.5) {
  const r = coverEl(sel).getBoundingClientRect();
  return [r.left + r.width * fx, r.top + r.height * fy];
}

// 旋转 / 3D 变换过的元素的真实四个角（外包盒给不出来）：往元素里临时放 0×0 的点，读变换后的位置。
// 元素本身要是 position: absolute / relative。返回 {tl, tr, br, bl, left, right, top, bottom}：后四个是画面上最靠左/右/上/下的角。
function coverCorners(sel) {
  const el = coverEl(sel), w = el.offsetWidth, h = el.offsetHeight;
  const pts = [[0, 0], [w, 0], [w, h], [0, h]].map(([x, y]) => {
    const i = document.createElement("i");
    i.style.cssText = `position:absolute;left:${x}px;top:${y}px;width:0;height:0;`;
    el.appendChild(i);
    const r = i.getBoundingClientRect();
    i.remove();
    return [r.left, r.top];
  });
  const by = (f) => pts.reduce((a, b) => (f(b, a) ? b : a));
  return { tl: pts[0], tr: pts[1], br: pts[2], bl: pts[3],
    left: by((b, a) => b[0] < a[0]), right: by((b, a) => b[0] > a[0]), top: by((b, a) => b[1] < a[1]), bottom: by((b, a) => b[1] > a[1]) };
}
function coverCorner(sel, which) { return coverCorners(sel)[which]; }
// 两点之间按比例取一点（比如平面左角和下角之间 30% 处，让箭头指在边上而不是尖角上）
function coverLerp(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]; }

function coverSvg() {
  let s = document.querySelector("svg.ov");
  if (!s) {
    s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("class", "ov");
    document.body.appendChild(s);
  }
  return s;
}

// 手绘箭头：a → b 一条二次曲线，箭头头部沿曲线末端的方向。a、b 是页面坐标 [x, y]。
// o.bend：拱起的比例，正数从左往右画时往上拱，负数往下（默认 0.2）；o.gap：在 b 前面停多远（默认 20）
function coverArrow(a, b, o = {}) {
  const { bend = 0.2, gap = 20, head = 17, color = "rgba(255,255,255,.82)", width = 3.2 } = o;
  const [sx, sy] = a, dl = Math.hypot(b[0] - sx, b[1] - sy);
  const ex = b[0] - ((b[0] - sx) / dl) * gap, ey = b[1] - ((b[1] - sy) / dl) * gap;
  const dx = ex - sx, dy = ey - sy, cx = (sx + ex) / 2 + dy * bend, cy = (sy + ey) / 2 - dx * bend;
  const tl = Math.hypot(ex - cx, ey - cy), ux = (ex - cx) / tl, uy = (ey - cy) / tl;
  const h1 = [ex - head * (ux * 0.87 - uy * 0.5), ey - head * (uy * 0.87 + ux * 0.5)];
  const h2 = [ex - head * (ux * 0.87 + uy * 0.5), ey - head * (uy * 0.87 - ux * 0.5)];
  const st = `fill="none" stroke="${color}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round"`;
  coverSvg().insertAdjacentHTML("beforeend",
    `<path d="M${sx} ${sy} Q${cx} ${cy} ${ex} ${ey}" ${st}/><path d="M${h1[0]} ${h1[1]} L${ex} ${ey} L${h2[0]} ${h2[1]}" ${st}/>`);
}

// 卡片高度（截图/快照裁切）：<div class="cwrap" data-fit="full"> 放完整内容（几张卡本来就不一样高，底边参差是真的）；
// data-fit="<选择器>" 裁到这个元素下面 12px（比如 '[data-region="submit"]'，裁到「登录」按钮下面）。
function coverFit() {
  for (const w of document.querySelectorAll(".cwrap[data-fit]")) {
    const top = w.getBoundingClientRect().top, f = w.dataset.fit;
    const bottom = f === "full"
      ? [...w.querySelectorAll("*")].reduce((m, e) => Math.max(m, e.getBoundingClientRect().bottom), top)
      : w.querySelector(f).getBoundingClientRect().bottom + 12;
    w.style.height = bottom - top + "px";
  }
}

function coverDone(fn) {
  document.fonts.ready.then(() => {
    if (fn) fn();
    window.__placed = true;
  });
}
