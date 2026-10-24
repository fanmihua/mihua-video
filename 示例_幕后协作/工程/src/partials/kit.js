// 这一期的小工具（各章共用，场景脚本里 INCLUDE；不是品牌层）
// 标注要指着内容（位置按版面量、不手估，框、圆点和引线才不会和内容错位）：
//   圆点落在被标的东西上（它的边上），引线朝空着的那一边伸出去，字在引线末端。
//   pin(标注, 目标, 边, {at, dx, dy, inset, dir})：边 "r" = 圆点在目标右边缘、字往右；"l" = 左边缘、字往左（自动换成 .note.l）；
//   "t" / "b" = 上 / 下边缘（at = 沿边的位置 0–1），字默认往右，dir: "l" 往左。位置按版面量（offsetLeft/Top 加到标注所在的那一层），不手估。
//   标注和目标要在同一个镜头层里（镜头动，两个一起动）；目标不要放在带 CSS 缩放的容器里（版面位置不含缩放）。
//   pinAt(标注, x, y, 往左?)：目标不在场景里（比如外壳上的导航）时，直接给圆点的坐标。
// 量版面之前，临时把隐藏着的那几层（播放器在这一章没轮到时会把整章设成 display:none）显示出来，量完原样还原
function kShow(el, fn) {
  const hidden = [];
  for (let e = el; e && e !== document.documentElement; e = e.parentElement) {
    if (getComputedStyle(e).display === "none") { hidden.push([e, e.style.display]); e.style.display = "block"; }
  }
  try { return fn(); } finally { hidden.forEach(([e, d]) => { e.style.display = d; }); }
}
function kBox(el, root) {
  let x = 0, y = 0, e = el;
  while (e && e !== root) { x += e.offsetLeft; y += e.offsetTop; e = e.offsetParent; }
  return { x, y, w: el.offsetWidth, h: el.offsetHeight };
}
function pinAt(note, x, y, left) {
  if (typeof note === "string") note = document.querySelector(note);
  const root = note.offsetParent || note.parentElement;
  note.classList.toggle("l", !!left);
  note.style.top = y + "px";
  note.style.transform = "translateY(-50%)";
  if (left) { note.style.left = "auto"; note.style.right = (root.offsetWidth - x - 4.5) + "px"; }
  else { note.style.left = (x - 4.5) + "px"; note.style.right = "auto"; }
}
// 版面要等这一章真的显示出来才排好：场景脚本刚运行时量到的位置可能是 0。
// 所以位置在时间线上「每一帧」再量一次（hfNote 显示的那段时间里一直跟着目标走），跳到任意一秒也对。
let __kPinTl = null, __kPinEnd = 1;
function kPinTimeline(tl, end) { __kPinTl = tl; __kPinEnd = end; }   // 每个场景建好 timeline 后调一次：kPinTimeline(tl, C.end)
function pin(note, target, side, o) {
  if (typeof note === "string") note = document.querySelector(note);
  if (typeof target === "string") target = document.querySelector(target);
  o = Object.assign({ at: 0.5, dx: 0, dy: 0, inset: 0, dir: null }, o || {});
  const place = () => kShow(target, () => {
    const root = note.offsetParent || note.parentElement, b = kBox(target, root);
    let x, y, left;
    if (side === "r") { x = b.x + b.w - o.inset; y = b.y + b.h * o.at; left = false; }
    else if (side === "l") { x = b.x + o.inset; y = b.y + b.h * o.at; left = true; }
    else if (side === "t") { x = b.x + b.w * o.at; y = b.y + o.inset; left = o.dir === "l"; }
    else { x = b.x + b.w * o.at; y = b.y + b.h - o.inset; left = o.dir === "l"; }
    pinAt(note, x + o.dx, y + o.dy, left);
  });
  place();
  if (document.fonts) document.fonts.ready.then(place);   // 字体加载完宽度会变，再量一次
  if (__kPinTl) __kPinTl.fromTo({ v: 0 }, { v: 0 }, { v: 1, duration: __kPinEnd, ease: "none", onUpdate: place }, 0);   // 播放时每一帧按当下的版面再放一次
}
// 跟着版面走的元素（删除线、括号这类）：每一帧调一次 fn
function kLive(tl, el, fn, end) { const f = () => kShow(el, fn); f(); if (document.fonts) document.fonts.ready.then(f); tl.fromTo({ v: 0 }, { v: 0 }, { v: 1, duration: end, ease: "none", onUpdate: f }, 0); }
