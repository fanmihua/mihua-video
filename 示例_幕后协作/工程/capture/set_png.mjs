// 开场拆层图用的两张透明图层：片场（光 + 七个角落，不含米花）、米花（站在正中间前面挥手）。从 src/partials/set 的同一份 SVG 渲染，3840×2160。
//   node capture/set_png.mjs
import { launch, sleep } from "./browser.mjs";
import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const set = readFileSync(join(root, "src/partials/set/set_actA.html"), "utf8").replace(/^<!--[^\n]*-->\n/, "");
const css = readFileSync(join(root, "src/partials/set/set.css"), "utf8");
const html = (mode) => `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: "ShuHei"; font-weight: 700; src: url("${pathToFileURL(join(root, "assets/fonts/AlimamaShuHeiTi-Bold.otf")).href}"); }
html, body { margin: 0; width: 1920px; height: 1080px; background: transparent; overflow: hidden; }
${css}
${mode === "set" ? "#a-s-mh { display: none; }" : ".mset-light, #a-s-svg > *:not(defs):not(#a-s-mh) { display: none; }"}
</style></head><body><div class="mset">${set}</div>
<script>
const mh = document.getElementById("a-s-mh"); mh.setAttribute("transform", "translate(960 806)"); document.getElementById("a-s-mh-b").setAttribute("transform", "scale(1.04)");
</script></body></html>`;
const b = await launch({ width: 1920, height: 1080, dpr: 2 });
try {
  await b.send("Emulation.setDefaultBackgroundColorOverride", { color: { r: 0, g: 0, b: 0, a: 0 } });
  for (const mode of ["set", "mh"]) {
    const f = join(root, "capture", `_tmp_${mode}.html`);
    writeFileSync(f, html(mode));
    await b.goto(pathToFileURL(f).href, 800);
    await b.ev("document.fonts.ready.then(() => true)"); await sleep(300);
    const shot = await b.send("Page.captureScreenshot", { format: "png" });
    writeFileSync(join(root, "assets/img", `layer_${mode}.png`), Buffer.from(shot.data, "base64"));
    (await import("node:fs")).rmSync(f);
    console.log("✓ layer_" + mode);
  }
} finally { b.close(); }
