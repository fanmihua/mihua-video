// 幕后协作 v2 · 无头 Chrome 小工具（CDP，不依赖 puppeteer）：开页面、量元素位置、截屏流录成 mp4。
// 只给这一期录 Skillry 用。
import { spawn, execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

export const sleep = (ms) => new Promise((r) => setTimeout(r, Math.max(0, ms)));
const CHROME = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium"].find((p) => existsSync(p));

// 页面里的小帮手：白点光标、平滑滚动、按文字找位置、把网址糊掉
const HELPERS = `(() => {
  const cur = { x: 0, y: 0, hidden: false };
  function el() {
    let c = document.getElementById("__rec_cursor");
    if (!c) { c = document.createElement("div"); c.id = "__rec_cursor";
      c.style.cssText = "position:fixed;left:0;top:0;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;background:#fff;box-shadow:0 0 0 2px rgba(20,20,22,.88),0 4px 12px rgba(0,0,0,.35);z-index:2147483647;pointer-events:none;transition:opacity .25s;";
      c.style.transform = "translate(" + cur.x + "px," + cur.y + "px)"; if (cur.hidden) c.style.opacity = "0";
      document.documentElement.appendChild(c); }
    return c; }
  const ease = (k) => k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
  function textRange(txt, nth) {
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n, k = 0;
    while ((n = w.nextNode())) { const i = n.data.indexOf(txt); if (i >= 0) { const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + txt.length);
      if (r.getBoundingClientRect().width < 1) continue;   // 藏起来的那份（菜单、meta）不算
      if (k++ < (nth || 0)) continue; return r; } }
    return null; }
  window.__rec = {
    place(x, y) { cur.x = x; cur.y = y; el().style.transform = "translate(" + x + "px," + y + "px)"; return true; },
    show(on) { cur.hidden = !on; el().style.opacity = on ? "1" : "0"; return true; },
    move(x, y, ms) { const c = el(), x0 = cur.x, y0 = cur.y, t0 = performance.now();
      return new Promise((res) => { const step = (now) => { const k = Math.min(1, (now - t0) / ms), e = ease(k);
        c.style.transform = "translate(" + (x0 + (x - x0) * e) + "px," + (y0 + (y - y0) * e) + "px)";
        if (k < 1) requestAnimationFrame(step); else { cur.x = x; cur.y = y; res(true); } }; requestAnimationFrame(step); }); },
    press() { el().animate([{ scale: "1" }, { scale: "0.8" }, { scale: "1" }], { duration: 180 }); return true; },
    // 文字（或 css 选择器）在视口里的位置
    rect(q, nth) { let r;
      if (q.startsWith("css:")) { const e = document.querySelectorAll(q.slice(4))[nth || 0]; if (!e) return null; r = e.getBoundingClientRect(); }
      else { const g = textRange(q, nth); if (!g) return null; r = g.getBoundingClientRect();
        const ls = [...g.getClientRects()].filter((c) => c.width > 1).map((c) => ({ x: +c.x.toFixed(1), y: +c.y.toFixed(1), w: +c.width.toFixed(1), h: +c.height.toFixed(1) }));
        return { x: +r.x.toFixed(1), y: +r.y.toFixed(1), w: +r.width.toFixed(1), h: +r.height.toFixed(1), lines: ls }; }
      return { x: +r.x.toFixed(1), y: +r.y.toFixed(1), w: +r.width.toFixed(1), h: +r.height.toFixed(1) }; },
    // 平滑滚动：把某段文字滚到视口 at（0–1）的高度
    scrollTo(q, at, ms, nth) { const r = this.rect(q, nth); if (!r) return null; const sc = document.scrollingElement, from = sc.scrollTop;
      const to = Math.max(0, Math.min(from + r.y - innerHeight * at, sc.scrollHeight - innerHeight)), t0 = performance.now();
      return new Promise((res) => { if (!ms) { sc.scrollTop = to; return res(true); }
        const step = (now) => { const k = Math.min(1, (now - t0) / ms); sc.scrollTop = from + (to - from) * ease(k); k < 1 ? requestAnimationFrame(step) : res(true); }; requestAnimationFrame(step); }); },
    // 提示词里的网址糊掉（画面不露网址）
    blurUrls() { const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); const hits = []; let n;
      while ((n = w.nextNode())) if (/https?:\\/\\//.test(n.data) && !n.parentElement.closest("#__rec_cursor")) hits.push(n);
      for (const t of hits) { const re = /https?:\\/\\/\\S+?(?=[:：\\s]|$)/g; const s = t.data; let m, last = 0; const frag = document.createDocumentFragment();
        while ((m = re.exec(s))) { frag.append(s.slice(last, m.index)); const sp = document.createElement("span"); sp.textContent = m[0]; sp.style.cssText = "filter:blur(5px);"; frag.append(sp); last = m.index + m[0].length; }
        frag.append(s.slice(last)); t.parentNode.replaceChild(frag, t); }
      return hits.length; },
  };
})()`;

export async function launch(vp) {
  const port = 9300 + Math.floor(Math.random() * 400);
  const profile = join(tmpdir(), `mh-v2-rec-${process.pid}-${port}`);
  const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--hide-scrollbars", "--no-first-run",
    "--no-default-browser-check", "--force-color-profile=srgb", `--window-size=${vp.width},${vp.height}`, `--force-device-scale-factor=${vp.dpr}`,
    "--autoplay-policy=no-user-gesture-required", "--mute-audio", "--remote-allow-origins=*", "about:blank"], { stdio: "ignore" });
  let target;
  for (let i = 0; i < 150 && !target; i++) { try { target = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((t) => t.type === "page"); } catch {} await sleep(100); }
  if (!target) throw new Error("Chrome 没有启动");
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener("open", r));
  let id = 0; const pending = new Map(), handlers = {};
  ws.addEventListener("message", (e) => { const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } else if (m.method && handlers[m.method]) handlers[m.method](m.params); });
  const send = (method, params = {}) => new Promise((res, rej) => { const n = ++id; pending.set(n, (m) => (m.error ? rej(new Error(`${method}: ${m.error.message}`)) : res(m.result))); ws.send(JSON.stringify({ id: n, method, params })); });
  await send("Page.enable"); await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: vp.width, height: vp.height, deviceScaleFactor: vp.dpr, mobile: false });
  await send("Page.addScriptToEvaluateOnNewDocument", { source: HELPERS });
  const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: `(async () => (${expr}))()`, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text); return r.result.value; };
  return {
    send, ev, on: (m, f) => { handlers[m] = f; },
    async goto(url, settle = 2500) { await send("Page.navigate", { url });
      for (let i = 0; i < 200; i++) { await sleep(100); if (await ev("document.readyState === 'complete' && !!window.__rec").catch(() => false)) break; }
      await ev("document.fonts.ready.then(() => true)"); await sleep(settle); },
    async click(x, y) { await send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y }); await send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
      await send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 }); },
    async hover(x, y) { await send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y }); },
    async screencast() { const frames = [], tmp = join(tmpdir(), `mh-v2-frames-${process.pid}-${port}`); rmSync(tmp, { recursive: true, force: true }); mkdirSync(tmp);
      handlers["Page.screencastFrame"] = (p) => { const f = join(tmp, `f${String(frames.length).padStart(6, "0")}.jpg`); writeFileSync(f, Buffer.from(p.data, "base64"));
        frames.push({ f, ts: p.metadata.timestamp }); send("Page.screencastFrameAck", { sessionId: p.sessionId }).catch(() => {}); };
      await send("Page.startScreencast", { format: "jpeg", quality: 93, maxWidth: vp.width * vp.dpr, maxHeight: vp.height * vp.dpr, everyNthFrame: 1 });
      return { frames, tmp }; },
    async stop(cast, t0, span, out) { await send("Page.stopScreencast"); await sleep(300);
      const list = []; let prev = null;
      for (const fr of cast.frames) { const t = Math.max(0, fr.ts - t0 / 1000); if (prev) list.push({ f: prev.f, d: Math.max(0, t - prev.t) }); prev = { f: fr.f, t }; }
      if (prev) list.push({ f: prev.f, d: Math.max(0.04, span - prev.t) });
      const txt = list.filter((x) => x.d > 0).map((x) => `file '${x.f}'\nduration ${x.d.toFixed(4)}`).join("\n") + `\nfile '${list[list.length - 1].f}'\n`;
      writeFileSync(join(cast.tmp, "list.txt"), txt);
      execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", join(cast.tmp, "list.txt"), "-vf", "fps=30,format=yuv420p", "-t", span.toFixed(3),
        "-c:v", "libx264", "-crf", "14", "-preset", "slow", "-g", "30", "-an", "-movflags", "+faststart", out]);
      const n = cast.frames.length; rmSync(cast.tmp, { recursive: true, force: true }); return n; },
    close() { try { ws.close(); } catch {} chrome.kill(); rmSync(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 }); },
  };
}
