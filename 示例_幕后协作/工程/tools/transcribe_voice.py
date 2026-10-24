#!/usr/bin/env python3
"""Transcribe the real voice-over into a draft timing file — the film's clock.

    python3 tools/transcribe_voice.py [--intro 1.4] [--prompt "术语提示"] [--out timing/film.json]

Reads assets/voice/voice.wav (run tools/prep_voice.py first). Uses mlx-whisper large-v3-turbo with
word timestamps (Apple Silicon; installed into the per-machine venv by scripts/new_project.sh).

Output lines are subtitle-sized clauses: split at ，。？！：； , very short clauses (<0.8 s) merged
into the next one, long ones (>17 字) split at 、. Every line gets:
  id, act: null, text (as heard), cap (same text — add 【keyword】 marks by hand), start/end (film s)
`--intro` is the music-only opening before the first word (film time = voice time + intro).

The draft ALWAYS needs a human pass (references/audio.md › 用户自己录):
  • fix mis-heard words (e.g. 优社→优设, 路径→录进) in BOTH text and cap — the recording is the truth,
    not the original script; keep the speaker's actual wording;
  • assign every line an act id; add 1–2 【key words】 per caption;
  • traditional characters from the model are converted to simplified below, but check names.
"""
import argparse, json, re
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--intro", type=float, default=1.4)
ap.add_argument("--prompt", default="")  # extra terms to bias recognition (names, products)
ap.add_argument("--out", default="timing/film.json")
a = ap.parse_args()
root = Path(__file__).resolve().parent.parent

import mlx_whisper  # noqa: E402  (venv: ~/.cache/mihua-video/venv)
r = mlx_whisper.transcribe(str(root / "assets/voice/voice.wav"), path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
                           language="zh", word_timestamps=True,
                           initial_prompt="以下是普通话口播，使用简体中文。" + a.prompt)
words = [w for s in r["segments"] for w in s.get("words", [])]
(root / "timing").mkdir(exist_ok=True)
(root / "timing/words.json").write_text(json.dumps(words, ensure_ascii=False, indent=0), encoding="utf8")

T2S = str.maketrans("們這個來說時後還會麼樣對過裡為經發現實際設計組規範資產準備關聯識頻課線視訊聽學習問題機場動畫裏見開點擊應該讓嗎號體標頁圖庫錄製單獨內結覺謝", "们这个来说时后还会么样对过里为经发现实际设计组规范资产准备关联识频课线视讯听学习问题机场动画里见开点击应该让吗号体标页图库录制单独内结觉谢")
clauses, cur = [], []
for w in words:
    cur.append(w)
    if re.search(r"[，,。？?！!：:；;]$", w["word"].strip()):
        clauses.append(cur); cur = []
if cur: clauses.append(cur)

def mk(ws):
    t = "".join(x["word"] for x in ws).strip().translate(T2S)
    t = t.replace(",", "，").replace("?", "？").replace("!", "！").replace(":", "：").replace(";", "；")
    return {"text": re.sub(r"[，。；：]+$", "", t), "start": ws[0]["start"], "end": ws[-1]["end"], "n": len(ws)}

lines = [mk(c) for c in clauses]
i = 0
while i < len(lines) - 1:              # merge very short clauses forward
    if lines[i]["end"] - lines[i]["start"] < 0.8:
        nxt = lines.pop(i + 1)
        lines[i] = {"text": lines[i]["text"] + "，" + nxt["text"], "start": lines[i]["start"], "end": nxt["end"], "n": 0}
    else:
        i += 1
out = []
for k, l in enumerate(lines):
    out.append({"id": f"L{k + 1:02d}", "act": None, "text": l["text"], "cap": l["text"],
                "start": round(l["start"] + a.intro, 2), "end": round(l["end"] + a.intro, 2)})
(root / a.out).write_text(json.dumps({"source": "voice.wav (whisper word timings)", "voice_offset": a.intro, "lines": out},
                                     ensure_ascii=False, indent=1), encoding="utf8")
for l in out:
    flag = "  ← >17 字，考虑在、处拆" if len(l["text"]) > 17 else ""
    print(f"{l['id']} {l['start']:6.2f}–{l['end']:6.2f}  {l['text']}{flag}")
print(f"\nwrote {a.out} · {len(out)} lines · now: fix words, assign acts, add 【key words】")
