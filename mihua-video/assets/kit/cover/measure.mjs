// 量封面各块的位置（页面 px），按从上到下排好，并算出和上一块的间距——用来调「上半松、下半挤」。
//   node cover/measure.mjs [页面…]      默认量 cover/ 里所有带 <meta name="out"> 的页面
// 量的是 body 下面每一块（背景、颗粒这些铺满的层除外），以及任何加了 data-m="名字" 的元素（比如标题里的某一行）。
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, resolve, dirname, basename } from "node:path";
import { fileURLToPath } from "node:url";
import { puppeteer, exe, openCover } from "./pp.mjs";

const dir = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const pages = args.length ? args.map((f) => (existsSync(resolve(f)) ? resolve(f) : resolve(dir, f)))   // 先按当前目录找，找不到再按 cover/ 找
  : readdirSync(dir).filter((f) => f.endsWith(".html") && /<meta name="out"/.test(readFileSync(join(dir, f), "utf8").replace(/<!--[\s\S]*?-->/g, ""))).map((f) => join(dir, f));
const b = await puppeteer.launch({ executablePath: exe, headless: true });
for (const f of pages) {
  const { p, w, h, errs } = await openCover(b, f, 1);
  const rows = await p.evaluate(() => {
    const skip = (e) => ["SCRIPT", "STYLE", "LINK"].includes(e.tagName) || e.matches(".bg, .ghosts, .vig, .grain, svg.ov");
    const els = new Set([...[...document.body.children].filter((e) => !skip(e)), ...document.querySelectorAll("[data-m]")]);
    const W = document.body.offsetWidth, H = document.body.offsetHeight, out = [];
    for (const e of els) {
      const r = e.getBoundingClientRect();
      if (!r.width || !r.height || (r.width >= W && r.height >= H)) continue;     // 不可见的、铺满的层不量
      const name = e.dataset.m || e.tagName.toLowerCase() + (e.id ? "#" + e.id : "") + (e.classList.length ? "." + [...e.classList].join(".") : "");
      out.push({ name, l: r.left, t: r.top, r: r.right, b: r.bottom });
    }
    return out.sort((a, b) => a.t - b.t);
  });
  console.log(`== ${basename(f)}  ${w}×${h}` + (errs.length ? "  ⚠ " + errs.join("；") : ""));
  let prev = 0;
  for (const x of rows) {
    const gap = Math.round(x.t - prev);
    console.log(`${x.name.slice(0, 22).padEnd(22)} x ${Math.round(x.l)}–${Math.round(x.r)}  y ${Math.round(x.t)}–${Math.round(x.b)}` + (gap > 0 ? `   ↑ 空 ${gap}` : ""));
    prev = Math.max(prev, x.b);
  }
  console.log(`底边留空 ${Math.round(h - prev)}`);
  await p.close();
}
await b.close();
