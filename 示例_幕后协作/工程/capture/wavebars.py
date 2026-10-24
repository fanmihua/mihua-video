#!/usr/bin/env python3
"""把真实音频的一段画成波形（SVG 小部件，放进场景里用）。波形是从 wav 里量出来的，不是画的示意。

  python3 capture/wavebars.py <名字> <wav> <起秒> <止秒> [--w 1600] [--h 160] [--bars 400] [--ref 文件最大值|数值] [--gain 1]
  → src/partials/wave/<名字>.html：<svg class="wave" viewBox="0 0 w h"><path …/></svg>，每根竖条 = 这一小段的峰值（上下对称）
  --ref：按哪个最大值归一（默认这段自己的最大值；想让几条波形大小可比，就给同一个数，比如人声文件的最大值）
"""
import argparse, wave, struct, sys
from pathlib import Path
import array

ap = argparse.ArgumentParser()
ap.add_argument("name"); ap.add_argument("wav"); ap.add_argument("t0", type=float); ap.add_argument("t1", type=float)
ap.add_argument("--w", type=float, default=1600); ap.add_argument("--h", type=float, default=160)
ap.add_argument("--bars", type=int, default=400); ap.add_argument("--ref", default="self"); ap.add_argument("--gain", type=float, default=1.0)
a = ap.parse_args()

root = Path(__file__).resolve().parent.parent
with wave.open(a.wav, "rb") as w:
    sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
    assert sw == 2, "只支持 16 位 wav"
    n0, n1 = int(a.t0 * sr), int(a.t1 * sr)
    w.setpos(max(0, n0)); raw = w.readframes(max(0, n1 - n0))
s = array.array("h", raw)
if ch > 1: s = s[::ch]
N = len(s); step = max(1, N // a.bars)
peaks = [max(abs(x) for x in s[i:i + step]) if s[i:i + step] else 0 for i in range(0, step * a.bars, step)]
ref = max(peaks) or 1 if a.ref == "self" else float(a.ref)
bw = a.w / a.bars; mid = a.h / 2
d = []
for i, p in enumerate(peaks):
    v = min(1.0, p / ref * a.gain) * (mid - 1)
    v = max(v, 0.8)
    x = i * bw + bw * 0.18
    d.append(f"M{x:.1f} {mid - v:.1f}h{bw * 0.64:.1f}v{2 * v:.1f}h{-bw * 0.64:.1f}Z")
out = root / "src/partials/wave"; out.mkdir(parents=True, exist_ok=True)
(out / f"{a.name}.html").write_text(f'<svg class="wave" viewBox="0 0 {a.w:g} {a.h:g}" preserveAspectRatio="none"><path d="{"".join(d)}" /></svg>', encoding="utf8")
print(f"{a.name}: {Path(a.wav).name} {a.t0:.2f}–{a.t1:.2f}s  max={max(peaks)}  ref={ref:g}")
