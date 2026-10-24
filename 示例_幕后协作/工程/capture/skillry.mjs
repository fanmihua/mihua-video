// 幕后协作 v2 · 风格章（actF）的 Skillry 真实录屏。按配音时间轴到点操作，录成 assets/video/sk_*.mp4（2880×1800）。
//   node capture/skillry.mjs [sk_list,sk_stoke_top,…]
// 视口 1152×720、2.5 倍（= 1440 宽的浏览器放大到 125%，提示词的字大一点）。
// 顶上那条带价格的横幅 + 导航 + 搜索框是固定在顶上的（约 135px），场景里裁掉；提示词里的 x.com 链接在页面里糊掉（画面不露网址）。
import { launch, sleep } from "./browser.mjs";
import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const acts = Object.fromEntries(JSON.parse(readFileSync(join(root, "timing/acts.generated.json"), "utf8")).map((a) => [a.id, a]));
const F = acts.actF.C;
const VP = { width: 1152, height: 720, dpr: 2.5 };
const BASE = "https://skillry.dev/ai-videos/opus-5-5";
const only = process.argv[2] ? process.argv[2].split(",") : null;

// steps: [actF 里的秒数, 动作]；anchor 是录屏第 0 秒对应的 actF 秒数
const CLIPS = [
  { id: "sk_list", url: BASE, anchor: F.l20 - 0.6, until: F.l26 + 0.2, cursor: [880, 520],
    steps: [
      [F.l22 - 0.45, { do: "scroll", to: "Browse 523 Opus 5.5 videos", at: 0.25, ms: 1500 }],
      [F.l24 - 0.2, { do: "move", to: "Motion graphics", ms: 520 }],
      [F.l24 + 0.95, { do: "move", to: "Explainers", ms: 420 }],
      [F.l24 + 1.75, { do: "move", to: "3D scenes", ms: 420 }],
      [F.l24 + 2.65, { do: "move", to: "Games", ms: 420 }],
      [F.l25 - 0.35, { do: "move", to: "css:a[href*='/ai-videos/opus-5-5/']", dx: 0.55, dy: 0.42, ms: 650 }],
      [F.l25 + 0.5, { do: "measure", names: ["css:a[href*='/ai-videos/opus-5-5/']", "css:nav.flex-wrap a|1", "css:nav.flex-wrap a|2", "css:nav.flex-wrap a|3", "css:nav.flex-wrap a|4"] }],
    ] },
  { id: "sk_stoke_top", url: `${BASE}/stokebuilder-356793`, anchor: F.l34 - 0.6, until: F.l37 + 0.2, cursor: [700, 560],
    steps: [
      [F.l34 - 0.5, { do: "measure", names: ["stokebuilder", "Play both", "css:video", "css:video|1"] }],
      [F.l34 + 0.15, { do: "move", to: "Play both", ms: 600 }],
      [F.l34 + 0.85, { do: "click", to: "Play both" }],
      [F.l34 + 1.4, { do: "move", abs: [610, 640], ms: 700 }],
    ] },
  { id: "sk_stoke_prompt", url: `${BASE}/stokebuilder-356793`, anchor: F.l44 - 0.6, until: F.l51 - 0.2, hidden: true,
    setup: [{ do: "showAll" }, { do: "blur" }, { do: "scroll", to: "Prompt", at: 0.31, ms: 0 }],
    steps: [
      [F.l44 - 0.5, { do: "measure", names: ["Prompt", "The author shared part"] }],
      [F.l45 - 0.6, { do: "scroll", to: "Style. Pick", at: 0.27, ms: 1300 }],
      [F.l45 + 1.2, { do: "measure", names: ["Style. Pick", "paper, typewriter-tape labels, hand-drawn marks", "halftone, manga and pixel print, kinetic data type",
        "charcoal, white and black only, Arial", "Write a shared style bible and a component kit first,", "so every animation looks like the same show."] }],
    ] },
  { id: "sk_tardi_prompt", url: `${BASE}/tardigrade111-160686`, anchor: F.l60 - 0.6, until: F.l62 + 0.3, hidden: true,
    setup: [{ do: "scroll", to: "Prompt", at: 0.3, ms: 0 }],
    steps: [
      [F.l60 - 0.5, { do: "measure", names: ["Prompt", "The author shared part", "Amazing that this is possible now.", "remotion, runway and veo to make this by itself"] }],
    ] },
];

const q = (s) => JSON.stringify(s);
async function centerOf(b, t, dx = 0.5, dy = 0.5) {
  const [sel, nth] = t.split("|");
  const r = await b.ev(`window.__rec.rect(${q(sel)}, ${+(nth || 0)})`);
  if (!r) throw new Error(`找不到：${t}`);
  return [r.x + r.w * dx, r.y + r.h * dy];
}
async function act(b, s, log, t0) {
  const stamp = (x) => log.push({ t: +((Date.now() - t0) / 1000).toFixed(2), do: s.do, ...x });
  if (s.do === "scroll") { await b.ev(`window.__rec.scrollTo(${q(s.to)}, ${s.at}, ${s.ms})`); return stamp({ to: s.to }); }
  if (s.do === "move") {
    const [x, y] = s.abs || (await centerOf(b, s.to, s.dx, s.dy));
    await b.ev(`window.__rec.move(${x}, ${y}, ${s.ms})`); await b.hover(x, y); return stamp({ x, y });
  }
  if (s.do === "click") { const [x, y] = await centerOf(b, s.to); await b.ev("window.__rec.press()"); await b.click(x, y); return stamp({ x, y }); }
  if (s.do === "measure") {
    const rects = {};
    for (const n of s.names) { const [sel, nth] = n.split("|"); rects[n] = await b.ev(`window.__rec.rect(${q(sel)}, ${+(nth || 0)})`); }
    return stamp({ rects });
  }
  if (s.do === "showAll") {   // 提示词默认折叠：先把「Show all」滚进视口再点（视口外的坐标点不到）
    for (let k = 0; k < 6 && (await b.ev(`!!window.__rec.rect("Show all")`)); k++) {
      await b.ev(`window.__rec.scrollTo("Show all", 0.5, 0)`); await sleep(700);
      const [x, y] = await centerOf(b, "Show all"); await b.click(x, y); await sleep(1200);
    }
    if (await b.ev(`!!window.__rec.rect("Show all")`)) throw new Error("提示词没有展开");
    return;
  }
  if (s.do === "blur") { await b.ev("window.__rec.blurUrls()"); return; }
}

for (const c of CLIPS) {
  if (only && !only.includes(c.id)) continue;
  const b = await launch(VP);
  try {
    await b.goto(c.url, 3500);
    for (const s of c.setup || []) await act(b, s, [], Date.now());
    await b.ev(`window.__rec.place(${(c.cursor || [900, 600]).join(",")})`);
    if (c.hidden) await b.ev("window.__rec.show(false)");
    await sleep(1200);
    const span = c.until - c.anchor, log = [];
    const cast = await b.screencast();
    await b.ev(`window.__rec.move(${(c.cursor || [900, 600])[0] + 1}, ${(c.cursor || [900, 600])[1]}, 40)`);
    while (!cast.frames.length) await sleep(20);
    const t0 = Date.now();
    for (const [at, s] of c.steps) {
      const wait = t0 + (at - c.anchor) * 1000 - Date.now();
      if (wait < -150) console.warn(`  ! ${c.id} ${s.do} 晚了 ${(-wait / 1000).toFixed(2)} 秒`);
      await sleep(wait);
      await act(b, s, log, t0);
    }
    await sleep(t0 + span * 1000 - Date.now() + 200);
    const n = await b.stop(cast, t0, span, join(root, "assets/video", `${c.id}.mp4`));
    writeFileSync(join(root, "capture", `${c.id}.json`), JSON.stringify({ id: c.id, anchor: +c.anchor.toFixed(3), span: +span.toFixed(3), viewport: VP, crop_top_css: 135, frames: n, steps: log }, null, 1));
    console.log(`✓ ${c.id}  ${span.toFixed(1)} 秒  ${n} 帧（${(n / span).toFixed(1)} 帧/秒）`);
  } finally { b.close(); }
}
