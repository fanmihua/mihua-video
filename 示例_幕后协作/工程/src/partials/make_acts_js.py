#!/usr/bin/env python3
"""把 build 算出的各章时长、配乐高光、换章音效的时间写成场景能用的数据（口播章的胶片、声音章的标记要用）。
build 之后跑一次、再 build 一次：CONFIG=… node tools/build.mjs && python3 src/partials/make_acts_js.py [config] && CONFIG=… node tools/build.mjs"""
import json, re, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent.parent
cfg = json.loads((root / (sys.argv[1] if len(sys.argv) > 1 else "video.config.json")).read_text(encoding="utf8"))
acts = {a["id"]: a for a in json.loads((root / "timing/acts.generated.json").read_text(encoding="utf8"))}
def at(ref):
    m = re.fullmatch(r"(act\w+)\.(\w+)([+-][\d.]+)?", ref.replace(" ", ""))
    a = acts[m.group(1)]; return round(a["start"] + a["C"][m.group(2)] + float(m.group(3) or 0), 2)
dur = {k: round(a["dur"], 2) for k, a in acts.items()}
start = {k: round(a["start"], 2) for k, a in acts.items()}
lifts = [at(r) for r in cfg.get("lifts", [])]
sfx = json.loads((root / cfg.get("sfx", "sfx.json")).read_text(encoding="utf8")) if (root / cfg.get("sfx", "sfx.json")).exists() else []
sfx_t = [round(acts[s["act"]]["start"] + acts[s["act"]]["C"][s["cue"]] + s.get("offset", 0), 2) for s in sfx if s.get("note") == "换章"]
(root / "src/partials/acts_dur.js").write_text(
    "// 由 src/partials/make_acts_js.py 从 timing/acts.generated.json、video.config.json、sfx.json 生成，不要手改\n"
    f"const ACTS_DUR = {json.dumps(dur)};\nconst ACTS_START = {json.dumps(start)};\nconst LIFTS = {json.dumps(lifts)};\nconst SFX_T = {json.dumps(sfx_t)};\n", encoding="utf8")
print("acts", dur, "lifts", lifts, "sfx", sfx_t)
