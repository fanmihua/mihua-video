// ─────────────────────────────────────────────────────────────────────────────
// AI 讲解视频 · 动效工具箱（固定）
// Injected into every scene and the shell by tools/build.mjs (//@COMMON_JS@).
// These are VERBS, not scenes: each video's scenes are designed fresh from its content and
// composed from these moves. Deterministic only — no Math.random / clocks.
// Deliberately absent: camera shake, starburst lines, flash frames, stamp/slam pops — they read
// as promotion, which this style avoids (see references/motion-language.md).
// ─────────────────────────────────────────────────────────────────────────────

// Virtual camera on a full-frame wrapper (transform-origin 50% 50%, 1920×1080 stage).
// cam.focus(tl, wx, wy, s, at, dur, ease) brings world point (wx, wy) to frame centre at scale s.
function hfCam(el) {
  if (typeof el === "string") el = document.querySelector(el);
  const cam = { s: 1, x: 0, y: 0 };
  const apply = () => { el.style.transform = `translate(${cam.x}px, ${cam.y}px) scale(${cam.s})`; };
  cam.apply = apply;
  cam.set = (s, x, y) => { cam.s = s; cam.x = x; cam.y = y; apply(); };
  cam.focus = (tl, wx, wy, s, at, dur, ease) => tl.to(cam, { s, x: -(wx - 960) * s, y: -(wy - 540) * s, duration: dur ?? 0.9, ease: ease || "expo.inOut", onUpdate: apply }, at);
  cam.home = (tl, at, dur, ease) => tl.to(cam, { s: 1, x: 0, y: 0, duration: dur ?? 0.7, ease: ease || "expo.inOut", onUpdate: apply }, at);
  // slow constant push on the point the camera is resting on, so a held frame never looks frozen.
  // Pass the same (wx, wy, s) the camera is at; it drifts to s × (1 + ds) linearly over [from, to].
  cam.breathe = (tl, wx, wy, s, from, to, ds) => cam.focus(tl, wx, wy, s * (1 + (ds ?? 0.035)), from, to - from, "none");
  apply();
  return cam;
}

function hfRand(seed) {
  let s = seed >>> 0;
  return function () { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
}

// Split an element's text into per-glyph spans (spaces stay plain text).
function hfChars(el) {
  if (typeof el === "string") el = document.querySelector(el);
  const text = el.textContent;
  el.textContent = "";
  for (const c of text) {
    if (c === " ") { el.appendChild(document.createTextNode(" ")); continue; }
    const s = document.createElement("span"); s.className = "ch"; s.textContent = c; el.appendChild(s);
  }
  return el;
}

// Text in: glyphs rise out of a blur into focus, left → right. Text out: lift away and dissolve.
function hfTextIn(tl, el, at, o) {
  o = Object.assign({ stagger: 0.045, dur: 0.75, y: 50, blur: 18 }, o || {});
  const chars = (typeof el === "string" ? document.querySelector(el) : el).querySelectorAll(".ch");
  tl.fromTo(chars, { yPercent: o.y, opacity: 0, filter: `blur(${o.blur}px)` },
    { yPercent: 0, opacity: 1, filter: "blur(0px)", duration: o.dur, ease: "expo.out", stagger: o.stagger }, at);
}
function hfTextOut(tl, el, at, o) {
  o = Object.assign({ stagger: 0.022, dur: 0.4 }, o || {});
  const chars = (typeof el === "string" ? document.querySelector(el) : el).querySelectorAll(".ch");
  tl.to(chars, { yPercent: -40, opacity: 0, filter: "blur(12px)", duration: o.dur, ease: "power2.in", stagger: o.stagger }, at);
}

// Film-grain boil (used by the shell): jump the grain tile every 2 frames.
// shift：只重渲后面几章时这一版从整片的第 shift 秒开始（deliver.sh）。随机数照样从 t0 抽起，shift 以前的只抽不放，颗粒和整片版一帧不差
function hfGrain(tl, target, t0, t1, seed, shift) {
  const r = hfRand(seed || 9), s = shift || 0;
  let held = null;
  for (let t = t0; t < t1; t += 2 / 30) {
    const v = { x: Math.round((r() - 0.5) * 220), y: Math.round((r() - 0.5) * 220) };
    if (t < s) { held = v; continue; }
    if (held) { tl.set(target, held, 0); held = null; }
    tl.set(target, v, t - s);
  }
}

// Directional motion blur through an SVG <filter><feGaussianBlur/></filter> for whips (axis "x" | "y").
function hfMotionBlur(tl, el, gaussEl, axis, t0, dur, peak) {
  const mb = { v: 0 };
  const ap = () => gaussEl.setAttribute("stdDeviation", axis === "x" ? `${mb.v} 0` : `0 ${mb.v}`);
  tl.set(el, { filter: `url(#${gaussEl.parentNode.id})` }, t0);
  tl.fromTo(mb, { v: 0 }, { v: peak, duration: dur / 2, ease: "power2.in", onUpdate: ap, immediateRender: false }, t0);
  tl.to(mb, { v: 0, duration: dur / 2 - 0.01, ease: "power2.out", onUpdate: ap }, t0 + dur / 2 + 0.01);
  tl.set(el, { filter: "none" }, t0 + dur + 0.02);
}

// Whip-pan: the camera travels to (wx, wy) in ~0.65 s with a blur streak along the travel axis.
// gaussEl must sit in a <filter> whose region is widened along that axis (see motion-language.md 3.2).
function hfWhip(tl, cam, worldEl, gaussEl, wx, wy, s, at, axis) {
  cam.focus(tl, wx, wy, s ?? 1, at, 0.65, "power4.inOut");
  hfMotionBlur(tl, worldEl, gaussEl, axis || "x", at, 0.63, 40);
}

// Annotation in: dot pops, leader line draws, label focuses in. Optional fade-out after `hold` s.
function hfNote(tl, el, at, hold) {
  if (typeof el === "string") el = document.querySelector(el);
  const dot = el.querySelector(".dot"), ln = el.querySelector(".ln"), lab = el.querySelector(".t");
  tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.01 }, at);
  if (dot) tl.fromTo(dot, { scale: 0 }, { scale: 1, duration: 0.3, ease: "back.out(2)" }, at);
  if (ln) tl.fromTo(ln, { scaleX: 0 }, { scaleX: 1, duration: 0.35, ease: "power3.out" }, at + 0.08);
  if (lab) tl.fromTo(lab, { opacity: 0, y: 8, filter: "blur(6px)" }, { opacity: 1, y: 0, filter: "blur(0px)", duration: 0.45, ease: "power3.out" }, at + 0.2);
  if (hold !== undefined) tl.to(el, { opacity: 0, duration: 0.3, ease: "power2.in" }, at + hold);
}

// Outline draws around a region; optional fade after `hold` s.
function hfOutline(tl, el, at, hold) {
  tl.fromTo(el, { opacity: 0, scaleX: 0.92, scaleY: 0.8 }, { opacity: 1, scaleX: 1, scaleY: 1, duration: 0.4, ease: "power3.out" }, at);
  if (hold !== undefined) tl.to(el, { opacity: 0, duration: 0.3 }, at + hold);
}

// Window / panel arrives from depth with a focus pull (no bounce). o: {z, rx, ry, rx2, ry2, dur}
function hfArrive(tl, el, at, o) {
  o = Object.assign({ z: -1600, rx: 14, ry: 0, dur: 1.0 }, o || {});
  tl.fromTo(el, { z: o.z, rotationX: o.rx, rotationY: o.ry, opacity: 0, filter: "blur(14px)", transformPerspective: 2200 },
    { z: 0, rotationX: o.rx2 ?? 0, rotationY: o.ry2 ?? 0, opacity: 1, filter: "blur(0px)", duration: o.dur, ease: "expo.out" }, at);
}

// Lift a cut-out out of its window: it starts at its place in the screenshot (from) and floats forward.
// from = {x, y, scale} relative to its resting position; the window behind dims and softens.
function hfLift(tl, cutEl, winEl, at, from) {
  tl.fromTo(cutEl, { x: from.x, y: from.y, scale: from.scale, opacity: 0 }, { x: 0, y: 0, scale: 1, opacity: 1, rotation: -1.2, duration: 0.8, ease: "expo.out" }, at);
  if (winEl) tl.to(winEl, { filter: "brightness(0.42) blur(5px)", duration: 0.6 }, at);
}

// Rack focus: everything in `others` falls back (blur + dim), `focusEl` comes forward.
function hfRack(tl, focusEl, others, at) {
  tl.to(others, { filter: "blur(8px) brightness(0.4)", duration: 0.6, ease: "power2.inOut" }, at);
  if (focusEl) tl.to(focusEl, { filter: "blur(0px) brightness(1)", duration: 0.6, ease: "power2.inOut" }, at);
}

// Code focus: dim every row of a .code panel except `keep` (row numbers counted inside the panel, from 1),
// so only the key 1–2 lines stay bright; optional fade-back at `until`. Rows sit at 64 + (row−1) × 23.25 px.
function hfFocus(tl, code, keep, at, until) {
  if (typeof code === "string") code = document.querySelector(code);
  const n = code.querySelectorAll("pre .n").length, masks = [];
  for (let r = 1; r <= n; ) {
    if (keep.includes(r)) { r++; continue; }
    const s = r;
    while (r <= n && !keep.includes(r)) r++;
    const m = document.createElement("div");
    m.className = "vmask";
    m.style.top = 64 + (s - 1) * 23.25 + "px";
    m.style.height = (r - s) * 23.25 + "px";
    code.appendChild(m);
    masks.push(m);
  }
  tl.to(masks, { opacity: 1, duration: 0.45, ease: "power2.out" }, at);
  if (until != null) tl.to(masks, { opacity: 0, duration: 0.4, ease: "power2.in" }, until);
  return masks;
}

// Reveal: element fades/rises in from a light blur (for screenshots that must stay still, e.g. feedback).
function hfReveal(tl, el, at, o) {
  o = Object.assign({ y: 26, blur: 10, dur: 0.7 }, o || {});
  tl.fromTo(el, { opacity: 0, y: o.y, filter: `blur(${o.blur}px)` }, { opacity: 1, y: 0, filter: "blur(0px)", duration: o.dur, ease: "power3.out" }, at);
}
