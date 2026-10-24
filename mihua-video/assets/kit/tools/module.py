#!/usr/bin/env python3
"""单章预览：python3 tools/module.py actB [actC …]

写出只含这几章的 timing/film_<名>.json、video.config.<名>.json（各自的配乐、混音、字幕路径）和 sfx_<名>.json。
改完一章，先出这一章的预览给用户看，确认了再出整片（整片先出 1080p 审片版 DRAFT=1，用户确认后才出 4K）：
  ~/.cache/mihua-video/venv/bin/python tools/make_music.py --config video.config.<名>.json   # 写到这个 config 的 music（bed_<名>.wav）
  sh tools/deliver.sh video.config.<名>.json 我的视频_<名> renders/预览
做完把 renders/预览 挪进废纸篓（过程文件不留在工程里）。
"""
import json, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
acts = sys.argv[1:]
if not acts:
    sys.exit(__doc__)
name = "_".join(acts)
c = json.loads((root / "video.config.json").read_text(encoding="utf8"))
d = json.loads((root / c.get("timing", "timing/film.json")).read_text(encoding="utf8"))
lines = [l for l in d["lines"] if l["act"] in acts]
if not lines:
    sys.exit(f"timing 里没有 {' '.join(acts)} 的口播")

# 从第一章开始的预览保留开头的纯音乐钩子；其他章从第一句前 0.4 秒开始
off = 0.0 if acts[0] == c["acts"][0]["id"] else lines[0]["start"] - 0.4
for l in lines:
    l["start"] = round(l["start"] - off, 3)
    l["end"] = round(l["end"] - off, 3)
(root / f"timing/film_{name}.json").write_text(
    json.dumps({**d, "voice_offset": d.get("voice_offset", 0) - off, "lines": lines}, ensure_ascii=False, indent=1), encoding="utf8")

sfx = c.get("sfx")
if sfx and (root / sfx).exists():
    keep = [s for s in json.loads((root / sfx).read_text(encoding="utf8")) if s.get("act") in acts]
    sfx = f"sfx_{name}.json"
    (root / sfx).write_text(json.dumps(keep, ensure_ascii=False, indent=1), encoding="utf8")

# rides（演示时的音量起伏）只留落在这几章里的：两头都在就原样留；跨出去的一头裁到章边（<章>.start / <章>.end），
# 比如整片「配乐降 4 dB」从 actA 到 actP，单章预览里就变成这一章从头到尾；整段落在别的章里的丢掉
order = [a["id"] for a in c["acts"]]
pos = {a: i for i, a in enumerate(order)}
kept = sorted(acts, key=lambda a: pos.get(a, 1e9))
def ride_act(ref):
    return ref.replace(" ", "").split(".")[0]
rides = []
for r in c.get("rides", []):
    fa, ta = ride_act(r["from"]), ride_act(r["to"])
    if fa in acts: f = r["from"]
    else:
        after = [a for a in kept if pos.get(a, 1e9) > pos.get(fa, -1)]
        f = f"{after[0]}.start" if after else None
    if ta in acts: t = r["to"]
    else:
        before = [a for a in kept if pos.get(a, -1) < pos.get(ta, 1e9)]
        t = f"{before[-1]}.end" if before else None
    if f and t and pos.get(ride_act(f), 0) <= pos.get(ride_act(t), 0):
        rides.append({**r, "from": f, "to": t})

conf = {a["id"]: a for a in c["acts"]}
c.update({
    "title": f'{c.get("title", "")} · {name}',
    "timing": f"timing/film_{name}.json",
    "acts": [{**conf.get(a, {"id": a}), "lead": 0 if i == 0 else conf.get(a, {}).get("lead", 0.4)} for i, a in enumerate(acts)],
    "tail": 1.2,
    "aliases": {k: v for k, v in c.get("aliases", {}).items() if k in acts},
    "chapters": [], "navFrom": None, "navUntil": None, "sigAt": f"{acts[0]}.l1",
    "sfx": sfx,
    "rides": rides,
    "music": f"assets/music/bed_{name}.wav",
    "mix": f"assets/mix/final_{name}.wav",
    "srt": f"renders/subtitles_{name}.srt",
})
(root / f"video.config.{name}.json").write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf8")
print(f"video.config.{name}.json · {len(lines)} 句 · rides {len(rides)}/{len(c.get('rides', []))} · 从原片 {off:.2f}s 开始 · 配乐长度约 {lines[-1]['end'] + 1.2 + 1:.0f} 秒")
