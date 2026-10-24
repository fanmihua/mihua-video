#!/usr/bin/env python3
"""只重渲改了的那几章，接回上一版成片（tools/deliver.sh 自动调用，平时不用手动跑）。

    python3 tools/patch_render.py plan   <上一版.mp4> <上一版指纹.json> timing/fingerprint.json <hyperframes@版本> [最早从哪章]
    python3 tools/patch_render.py splice <上一版.mp4> <新渲的后半段.mp4> <从第几帧接> timing/fingerprint.json <输出.mp4>
    python3 tools/patch_render.py save   <成片.mp4> timing/fingerprint.json <指纹存到哪> <hyperframes@版本> [drift]

plan：拿这次 build 的指纹（tools/build.mjs 写的 timing/fingerprint.json）和上一版成片出片时存的指纹比，
  找出最早从哪一章开始变了（这一章搭好的 HTML、用到的素材、开头结尾、字幕、外壳的签名 / 导航动画），往前推到切点不落在字幕、动画中间的那一章。
  stdout 一行：`from <章> <帧> <drift>` 只重渲这章到片尾 · `audio <drift>` 画面全没变、只换音轨 · `full` 整片出；原因打到 stderr。
  第一章就变了、外壳 / 字体 / 分辨率 / 帧率 / HyperFrames 版本变了、上一版成片被换过，都整片出。
splice：上一版成片的前 N 帧原样拷（编码器不出 B 帧，任何一帧都能截断，不用重新编码）+ 新渲的后半段（第一帧是关键帧），
  拼成一条只有画面的 mp4。先核两边编码参数一样（avcC 里的 SPS / PPS、尺寸、帧率、时间基），拼完核总帧数、
  每个视频包和两边原文件逐个一样，再解码接缝前 2 帧、后 3 帧和原文件比 md5；有一项不对就退出 1，deliver.sh 改成整片出。
save：成片出完（换好音轨以后）把指纹存起来，记下成片的路径、大小、修改时间、帧数，下次 plan 用。
为什么：只改了最后一章也整片重渲，6 分半的 4K 要 20 分钟（大半花在编码上）；只渲那一章接回去 3–4 分钟。
"""
import json, math, mmap, os, subprocess, sys
from pathlib import Path


def say(msg):
    print(msg, file=sys.stderr)


def load(p):
    return json.loads(Path(p).read_text(encoding="utf8"))


def frames_for(dur, fps):
    """和 HyperFrames 的 durationToFrameCount 一样：离整帧 0.001 以内取整，否则往上取。"""
    raw = dur * fps
    n = round(raw)
    return n if abs(raw - n) <= 1e-3 else math.ceil(raw)


def probe(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                          "stream=codec_name,width,height,pix_fmt,r_frame_rate,time_base,has_b_frames,nb_read_packets",
                          "-of", "json", str(p)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)["streams"][0]


def avcc(p):
    """mp4 里视频轨的 avcC（SPS / PPS）原样字节。"""
    with open(p, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
        i = m.find(b"avcC")
        return None if i < 4 else m[i - 4:i - 4 + int.from_bytes(m[i - 4:i], "big")]


def pkts(p, n=None):
    """每个视频包的 md5（不解码，-c copy）。"""
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-map", "0:v:0", "-c", "copy"] + (["-frames:v", str(n)] if n else []) +
                         ["-f", "framemd5", "-"], capture_output=True, text=True, check=True).stdout
    return [l.split(",")[-1].strip() for l in out.splitlines() if l and not l.startswith("#")]


def md5s(p, first, n, fps):
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, first - 0.5) / fps:.6f}", "-i", str(p), "-map", "0:v:0",
                          "-frames:v", str(n), "-f", "framemd5", "-"], capture_output=True, text=True, check=True).stdout
    return [l.split(",")[-1].strip() for l in out.splitlines() if l and not l.startswith("#")]


def plan(old_mp4, old_fp, new_fp, hf, force=""):
    new = load(new_fp)

    def full(why):
        say("· 整片出：" + why)
        print("full")
        sys.exit(0)

    if not Path(old_mp4).exists():
        full("这一版还没出过")
    if not Path(old_fp).exists():
        full("上一版成片没有指纹（旧工具出的）；这次出完就有了，下次再改就能只渲改了的章")
    old = load(old_fp)
    film, st = old.get("film", {}), os.stat(old_mp4)
    if film.get("path") != str(Path(old_mp4).resolve()) or film.get("size") != st.st_size or abs(film.get("mtime", 0) - st.st_mtime) > 1:
        full("上一版成片和记录对不上（文件被换过或改过）")
    for k, what in (("version", "指纹格式"), ("fps", "帧率"), ("res", "分辨率"), ("shell", "外壳（品牌层、签名头像、字体）")):
        if old.get(k) != new.get(k):
            full(f"{what}变了")
    if old.get("hf") != hf:
        full(f"HyperFrames 版本变了（{old.get('hf')} → {hf}）")
    fps, oa, na = new["fps"], old["acts"], new["acts"]
    d = next((i for i in range(max(len(oa), len(na))) if i >= len(oa) or i >= len(na) or oa[i] != na[i]), None)

    def first_diff(a, b):
        a, b = sorted(map(tuple, a)), sorted(map(tuple, b))
        for x, y in zip(a, b):
            if x != y:
                return min(x[0], y[0])
        return (a if len(a) > len(b) else b)[min(len(a), len(b))][0] if len(a) != len(b) else None

    tes = [t for t in (first_diff(old["captions"], new["captions"]), first_diff(old["events"], new["events"])) if t is not None]
    if d is None and not tes and not force:
        say("· 画面、字幕、外壳都和上一版一样：不重渲，只换音轨")
        print(f"audio {old['drift']}")
        return
    k = len(na) if d is None else d
    if tes:
        k = min(k, max(i for i, a in enumerate(na) if a["start"] <= min(tes) + 1e-9))
    why = f"最早变的是 {na[k]['id']}" if k < len(na) else "没有改动"
    if force:
        ids = [a["id"] for a in na]
        if force not in ids:
            full(f"FROM={force}：没有这一章")
        if ids.index(force) < k:
            k, why = ids.index(force), f"指定从 {force} 起（{why}）"
    while k >= 1:
        t0 = math.ceil(na[k]["start"] * fps - 1e-6) / fps
        frame = round(t0 * fps)
        before = lambda xs: sorted(tuple(x) for x in xs if x[0] < t0)
        across = [x for x in new["captions"] + new["events"] if x[0] < t0 < x[0] + x[1] - 1e-9]
        if before(old["captions"]) == before(new["captions"]) and before(old["events"]) == before(new["events"]) \
                and not across and frame < film.get("frames", 0):
            dur = new["total"] - t0
            say(f"· {why}：只重渲 {na[k]['id']} 到片尾（第 {frame} 帧起，{dur:.0f} 秒 / 整片 {new['total']:.0f} 秒），前 {k} 章照用上一版成片")
            print(f"from {na[k]['id']} {frame} {old['drift']}")
            return
        k -= 1
    full(f"{why}，往前推到了第一章（改动在第一章，或切点都卡在字幕、外壳动画中间）")


def splice(old_mp4, tail_mp4, frame, new_fp, out_mp4):
    new, frame = load(new_fp), int(frame)
    fps, want = new["fps"], frames_for(new["total"], new["fps"])
    a, b = probe(old_mp4), probe(tail_mp4)

    def stop(why):
        say("✗ 接不上：" + why)
        sys.exit(1)

    keys = ("codec_name", "width", "height", "pix_fmt", "r_frame_rate", "time_base")
    if any(a.get(k) != b.get(k) for k in keys):
        stop("两边视频参数不一样 " + str({k: (a.get(k), b.get(k)) for k in keys if a.get(k) != b.get(k)}))
    if a.get("codec_name") != "h264" or int(a.get("has_b_frames", 1)) or int(b.get("has_b_frames", 1)):
        stop("不是没有 B 帧的 H.264，不能直接截断")
    if avcc(old_mp4) != avcc(tail_mp4):
        stop("两边的编码参数（SPS / PPS）不一样")
    if int(a["nb_read_packets"]) < frame:
        stop(f"上一版只有 {a['nb_read_packets']} 帧，不到第 {frame} 帧")
    if int(b["nb_read_packets"]) != want - frame:
        stop(f"后半段 {b['nb_read_packets']} 帧，应该是 {want - frame} 帧")
    out = Path(out_mp4)
    pre, lst = out.with_name(out.stem + ".前段.mp4"), out.with_name(out.stem + ".list.txt")
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", old_mp4, "-map", "0:v:0", "-c", "copy", "-frames:v", str(frame), str(pre)], check=True)
        lst.write_text(f"file '{pre.resolve()}'\nfile '{Path(tail_mp4).resolve()}'\n", encoding="utf8")
        # auto_convert 0：两边 avcC 一样，不让 concat 往每个关键帧里塞 SPS / PPS（默认会塞，包就不是上一版的原样字节了）
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-auto_convert", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)], check=True)
    finally:
        pre.unlink(missing_ok=True)
        lst.unlink(missing_ok=True)
    joined = pkts(out)
    if len(joined) != want:
        stop(f"拼好 {len(joined)} 帧，应该是 {want} 帧")
    if joined[:frame] != pkts(old_mp4, frame) or joined[frame:] != pkts(tail_mp4):
        stop("拼好的视频包和两边原文件不是原样字节")
    seam = md5s(out, frame - 2, 5, fps)
    ref = md5s(old_mp4, frame - 2, 2, fps) + md5s(tail_mp4, 0, 3, fps)
    if seam != ref:
        stop("接缝前后几帧解码出来和原文件不一样")
    say(f"✓ 接好了：上一版前 {frame} 帧 + 新渲 {want - frame} 帧 = {want} 帧；每个包都是两边原样字节，接缝前 2 帧、后 3 帧解码和原文件一致")


def save(mp4, new_fp, dest, hf, drift=""):
    fp = load(new_fp)
    if drift:
        fp["drift"] = float(drift)
    st, frames = os.stat(mp4), int(probe(mp4)["nb_read_packets"])
    if frames != frames_for(fp["total"], fp["fps"]):
        say(f"⚠ 成片 {frames} 帧，按片长应该是 {frames_for(fp['total'], fp['fps'])} 帧")
    fp.update(hf=hf, film={"path": str(Path(mp4).resolve()), "size": st.st_size, "mtime": st.st_mtime, "frames": frames})
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_text(json.dumps(fp, ensure_ascii=False), encoding="utf8")


if __name__ == "__main__":
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    fn = {"plan": plan, "splice": splice, "save": save}.get(cmd)
    if not fn:
        sys.exit(__doc__)
    fn(*args)
