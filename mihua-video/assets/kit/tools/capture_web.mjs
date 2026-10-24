// Capture real web pages (a URL or a local .html) as 4K stills — sharp UI for windows and camera pushes.
//
//   node tools/capture_web.mjs tools/capture.json
//
// capture.json:
//   { "url": "file:///…/资源库.html",          // or https://…
//     "out": "assets/web",
//     "viewport": [1920, 1080],                 // CSS px; saved at 2× = 3840×2160
//     "shots": [
//       { "name": "home" },
//       { "name": "agent", "click": { "selector": ".nav-item", "text": "设计 Agent" } },
//       { "name": "detail", "click": { "selector": ".card-target" }, "wait": 1000 },
//       { "name": "search", "type": { "selector": "input", "text": "设计规范" } }
//     ] }
// Each shot applies its actions to the current page state, then screenshots. Prints the bounding
// boxes of clicked elements (CSS px) so scenes can place outlines/notes exactly.
// Only capture pages the creator owns or has the right to show; never log in or type credentials.
import { createRequire } from "node:module";
import { readFileSync, readdirSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const npx = join(homedir(), ".npm/_npx");
const pc = existsSync(npx) && readdirSync(npx).map((d) => join(npx, d, "node_modules")).find((d) => existsSync(join(d, "puppeteer-core")));
if (!pc) throw new Error("puppeteer-core not found — run `npx --yes hyperframes@<package.json 里锁定的版本> snapshot` once in the project, which installs it");
const puppeteer = createRequire(pc + "/")("puppeteer-core");
const shells = join(homedir(), ".cache/puppeteer/chrome-headless-shell");
const exe = existsSync(shells) && readdirSync(shells).filter((d) => !d.endsWith(".zip")).sort().reverse()
  .map((d) => join(shells, d, readdirSync(join(shells, d)).find((x) => x.startsWith("chrome-headless-shell")) || "", "chrome-headless-shell"))
  .find((p) => existsSync(p));
if (!exe) throw new Error("chrome-headless-shell not found under ~/.cache/puppeteer — run `npx --yes hyperframes@<package.json 里锁定的版本> snapshot` once");

const spec = JSON.parse(readFileSync(process.argv[2], "utf8"));
mkdirSync(spec.out, { recursive: true });
const [w, h] = spec.viewport || [1920, 1080];
const b = await puppeteer.launch({ executablePath: exe, headless: true });
const p = await b.newPage();
await p.setViewport({ width: w, height: h, deviceScaleFactor: 2 });
await p.goto(spec.url, { waitUntil: "networkidle0" });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
await wait(800);
for (const s of spec.shots) {
  let box = null;
  if (s.click) {
    box = await p.evaluate(({ selector, text }) => {
      const el = [...document.querySelectorAll(selector)].find((e) => !text || e.textContent.trim().startsWith(text));
      if (!el) return null; el.click(); const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height };
    }, s.click);
    if (!box) console.warn(`  ${s.name}: nothing matched ${JSON.stringify(s.click)}`);
  }
  if (s.type) { await p.click(s.type.selector); await p.keyboard.type(s.type.text, { delay: 40 }); }
  await wait(s.wait ?? 900);
  await p.screenshot({ path: join(spec.out, `${s.name}.png`) });
  console.log(`${s.name}.png${box ? `  clicked box (css px) x${Math.round(box.x)} y${Math.round(box.y)} w${Math.round(box.w)} h${Math.round(box.h)}` : ""}`);
}
await b.close();
