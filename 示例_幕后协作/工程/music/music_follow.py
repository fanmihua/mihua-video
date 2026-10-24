#!/usr/bin/env python3
"""「幕后协作」v2 的配乐：跟着口播走。原创合成，只用 numpy，无版权问题。

    python3 music/music_follow.py [--config video.config.json] [--out assets/music/bed.wav]

要在换配音、build（有了 timing/acts.generated.json）之后跑，替代 tools/make_music.py；跑完照常 tools/mix.py。
和 skill 的 make_music.py 同一套乐器（暖 pad、电钢琴、低音、轻底鼓），区别在怎么变化：
  · 说话时只有和弦、低音和很轻的底鼓，没有一直走的琶音；
  · 换话题的停顿（≥0.9 秒，从 timing/film.json 读）钢琴接一小句，停多久弹几个音；
  · 每章换一组和弦、换调，换章前轻轻渐起、新章第一拍一声铃；开场和结尾用以前那组和弦（首尾呼应）；
  · config 的 lifts（三处高光）琶音进来、多一层；结尾落在 Cmaj9。
声音章「配乐跟着口播走」那段的演示（按字幕文字找时间，稿子改了行号也不怕）：
  · 「以前的配乐，从头到尾」到「我看样片的时候」之前：放以前那组四和弦循环（Fmaj7–G6–Em7–Am7 琶音 + 鼓）；
  · 「配乐会多加一点层次」那句：加一处高光，真的多一层（最高点在这句后面的停顿里）。
  三处演示停顿由 config 的 rides（bus music）单独放大配乐，说话时人声、配乐照常。
整体响度归一到 -17.1 LUFS（= 以前 bed.wav 的响度），mix.py 的底量 -9 dB 意思不变；整片「配乐降 4 dB」
写在 video.config.json 的 rides（bus music）里。
"""
import argparse, json, re, subprocess, wave
import numpy as np
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--project", default=str(Path(__file__).resolve().parent.parent))
ap.add_argument("--config", default="video.config.json")
ap.add_argument("--out", default="assets/music/bed.wav")
ap.add_argument("--intro", type=float, default=4.0)
ap.add_argument("--bpm", type=float, default=92)
ap.add_argument("--lufs", type=float, default=-17.1)
a = ap.parse_args()

P = Path(a.project)
cfg = json.loads((P / a.config).read_text(encoding="utf8"))
acts = json.loads((P / "timing/acts.generated.json").read_text(encoding="utf8"))
lines = json.loads((P / cfg["timing"]).read_text(encoding="utf8"))["lines"]
LENGTH = max(x["end"] for x in acts)
CHAPS = [(x["id"], x["start"], x["end"]) for x in acts]
ACT = {x["id"]: x for x in acts}
def at(ref):
    m = re.fullmatch(r"(act\w+)\.(\w+)([+-][\d.]+)?", ref.replace(" ", ""))
    x = ACT[m.group(1)]; return x["start"] + x["C"][m.group(2)] + float(m.group(3) or 0)
def line_with(text):
    hit = [l for l in lines if text in l["cap"]]
    return hit[0] if hit else None
PAUSES = [(p["end"], q["start"]) for p, q in zip(lines, lines[1:]) if q["start"] - p["end"] >= 0.9]
LIFTS = [at(r) for r in cfg.get("lifts", [])]
# 声音章演示
old_a, old_b = line_with("以前的配乐"), line_with("我看样片的时候")
OLD = (old_a["start"] - 0.3, old_b["start"] - 0.15) if old_a and old_b else None
demo_lift = line_with("配乐会多加一点层次")
if demo_lift: LIFTS.append(demo_lift["end"] + 0.8)        # 抬得最高的地方落在这句后面的演示停顿里

SR = 48000
N = int(LENGTH * SR)
beat = 60 / a.bpm
bar = 4 * beat
L = np.zeros(N); R = np.zeros(N)
L2 = np.zeros(N); R2 = np.zeros(N)   # 声音章演示「以前那组循环」单独一轨，最后按时间换进来
BUF = [L, R]
rng = np.random.default_rng(7)

# ---------- 乐器（和 make_music.py 同一套，多了铃声、渐起） ----------
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
    BUF[0][i:j] += sig[: j - i] * g * (1 - pan); BUF[1][i:j] += sig[: j - i] * g * (1 + pan)
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
def noise_hit(dur, decay, hp, lp=1):
    n = int(dur * SR); x = rng.standard_normal(n)
    x = x - np.convolve(x, np.ones(hp) / hp, mode="same")
    if lp > 1: x = np.convolve(x, np.ones(lp) / lp, mode="same")
    return x * np.exp(-np.arange(n) / SR * decay)
def swell(dur=1.6):
    n = int(dur * SR); x = rng.standard_normal(n)
    x = np.convolve(x - np.convolve(x, np.ones(6) / 6, mode="same"), np.ones(9) / 9, mode="same")
    return x * np.linspace(0, 1, n) ** 2.5

# ---------- 和弦：根音 + 性质，换调时重新排位置，音区不跑 ----------
Q = {"maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "6": [0, 4, 7, 9], "m9": [0, 3, 10, 14], "sus": [0, 5, 7, 10], "add9": [0, 4, 7, 14]}
def voicing(root, q, lo=52): return sorted(lo + ((root + iv - lo) % 12) for iv in Q[q])
def bass_of(root, lo=38): return lo + ((root - lo) % 12)
SIG    = [(5, "maj7"), (7, "6"), (4, "m7"), (9, "m7")]          # 以前那组：Fmaj7 G6 Em7 Am7
BRIGHT = [(0, "maj7"), (4, "m7"), (5, "maj7"), (7, "6")]
SOFT   = [(9, "m7"), (5, "maj7"), (0, "add9"), (7, "6")]
FLOAT  = [(2, "m9"), (7, "sus"), (0, "maj7"), (9, "m7")]
LONG   = [(5, "maj7"), (4, "m7"), (2, "m9"), (0, "maj7"), (5, "maj7"), (7, "6"), (9, "m7"), (7, "sus")]
CHAP = {"actA": (0, SIG), "actB": (0, BRIGHT), "actC": (2, FLOAT), "actD": (-3, SOFT), "actE": (5, BRIGHT),
        "actF": (-2, LONG), "actG": (0, FLOAT), "actH": (2, SOFT), "actO": (0, SIG), "actP": (0, SIG)}
ORIG_ARP = [0, 1, 2, 3, 2, 1, 3, 2]

def lift_amt(t): return max([0.0] + [float(np.clip(1 - abs(t - l) / (2 * bar), 0, 1)) for l in LIFTS])
def in_old(t): return OLD is not None and OLD[0] <= t < OLD[1]
END_T = LENGTH - 3.2

GRID = []   # (t0, 和弦, 低音, 章 id, 章内第几小节, 本章结束)
for cid, cs, ce in CHAPS:
    tr, prog = CHAP.get(cid, (0, SIG))
    b = 0
    while cs + b * bar < min(ce, END_T) - 0.2:
        root, q = prog[b % len(prog)]
        GRID.append((cs + b * bar, voicing((root + tr) % 12, q), bass_of((root + tr) % 12), cid, b, min(ce, END_T)))
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
    for k, i in enumerate(ORIG_ARP):
        tk = t0 + k * beat / 2
        if tk > ce - 0.15: break
        add(tk, ep_note(ch[i] + 12, 1.4, bright + 0.6 * lift_amt(tk)), g, 0.35 * np.sin(k * 1.3 + i))

# 1) 底：和弦 + 低音 + 轻底鼓；开头纯音乐时琶音；高光处琶音进来
for t0, ch, bs, cid, b, ce in GRID:
    first = b == 0 and t0 > 1
    pad_bar(t0, ch, ce)
    if first:
        add(t0 - 1.6, swell(1.6), 0.010)
        add(t0, bell(ch[0] + 24, 3.5), 0.03, 0.25)
    add(t0, bass_note(bs, bar), 0.12); add(t0 + 2 * beat, bass_note(bs, bar / 2), 0.08)
    if t0 < a.intro:
        arp(t0, ch, ce, 0.07); continue
    if not first and t0 + bar < ce - 0.05:
        for q in (0, 2):
            if t0 + q * beat < ce - 0.1: add(t0 + q * beat, kick(), 0.08)
    la = lift_amt(t0 + bar / 2)
    if la > 0.05: arp(t0, ch, ce, 0.05 * la, 1.2)

# 2) 声音章演示：以前那组四和弦循环（和以前的 make_music.py 一样：一小节一个和弦、八分音符琶音、底鼓 + 刷子 + 沙锤）
if OLD:
    BUF = [L2, R2]
    oa, ob = OLD
    b = 0
    while oa + b * bar < ob - 0.2:
        t0 = oa + b * bar; ch = voicing(*SIG[b % 4]); bs = bass_of(SIG[b % 4][0])
        pad_bar(t0, ch, ob + 0.3, 0.055, 1.0)
        arp(t0, ch, ob, 0.05)
        add(t0, bass_note(bs, bar), 0.16); add(t0 + 2 * beat, bass_note(bs, bar / 2), 0.11)
        for q in range(4):
            tq = t0 + q * beat
            if tq > ob - 0.1: break
            if q in (0, 2): add(tq, kick(), 0.22)
            if q in (1, 3): add(tq, noise_hit(0.22, 22, 24, 5), 0.016)
            add(tq + beat / 2, noise_hit(0.05, 80, 2, 2), 0.014, 0.1)
        b += 1
    BUF = [L, R]
    tt_ = np.arange(N) / SR
    m = np.clip(np.minimum((tt_ - oa) / 0.3 + 1, (ob - tt_) / 0.4), 0, 1)   # 0.3 秒换进、0.4 秒换回
    L[:] = L * (1 - m) + L2 * m; R[:] = R * (1 - m) + R2 * m

# 3) 换话题的停顿：钢琴接一句（停多久弹几个音，最多 6 个），音从当时的和弦里取
PHRASES = [[0, 1, 2, 3], [3, 2, 1, 0], [0, 2, 3, 2], [1, 2, 3, 3], [3, 1, 2, 0], [0, 1, 3, 2, 3]]
for k, (s, e) in enumerate(PAUSES):
    if s < a.intro + 1 or s > END_T - 2: continue
    if OLD and s < OLD[1] and e > OLD[0] - 0.2: continue      # 紧挨着「以前那组循环」的停顿留给循环
    _, ch, *_ = chord_at(s + 0.1)
    n = int(np.clip((e - s - 0.1) / (beat / 2), 2, 6))
    pat = PHRASES[k % len(PHRASES)]
    octv = 12 if k % 3 else 24
    for j in range(n):
        tj = s + 0.1 + j * beat / 2
        add(tj, ep_note(ch[pat[j % len(pat)]] + octv, 2.4 if j == n - 1 else 1.4, 1.1), 0.09 if j == 0 else 0.078, 0.3 * np.sin(j * 1.7 + k))

# 4) 结尾：Cmaj9 长音
for m in [48, 55, 59, 62, 64, 67]:
    add(END_T + 0.1, pad_note(m, 3.4), 0.06); add(END_T + 0.1, ep_note(m + 12, 3.0), 0.035)

t = np.arange(N) / SR
k = np.where(t < a.intro, 0.35 + 0.65 * np.clip(t / a.intro, 0, 1) ** 1.6, 1.0); L *= k; R *= k
def reverb(x, seed):
    r = np.random.default_rng(seed); n = int(2.2 * SR)
    ir = r.standard_normal(n) * np.exp(-np.arange(n) / SR * 3.2); ir[0] = 0
    ir = np.convolve(ir, np.ones(24) / 24, mode="same")
    m = 1 << int(np.ceil(np.log2(len(x) + n)))
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[: len(x)] / (np.max(np.abs(ir)) * 60)
L = L + 0.35 * reverb(L, 1); R = R + 0.35 * reverb(R, 2)
fade = np.clip((LENGTH - t) / 1.5, 0, 1); L *= fade; R *= fade

out = P / a.out
def write(gain):
    pcm = (np.stack([L, R], 1) * gain * 32767).astype(np.int16)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
def lufs():
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1])
g = 0.7 / max(np.max(np.abs(L)), np.max(np.abs(R)))
write(g); g *= 10 ** ((a.lufs - lufs()) / 20)
g = min(g, 0.98 / max(np.max(np.abs(L)), np.max(np.abs(R))))
write(g)
print(f"wrote {a.out} · {LENGTH:.2f}s · {lufs():.1f} LUFS · {len(PAUSES)} 处停顿 · lifts {[round(x, 2) for x in LIFTS]} · 以前那组循环 {OLD and [round(x, 2) for x in OLD]}")
