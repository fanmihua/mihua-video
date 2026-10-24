#!/usr/bin/env python3
"""审片表：给 1080p 审片版配一张带时间点的章节表，用户看片时按「时间点 + 问题」一条条写意见。

    python3 tools/review_sheet.py video.config.json renders/审片/我的视频_审片表.md

deliver.sh 在 DRAFT=1 时会自动生成。每章一行：起止时间、导航上的章节名、开头那句口播，
最后一列留空给用户写。用户写回来的意见，按时间点逐条改、改完逐条回复「改了 / 没改，因为…」。
"""
import json, sys
from pathlib import Path

cfg_path, out = sys.argv[1], Path(sys.argv[2])
cfg = json.loads(Path(cfg_path).read_text(encoding="utf8"))
lines = json.loads(Path(cfg["timing"]).read_text(encoding="utf8"))["lines"]
label = {c["act"]: c["label"] for c in cfg.get("chapters", [])}

def mmss(t):
    t = max(0, int(t)); return f"{t // 60}:{t % 60:02d}"

rows, chapter = [], "开场"
for a in cfg["acts"]:
    ls = [l for l in lines if l["act"] == a["id"]]
    if not ls:
        continue
    chapter = label.get(a["id"], chapter)
    first = (ls[0].get("cap") or ls[0]["text"]).replace("【", "").replace("】", "")
    rows.append(f"| {mmss(ls[0]['start'])}–{mmss(ls[-1]['end'])} | {a['id']} · {chapter} | {first} |  |")

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(f"""# 审片表：{cfg.get('title', '')}

看完整片再写，意见一次列全。每条写「时间点 + 问题」，比如：
- 0:42 右上角的框歪了
- 3:10 「一行」读成了行人的行
- 5:20–5:40 这段太快，看不清

截图可以附，但写上时间点就够了。

| 时间 | 章节 | 开头这句 | 意见 |
|---|---|---|---|
""" + "\n".join(rows) + "\n\n## 其他意见\n\n- \n", encoding="utf8")
print(f"审片表 → {out}")
