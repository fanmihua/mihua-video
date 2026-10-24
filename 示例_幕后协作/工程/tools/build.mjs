// AI 讲解视频 · build. One timing file (the real voice-over) drives the whole film.
//
//   CONFIG=video.config.json node tools/build.mjs
//
// video.config.json
//   timing    timing/film.json — every spoken line {id, act, text, cap, start, end} in film seconds
//   acts      [{id, lead}] — one src/scenes/<id>.html per act; an act spans its lines (+lead before)
//   tail      seconds after the last line
//   aliases   {actId: {name: "l3"}} — readable cue names inside a scene (C.name)
//   chapters  [{label, act, preview?: ["actA.l3"]}] — the top navigation (omit / [] = no nav)
//   navFrom   "actA.l2"  when the nav appears (default: first chapter's act start)
//   navUntil  "actO.l1"  when it fades out (default: stays)
//   sigAt     "actA.l1"  when the handwritten greeting writes on (default: first line)
//   mix       assets/mix/final.wav — the one mixed audio track (tools/mix.py)
//   srt       renders/subtitles.srt
//   textReplace {from: to} applied to all built HTML (per-platform wording)
//   forbid    ["小红书", …] — build fails if any of these appear in built text or captions
//   noCaptions ["actP"] — acts whose lines get no burned-in caption (the SRT still has them)
//   fonts     {outName: sourceFile} subset to the glyphs actually used
//
// 每次整片 build 写 timing/fingerprint.json：每章搭好的 HTML 和它用到的素材、每条字幕、外壳的每个动画。
// deliver.sh 拿它和上一版成片的指纹比，找出最早从哪一章变了，只重渲那一章到片尾，接回上一版（tools/patch_render.py）。
//   FROM=actF DRIFT=<上一版的 drift> node tools/build.mjs   index.html 换成从 actF 开头那一帧起的一版：外壳、字幕、后面各章的时间都减掉这一帧的时间，
//                                                           前面各章不进来；timing/window.json 记下从第几帧接。不写 SRT、字体、acts.generated.json、指纹。
//                                                           deliver.sh 自己会这样调，出完再整片 build 一次，平时不用手动跑
//
// Into each src/scenes/<act>.html: /*@THEME@*/ /*@CUES@*/ //@COMMON_JS@ <!--@@INCLUDE:path@@--> @@expr-of-C@@
// Into src/index.html: @@TOTAL@@ <!--@@ACTS@@--> <!--@@NAV@@--> <!--@@CAPTIONS@@--> <!--@@VOICE@@--> /*@SHELL@*/
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, statSync } from "node:fs";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { join, dirname } from "node:path";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const rd = (p) => readFileSync(join(root, p), "utf8");
const cfgPath = process.env.CONFIG || "video.config.json";
const cfg = JSON.parse(rd(cfgPath));
const swap = (s) => Object.entries(cfg.textReplace || {}).reduce((acc, [a, b]) => acc.split(a).join(b), s);
const timing = JSON.parse(rd(cfg.timing));
const r3 = (x) => Math.round(x * 1000) / 1000;

// ── acts: start = first line − lead (first act starts at 0); end = next act start (last: last line + tail)
const acts = cfg.acts.map((a) => ({ ...a, lines: timing.lines.filter((l) => l.act === a.id) }));
const orphan = timing.lines.filter((l) => !cfg.acts.some((a) => a.id === l.act));
if (orphan.length) throw new Error(`lines without a configured act: ${orphan.map((l) => l.id).join(", ")}`);
acts.forEach((a) => { if (!a.lines.length) throw new Error(`act ${a.id} has no lines in ${cfg.timing}`); });
acts.forEach((a, i) => { a.start = i === 0 ? 0 : r3(a.lines[0].start - (a.lead ?? 0.4)); });
acts.forEach((a, i) => {
  a.end = i < acts.length - 1 ? acts[i + 1].start : r3(a.lines[a.lines.length - 1].end + (cfg.tail ?? 2.5));
  a.dur = r3(a.end - a.start);
  const C = { end: a.dur };
  a.lines.forEach((l, k) => { C[`l${k + 1}`] = r3(l.start - a.start); C[`l${k + 1}e`] = r3(l.end - a.start); });
  for (const [alias, key] of Object.entries((cfg.aliases || {})[a.id] || {})) {
    if (C[key] === undefined) throw new Error(`alias ${a.id}.${alias} → ${key} does not exist`);
    C[alias] = C[key];
  }
  a.C = C;
});
const total = acts[acts.length - 1].end;
const byId = Object.fromEntries(acts.map((a) => [a.id, a]));
// "actB.l3" / "actB.alias" / "actB" (act start) → film seconds
const at = (ref) => {
  if (typeof ref === "number") return ref;
  const [id, key] = ref.split(".");
  const a = byId[id]; if (!a) throw new Error(`cue ${ref}: unknown act`);
  if (!key) return a.start;
  if (a.C[key] === undefined) throw new Error(`cue ${ref}: unknown key`);
  return r3(a.start + a.C[key]);
};

// ── 只重渲后面几章：FROM 那章开头所在的那一帧 = 这一版的第 0 帧（t0）。那章开头不在整帧上时，这一章晚开 lag 秒（不到一帧）
const fps = cfg.fps || 30;
const r6 = (x) => Math.round(x * 1e6) / 1e6;
let win = null;
if (process.env.FROM) {
  const k = acts.findIndex((a) => a.id === process.env.FROM);
  if (k < 1) throw new Error(`FROM=${process.env.FROM}：要写第二章以后的章 id`);
  const frame = Math.ceil(acts[k].start * fps - 1e-6);
  win = { from: acts[k].id, k, frame, t0: frame / fps, lag: r3(frame / fps - acts[k].start), drift: Number(process.env.DRIFT) || total };
}
const shown = win ? acts.slice(win.k) : acts;
const t0 = win ? win.t0 : 0;
const slotStart = (a) => (!win ? a.start : a.id === win.from ? 0 : r6(a.start - t0));
const slotDur = (a) => (!win ? a.dur : r6(a.end - t0 - slotStart(a)));

// ── scenes
const css = rd("src/theme.css"), js = rd("src/common.js");
const evalExpr = (C, expr) => {
  const v = Function("C", `"use strict"; return (${expr});`)(C);
  if (typeof v !== "number" || !isFinite(v)) throw new Error(`@@${expr}@@ did not give a number`);
  return String(r3(v));
};
const inject = (s, C) => {
  s = s.replace("/*@THEME@*/", css).replace("//@COMMON_JS@", js).replace(/<!--@@INCLUDE:([^@]+)@@-->/g, (_, f) => rd(f.trim()));
  if (C) s = s.replace("/*@CUES@*/", JSON.stringify(C)).replace(/@@([^@]+)@@/g, (_, e) => evalExpr(C, e));
  return s;
};
mkdirSync(join(root, "compositions"), { recursive: true });
// remove stale scene builds from another version so lint/preview only see this one
const keep = new Set(shown.map((a) => a.id));
for (const f of readdirSync(join(root, "compositions"))) if (/^act.*\.html$/.test(f) && !keep.has(f.replace(".html", ""))) execFileSync("rm", [join(root, "compositions", f)]);
let allText = "";
for (const a of shown) {
  const src = `src/scenes/${a.id}.html`;
  if (!existsSync(join(root, src))) throw new Error(`missing ${src} — write this act's scene (see references/motion-language.md)`);
  const out = swap(inject(rd(src), a.C));
  writeFileSync(join(root, "compositions", `${a.id}.html`), out);
  a.html = out;
  allText += out;
}

// ── shell: act slots, navigation, captions, audio
const slots = shown.map((a) => `        <div id="el-${a.id}" data-composition-id="${a.id}" data-composition-src="compositions/${a.id}.html" data-start="${slotStart(a)}" data-duration="${slotDur(a)}" data-track-index="1" data-width="1920" data-height="1080"></div>`).join("\n");
const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;");
const chapters = cfg.chapters || [];
let navHtml = "", nav = null;
if (chapters.length) {
  navHtml = `          <div class="nav" id="nav">${chapters.map((c, i) => `<span><em>${String(i + 1).padStart(2, "0")}</em>${esc(c.label)}</span>`).join("")}</div>`;
  const marks = [];
  chapters.forEach((c, i) => {
    (c.preview || []).forEach((p) => marks.push([at(p), i]));
    marks.push([r3(at(c.act) + 0.2), i]);
  });
  marks.sort((a, b) => a[0] - b[0]);
  nav = { show: cfg.navFrom ? at(cfg.navFrom) : r3(at(chapters[0].act)), hide: cfg.navUntil ? r3(at(cfg.navUntil) - 0.2) : null, marks };
}
const pangu = (t) => t.replace(/([一-鿿])([A-Za-z0-9])/g, "$1 $2").replace(/([A-Za-z0-9])([一-鿿])/g, "$1 $2").replace(/ {2,}/g, " ");
const capHtml = (t) => esc(pangu(t)).replace(/【([^】]+)】/g, '<b class="k"><i>$1</i></b>');
// noCaptions: ["actP"] — 这些章底部不出字幕（比如片尾字幕那种画面里自己就有文字的章）；SRT 照常完整导出
const noCap = new Set(cfg.noCaptions || []);
// 字幕多留 0.12 秒，但不压到下一句（两句紧挨着时不叠在一起）
const capDur = (l, i) => { const nx = timing.lines[i + 1]; const d = l.end - l.start + 0.12; return r3(nx && nx.start > l.start ? Math.min(d, nx.start - l.start) : d); };
const capItems = timing.lines.map((l, i) => ({ i, l, s: l.start, d: capDur(l, i), h: capHtml(l.cap || l.text) })).filter((c) => !noCap.has(c.l.act));
const capCut = win && capItems.find((c) => c.s < t0 && c.s + c.d > t0);
if (capCut) throw new Error(`FROM=${win.from}：字幕「${capCut.l.text}」跨在切点 ${t0}s 上`);
const captions = capItems.filter((c) => c.s >= t0).map((c) => `          <div class="cap clip" id="cap-${c.i}" data-start="${r6(c.s - t0)}" data-duration="${c.d}" data-track-index="5"><span>${c.h}</span></div>`).join("\n");
const cues = timing.lines.map((l) => [l.start, l.end, pangu((l.cap || l.text).replace(/[【】]/g, ""))]);
const ts = (t) => { let ms = Math.round(t * 1000); const h = Math.floor(ms / 3600000); ms -= h * 3600000; const m = Math.floor(ms / 60000); ms -= m * 60000; const s = Math.floor(ms / 1000); ms -= s * 1000; return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")},${String(ms).padStart(3, "0")}`; };
mkdirSync(join(root, "renders"), { recursive: true });
if (!win) writeFileSync(join(root, cfg.srt || "renders/subtitles.srt"), cues.map(([a, b, t], i) => `${i + 1}\n${ts(a)} --> ${ts(b)}\n${t}\n`).join("\n"));
const voice = !win && cfg.mix && existsSync(join(root, cfg.mix))   // 只重渲后面几章时不带音轨：接好以后整条换成混音
  ? `      <audio id="mix" src="${cfg.mix}" data-start="0" data-duration="${total}" data-track-index="10" data-volume="1"></audio>`
  : "";
if (!voice && !win) console.warn(`(no mixed audio yet — run python3 tools/mix.py ${cfgPath} after this build, then build again)`);
const sigAt = cfg.sigAt ? at(cfg.sigAt) : timing.lines[0].start;
const shell = { total, sigAt, nav, ...(win ? { t0, drift: win.drift } : {}) };
// 外壳的每个动画 [开始, 时长, 是什么]（和 src/index.html 里的一一对应）：写进指纹；切点不能落在动画中间
const shellEv = [[sigAt - 0.1, 1.3, "sig"], [sigAt + 0.3, 0.6, "avatar"]];
if (nav) {
  shellEv.push([nav.show, 0.6, "nav " + chapters.map((c) => c.label).join("|")]);
  nav.marks.forEach(([t, i]) => shellEv.push([t, 0.45, "mark " + i]));
  if (nav.hide !== null) shellEv.push([nav.hide, 0.6, "hide"]);
}
const evCut = win && shellEv.find(([t, d]) => t < t0 && t + d > t0);
if (evCut) throw new Error(`FROM=${win.from}：切点 ${t0}s 落在外壳动画「${evCut[2]}」中间`);
let index = swap(inject(rd("src/index.html"))
  .replaceAll("@@TOTAL@@", String(win ? r6(total - t0) : total))
  .replace("<!--@@ACTS@@-->", slots).replace("<!--@@NAV@@-->", navHtml)
  .replace("<!--@@VOICE@@-->", voice).replace("<!--@@CAPTIONS@@-->", captions)
  .replace("/*@SHELL@*/", JSON.stringify(shell)));
// 样片：RES=1080 时外壳按 1920×1080 搭（画布不放大 2 倍），截图像素只有 4K 的四分之一，渲染快（本机渲染，不花 AI 额度）。
// 成片不设 RES，照常 4K。场景、素材都不用改。
// RES=1440：2K（2560×1440），画布放大 4/3 倍，给内存 16–31 GB 的电脑出成片用（tools/render_plan.sh）。
const RES_SHELL = { "1080": [1920, 1080, "none"], "1440": [2560, 1440, "scale(1.3333333333)"] };
if (RES_SHELL[process.env.RES]) {
  const [w, h, t] = RES_SHELL[process.env.RES];
  const swaps = [['content="width=3840, height=2160"', `content="width=${w}, height=${h}"`],
    ["html, body { width: 3840px; height: 2160px;", `html, body { width: ${w}px; height: ${h}px;`],
    ["transform: scale(2); transform-origin: 0 0;", `transform: ${t}; transform-origin: 0 0;`],
    ['data-width="3840" data-height="2160"', `data-width="${w}" data-height="${h}"`]];
  for (const [a, b] of swaps) { if (!index.includes(a)) throw new Error(`RES=${process.env.RES}: shell no longer contains ${a}`); index = index.replace(a, b); }
}
writeFileSync(join(root, "index.html"), index);
allText += index;
if (win) {
  writeFileSync(join(root, "timing/window.json"), JSON.stringify({ from: win.from, frame: win.frame, t0, lag: win.lag, drift: win.drift }));
} else {
  writeFileSync(join(root, "timing/acts.generated.json"), JSON.stringify(acts.map(({ id, start, end, dur, C }) => ({ id, start, end, dur, C })), null, 1));
  // 指纹：素材按路径 + 大小 + 修改时间认（不读内容，大视频也快；JS 里拼出来的路径认不出）；字体子集、混音、配乐、配音每次 build 都重做，不算
  const hash = (x) => createHash("sha1").update(x).digest("hex").slice(0, 16);
  const files = (ps) => ps.filter((p) => existsSync(join(root, p))).sort().map((p) => { const st = statSync(join(root, p)); return `${p} ${st.size} ${Math.round(st.mtimeMs)}`; }).join("\n");
  const refs = (html) => files([...new Set(html.match(/assets\/[^"'`()\s<>]+\.[A-Za-z0-9]{2,5}/g) || [])].filter((p) => !/^assets\/(fonts|mix|music|voice)\//.test(p)));
  const shellSrc = rd("src/index.html");
  writeFileSync(join(root, "timing/fingerprint.json"), JSON.stringify({
    version: 1, fps, res: process.env.RES || "4k", total, drift: total,
    shell: hash([shellSrc, css, js, JSON.stringify(cfg.textReplace || {}), refs(shellSrc), files(Object.values(cfg.fonts || {}).map((f) => `assets/fonts/${f}`))].join("\n")),
    acts: acts.map((a) => ({ id: a.id, start: a.start, end: a.end, html: hash(a.html), assets: hash(refs(a.html)) })),
    captions: capItems.map((c) => [c.s, c.d, hash(c.h)]),
    events: shellEv.map(([t, d, w]) => [r3(t), d, w]),
  }));
}

// ── platform word guard (visible text + captions; HTML comments ignored)
const visible = allText.replace(/<!--[\s\S]*?-->/g, "").replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1") + cues.map((c) => c[2]).join("");
const hits = (cfg.forbid || []).filter((w) => visible.includes(w));
if (hits.length) throw new Error(`forbidden words for this version still present: ${hits.join(", ")} — fix the scene, timing or textReplace`);

// ── font subsetting (pyftsubset from the per-machine venv made by scripts/new_project.sh)
const chars = new Set();
for (const ch of allText) if (ch.codePointAt(0) > 0x7f) chars.add(ch);
let ascii = "";
for (let c = 0x20; c < 0x7f; c++) ascii += String.fromCharCode(c);
writeFileSync(join(root, "tools/glyphs.txt"), ascii + [...chars].join("") + "“”‘’—…·「」『』（）：；，。！？、％→←");
const pyft = process.env.PYFTSUBSET || join(homedir(), ".cache/mihua-video/venv/bin/pyftsubset");
if (win) {}   // 字体子集用整片 build 那一份（字只多不少）
else if (existsSync(pyft)) {
  for (const [out, file] of Object.entries(cfg.fonts || {})) {
    if (!existsSync(join(root, "assets/fonts", file))) { console.warn(`font missing: assets/fonts/${file}`); continue; }
    execFileSync(pyft, [join(root, "assets/fonts", file), `--text-file=${join(root, "tools/glyphs.txt")}`, "--flavor=woff2", `--output-file=${join(root, `assets/fonts/${out}.woff2`)}`, "--layout-features=*"]);
  }
} else console.warn("pyftsubset not found — fonts not subset (run scripts/new_project.sh once on this machine)");
if (win) console.log(`built ${cfgPath} 只从 ${win.from} 起：第 ${win.frame} 帧（${t0.toFixed(3)}s）到片尾 ${r3(total - t0)}s${win.lag ? `，${win.from} 晚开 ${Math.round(win.lag * 1000)} 毫秒（那章开头不在整帧上）` : ""}`);
else console.log(`built ${cfgPath}${process.env.RES === "1080" ? " (1080p)" : process.env.RES === "1440" ? " (2K)" : ""}: ${acts.length} acts · ${total}s · ${cues.length} captions · ${chars.size} glyphs${chapters.length ? ` · nav ${chapters.length}` : ""}`);
acts.forEach((a) => console.log(`  ${a.id.padEnd(6)} ${String(a.start).padStart(7)} → ${String(a.end).padStart(7)}  (${a.dur}s)`));
