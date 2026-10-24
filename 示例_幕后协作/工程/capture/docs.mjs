// 幕后协作 v2 · 官方文档页截图（口播提到某个工具时放它的官方原文；画面不露网址）。
//   node capture/docs.mjs [name,…]  → assets/web/<name>.png（视口 1280×800、2.5 倍 = 3200×2000）+ capture/docs.json（要框的那句话在截图里的位置，CSS px）
import { launch, sleep } from "./browser.mjs";
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const VP = { width: 1280, height: 800, dpr: 2.5 };
const PAGES = [
  { name: "doc_fish_clone", url: "https://docs.fish.audio/features/voice-cloning", anchor: "Clone your own voice", at: 0.35, quotes: ["Clone your own voice", "a minute or two of clear speech"] },
  { name: "doc_cc_overview", url: "https://code.claude.com/docs/en/overview", anchor: "agentic coding tool", at: 0.35, quotes: ["agentic coding tool"] },
  { name: "doc_hf_intro", url: "https://hyperframes.heygen.com/introduction", anchor: "turns HTML into video", at: 0.35, quotes: ["turns HTML into video"] },
  { name: "doc_cc_costs", url: "https://code.claude.com/docs/en/costs", anchor: "token consumption", at: 0.35, quotes: ["token consumption"] },
  { name: "doc_cc_context", url: "https://code.claude.com/docs/en/costs", anchor: "Token costs scale with context size", at: 0.4, quotes: ["Token costs scale with context size"] },
  { name: "doc_skills", url: "https://code.claude.com/docs/en/skills", anchor: "Skills extend what Claude can do", at: 0.35, quotes: ["Skills extend what Claude can do"] },
];
const only = process.argv[2] ? process.argv[2].split(",") : null;
const outJ = join(root, "capture/docs.json");
const res = existsSync(outJ) ? JSON.parse(readFileSync(outJ, "utf8")) : {};
mkdirSync(join(root, "assets/web"), { recursive: true });
for (const p of PAGES) {
  if (only && !only.includes(p.name)) continue;
  const b = await launch(VP);
  try {
    await b.goto(p.url, 3000);
    // 隐藏 cookie 提示、聊天浮窗这类挡画面的东西（不点同意）
    await b.ev(`(() => { for (const e of document.querySelectorAll('[id*=cookie i],[class*=cookie i],[aria-label*=cookie i],[id*=consent i],[class*=consent i]')) e.style.display = 'none'; return true; })()`);
    const ok = await b.ev(`window.__rec.scrollTo(${JSON.stringify(p.anchor)}, ${p.at}, 0)`);
    if (!ok) { console.log(`✗ ${p.name}: 页面上没找到「${p.anchor}」`); console.log((await b.ev("document.body.innerText")).slice(0, 1500)); continue; }
    await sleep(900);
    const quotes = {};
    for (const q of p.quotes) quotes[q] = await b.ev(`window.__rec.rect(${JSON.stringify(q)})`);
    const shot = await b.send("Page.captureScreenshot", { format: "png" });
    writeFileSync(join(root, "assets/web", `${p.name}.png`), Buffer.from(shot.data, "base64"));
    res[p.name] = { url_not_shown: p.url, viewport: VP, quotes };
    console.log(`✓ ${p.name}`, JSON.stringify(quotes));
  } finally { b.close(); }
}
writeFileSync(outJ, JSON.stringify(res, null, 1));
