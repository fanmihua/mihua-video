#!/usr/bin/env python3
"""配音、配乐、混音都做好以后跑一次：从真实音频里生成场景要用的波形和数据（全是量出来的，不是画的）。

    ~/.cache/mihua-video/venv/bin/python capture/make_waves.py [video.config.json]

生成：
  assets/mix/stem_voice.wav / stem_bed.wav / stem_sfx.wav —— 跟 tools/mix.py 同样的摆法：人声按 voice_offset 放好；配乐按说话自动压低（闪避）；音效按 sfx.json
  src/partials/wave/*.html —— 声音章、口播章用的波形（每段的起止都从口播节点算，和场景里写的一致）
  src/partials/pitch.js —— 每一章音高起伏（半音的标准差）
  src/partials/ttscheck.html —— 配音转回文字的对照（稿子 / 听到），截「一航」那一小段
  src/partials/film-c.html —— timing/film.json 里口播章那一句（tools/code_panels.py）
改了配音或混音以后重跑，再 build。"""
import json, re, subprocess, sys, wave, array, math, html
from pathlib import Path
import numpy as np

root = Path(__file__).resolve().parent.parent
cfg = json.loads((root / (sys.argv[1] if len(sys.argv) > 1 else "video.config.json")).read_text(encoding="utf8"))
acts = {a["id"]: a for a in json.loads((root / "timing/acts.generated.json").read_text(encoding="utf8"))}
timing = json.loads((root / cfg["timing"]).read_text(encoding="utf8"))
vo_off = timing.get("voice_offset", 0)
total = max(a["end"] for a in acts.values())
first, last_end = timing["lines"][0]["start"], timing["lines"][-1]["end"]
mixdir = root / "assets/mix"; mixdir.mkdir(parents=True, exist_ok=True)
def at(act, key, off=0.0): a = acts[act]; return a["start"] + a["C"][key] + off
def ff(*args): subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)

# ── stems（和 tools/mix.py 同一套摆法）──
voice = root / cfg.get("voiceFile", "assets/voice/voice.wav"); bed = root / cfg.get("music", "assets/music/bed.wav")
ff("-i", str(voice), "-af", f"adelay={int(vo_off*1000)},apad=whole_dur={total},atrim=0:{total},aformat=sample_fmts=s16:channel_layouts=mono", "-ar", "48000", str(mixdir / "stem_voice.wav"))
bed_gain = (f"if(lt(t,{first - 0.1}),2.8,if(lt(t,{first + 0.7}),2.8-1.8*(t-{first - 0.1})/0.8,"
            f"if(lt(t,{last_end + 0.2}),1.0,if(lt(t,{last_end + 1.2}),1.0+1.2*(t-{last_end + 0.2}),2.2))))")
ff("-i", str(voice), "-i", str(bed), "-filter_complex",
   f"[0:a]adelay={int(vo_off*1000)}|{int(vo_off*1000)},aformat=channel_layouts=stereo,apad=whole_dur={total}[vo];"
   f"[1:a]volume=-9dB,volume='{bed_gain}':eval=frame,atrim=0:{total}[b];[b][vo]sidechaincompress=threshold=0.03:ratio=5:attack=40:release=450:makeup=1,aformat=sample_fmts=s16:channel_layouts=mono[o]",
   "-map", "[o]", "-ar", "48000", str(mixdir / "stem_bed.wav"))
sfx = json.loads((root / cfg.get("sfx", "sfx.json")).read_text(encoding="utf8"))
ins, parts = [], []
for i, s in enumerate(sfx):
    t = at(s["act"], s["cue"], s.get("offset", 0)); ins += ["-i", str(root / "assets/sfx" / f"{s['file']}.mp3")]
    parts.append(f"[{i}:a]aformat=channel_layouts=mono:sample_rates=48000,lowpass=f=4200,volume={s['vol']},adelay={int(t*1000)}[s{i}]")
ff(*ins, "-filter_complex", ";".join(parts) + ";" + "".join(f"[s{i}]" for i in range(len(sfx))) + f"amix=inputs={len(sfx)}:normalize=0,apad=whole_dur={total},atrim=0:{total},aformat=sample_fmts=s16[o]",
   "-map", "[o]", "-ar", "48000", str(mixdir / "stem_sfx.wav"))
final = root / cfg["mix"]
ff("-i", str(final), "-ac", "1", "-ar", "48000", "-sample_fmt", "s16", str(mixdir / "final_mono.wav"))

# ── 波形 ──
def read(path, t0, t1):
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate(); w.setpos(max(0, int(t0 * sr))); raw = w.readframes(max(0, int((t1 - t0) * sr)))
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32), sr
def peakmax(path):
    with wave.open(str(path), "rb") as w: raw = w.readframes(w.getnframes())
    return float(np.abs(np.frombuffer(raw, dtype=np.int16)).max() or 1)
def bars(name, path, t0, t1, w=1500, h=150, n=300, ref=None, gain=1.0):
    x, sr = read(path, t0, t1); step = max(1, len(x) // n)
    pk = np.array([np.abs(x[i*step:(i+1)*step]).max() if len(x[i*step:(i+1)*step]) else 0 for i in range(n)])
    ref = ref or (pk.max() or 1); bw = w / n; mid = h / 2; d = []
    for i, p in enumerate(pk):
        v = max(0.8, min(1.0, p / ref * gain) * (mid - 1)); xx = i * bw + bw * 0.18
        d.append(f"M{xx:.1f} {mid - v:.1f}h{bw*0.64:.1f}v{2*v:.1f}h{-bw*0.64:.1f}Z")
    out = root / "src/partials/wave"; out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.html").write_text(f'<svg class="wave" viewBox="0 0 {w:g} {h:g}" preserveAspectRatio="none"><path d="{"".join(d)}" /></svg>', encoding="utf8")
    print(f"wave {name}: {t0:.2f}–{t1:.2f}s")
sv, sb, ss, fm = mixdir / "stem_voice.wav", mixdir / "stem_bed.wav", mixdir / "stem_sfx.wav", mixdir / "final_mono.wav"
vref = peakmax(sv)
# 口播章「时钟」：配音（成片时间）C.l21 前 0.28 秒起 17 秒
bars("wave_c", sv, at("actC", "l21", -0.28), at("actC", "l21", -0.28) + 17.0, 1500, 150, 340)
# 声音章：三条音轨。整支片子压成一条，人声会糊成一整块；所以截分镜章开头前后 40 秒（有句间停顿、配乐在停顿处回来、换章那一声音效），
# 三条用同一个最大值，大小可比。场景里的时间标签从 ACTS_START.actD 算，和这里一致。
w0 = acts["actD"]["start"] - 20; vw, _ = read(sv, w0, w0 + 40); wref = float(np.abs(vw).max() or 1)
bars("e_voice_win", sv, w0, w0 + 40, 1220, 130, 420, wref)
bars("e_bed_win", sb, w0, w0 + 40, 1220, 130, 420, wref)
bars("e_sfx_win", ss, w0, w0 + 40, 1220, 130, 420, wref)
bars("e_bed_lifts", sb, 0, total, 1500, 90, 420)
bars("e_now", sv, at("actE", "l10", -0.2), at("actE", "l10", -0.2) + 8.0, 1500, 140, 320)
clone = root / "assets/voice/clone_sample.wav"   # 换成你自己克隆声音时用的样本；没有就删掉画 e_clone 的这几行
ff("-i", str(clone), "-ac", "1", "-ar", "48000", "-sample_fmt", "s16", str(mixdir / "clone_mono.wav"))
bars("e_clone", mixdir / "clone_mono.wav", 0, 74.0, 1500, 120, 420)
bars("e_gap", sv, at("actE", "l20", -0.3), at("actE", "l22e", 0.3), 1500, 150, 360)
d0 = at("actE", "l32", -1.0)
bars("e_duck_v", sv, d0, d0 + 10, 1500, 130, 320, vref)
bars("e_duck_m", sb, d0, d0 + 10, 1500, 130, 320, vref)
bars("e_sfxdemo", fm, at("actE", "l46"), at("actE", "l49", 0.5), 1500, 260, 380)   # 行号跟着 script.md 走：声音章前面加减句子，这里和场景里要一起改
bars("e_ride", fm, at("actE", "l51"), at("actE", "l54e", 1.0), 1180, 300, 320)
# 配乐跟着口播走（声音章 l35–l42）：以前的配乐（换之前的 bed_old.wav）截 4 个循环，一段段一模一样；
# 新的一段：「后来就改成」到「换一章」之前，人声和配乐两条对齐（中间 3 秒停顿里钢琴接一句）
# 没有 assets/music/bed_old.wav 就删掉画 e_old 的这几行（下面 ff + loop + bars("e_old"…)）
ff("-i", str(root / "assets/music/bed_old.wav"), "-ac", "1", "-ar", "48000", "-sample_fmt", "s16", str(mixdir / "bed_old_mono.wav"))
loop = 4 * 4 * 60 / 92   # 以前那组：92 BPM，一小节一个和弦，四个和弦一循环
bars("e_old", mixdir / "bed_old_mono.wav", 6 * loop, 10 * loop, 930, 130, 360)
f0, f1 = at("actE", "l38", -0.4), at("actE", "l42", 0.2)
bars("e_fol_v", sv, f0, f1, 1500, 110, 360, vref)
bars("e_fol_m", sb, f0, f1, 1500, 110, 360)

# ── 每一章音高起伏（半音的标准差）──
def f0_track(x, sr):
    hop, win = int(0.01 * sr), int(0.04 * sr); out = []
    lo, hi = int(sr / 400), int(sr / 75)
    for i in range(0, len(x) - win, hop):
        fr = x[i:i+win] * np.hanning(win); e = float(np.sqrt(np.mean(fr**2)))
        if e < 300: continue
        ac = np.correlate(fr, fr, "full")[win-1:]; ac /= ac[0] + 1e-9
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.45: out.append(sr / k)
    return np.array(out)
pitch = {}
for aid in ["actA", "actB", "actC", "actD", "actE", "actF", "actG", "actH", "actO"]:
    fs = []
    for l in timing["lines"]:
        if l["act"] != aid: continue
        x, sr = read(sv, l["start"], l["end"]); f = f0_track(x, sr)
        if len(f): fs.append(f)
    f = np.concatenate(fs) if fs else np.array([100.0])
    st = 12 * np.log2(f / np.median(f)); st = st[np.abs(st) < 12]
    pitch[aid] = round(float(np.std(st)), 2)
(root / "src/partials/pitch.js").write_text("const PITCH = " + json.dumps(pitch) + ";   // 每章音高的半音标准差，capture/make_waves.py 从配音里算\n", encoding="utf8")
print("pitch", pitch)

# ── 配音转回文字的对照：tts_check.txt 真实的前三行（# actA / 稿子 / 听到），各截到一行宽，同音字的差别标亮 ──
# timing/tts_check.txt 由 tools/tts_voice.py 配音时生成（示例工程里没带），先配音再跑这一段
import difflib
chk = (root / "timing/tts_check.txt").read_text(encoding="utf8").split("\n")
k = chk.index("# actA"); rows = chk[k:k+3]
gao, ting = rows[1][3:].split(" / ")[0], rows[2][3:].split(" / ")[0]
W = 52
def mark(s, other, tag):
    sm = difflib.SequenceMatcher(None, s, other, autojunk=False); out = ""
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        seg = html.escape(s[i1:i2])
        # 标点、空格不同不算（转写不带标点），只标字不一样的地方
        if op != "equal" and re.search(r"[\u4e00-\u9fff]", s[i1:i2]) and re.search(r"[\u4e00-\u9fff]", other[j1:j2] if op != "delete" else ""):
            seg = f'<span class="s">{seg}</span>'
        out += seg
    return out
def clip(s, n): return s[:n]
g = clip(gao, W); t = clip(ting, W - 3)
(root / "src/partials/ttscheck.html").write_text(
    f'<pre><span class="n">{k+1}</span><span class="c">{html.escape(rows[0])}</span>\n'
    f'<span class="n">{k+2}</span>稿子：{mark(g, t, "g")}…\n'
    f'<span class="n">{k+3}</span>听到：{mark(t, g, "t")}…</pre>', encoding="utf8")
print("ttscheck", g, "|", t)

# ── film.json 里口播章那一句 ──
spec = [{"name": "film-c", "file": "timing/film.json", "find": "\"记下每一句，是在第几秒说的\"", "before": 3, "count": 8}]
(root / "capture/_cp_film.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf8")
subprocess.run(["python3", str(root / "tools/code_panels.py"), str(root / "capture/_cp_film.json")], check=True)
(root / "capture/_cp_film.json").unlink()
