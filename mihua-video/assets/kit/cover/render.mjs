// 封面出图：按 2 倍截成 PNG（1242×1656 → 2484×3312）。
//   node cover/render.mjs                      渲染 cover/ 里所有带 <meta name="out" content="封面_3比4.png"> 的页面
//   node cover/render.mjs cover_34.html --out ../成片    只渲染指定页面，写到别的目录
// 输出文件名取 <meta name="out">，没有就用页面文件名。
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, resolve, dirname, basename } from "node:path";
import { fileURLToPath } from "node:url";
import { puppeteer, exe, openCover } from "./pp.mjs";

const dir = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const oi = args.indexOf("--out");
const out = oi >= 0 ? resolve(args.splice(oi, 2)[1]) : dir;
const outName = (f) => (readFileSync(f, "utf8").replace(/<!--[\s\S]*?-->/g, "").match(/<meta name="out" content="([^"]+)"/) || [])[1];
// 页面路径先按当前目录找，找不到再按 cover/ 找
const pages = args.length ? args.map((f) => (existsSync(resolve(f)) ? resolve(f) : resolve(dir, f))) : readdirSync(dir).filter((f) => f.endsWith(".html")).map((f) => join(dir, f)).filter(outName);
if (!pages.length) { console.log("没有要渲染的页面：给封面页面加 <meta name=\"out\" content=\"封面_3比4.png\">，或在命令后面写页面文件名"); process.exit(1); }
const b = await puppeteer.launch({ executablePath: exe, headless: true });
for (const f of pages) {
  const { p, w, h, errs } = await openCover(b, f);
  const name = outName(f) || basename(f, ".html") + ".png";
  await new Promise((r) => setTimeout(r, 300));
  await p.screenshot({ path: join(out, name) });
  console.log(`${name}  ${w * 2}×${h * 2}` + (errs.length ? "  ⚠ " + errs.join("；") : ""));
  await p.close();
}
await b.close();
