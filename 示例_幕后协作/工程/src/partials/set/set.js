// ── 微观片场：各章共用的动作（每章 <script> 里 INCLUDE 这个文件，再 const S = hfSet("b-s-", tl)）──
// 米花走路、摆姿势、眨眼；七个道具的小动作；线条一笔笔画出来；线条「活」着（每 3 帧换一次抖动的 seed）。
// 只做小动作：不砸下、不弹跳、不闪（大动作会显得像广告）。全部写进同一条 timeline，可以任意跳到某一秒。
function hfSet(P, tl) {
  const $ = (id) => document.getElementById(P + id);
  // 七个角落：米花站哪（脚底中点 + 远近大小）、镜头推近时看哪一点、推多近
  const K = [
    { c: "c1", mh: [648, 784, 1.0], look: [585, 668, 2.0] },
    { c: "c2", mh: [562, 532, 0.92], look: [500, 440, 2.1] },
    { c: "c3", mh: [580, 380, 0.86], look: [650, 284, 2.2] },
    { c: "c4", mh: [856, 362, 0.84], look: [915, 262, 2.2] },
    { c: "c5", mh: [1088, 380, 0.86], look: [1160, 284, 2.2] },
    { c: "c6", mh: [1318, 534, 0.92], look: [1410, 440, 2.1] },
    { c: "c7", mh: [1270, 788, 1.0], look: [1340, 668, 2.0] },
  ];
  const corners = K.map((k) => $(k.c));
  // 改 transform 属性的小代理：o.v 补间，onUpdate 写回属性（SVG 里带原点的旋转、缩放都这样做，跳秒也对）
  const attr = (el, fmt, v0) => {
    const o = { v: v0 }; const ap = () => el.setAttribute("transform", fmt(o.v)); ap();
    return (v, at, dur, ease) => tl.to(o, { v, duration: dur, ease: ease || "power2.inOut", onUpdate: ap }, at);
  };

  // ── 米花 ──
  const mh = { x: 960, y: 800, s: 1, r: 0 };
  const mhEl = $("mh"), mhB = $("mh-b");
  const apply = () => { mhEl.setAttribute("transform", `translate(${mh.x} ${mh.y})`); mhB.setAttribute("transform", `rotate(${mh.r}) scale(${mh.s})`); };
  apply();
  const place = (x, y, s) => { mh.x = x; mh.y = y; mh.s = s ?? mh.s; apply(); };
  const fl = $("mh-fl"), fr = $("mh-fr");
  // 走过去：身体左右轻摆 ±3°，两只脚交替抬一下
  const walk = (x, y, s, at, dur) => {
    dur = dur ?? 1.0;
    tl.to(mh, { x, y, s, duration: dur, ease: "power2.inOut", onUpdate: apply }, at);
    const n = Math.max(2, Math.round(dur / 0.24)), d = dur / n;
    for (let i = 0; i < n; i++) {
      const t = at + i * d, foot = i % 2 ? fr : fl;
      tl.to(mh, { r: i % 2 ? -3 : 3, duration: d, ease: "sine.inOut", onUpdate: apply }, t);
      tl.to(foot, { y: -5, duration: d / 2, ease: "sine.out" }, t);
      tl.to(foot, { y: 0, duration: d / 2, ease: "sine.in" }, t + d / 2);
    }
    tl.to(mh, { r: 0, duration: 0.25, ease: "sine.out", onUpdate: apply }, at + dur);
  };
  const ARMS = ["mh-wave", "mh-down", "mh-point"].map($);
  const pose = (at, arm, eye, mouth) => {
    ARMS.forEach((el) => tl.set(el, { opacity: el === $(arm) ? 1 : 0 }, at));
    tl.set($("mh-pl"), { attr: { transform: `translate(${-17 + eye[0]} ${-73 + eye[1]})` } }, at);
    tl.set($("mh-pr"), { attr: { transform: `translate(${17 + eye[0]} ${-73 + eye[1]})` } }, at);
    tl.set($("mh-smile"), { opacity: mouth === "oh" ? 0 : 1 }, at);
    tl.set($("mh-oh"), { opacity: mouth === "oh" ? 1 : 0 }, at);
  };
  const eyes = attr($("mh-eyes"), (k) => `translate(0 -73) scale(1 ${k}) translate(0 73)`, 1);
  const blink = (at) => { eyes(0.08, at, 0.07, "power2.in"); eyes(1, at + 0.09, 0.1, "power2.out"); };
  const pop = attr($("mh-pop"), (y) => `translate(0 ${y})`, 0);
  const hop = (at) => { pop(-16, at, 0.22, "power2.out"); pop(0, at + 0.22, 0.26, "power2.in"); };
  const arm = attr($("mh-wave"), (a) => `rotate(${a} 54 -86)`, 0);
  const wave = (at, n) => { for (let i = 0; i < (n ?? 2); i++) { arm(-16, at + i * 0.5, 0.25, "sine.inOut"); arm(6, at + i * 0.5 + 0.25, 0.25, "sine.inOut"); } arm(0, at + (n ?? 2) * 0.5, 0.2); };

  // ── 道具的小动作 ──
  const clapR = attr($("clap"), (a) => `rotate(${a} -90 -164)`, -17);
  const clap = (at) => { clapR(0, at, 0.14, "power2.in"); clapR(-17, at + 0.24, 0.45, "power2.out"); };
  const flipS = attr($("c2-flip"), (k) => `scale(${k} 1)`, 1);
  const mouthS = attr($("c2-mouth"), (k) => `translate(0 -30) scale(1 ${k}) translate(0 30)`, 1);
  const script = (at) => {
    tl.set($("c2-flip"), { opacity: 1 }, at); flipS(-1, at, 0.75, "power2.inOut"); tl.set($("c2-flip"), { opacity: 0 }, at + 0.76); flipS(1, at + 0.8, 0.01);
    for (let i = 0; i < 3; i++) { mouthS(0.45, at + 0.3 + i * 0.3, 0.13, "sine.inOut"); mouthS(1, at + 0.43 + i * 0.3, 0.14, "sine.inOut"); }
  };
  const cells = [1, 2, 3, 4, 5, 6].map((i) => $("d" + i));
  const waves = [...$("waves").querySelectorAll("path")];
  const noteY = attr($("note"), (y) => `translate(166 ${-150 + y}) rotate(8)`, 0);
  const sound = (at, dur) => {
    for (let t = 0; t < dur; t += 1.1) {
      waves.forEach((w, i) => { tl.fromTo(w, { opacity: 0.15 }, { opacity: 1, duration: 0.2, ease: "power1.out", immediateRender: false }, at + t + i * 0.18); tl.to(w, { opacity: 0.15, duration: 0.45, ease: "power1.in" }, at + t + i * 0.18 + 0.22); });
    }
    noteY(-22, at + 0.2, 1.2, "sine.out"); tl.to($("note"), { opacity: 0, duration: 0.4 }, at + 1.0);
    noteY(0, at + 1.45, 0.01); tl.to($("note"), { opacity: 1, duration: 0.4 }, at + 1.5);
  };
  const paints = [["p1", 30, -59], ["p2", 56, -60], ["p3", 80, -51]].map(([id, cx, cy]) => attr($(id), (k) => `translate(${cx} ${cy}) scale(${k}) translate(${-cx} ${-cy})`, 1));
  const brushR = attr($("brush"), (a) => `translate(-122 -4) rotate(${16 + a})`, 0);
  const style = (at) => {
    paints.forEach((p, i) => { p(0.2, at + i * 0.32 - 0.01, 0.01); p(1.12, at + i * 0.32, 0.22, "power2.out"); p(1, at + i * 0.32 + 0.22, 0.18, "sine.inOut"); });
    brushR(9, at + 1.05, 0.3, "sine.inOut"); brushR(-5, at + 1.35, 0.3, "sine.inOut"); brushR(0, at + 1.65, 0.3, "sine.inOut");
  };
  const reel1 = attr($("reel1"), (a) => `rotate(${a} 56 -213.3)`, 0), reel2 = attr($("reel2"), (a) => `rotate(${a} 108 -209.7)`, 0);
  const crew = (at, dur) => { reel1(dur * 70, at, dur, "none"); reel2(dur * 70, at, dur, "none"); };
  const coinY = attr($("coin"), (y) => `translate(0 ${y})`, 0);
  const pigE = attr($("pig-eyes"), (k) => `translate(0 -82) scale(1 ${k}) translate(0 82)`, 1);
  const quota = (at) => {
    coinY(38, at, 0.7, "power2.in"); tl.to($("coin"), { opacity: 0, duration: 0.25 }, at + 0.5);
    pigE(0.1, at + 0.85, 0.08, "power2.in"); pigE(1, at + 0.95, 0.12, "power2.out");
    coinY(0, at + 2.2, 0.01); tl.to($("coin"), { opacity: 1, duration: 0.5 }, at + 2.2);
  };
  const props = [clap, script, (at) => board(at), (at) => sound(at, 3.3), style, (at) => crew(at, 4), quota];

  // 分镜板的六个小格子一格一格画出来（先藏起来；只有调用 hideCells 的章才藏）
  const hideCells = () => cells.forEach((g) => g.querySelectorAll("path, rect, circle").forEach((el) => gsap.set(el, { opacity: 0 })));
  const board = (at, gap) => cells.forEach((g, i) => drawEls([...g.querySelectorAll("path, rect, circle")], at + i * (gap ?? 0.36), 0.45));

  // ── 线条一笔笔画出来 ──
  // 描边的元素：虚线偏移从整条长度走到 0；有填充的，填充在描边画到一半以后淡入；只有填充的（阴影、黑点）、文字直接淡入
  function drawEls(els, at, dur) {
    els.forEach((el) => {
      const cs = getComputedStyle(el);
      if (parseFloat(cs.opacity) === 0) return;   // 本来就藏着的（张嘴、另外两种手势、翻页）不动
      const stroked = cs.stroke && cs.stroke !== "none" && typeof el.getTotalLength === "function";
      if (stroked) {
        const L = Math.max(1, el.getTotalLength());
        gsap.set(el, { strokeDasharray: `${L} ${L}`, strokeDashoffset: L, opacity: 0 });
        tl.set(el, { opacity: 1 }, at);
        tl.to(el, { strokeDashoffset: 0, duration: dur, ease: "power1.inOut" }, at);
        if (cs.fill && cs.fill !== "none") { gsap.set(el, { fillOpacity: 0 }); tl.to(el, { fillOpacity: 1, duration: 0.35, ease: "power1.out" }, at + dur * 0.55); }
      } else {
        gsap.set(el, { opacity: 0 });
        tl.to(el, { opacity: 1, duration: 0.35, ease: "power1.out" }, at + dur * 0.55);
      }
    });
  }
  const geo = (root, skip) => [...root.querySelectorAll("path, rect, circle, ellipse, text")].filter((el) => !(skip && skip.some((g) => g.contains(el))));
  // 某个角落画出来（dur 秒内整组同时画；skipCells: 分镜板的小格子留给 board 单独画）
  const drawCorner = (i, at, dur, skipCells) => drawEls(geo(corners[i], skipCells ? cells : null), at, dur ?? 0.8);
  const drawMh = (at, dur) => drawEls(geo($("mh")), at, dur ?? 0.8);
  const drawTape = (i, at) => drawEls(geo($("tapes").children[i]), at, 0.5);

  // ── 线条「活」着：每 3 帧（0.1 秒）换一次抖动滤镜的 seed ──
  const turb = [...$("wob").querySelectorAll("feTurbulence")];
  const boil = (t0, t1) => {
    let k = 0;
    for (let t = t0; t < t1; t += 0.1, k++) {
      tl.set(turb[0], { attr: { seed: 7 + (k % 4) * 5 } }, t);
      tl.set(turb[1], { attr: { seed: 3 + (k % 3) * 7 } }, t);
    }
  };

  // 镜头推到第 i 个角落，别的角落退后（0.32）
  const focus = (cam, i, at, dur) => {
    cam.focus(tl, K[i].look[0], K[i].look[1], K[i].look[2], at, dur ?? 0.95);
    tl.to(corners.filter((_, j) => j !== i), { opacity: 0.32, duration: 0.5, ease: "power2.out" }, at);
    tl.to(corners[i], { opacity: 1, duration: 0.5, ease: "power2.out" }, at);
  };
  // 章节卡：只亮这一章的角落和它的标签，别的角落、别的标签一起压暗（不然上一章的标签还亮着，分不清现在讲到哪一章）
  const dimOthers = (i) => {
    corners.forEach((c, j) => gsap.set(c, { opacity: j === i ? 1 : 0.32 }));
    [...$("tapes").children].forEach((t, j) => gsap.set(t, { opacity: j === i ? 1 : 0.32 }));
  };

  const clapTo = (a, at, dur) => clapR(a, at, dur ?? 0.3, "power2.inOut");
  return { K, corners, mh, place, walk, pose, blink, hop, wave, clap, clapTo, script, board, hideCells, sound, style, crew, quota, props, drawEls, drawCorner, drawMh, drawTape, boil, focus, dimOthers, $ };
}

// 章节卡：每章开头回到这个角落（镜头已经在角落上，慢慢往后让一点），这个角落一笔笔画出来、道具动一下，米花在旁边
function hfCard(P, tl, cam, i, o) {
  o = Object.assign({ draw: 0.15, prop: 0.75, hold: 3 }, o || {});
  const S = hfSet(P, tl);
  const k = S.K[i];
  S.dimOthers(i);
  cam.set(k.look[2] * 1.06, -(k.look[0] - 960) * k.look[2] * 1.06, -(k.look[1] - 540) * k.look[2] * 1.06);
  cam.focus(tl, k.look[0], k.look[1], k.look[2], 0.05, o.hold, "power1.out");
  S.place(k.mh[0], k.mh[1], k.mh[2]);
  S.pose(0, i === 2 ? "mh-point" : i === 0 ? "mh-wave" : "mh-down", [i < 3 ? 3 : 4, i === 2 ? -4 : 0], i === 3 ? "oh" : "smile");
  if (o.draw !== null) {   // 接着上一章同一个画面（开场 → 选题）时不重画
    if (i === 2) S.hideCells();
    S.drawCorner(i, o.draw, 0.8, i === 2);
    S.drawTape(i, o.draw + 0.3);
  }
  S.props[i](o.prop + 0.4);
  S.blink(o.prop + 1.6);
  S.boil(0, o.hold + 1.2);
  return S;
}
