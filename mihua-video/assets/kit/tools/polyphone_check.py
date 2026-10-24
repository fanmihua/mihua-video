#!/usr/bin/env python3
"""合成配音前扫一遍稿子，把容易被 AI 读错的多音字列出来，让用户一次确认读法。

    python3 tools/polyphone_check.py [script.md]

为什么要有：whisper 读回检查听不出多音字读错（「一行代码」读成 xíng，它照样写「行」），
合成前不查，就只能等人在成片里听出来。

查的是「实际要读的文字」：有 `显示 | 读法` 的行查右边的读法，没有的查整行。
- 已知易错词：直接给出整行建议写法——用 Fish Audio 官方的拼音标签
  `<|phoneme_start|>hang2<|phoneme_end|>`（带声调数字，一个字一个标签），照着把那一行换掉就行；
- 其他多音字：只标出来，听一下第一章或问用户，确认没问题就不用改；
- 已经写了拼音标签的字不再提示；标签写法不合官方格式的（大写、没声调、一个标签塞了几个字、标点在里面）列出来；
- 同一个字锁了一半：一句里这个字有一处锁了读音（拼音标签或同音字）、另一处没锁，或者前后两句里锁过、这一句没锁。
  例：「读成了行人的「行」」只把最后一个字写成「型」，「行人」的「行」会被前一句的「一航」带偏读成 háng。
只提示、不拦截；退出码永远是 0。
"""
import difflib, re, sys
from pathlib import Path

PH = re.compile(r"<\|phoneme_start\|>(.*?)<\|phoneme_end\|>")
def tag(py): return f"<|phoneme_start|>{py}<|phoneme_end|>"

# 已知会读错的词 → 建议的读法写法（踩过一次就加进来）
KNOWN = {w: w.replace("行", tag("hang2")) for w in
         "一行 两行 几行 每行 这行 那行 哪行 一行行 多行 单行 整行 换行 行高 行距 行号 首行 行内".split()}
KNOWN |= {
    "调研": tag("diao4") + "研",
    "剖": tag("pou1"),                     # 「剖面图」容易读成 pāo
}
# 其他容易读错的多音字（只标出来，人工判断）；「和、都、还、只」这类 AI 很少读错的不查，免得满屏提示
RISKY = set("行重长调差数量传便降朝薄藏转折卡参背空曾")
# 这些常用词 AI 读得稳，出现了不算
SAFE = """重新 重点 重要 重复 重做 重来 重合 重叠 重心 严重 很重 太重 偏重 比重 尊重 长度 很长 太长 成长 增长 时长 长期 擅长
数据 数量 数字 数值 参数 次数 字数 函数 多数 少数 质量 能量 音量 大量 数量 流量 调整 调用 强调 色调 语调 单调 协调
差别 差异 差不多 差距 偏差 方便 随便 便宜 顺便 传统 上传 传给 传进 宣传 转场 转换 转到 转写 转成 旋转 转向 空间 空白 留空 空格
卡片 卡住 参考 参与 背景 背后 运行 执行 进行 行为 可行 银行 不行 流行 行业 发行 行动 同行 自行 降低 下降 折叠 打折 曾经 朝向
藏起 隐藏 收藏 薄片""".split()

def split_line(s):
    """「显示 | 读法」按第一个不在拼音标签里的 | 切开（标签自己也带 |），和 tts_voice.py 一样。"""
    i = PH.sub(lambda t: "_" * len(t.group()), s).find("|")
    return (s, "") if i < 0 else (s[:i], s[i + 1:])

def locks(show, say):
    """显示行里每个汉字是照读（False）还是锁了读音（True：读法里换成了拼音标签或同音字）；没写读法 = 全部照读。"""
    clean = lambda t: re.sub(r"[\s\W_]", "", t)              # 只比字，不比标点、引号、空格
    show_c = clean(show)
    if not say.strip():
        out = [(c, False) for c in show_c]
    else:
        say_c, out = "\0".join(clean(t) for t in PH.split(say)[::2]), []   # 每个标签 → 一个 \0
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, show_c, say_c, autojunk=False).get_opcodes():
            if op == "equal":
                out += [(c, False) for c in show_c[i1:i2]]
            elif op == "replace" and i2 - i1 == j2 - j1:          # 一个字对一个字：换成了别的字或标签 = 锁了
                out += [(c, True) for c in show_c[i1:i2]]
    return [(c, lk) for c, lk in out if "\u4e00" <= c <= "\u9fff"]

def lines(path):
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group().count("\n"),      # 注释换成同样多的空行，行号才和稿子对得上
                  Path(path).read_text(encoding="utf8"), flags=re.S)
    act = "?"
    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s or re.fullmatch(r"<\w+\s+[\d.]+>", s):    # <pause 1.0>、<speed 0.9> 这类指令
            continue
        if s.startswith("#"):
            act = s.lstrip("#").strip(); continue
        s = re.sub(r"^\[(小红书|通用)\]\s*", "", s)
        show, say = split_line(s)
        spoken = (say if say.strip() else show).replace("【", "").replace("】", "").strip()
        yield n, act, show.strip(), say.strip(), spoken, locks(show, say)

def tag_problems(show, spoken):
    """拼音标签的写法照官方文档：小写拼音 + 声调数字 1–5、一个字一个标签、标点放在标签外面。"""
    out = []
    if PH.search(show):
        out.append("标签写在了 | 左边（字幕会显示出来）——只写在右边的读法里")
    if spoken.count("<|phoneme_start|>") != spoken.count("<|phoneme_end|>"):
        out.append("<|phoneme_start|> 和 <|phoneme_end|> 没有成对")
    for py in PH.findall(spoken):
        if not re.fullmatch(r"[a-zü]+[1-5]", py):
            out.append(f"「{py}」应写成一个音节的小写拼音 + 声调数字，如 pou1、hang2、ma5")
    return out

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "script.md"
    known_hits, risky_hits, bad_tags, half = [], [], [], []
    rows = list(lines(path))
    for i, (n, act, show, say, spoken, lk) in enumerate(rows):
        probs = tag_problems(show, spoken)
        if probs:
            bad_tags.append((n, act, show, "；".join(probs)))
        rest = PH.sub("□", spoken)                     # 写了拼音标签的字已经定了读法，不再查
        hits = sorted({w for w in KNOWN if w in rest}, key=len, reverse=True)
        hits = [w for w in hits if not any(w != h and w in h for h in hits)]   # 「一行行」盖过「一行」
        if hits:
            fixed = spoken
            for w in hits:
                fixed = fixed.replace(w, KNOWN[w])
            known_hits.append((n, act, show, ", ".join(hits), f"{show} | {fixed}"))
            continue
        # 同一个字锁了一半：这句里别处锁过，或前后两句（同一章）锁过，这句还有照读的
        near = {c for _, a2, *_, lk2 in rows[max(0, i - 2): i + 3] if a2 == act for c, y in lk2 if y}
        mine = {c for c, y in lk if y}
        loose = [c for c in dict.fromkeys(c for c, y in lk if not y) if c in near]
        if loose:
            why = "；".join(f"「{c}」{'这句里另一处锁了读音' if c in mine else '前后句锁过读音'}，这里也要锁" for c in loose)
            half.append((n, act, show, why))
            continue
        for w in SAFE:
            rest = rest.replace(w, "")
        chars = [c for c in dict.fromkeys(rest) if c in RISKY]
        if chars:
            risky_hits.append((n, act, show, "".join(chars)))
    print(f"多音字检查：{path}")
    if half:
        print(f"\n✗ 同一个字锁了一半 {len(half)} 行——讲读音、演示读错的句子，每个多音字都要锁（模型会跟着前一句的读法念）：")
        for n, act, show, why in half:
            print(f"  L{n:<4} {act:<6} {show}    〔{why}〕")
    if bad_tags:
        print(f"\n✗ 拼音标签写法不对 {len(bad_tags)} 行（官方格式：<|phoneme_start|>pou1<|phoneme_end|>）：")
        for n, act, show, why in bad_tags:
            print(f"  L{n:<4} {act:<6} {show}    〔{why}〕")
    if known_hits:
        print(f"\n✗ 已知易错 {len(known_hits)} 行——把这一行换成下面的写法（字幕不变，读法用拼音标签）：")
        for n, act, show, words, line in known_hits:
            print(f"  L{n:<4} {act:<6} {show}    〔{words}〕\n         → {line}")
    if risky_hits:
        print(f"\n· 含多音字 {len(risky_hits)} 行——过一眼，拿不准的列给用户确认：")
        for n, act, show, chars in risky_hits:
            print(f"  L{n:<4} {act:<6} {show}    〔{chars}〕")
    if not known_hits and not risky_hits and not bad_tags and not half:
        print("  没发现多音字。")

if __name__ == "__main__":
    main()
