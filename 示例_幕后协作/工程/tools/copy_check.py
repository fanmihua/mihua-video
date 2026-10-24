#!/usr/bin/env python3
"""扫稿：按 mihua-video 的写稿规则和自查清单，逐行标出「要改」「留意」的地方。

  python3 copy_check.py 稿子.md [更多文件] --scene selfmedia|tutorial|article
  （selfmedia = 对外自媒体，tutorial = 教程，article = 文章）

自动认两种格式（--kind 可以强制）：
  口播稿：mihua-video 的格式（# actX 章、<pause>、「显示 | 读法」、行尾 ~）。查字幕显示的文字；代码名、符号查实际要读的那部分。
  文章：Markdown。跳过 front matter、图片、代码块（```text 块照查）。
「要改」是硬规则（转折句、营销腔，教程还有问句），有就退出码 1；「留意」只负责把可疑的地方找出来，读上下文再定。
不查：字幕每行字数、多音字（mihua-video 的 tts_voice.py、polyphone_check.py 管）。
规则原文：mihua-video references/script.md › 0、› 3、› 4、› 7。
"""
import argparse, re, sys
from pathlib import Path

S = r"[^。！？；\n]"  # 同一句里的字

# (等级, 类别, 正则, 只在哪些场景查 / None = 都查, 查哪部分：show 显示文字 / say 要读的文字)
RULES = [
    ("要改", "转折句", rf"(?<!是)不是{S}{{0,40}}?而是|并非{S}{{0,30}}?而是|不在于{S}{{0,30}}?而在于|与其说{S}{{0,30}}?不如说|[，,]\s*而非|就不像{S}{{0,15}}了|你以为{S}{{0,30}}?其实|很多人以为", None, "show"),
    ("留意", "转折句", r"(?<!是)不是|而是|并非|而非|不仅|但是|但|可是|然而|其实|不像", None, "show"),
    ("要改", "营销腔", r"家人们|宝子|姐妹们|集美|干货满满|绝绝子|yyds|YYDS|强烈推荐|一定不要错过|速速|码住|建议收藏|炸裂|天花板|封神|吹爆|震惊|闭眼入|逆袭|弯道超车", None, "show"),
    ("留意", "营销腔", r"干货|手把手|保姆级|零基础|小白|一键|必看|必学|赶紧|极致|满满的|宝藏|硬核", None, "show"),
    ("留意", "说满了", rf"就能|只要{S}{{0,12}}?就|一句(?:话)?就(?:行|够|搞定)|一定|解决|不会再|再也不|都能|都会|全都|所有|彻底|完美|轻松|永远|100%|百分百|完全|保证|任何", None, "show"),
    ("留意", "动词对人", r"写设计|写(?:一份|一套)?设计稿|画(?:出来的)?页面|写规范|(?:组件库|库|AI)\s*(?:读|看)不懂|组件库(?:画|写|读|懂|理解)", None, "show"),
    ("留意", "AI 腔", r"在" + S + r"{1,12}的(?:今天|时代|当下|背景下)|众所周知|不得不说|说到底|归根结底|颗粒度|降维打击|拉通|至关重要|不可或缺|里程碑|革命性|颠覆|赋能|助力|打造|全方位|无缝|一站式|闭环|抓手|底层逻辑|降本增效|深入探讨|值得(?:注意|一提)的是|需要注意的是|综上所述|总而言之|总的来说|由此可见|不难发现|让我们|扮演着?" + S + r"{0,10}角色|彰显|体现了|奠定了?" + S + r"{0,10}基础|未来可期|机遇与挑战|挑战与(?:机遇|展望)|希望对你有(?:所)?帮助|下面我将|如果你需要|在当今|随着" + S + r"{0,15}的(?:发展|普及)|不言而喻|毋庸置疑|显而易见|本质上|某种程度上", None, "show"),
    ("留意", "翻译腔", rf"进行|作出|给予|加以|予以|之一|当{S}{{1,20}}?的?时候|作为{S}{{1,12}}?，|通过{S}{{1,15}}?来|对于{S}{{1,15}}?(?:来说|而言)|被(?:设计|定义|称为|视为|认为|用于)", None, "show"),
    ("留意", "书面腔", r"此外|然而|因此|从而|进而|鉴于|旨在|诸如|并且|(?<![不])亦|(?<![人])乃(?!至)|皆|(?<![未])遂|无须|无需|毋须|(?<![尤极])其(?![中他它余实次间])|该(?=组件|功能|方法|库|文件|页面|项|按钮|属性|规范)|若(?![是干])", {"selfmedia", "tutorial"}, "show"),
    ("要改", "问句", r"？|\?(?=\s|$)", {"tutorial"}, "show"),
    ("留意", "语气词", r"(?:呢|吧|啦|哦|嘛|呀|咯|喔)(?=[，。！？、~～\s]|$)", {"tutorial"}, "show"),
    ("留意", "四字堆砌", r"(?:[\u4e00-\u9fff]{4}、){2,}[\u4e00-\u9fff]{4}(?![\u4e00-\u9fff])|高效便捷|简单易用|灵活多变|丰富多彩|一目了然|轻松上手|赏心悦目|举足轻重|层出不穷|日新月异|事半功倍|如虎添翼|恰到好处|焕然一新|一应俱全|得心应手|游刃有余|无缝衔接|精益求精|应运而生", None, "show"),
    ("留意", "金句", r"(?:才是|就是)" + S + r"{0,10}(?:本质|真谛|意义)|真正的" + S + r"{0,6}在于", None, "show"),
    ("留意", "比喻", r"仿佛|宛如|犹如|如同|恍若|好比", None, "show"),
    ("留意", "空泛", r"在(?:实际|很多|一定|某些)(?:项目|情况|场景|程度)[中下上]?|诸多|各种各样|一些(?=问题|方面|场景|情况)", None, "show"),
]
SPOKEN_ONLY = [  # 只查口播稿，查实际要读的文字
    ("留意", "代码名", r"`[^`]+`|\b[a-z]+[A-Z]\w*\b|\b[A-Za-z]+_\w+\b|\b[a-z][\w-]*\.(?!(?:md|json|html|css|js|ts|tsx|jsx|py|sh|png|jpg|svg|mp4)\b)[a-z][\w.]*\b|[{}<>=]|\b(?!(?:shadcn|ui|app|web|logo)\b)[a-z]{2,}\b"),
    ("留意", "符号", r"[（）()／—–]|(?<![A-Za-z])/|/(?![A-Za-z])"),
]
HINT = {
    "转折句": "直接说后半句；改前改后的对比是内容本身，照常讲（script.md › 4）",
    "营销腔": "换成具体内容：这东西能干什么、省了什么",
    "说满了": "这件事真的做到、验证过吗？没验证说「一种可行的做法」「可以照着试」，验证过说清范围（script.md › 3）",
    "动词对人": "这个动作是谁做的？设计师做设计、定规范；组件库实现页面；AI 生成、翻译；代码和文档才是写的（script.md › 4）",
    "AI 腔": "删掉，或换成具体事实、具体动作（script.md › 7）",
    "翻译腔": "换回简单动词和中文语序（script.md › 7）；「组件库实现页面」照用，「实现…功能 / 效果」才换",
    "书面腔": "口播用讲课的说法：此外 → 另外，因此 → 所以，该 / 其 → 直接说名字，亦 / 皆 / 无需 → 也 / 都 / 不用",
    "问句": "教程不用问句、不自问自答，直接说结论或担心；自问自答听着像卖关子（script.md › 0）",
    "语气词": "教程不加语气词（script.md › 0）",
    "代码名": "口播说中文意思，英文放画面；产品名、文件名照念（script.md › 4）",
    "符号": "口播里不放括号、斜杠、破折号，配音会念怪（script.md › 7）",
    "的": "一句三个以上「的」：拆句，或删掉几个（script.md › 7）",
    "开头": "第一句给结果或痛点，问候、来由放在后面（script.md › 2、› 0）",
    "长句": "一句一个意思，拆开",
    "四字堆砌": "一行最多一个四字词；评价类的换成具体东西",
    "金句": "一篇最多一两句重话；说完就收，不升华",
    "比喻": "能直写就直写；比喻只讲为什么（script.md › 5）",
    "空泛": "换成一个真的细节：哪一次、哪个组件、哪一步",
    "句尾": "关键词放句尾，不收在轻飘的尾巴上",
    "节奏平": "连着几行一样长、一样的句式：插一句短的，放在关键处",
}
PH = re.compile(r"<\|phoneme_start\|>.*?<\|phoneme_end\|>")


def lines_of(text, kind):
    """逐行产出 (行号, 显示文字, 要读的文字)。"""
    if kind == "auto":
        kind = "script" if re.search(r"^(# act|<pause)", text, re.M) else "text"
    out, in_comment, fence = [], False, None
    raw = text.split("\n")
    i0 = 0
    if kind == "text" and raw and raw[0].strip() == "---":           # front matter
        i0 = next((i + 1 for i in range(1, len(raw)) if raw[i].strip() == "---"), 0)
    for n, line in enumerate(raw, 1):
        if n <= i0:
            continue
        s = line.strip()
        if in_comment:
            in_comment = "-->" not in s
            continue
        if s.startswith("<!--"):
            in_comment = "-->" not in s
            continue
        if s.startswith("```"):
            fence = None if fence is not None else s[3:].strip()
            continue
        if fence is not None and not fence.startswith("text"):
            continue
        if not s or s.startswith(("<pause", "![", "|---", "| ---")) or (kind == "script" and s.startswith("#")):
            continue
        s = re.sub(r"<!--.*?-->", "", s)
        s = re.sub(r"^\[[^\]]+\]\s*", "", s)                            # [小红书] 这类标记
        if kind == "script":
            show, _, say = s.partition(" | ")
            show = show.replace("【", "").replace("】", "").rstrip(" ~")
            has_say = bool(say)
            say = PH.sub("", say).rstrip(" ~") if say else show
            out.append((n, show, say, has_say))
        else:
            t = re.sub(r"`[^`]*`", "", s)                                  # 文章里的代码名照写
            t = re.sub(r"^#+\s*|^[-*>]\s+|^\d+\.\s+|\*\*|__", "", t)
            out.append((n, t, t, False))
    return out, kind


def check(path, scene):
    rows, kind = lines_of(Path(path).read_text(encoding="utf8"), ARGS.kind)
    found, prev = [], []
    k, lens, flat_open = kind, [], False
    for idx, (n, show, say, has_say) in enumerate(rows):
        hits = {}
        for level, cat, rx, scenes, part in RULES:
            if scenes and scene not in scenes:
                continue
            if level == "留意" and (("要改", cat) in hits):
                continue
            m = sorted(set(x if isinstance(x, str) else x[0] for x in re.findall(rx, show if part == "show" else say)))
            m = [x for x in m if x]
            if m:
                hits[(level, cat)] = m
        # 「实现」：组件库实现页面是准确的动词，前面 6 个字里有「库」就不算；「实现…功能 / 效果」才标
        bad = [m for m in re.finditer("实现", show) if "库" not in show[max(0, m.start() - 6):m.start()]]
        if bad and not (len(prev) and prev[-1].endswith("组件库") and show.startswith("实现")):
            hits.setdefault(("留意", "翻译腔"), []).append("实现")
        # 跨行的「不是 … / 而是 …」（口播稿一行一句）
        if "而是" in show and ("要改", "转折句") not in hits and any(re.search(r"(?<!是)不是|并非|不在于", p) for p in prev[-2:]):
            hits[("要改", "转折句")] = ["上一两行「不是」+ 这一行「而是」"]
            hits.pop(("留意", "转折句"), None)
        if k == "script":
            if scene in ("selfmedia", "tutorial"):
                for level, cat, rx in SPOKEN_ONLY:
                    if cat == "代码名" and has_say:       # 写了读法的行，读法是作者有意写的发音，不再查代码名
                        continue
                    m = sorted(set(re.findall(rx, say)))
                    if m:
                        hits[(level, cat)] = m
            if re.search(r"(?:注意一下|一些|的问题|这样子|而已)$", show):
                hits[("留意", "句尾")] = [show[-4:]]
            lens.append(len(re.sub(r"[，。！？、：；\s~]", "", show)))
            last5 = lens[-5:]
            if len(last5) == 5 and min(last5) >= 10 and max(last5) - min(last5) <= 2 and not flat_open:
                hits[("留意", "节奏平")] = ["连着 5 行差不多长"]
                flat_open = True
            elif len(last5) == 5 and max(last5) - min(last5) > 2:
                flat_open = False
            if idx < 2 and re.search(r"大家好|hello|Hello|我是|上一期|今天我们|这期视频", show):
                hits[("留意", "开头")] = ["开头两句在打招呼 / 讲来由"]
        for sent in re.split(r"[。！？；]", show):
            if sent.count("的") >= 3:
                hits[("留意", "的")] = [f"{sent.count('的')} 个「的」"]
            if k == "text" and scene == "article" and len(sent) > 60:
                hits[("留意", "长句")] = [f"{len(sent)} 字"]
        prev.append(show)
        if hits:
            found.append((n, show, hits))
    return found, kind


def main():
    must = 0
    for path in ARGS.files:
        found, kind = check(path, ARGS.scene)
        print(f"\n{path}（{'口播稿' if kind == 'script' else '文章'} · {ARGS.scene}）")
        cats = {}
        for n, show, hits in found:
            tags = "；".join(f"{lv}·{cat}：{'、'.join(m)}" for (lv, cat), m in hits.items())
            print(f"  {n:>4}  {show[:40]}{'…' if len(show) > 40 else ''}\n        {tags}")
            for (lv, cat) in hits:
                cats[(lv, cat)] = cats.get((lv, cat), 0) + 1
                must += lv == "要改"
        if not found:
            print("  ✓ 没有发现")
            continue
        print("\n  怎么改：")
        for cat in dict.fromkeys(c for (_, c) in sorted(cats, key=lambda x: x[0] != "要改")):
            n_must = cats.get(("要改", cat), 0)
            n_warn = cats.get(("留意", cat), 0)
            cnt = "、".join(x for x in (f"要改 {n_must}" if n_must else "", f"留意 {n_warn}" if n_warn else "") if x)
            print(f"  · {cat}（{cnt}）：{HINT.get(cat, '')}")
    print(f"\n{'✗ ' + str(must) + ' 处要改' if must else '✓ 没有要改的'}（「留意」逐处看上下文再定）")
    return 1 if must else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--scene", choices=["selfmedia", "tutorial", "article"], required=True)
    ap.add_argument("--kind", choices=["auto", "script", "text"], default="auto")
    ARGS = ap.parse_args()
    sys.exit(main())
