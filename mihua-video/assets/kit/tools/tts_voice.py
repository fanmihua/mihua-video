#!/usr/bin/env python3
"""AI voice-over: script.md → the user's cloned voice (Fish Audio) → assets/voice/voice.wav + timing/film.json.

    ~/.cache/mihua-video/venv/bin/python tools/tts_voice.py [--script script.md] [--intro 1.4] [--variant neutral]
                                                            [--speed 1.0] [--act-gap 0.7] [--redo actB]

Replaces the "user records → prep_voice → transcribe" path. Output files have exactly the same shape, so
build.mjs / mix.py / deliver.sh do not care which path made them.

script.md (one subtitle line per line, written for the ear — see references/audio.md › AI 配音):
    # actA                         ← every act starts with "# <actId>"
    Hello，大家好
    今天聊聊【AI 配音】怎么做            ← 【】 = caption key word (spoken normally)
    都写进 SKILL.md | 都写进 skill 点 M D   ← "shown | spoken" when a term needs a pronunciation hint
    像剖面图一样 | 像<|phoneme_start|>pou1<|phoneme_end|>面图一样   ← Fish Audio pinyin tag (tone number, one per character)
    [小红书] 小红书版才有的一句              ← only in the 小红书 version   ([通用] = only in the neutral one)
    同一份设计 ~                           ← trailing " ~": read straight on into the next line (no comma between); not shown in captions
    为什么会放不进去？                     ← questions keep "？" so they are read as questions
    <pause 0.6>                          ← silence after the previous line (the act is split into passages here)
    <speed 0.9>                          ← (right under "# actX") this act only: slower / faster than --speed

How it works: an act is split at its <pause> lines into short passages; each passage is synthesised in ONE
request (natural sentence flow inside it), cached by its text in assets/voice/tts/, and the passages are joined
with exactly the written silence. Nothing is ever cut out of the middle of a clip — the old way (one request per
act, then cutting it at whisper-guessed line ends to splice in silence) clipped words and made audible stutters.
Editing one passage only re-generates that passage. Line timings come from whisper word
timestamps aligned to the known script; the same pass is the read-back check — lines whose audio does not
match the script are flagged. English terms are often mis-heard by whisper itself: listen before re-doing.
Pinyin tags (docs.fish.audio › Fine-grained control › Chinese) are sent to Fish Audio as written; before the
read-back each tag is put back to the character it stands for in the shown line, so tag text never counts as words.

Voice: voice.json in the project (copied from the skill's assets/brand/voice.json): provider, model,
reference_id, and optional "cue": a delivery direction sent in [brackets] at the start of every passage (Fish Audio
S2 emotion control; docs.fish.audio › Emotion Control). The brand default is "relaxed and conversational, light and
smooth sentence endings": without it sentence-final words come out too heavy, and temperature 0.5 makes them heavier still.
The cue is never spoken and is not part of the read-back text. API key: env FISH_API_KEY, else FISH_API_KEY=… in a .voice_keys.env in the project or any
parent folder, else ~/.config/mihua-video/keys.env. The key is never printed.
"""
import argparse, difflib, hashlib, json, os, re, subprocess, sys, urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--script", default="script.md")
ap.add_argument("--intro", type=float, default=1.4)       # music-only opening before the first word
ap.add_argument("--variant", choices=["main", "neutral"], default="main")
ap.add_argument("--speed", type=float, default=1.0)
ap.add_argument("--act-gap", type=float, default=0.7)     # breath between acts
ap.add_argument("--line-pause", type=float, default=0.0)  # extra pause added after every line (0 = natural)
ap.add_argument("--redo", nargs="*", default=[])          # act ids (actB) or single passages (actB.3 = 第 3 段) to synthesise again
ap.add_argument("--cue", default=None)                    # override voice.json "cue" for this run ("" = none)
ap.add_argument("--prompt", default="")                   # names / terms so the read-back check knows them
a = ap.parse_args()
root = Path(__file__).resolve().parent.parent

# ── voice + key ──────────────────────────────────────────────────────────────
vcfg = json.loads((root / "voice.json").read_text())
key = os.environ.get("FISH_API_KEY")
if not key:
    cands = [d / ".voice_keys.env" for d in [root, *root.parents]] + [Path.home() / ".config/mihua-video/keys.env"]
    for f in cands:
        if f.is_file():
            m = re.search(r"^FISH_API_KEY=(.+)$", f.read_text(), re.M)
            if m:
                key = m.group(1).strip(); break
if not key:
    sys.exit("✗ no FISH_API_KEY — put FISH_API_KEY=… in ~/.config/mihua-video/keys.env (or a .voice_keys.env above the project)")
try:
    import certifi; os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

# ── parse script ─────────────────────────────────────────────────────────────
# Fish Audio 官方的中文拼音标签：一个字一个 <|phoneme_start|>pou1<|phoneme_end|>（给多音字、易错字定读音）
PH = re.compile(r"<\|phoneme_start\|>(.*?)<\|phoneme_end\|>")
def split_line(s):
    """「显示 | 读法」按第一个不在拼音标签里的 | 切开（标签自己也带 |）。"""
    i = PH.sub(lambda t: "_" * len(t.group()), s).find("|")
    return (s, "") if i < 0 else (s[:i], s[i + 1:])

def plain(say, shown):
    """读法里的拼音标签换回显示行里对应的那个字：whisper 听到的是汉字，标签文字不能拿去比对，也不算字数。
    返回 (换好的读法, [(字, 拼音), …])。"""
    if not PH.search(say):
        return say, []
    shown = re.sub(r"[\s\W_]", "", shown)        # 显示行的标点、引号、空格不参与对齐（「行」的引号不能顶替那个字）
    marked, out, pys, tags = PH.sub("\0", say), [], iter(PH.findall(say)), []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, marked, shown, autojunk=False).get_opcodes():
        # 标签 ↔ 显示行同一位置的字；两边长度不同时按顺序对给其中的汉字；对不上就去掉
        han = list(shown[j1:j2]) if i2 - i1 == j2 - j1 else [c for c in shown[j1:j2] if "\u4e00" <= c <= "\u9fff"]
        for k in range(i1, i2):
            c = marked[k]
            if c == "\0":
                c = han.pop(0) if op == "replace" and han else ""
                tags.append((c, next(pys)))
            elif op == "replace" and i2 - i1 == j2 - j1 and han:
                han.pop(0)
            out.append(c)
    return "".join(out), [t for t in tags if t[0]]

acts, cur = [], None
src_text = re.sub(r"<!--.*?-->", "", (root / a.script).read_text(encoding="utf8"), flags=re.S)   # 画面注释（可以跨多行）不读
for raw in src_text.splitlines():
    s = raw.strip()
    if not s or s.startswith("<!--"):
        continue
    if s.startswith("#"):
        cur = {"id": s.lstrip("#").strip(), "lines": []}; acts.append(cur); continue
    if cur is None:
        sys.exit(f"✗ {a.script}: text before the first '# actId' heading")
    m = re.fullmatch(r"<pause\s+([\d.]+)>", s)
    if m:
        if cur["lines"]: cur["lines"][-1]["pause"] += float(m.group(1))
        continue
    m = re.fullmatch(r"<speed\s+([\d.]+)>", s)     # 这一章单独的语速（节奏检查说某章太快时用）
    if m:
        cur["speed"] = float(m.group(1)); continue
    tag = re.match(r"\[(小红书|通用)\]\s*", s)
    if tag:
        if (tag.group(1) == "小红书") == (a.variant == "neutral"):
            continue
        s = s[tag.end():]
    join = s.endswith("~")                           # 行末 " ~"：和下一行连着读，中间不加逗号（字幕里不显示）
    if join:
        s = s[:-1].rstrip()
    show, say = split_line(s)
    show = re.sub(r"\s*~\s*$", "", show)          # 「显示 ~ | 读法 ~」：显示那一半的 ~ 也去掉，不进字幕（不去掉就会漏进字幕里）
    if PH.search(show):
        sys.exit(f"✗ {a.script}: 拼音标签只能写在 | 右边的读法里，左边是字幕：{s}")
    cap = show.strip()
    text = cap.replace("【", "").replace("】", "")
    say = say.strip() or text
    ref, tags = plain(say, text)
    cur["lines"].append({"cap": cap, "text": text, "say": say, "ref": ref, "tags": tags, "pause": 0.0, "join": join})
acts = [x for x in acts if x["lines"]]
if a.line_pause:
    print("⚠ --line-pause 不再生效：给每一句后面加停顿要把整段配音剪开，会剪在字中间、听得到卡顿。要停就在稿子里写 <pause 秒>。")
# 每章按 <pause> 切成几小段：一段一次合成，段和段之间接上写好的静音（不剪任何一段）
for act in acts:
    segs, cur_s = [], []
    for l in act["lines"]:
        cur_s.append(l)
        if l["pause"] > 0:
            segs.append(cur_s); cur_s = []
    if cur_s: segs.append(cur_s)
    act["segs"] = [{"id": act["id"], "lines": sg, "gap": sg[-1]["pause"]} for sg in segs]

# 多音字：whisper 读回检查听不出来，合成前先列出来（只提示，不拦截）
if (root / "tools/polyphone_check.py").is_file():
    subprocess.run([sys.executable, str(root / "tools/polyphone_check.py"), str(root / a.script)])

PUNCT = "，。？！、：；,.?!:;…"
CUE = vcfg.get("cue", "") if a.cue is None else a.cue   # 每段开头的语气提示（方括号，不会被读出来）
def spoken(act, key="say"):            # key="ref"：拼音标签换回汉字的版本（读回检查、tts_check.txt 用）
    out = []
    for i, l in enumerate(act["lines"]):
        t = l[key]
        last = i == len(act["lines"]) - 1
        if l.get("join") and not last:
            t += "" if re.search(r"[A-Za-z0-9]$", t) is None else " "
        elif t[-1] not in PUNCT:
            t += "。" if last else "，"
        out.append(t)
    return out

# ── synthesise (one request per passage, cached) ─────────────────────────────────
tts_dir = root / "assets/voice/tts"; tts_dir.mkdir(parents=True, exist_ok=True)
def fish(text, speed):
    body = {"text": text, "reference_id": vcfg["reference_id"], "format": "wav", "sample_rate": 44100,
            "normalize": True, "latency": "normal"}
    if speed != 1.0:
        body["prosody"] = {"speed": speed}
    req = urllib.request.Request("https://api.fish.audio/v1/tts", json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "model": vcfg["model"]})
    import http.client, time
    for attempt in range(5):                       # 网络偶尔中途断开（IncompleteRead），断了就重来，最多 5 次
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == 4:
                sys.exit(f"✗ Fish Audio HTTP {e.code}: {e.read()[:300].decode('utf8', 'replace')}")
        except (http.client.IncompleteRead, urllib.error.URLError, ConnectionError, TimeoutError) as e:
            if attempt == 4: raise
            print(f"  ↻ 网络断了一下（{type(e).__name__}），{2 + attempt * 3} 秒后重试")
        time.sleep(2 + attempt * 3)

def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)

def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout)

billed = 0
for act in acts:
    sp = act.get("speed", a.speed)
    for si, seg in enumerate(act["segs"]):
        text = "".join(spoken(seg))
        if CUE:
            text = f"[{CUE}] " + text
        h = hashlib.sha1(f"{vcfg['model']}|{vcfg['reference_id']}|{sp}|{text}".encode()).hexdigest()[:10]
        raw, clip = tts_dir / f"{act['id']}_s{h}.raw.wav", tts_dir / f"{act['id']}_s{h}.wav"
        if not raw.exists() or act["id"] in a.redo or f"{act['id']}.{si + 1}" in a.redo:
            print(f"→ synth {act['id']} 第 {si + 1} 段 ({len(PH.sub('字', text))} 字)")
            raw.write_bytes(fish(text, sp)); billed += len(text.encode())
        # trim edge silence so every gap is exactly the written one; 48 kHz mono like a recorded voice
        ff("-i", str(raw), "-af", "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
           "silenceremove=start_periods=1:start_threshold=-50dB,areverse,aresample=48000", "-ac", "1", str(clip))
        seg["clip"], seg["dur"] = clip, dur(clip)

# ── align lines to audio with whisper (also the read-back check) ─────────────
import mlx_whisper  # noqa: E402  (venv)
NORM = re.compile(r"[\s" + re.escape(PUNCT) + r"“”\"'（）()《》【】—-]")
def norm(t): return NORM.sub("", t).lower()

def hear(act, cond):
    """One whisper pass over an act → line times (st/en), read-back diffs, and how many lines look broken."""
    r = mlx_whisper.transcribe(str(act["clip"]), path_or_hf_repo="mlx-community/whisper-large-v3-turbo", language="zh",
                               word_timestamps=True, condition_on_previous_text=cond,
                               initial_prompt="以下是普通话口播，使用简体中文。" + a.prompt)
    chars, times = [], []                     # whisper chars with interpolated times
    for w in (w for s in r["segments"] for w in s.get("words", [])):
        c = norm(w["word"])
        for k, ch in enumerate(c):
            chars.append(ch); times.append(w["start"] + (w["end"] - w["start"]) * (k + 0.5) / len(c))
    ref, spans = "", []
    for l in act["lines"]:
        n = norm(l["ref"]); spans.append((len(ref), len(ref) + len(n))); ref += n
    sm = difflib.SequenceMatcher(None, ref, "".join(chars), autojunk=False)
    at = [None] * len(ref)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            at[blk.a + k] = times[blk.b + k]
    known = [i for i, v in enumerate(at) if v is not None]     # fill gaps by linear interpolation
    for i in range(len(at)):
        if at[i] is None:
            lo = max([k for k in known if k < i], default=None); hi = min([k for k in known if k > i], default=None)
            if lo is None: at[i] = 0.0 if hi is None else at[hi] * i / hi
            elif hi is None: at[i] = at[lo] + (act["dur"] - at[lo]) * (i - lo) / (len(at) - lo)
            else: at[i] = at[lo] + (at[hi] - at[lo]) * (i - lo) / (hi - lo)
    hc = "".join(chars)
    diffs = [(i1, i2, j1, j2) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"]
    st, en, rep, bad = [], [], [], 0
    for li, (l, (s, e)) in enumerate(zip(act["lines"], spans)):
        st.append(max(0.0, at[s] - 0.12)); en.append(min(act["dur"], at[e - 1] + 0.18))
        # 一句的时长按字数算明显不对（几个字被压成 0.1 秒、或一句拉成十几秒）= 这一段读回乱了
        if e - s >= 3 and not 0.05 <= (at[e - 1] - at[s]) / (e - s) <= 0.8: bad += 1
        frag = [f"「{ref[max(i1, s):min(i2, e)] or '∅'}」→「{hc[j1:j2] or '∅'}」" for i1, i2, j1, j2 in diffs
                if (i1 < e and i2 > s) or (i1 == i2 and s <= i1 < e)]
        if frag:
            # 对不上的字写了拼音标签：whisper 本来就听不准多音字和少见的音节，标出来，以试听为准
            tagged = [f"{c} {py}" for c, py in dict.fromkeys(l["tags"]) if any(c in ref[max(i1, s):min(i2, e)] for i1, i2, _, _ in diffs)]
            rep.append(f"  ? {act['id']} 第{li + 1}行「{l['text']}」 稿子→听到：" + "  ".join(frag)
                       + (f"   〔拼音标签：{'、'.join(tagged)}〕" if tagged else ""))
    return {"st": st, "en": en, "rep": rep, "bad": bad, "heard": "".join(s["text"] for s in r["segments"])}

report = []
for act in acts:
    heard = []
    for seg in act["segs"]:
        h = hear(seg, True)
        if h["bad"]:
            h2 = hear(seg, False)
            print(f"  ↻ {act['id']}：读回有 {h['bad']} 句时间对不上，换一种方式重听 → {h2['bad']} 句")
            if h2["bad"] < h["bad"]: h = h2
        for l, st, en in zip(seg["lines"], h["st"], h["en"]):
            l["st"], l["en"] = st, en
        report += h["rep"]
        for x, y in zip(seg["lines"], seg["lines"][1:]):        # neighbouring lines may not overlap
            if x["en"] > y["st"]:
                x["en"] = y["st"] = (x["en"] + y["st"]) / 2
        heard.append(h["heard"])
    act["heard"] = " / ".join(heard)

# ── assemble voice track: passages back to back with their written silence, --act-gap between acts ──
inputs, filt, film_lines, T = [], [], [], 0.0
def sil(d):
    inputs.extend(["-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=48000:cl=mono"])
    filt.append(f"[{len(filt)}:a]anull[p{len(filt)}]")
for ai, act in enumerate(acts):
    for seg in act["segs"]:
        for l in seg["lines"]:
            film_lines.append({"act": act["id"], "text": l["text"], "cap": l["cap"],
                               "start": round(a.intro + T + l["st"], 2), "end": round(a.intro + T + l["en"], 2)})
        inputs += ["-i", str(seg["clip"])]
        filt.append(f"[{len(filt)}:a]anull[p{len(filt)}]")
        T += seg["dur"]
        if seg["gap"] > 0:
            sil(seg["gap"]); T += seg["gap"]
    if ai < len(acts) - 1:
        sil(a.act_gap); T += a.act_gap
n = len(filt)
filt.append("".join(f"[p{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[cat]")

suffix = "" if a.variant == "main" else "-neutral"
vdir = root / "assets/voice"; pre, out = vdir / f"voice{suffix}_pre.wav", vdir / f"voice{suffix}.wav"
ff(*inputs, "-filter_complex", ";".join(filt), "-map", "[cat]", "-ar", "48000", "-ac", "1", str(pre))
m = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(pre), "-af", "loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json", "-f", "null", "-"],
                   capture_output=True, text=True).stderr
j = json.loads(m[m.rindex("{"): m.rindex("}") + 1])
ff("-i", str(pre), "-af", f"loudnorm=I=-16:TP=-1.5:LRA=7:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
   f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true",
   "-ar", "48000", str(out))

lines = [{"id": f"L{i + 1:02d}", **x} for i, x in enumerate(film_lines)]
tfile = root / ("timing/film.json" if a.variant == "main" else "timing/film-neutral.json")
tfile.parent.mkdir(exist_ok=True)
tfile.write_text(json.dumps({"source": f"AI voice · Fish Audio {vcfg['model']} · {a.script}", "voice_offset": a.intro,
                             "lines": lines}, ensure_ascii=False, indent=1), encoding="utf8")
(root / "timing" / f"tts_check{suffix}.txt").write_text(
    "\n\n".join(f"# {x['id']}\n稿子：{' / '.join(''.join(spoken(g, 'ref')) for g in x['segs'])}\n听到：{x['heard']}" for x in acts), encoding="utf8")

for l in lines:
    flag = "  ← >17 字，考虑拆行" if len(l["text"]) > 17 else ""
    print(f"{l['id']} {l['act']:<6} {l['start']:6.2f}–{l['end']:6.2f}  {l['text']}{flag}")
print(f"\nvoice → {out.relative_to(root)} · {dur(out):.1f}s   timing → {tfile.relative_to(root)}"
      f"   本次合成 {billed} 字节 ≈ ${billed * 15 / 1e6:.3f}")
if report:
    print("\n需要听一下的行（whisper 常把英文术语听错，先听再决定要不要改读法 / --redo）：\n" + "\n".join(report))
    print(f"逐章对照：timing/tts_check{suffix}.txt")
