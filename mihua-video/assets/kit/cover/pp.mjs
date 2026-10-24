// 找 puppeteer 和无头 Chrome（和 tools/capture_web.mjs 同一套查找方式；没有就先在工程里跑一次 npx --yes hyperframes@<锁定版本> snapshot）
import { createRequire } from "node:module";
import { readdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const npx = join(homedir(), ".npm/_npx");
const pc = existsSync(npx) && readdirSync(npx).map((d) => join(npx, d, "node_modules")).find((d) => existsSync(join(d, "puppeteer-core")));
if (!pc) throw new Error("puppeteer-core not found — run `npx --yes hyperframes@<package.json 里锁定的版本> snapshot` once in the project, which installs it");
export const puppeteer = createRequire(pc + "/")("puppeteer-core");
const shells = join(homedir(), ".cache/puppeteer/chrome-headless-shell");
export const exe = existsSync(shells) && readdirSync(shells).filter((d) => !d.endsWith(".zip")).sort().reverse()
  .map((d) => join(shells, d, readdirSync(join(shells, d)).find((x) => x.startsWith("chrome-headless-shell")) || "", "chrome-headless-shell"))
  .find((p) => existsSync(p));
if (!exe) throw new Error("chrome-headless-shell not found under ~/.cache/puppeteer — run `npx --yes hyperframes@<package.json 里锁定的版本> snapshot` once");

// 打开一页封面：先读 body 的尺寸，把视口设成一样大再重新加载，等 window.__placed（cover.js 的 coverDone）
export async function openCover(browser, file, dpr = 2) {
  const p = await browser.newPage();
  const errs = [];
  p.on("pageerror", (e) => errs.push(String(e)));
  await p.setViewport({ width: 2000, height: 2000, deviceScaleFactor: dpr });
  await p.goto("file://" + file, { waitUntil: "networkidle0" });
  const [w, h] = await p.evaluate(() => [document.body.offsetWidth, document.body.offsetHeight]);
  await p.setViewport({ width: w, height: h, deviceScaleFactor: dpr });
  await p.reload({ waitUntil: "networkidle0" });
  await p.waitForFunction("window.__placed === true", { timeout: 20000 }).catch(() => errs.push("等不到 window.__placed（页面最后要调用 coverDone）"));
  return { p, w, h, errs };
}
