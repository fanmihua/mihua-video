#!/usr/bin/env python3
"""口播节奏检查（全局规则）：换话题的地方要停够，断句太短，听的人脑子跟不上。

读 timing/film.json（AI 配音和用户自己录的都一样），逐章量：
  · 说话时每秒几个字（只算说话的时间，不算停顿）          只列出来（参考：克隆声音原速约 5.2；真人口播约 5.8）
  · 句与句之间停顿的中位数                                  只列出来
  · 换话题处的停顿：script.md 里写了 <pause ≥1.0> 的地方，实际停顿要 ≥ 1.0 秒；
    超过 16 句的章至少有一处换话题停顿（章与章之间靠 --act-gap，也要 ≥ 1.2 秒）
不达标的章列出来：AI 配音就在稿子里加 <pause>、调 --speed 重新合成；用户自己录的，把太赶的地方告诉用户。

用法：python3 tools/pace_check.py [--script script.md] [--timing timing/film.json]
"""
import argparse, json, re, statistics as st, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--script", default="script.md")
ap.add_argument("--timing", default="timing/film.json")
ap.add_argument("--max-rate", type=float, default=6.5)   # 只拦异常快的；语速用原速，不调快慢
ap.add_argument("--min-gap", type=float, default=0.0)    # 句间停顿只列出来看，不拦（句子之间交给声音自己的节奏）
ap.add_argument("--topic-gap", type=float, default=1.0)
ap.add_argument("--act-gap", type=float, default=1.2)
a = ap.parse_args()

L = json.loads(Path(a.timing).read_text(encoding="utf-8"))["lines"]
chars = lambda t: len(re.sub(r"[\s，。、？！：；「」【】,.?!:;|\-]", "", t))

# script.md 里每章「哪一句后面写了 ≥1 秒的 pause」（按句子在章里的序号）
topic = {}
sp = Path(a.script)
if sp.exists():
    txt = re.sub(r"<!--.*?-->", "", sp.read_text(encoding="utf-8"), flags=re.S)
    cur, n = None, 0
    for raw in txt.splitlines():
        s = raw.strip()
        m = re.match(r"#\s*(act\w+)", s)
        if m:
            cur, n = m.group(1), 0; topic[cur] = set(); continue
        if not cur or not s:
            continue
        m = re.fullmatch(r"<pause\s+([\d.]+)>", s)
        if m:
            if float(m.group(1)) >= a.topic_gap and n: topic[cur].add(n - 1)
            continue
        if s.startswith("[通用]") or re.fullmatch(r"<\w+\s+[\d.]+>", s):   # [通用] 行、<speed> 这类指令不算句子
            continue
        n += 1

by = {}
for l in L:
    by.setdefault(l.get("act"), []).append(l)
acts = list(by)
bad = 0
print(f"{'章':6}{'行':>4}{'字/秒':>8}{'句间中位':>9}{'换话题停顿':>12}   问题")
for ai, act in enumerate(acts):
    ls = by[act]
    c = sum(chars(l["text"]) for l in ls); t = sum(l["end"] - l["start"] for l in ls) or 1
    gaps = [ls[i + 1]["start"] - ls[i]["end"] for i in range(len(ls) - 1)]
    rate, med = c / t, (st.median(gaps) if gaps else 0)
    want = sorted(i for i in topic.get(act, set()) if i < len(gaps))
    short = [i for i in want if gaps[i] < a.topic_gap]
    probs = []
    if rate > a.max_rate: probs.append(f"太快（{rate:.2f} > {a.max_rate}）")
    if gaps and med < a.min_gap: probs.append(f"句间太短（中位 {med:.2f} 秒）")
    if len(ls) > 16 and not want: probs.append("稿子里没标换话题停顿（<pause 1.2>）")
    for i in short: probs.append(f"第 {i + 1} 句后只停了 {gaps[i]:.2f} 秒")
    if ai + 1 < len(acts):
        g = by[acts[ai + 1]][0]["start"] - ls[-1]["end"]
        if g < a.act_gap: probs.append(f"到下一章只停了 {g:.2f} 秒")
    bad += bool(probs)
    tp = f"{len(want) - len(short)}/{len(want)}" if want else "—"
    print(f"{act:6}{len(ls):>4}{rate:>8.2f}{med:>9.2f}{tp:>12}   {'；'.join(probs) or '✓'}")
allc = sum(chars(l["text"]) for l in L); allt = sum(l["end"] - l["start"] for l in L) or 1
print(f"全片 {allc / allt:.2f} 字/秒，总长 {L[-1]['end']:.1f} 秒")
print("✓ 节奏达标" if not bad else f"✗ {bad} 章要改：稿子里加 <pause>、调 --speed 重新合成（用户自己录的，把太赶的地方告诉用户）")
sys.exit(1 if bad else 0)
