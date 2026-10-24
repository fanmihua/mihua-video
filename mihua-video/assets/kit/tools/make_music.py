#!/usr/bin/env python3
"""原创合成配乐「跟着口播走」（只用 numpy，无版权问题）。所有视频都用这一版（品牌声音，每支都一样）。

    ~/.cache/mihua-video/venv/bin/python tools/make_music.py [--config video.config.json] [--out <默认 config 的 music>]
        [--lifts actD.l54+1.0,612.5] [--intro <秒>] [--length <秒>]

读 config 的 timing（timing/film.json 每一句的起止）和 acts / chapters / lifts，章节起止按 build.mjs 的同一套规则自己算，
不依赖 build：换了配音、做单章预览（--config video.config.actB.json）都直接跑。跑完照常 build → mix.py。
  · 说话时只有和弦、低音和很轻的底鼓，没有一直走的琶音，不抢人声；
  · 换话题的停顿（相邻两句之间 ≥ --pause 秒，默认 0.9）钢琴接一小句，停多久弹几个音（2–6 个），音取当时的和弦；
  · 每章（config chapters 里的 act，按导航顺序）换一组和弦、换调；换章前轻轻渐起，新章第一拍一声铃；
    开场、结尾这类不在 chapters 里的 act 用品牌那组和弦 Fmaj7–G6–Em7–Am7，首尾呼应；
  · 开头 --intro 秒是纯音乐（默认 = 第一句开始的时间）：钢琴琶音、渐起，不进鼓；
  · 高光（config 的 "lifts" 加上 --lifts，写口播节点 actD.l54+1.0 / actE.l44e+0.8，或直接写秒数）前后两小节琶音进来、
    多一层；结尾落在 Cmaj9 长音。
整体响度归一到 --lufs（默认 -17.1 LUFS），mix.py 的底量 -9 dB 意思不变。
--length 只在要和时间轴不一样长时才写（默认 = 最后一句 + config 的 tail）；工程里还没有时间轴时必须写，出一段不分章的配乐。
"""
import argparse, json, re, subprocess, sys, wave
import numpy as np
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--config", default="video.config.json")
ap.add_argument("--out", default=None, help="默认 config 的 music（assets/music/bed.wav）")
ap.add_argument("--length", type=float, default=None)
ap.add_argument("--intro", type=float, default=None)
ap.add_argument("--lifts", default="")
ap.add_argument("--pause", type=float, default=0.9)
ap.add_argument("--bpm", type=float, default=92)
ap.add_argument("--lufs", type=float, default=-17.1)
a = ap.parse_args()

root = Path(__file__).resolve().parent.parent
def rel(p): p = Path(p); return p if p.is_absolute() else root / p
cfg_path = rel(a.config)
cfg = json.loads(cfg_path.read_text(encoding="utf8")) if cfg_path.exists() else {}
tl_path = rel(cfg.get("timing", "timing/film.json"))
lines = json.loads(tl_path.read_text(encoding="utf8"))["lines"] if tl_path.exists() else []

# ---------- 章节：和 build.mjs 一样——起点 = 第一句 − lead（第一章从 0 开始），终点 = 下一章起点（最后一章：最后一句 + tail）
r3 = lambda x: round(x, 3)
conf_acts = cfg.get("acts") or [{"id": i} for i in dict.fromkeys(l["act"] for l in lines)]
ACTS = []
for x in conf_acts:
    ls = [l for l in lines if l["act"] == x["id"]]
    if ls: ACTS.append({"id": x["id"], "lines": ls, "start": 0.0 if not ACTS else r3(ls[0]["start"] - x.get("lead", 0.4))})
for i, x in enumerate(ACTS):
    x["end"] = ACTS[i + 1]["start"] if i < len(ACTS) - 1 else r3(x["lines"][-1]["end"] + cfg.get("tail", 2.5))
    C = {"end": r3(x["end"] - x["start"])}
    for k, l in enumerate(x["lines"], 1):
        C[f"l{k}"] = r3(l["start"] - x["start"]); C[f"l{k}e"] = r3(l["end"] - x["start"])
    for alias, key in cfg.get("aliases", {}).get(x["id"], {}).items():
        if key in C: C[alias] = C[key]
    x["C"] = C
ACT = {x["id"]: x for x in ACTS}
main_cfg = root / "video.config.json"     # 单章预览、通用版的 config 是从它改出来的：缺导航时借它的章节顺序，lifts 指到别的章不算写错
MAIN = json.loads(main_cfg.read_text(encoding="utf8")) if main_cfg.exists() else {}

if a.length is None and not ACTS:
    sys.exit(f"✗ 没找到口播时间轴（{tl_path.relative_to(root) if tl_path.is_relative_to(root) else tl_path}）：先配音 / 转写，或者用 --length <秒> 出一段不分章的配乐")
LENGTH = a.length or ACTS[-1]["end"]
if ACTS:
    CHAPS = [(x["id"], x["start"], x["end"]) for x in ACTS if x["start"] < LENGTH - 0.5]
    CHAPS[-1] = (CHAPS[-1][0], CHAPS[-1][1], LENGTH)                 # --length 比时间轴长 / 短：最后一章跟着伸缩
    if lines[-1]["end"] > LENGTH - 1: print(f"⚠ --length {LENGTH} 秒没盖住最后一句（{lines[-1]['end']} 秒），结尾和弦会压在说话上", file=sys.stderr)
else:
    CHAPS = [("", 0.0, LENGTH)]
    print("⚠ 工程里还没有口播时间轴：这段配乐不分章、停顿里没有钢琴接句；配音做好后再跑一次", file=sys.stderr)

def at(ref):
    """口播节点（actD.l54+1.0 / actE.l44e / actA.hello / actB）或秒数 → 全片秒数；写错的返回 None。"""
    ref = str(ref).replace(" ", "")
    try: return float(ref)
    except ValueError: pass
    m = re.fullmatch(r"(act\w+)(?:\.(\w+))?([+-][\d.]+)?", ref)
    if not m or m.group(1) not in ACT or (m.group(2) and m.group(2) not in ACT[m.group(1)]["C"]): return None
    x = ACT[m.group(1)]
    return x["start"] + (x["C"][m.group(2)] if m.group(2) else 0) + float(m.group(3) or 0)
LIFTS = []
for ref in [*cfg.get("lifts", []), *(s for s in a.lifts.split(",") if s.strip())]:
    t_ = at(ref)
    if t_ is not None: LIFTS.append(t_)
    elif str(ref).split(".")[0] not in {x["id"] for x in MAIN.get("acts", [])} - set(ACT):   # 这一版没有那一章（单章预览）就安静跳过
        print(f"⚠ lifts 里的 {ref} 在这份时间轴里找不到，跳过", file=sys.stderr)
PAUSES = [(p["end"], q["start"]) for p, q in zip(lines, lines[1:]) if q["start"] - p["end"] >= a.pause]
INTRO = a.intro if a.intro is not None else (lines[0]["start"] if lines else 3.0)
if a.intro is None and INTRO < 1: INTRO = 0.0                        # 单章预览从说话前 0.4 秒开始，没有纯音乐开头

SR = 48000
N = int(LENGTH * SR)
beat = 60 / a.bpm
bar = 4 * beat
L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(7)

# ---------- 乐器：暖 pad、电钢琴、低音、轻底鼓，加换章用的铃声和渐起 ----------
def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
def env_adsr(n, att, rel, sus=1.0):
    e = np.ones(n) * sus
    na, nr = min(int(att * SR), n), min(int(rel * SR), n)
    e[:na] = np.linspace(0, sus, na)
    if nr: e[-nr:] *= np.linspace(1, 0, nr)
    return e
def add(start, sig, g=1.0, pan=0.0):
    i = int(start * SR)
    if i >= N or i < 0: return
    j = min(N, i + len(sig))
    L[i:j] += sig[: j - i] * g * (1 - pan); R[i:j] += sig[: j - i] * g * (1 + pan)
def pad_note(m, dur, bright=1.0, att=0.9, rel=1.2):
    n = int(dur * SR); tt = np.arange(n) / SR; s = np.zeros(n)
    for k, amp in ((1, 1.0), (2, 0.35 * bright), (3, 0.16 * bright), (4, 0.08 * bright)):
        s += amp * (np.sin(2 * np.pi * hz(m) * k * tt * 1.0012) + np.sin(2 * np.pi * hz(m) * k * tt * 0.9988))
    return s * env_adsr(n, att, rel) * 0.5
def ep_note(m, dur, bright=1.0):
    n = int(dur * SR); tt = np.arange(n) / SR
    s = np.sin(2 * np.pi * hz(m) * tt) + 0.28 * bright * np.sin(4 * np.pi * hz(m) * tt) * np.exp(-tt * 6) \
        + 0.08 * bright * np.sin(6 * np.pi * hz(m) * tt) * np.exp(-tt * 9)
    return s * np.exp(-tt * 3.2) * env_adsr(n, 0.004, 0.08)
def bell(m, dur=3.0):
    n = int(dur * SR); tt = np.arange(n) / SR; f = hz(m)
    s = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 1.8) + 0.3 * np.sin(2 * np.pi * 2.76 * f * tt) * np.exp(-tt * 4.5) \
        + 0.1 * np.sin(2 * np.pi * 5.4 * f * tt) * np.exp(-tt * 8)
    return s * env_adsr(n, 0.003, 0.3)
def bass_note(m, dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * hz(m) * tt) + 0.15 * np.sin(4 * np.pi * hz(m) * tt)) * np.exp(-tt * 1.6) * env_adsr(n, 0.01, 0.1)
def kick():
    n = int(0.32 * SR); tt = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(46 + 70 * np.exp(-tt * 30)) / SR) * np.exp(-tt * 11)
def swell(dur=1.6):
    n = int(dur * SR); x = rng.standard_normal(n)
    x = np.convolve(x - np.convolve(x, np.ones(6) / 6, mode="same"), np.ones(9) / 9, mode="same")
    return x * np.linspace(0, 1, n) ** 2.5

# ---------- 和弦：根音 + 性质，换调时重新排位置，音区不跑 ----------
Q = {"maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "6": [0, 4, 7, 9], "m9": [0, 3, 10, 14], "sus": [0, 5, 7, 10], "add9": [0, 4, 7, 14]}
def voicing(root_, q, lo=52): return sorted(lo + ((root_ + iv - lo) % 12) for iv in Q[q])
def bass_of(root_, lo=38): return lo + ((root_ - lo) % 12)
SIG    = [(5, "maj7"), (7, "6"), (4, "m7"), (9, "m7")]          # 品牌那组：Fmaj7 G6 Em7 Am7（开场、结尾）
BRIGHT = [(0, "maj7"), (4, "m7"), (5, "maj7"), (7, "6")]
SOFT   = [(9, "m7"), (5, "maj7"), (0, "add9"), (7, "6")]
FLOAT  = [(2, "m9"), (7, "sus"), (0, "maj7"), (9, "m7")]
LONG   = [(5, "maj7"), (4, "m7"), (2, "m9"), (0, "maj7"), (5, "maj7"), (7, "6"), (9, "m7"), (7, "sus")]
PALETTE = [(0, BRIGHT), (2, FLOAT), (-3, SOFT), (5, BRIGHT), (-2, LONG), (0, FLOAT), (2, SOFT)]   # 第 1、2、3… 章依次（升降几个半音, 和弦）
chapters = cfg.get("chapters") or MAIN.get("chapters", [])          # 单章预览的 config 没有导航：用主 config 的，和整片一个颜色
chap_acts = list(dict.fromkeys(c["act"] for c in chapters if c.get("act")))
if not chap_acts: chap_acts = [x["id"] for x in ACTS[1:-1]]          # 哪里都没写导航：首尾当开场结尾，中间按顺序换
CHAP = {aid: PALETTE[k % len(PALETTE)] for k, aid in enumerate(chap_acts)}
ARP = [0, 1, 2, 3, 2, 1, 3, 2]

def lift_amt(t): return max([0.0] + [float(np.clip(1 - abs(t - l) / (2 * bar), 0, 1)) for l in LIFTS])
END_T = LENGTH - 3.2

GRID = []   # (t0, 和弦, 低音, 章 id, 章内第几小节, 本章结束)
for cid, cs, ce in CHAPS:
    tr, prog = CHAP.get(cid, (0, SIG))
    b = 0
    while cs + b * bar < min(ce, END_T) - 0.2:
        root_, q = prog[b % len(prog)]
        GRID.append((cs + b * bar, voicing((root_ + tr) % 12, q), bass_of((root_ + tr) % 12), cid, b, min(ce, END_T)))
        b += 1
def chord_at(t):
    cur = GRID[0]
    for g in GRID:
        if g[0] <= t + 1e-6: cur = g
        else: break
    return cur

def pad_bar(t0, ch, ce, g=0.05, bright=0.8):
    dur = min(bar + 0.6, ce - t0 + 0.5)
    for m in ch:
        add(t0, pad_note(m, dur, bright), g, -0.05); add(t0, pad_note(m + 12 if m < 50 else m, dur, bright), g * 0.9, 0.05)
def arp(t0, ch, ce, g=0.05, bright=1.0):
    for k, i in enumerate(ARP):
        tk = t0 + k * beat / 2
        if tk > ce - 0.15: break
        add(tk, ep_note(ch[i] + 12, 1.4, bright + 0.6 * lift_amt(tk)), g, 0.35 * np.sin(k * 1.3 + i))

# 1) 底：和弦 + 低音 + 轻底鼓；换章渐起 + 铃；开头纯音乐时琶音；高光处琶音进来
for t0, ch, bs, cid, b, ce in GRID:
    first = b == 0 and t0 > 1
    pad_bar(t0, ch, ce)
    if first:
        add(t0 - 1.6, swell(1.6), 0.010)
        add(t0, bell(ch[0] + 24, 3.5), 0.03, 0.25)
    add(t0, bass_note(bs, bar), 0.12); add(t0 + 2 * beat, bass_note(bs, bar / 2), 0.08)
    if t0 < INTRO:
        arp(t0, ch, ce, 0.07); continue
    if not first and t0 + bar < ce - 0.05:
        for q in (0, 2):
            if t0 + q * beat < ce - 0.1: add(t0 + q * beat, kick(), 0.08)
    la = lift_amt(t0 + bar / 2)
    if la > 0.05: arp(t0, ch, ce, 0.05 * la, 1.2)

# 2) 换话题的停顿：钢琴接一句（停多久弹几个音，2–6 个），音从当时的和弦里取
PHRASES = [[0, 1, 2, 3], [3, 2, 1, 0], [0, 2, 3, 2], [1, 2, 3, 3], [3, 1, 2, 0], [0, 1, 3, 2, 3]]
answered = 0
for k, (s, e) in enumerate(PAUSES):
    if s < INTRO + 1 or s > END_T - 2: continue
    _, ch, *_ = chord_at(s + 0.1)
    n = int(np.clip((e - s - 0.1) / (beat / 2), 2, 6))
    pat = PHRASES[k % len(PHRASES)]
    octv = 12 if k % 3 else 24
    for j in range(n):
        tj = s + 0.1 + j * beat / 2
        add(tj, ep_note(ch[pat[j % len(pat)]] + octv, 2.4 if j == n - 1 else 1.4, 1.1), 0.09 if j == 0 else 0.078, 0.3 * np.sin(j * 1.7 + k))
    answered += 1

# 3) 结尾：Cmaj9 长音
for m in [48, 55, 59, 62, 64, 67]:
    add(END_T + 0.1, pad_note(m, 3.4), 0.06); add(END_T + 0.1, ep_note(m + 12, 3.0), 0.035)

t = np.arange(N) / SR
if INTRO > 0.05:
    k = np.where(t < INTRO, 0.35 + 0.65 * np.clip(t / INTRO, 0, 1) ** 1.6, 1.0); L *= k; R *= k
def reverb(x, seed):
    r = np.random.default_rng(seed); n = int(2.2 * SR)
    ir = r.standard_normal(n) * np.exp(-np.arange(n) / SR * 3.2); ir[0] = 0
    ir = np.convolve(ir, np.ones(24) / 24, mode="same")
    m = 1 << int(np.ceil(np.log2(len(x) + n)))
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[: len(x)] / (np.max(np.abs(ir)) * 60)
L = L + 0.35 * reverb(L, 1); R = R + 0.35 * reverb(R, 2)
fade = np.clip((LENGTH - t) / 1.5, 0, 1); L *= fade; R *= fade

# ---------- 响度归一（ffmpeg 量 LUFS），峰值不超过 -0.2 dBFS ----------
out = rel(a.out or cfg.get("music", "assets/music/bed.wav"))
out.parent.mkdir(parents=True, exist_ok=True)
def write(gain):
    pcm = (np.stack([L, R], 1) * gain * 32767).astype(np.int16)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
def lufs():
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1])
pk = max(np.max(np.abs(L)), np.max(np.abs(R)))
g = 0.7 / pk
write(g); g *= 10 ** ((a.lufs - lufs()) / 20)
g = min(g, 0.98 / pk)
write(g)
cols = " ".join(f"{cid}:{'品牌' if cid not in CHAP else ('%+d' % CHAP[cid][0])}" for cid, *_ in CHAPS if cid)
print(f"wrote {out.relative_to(root) if out.is_relative_to(root) else out} · {LENGTH:.2f}s · {lufs():.1f} LUFS · "
      f"{len(CHAPS)} 段（{cols or '不分章'}）· 停顿里钢琴接句 {answered} 处 · lifts {[round(x, 2) for x in LIFTS]} · 开头纯音乐 {INTRO:.1f}s")
