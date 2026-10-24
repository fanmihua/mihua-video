#!/usr/bin/env python3
"""把用户给的两张照片做成品牌层要的头像、签名，写进 skill 的 assets/brand/。

    ~/.cache/mihua-video/venv/bin/python scripts/make_brand.py --avatar 头像.jpg --signature 签名照片.jpg
    （只换一样就只给一个参数；--out 指定别的输出文件夹，默认是这个 skill 的 assets/brand/）

头像：从中间裁成正方形，缩到 500×500。画面里会裁成圆，脸放在照片中间最好。
签名：白纸上的深色手写字的照片或扫描 → 字变成白色、纸变成透明，裁掉四周空白，高 380px。
      照片光线不匀、纸上有阴影时，加 --threshold（0–255，默认自动）调到只剩字。
做完要重新跑 bash scripts/install.sh，装好的 skill 才会用新的图；已经建好的工程，把两张图拷进工程的 assets/img/。
"""
import argparse
from pathlib import Path
from PIL import Image, ImageOps

SKILL = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--avatar")
ap.add_argument("--signature")
ap.add_argument("--threshold", type=int, default=None, help="签名：比这个亮的算纸（0–255），默认自动")
ap.add_argument("--out", default=str(SKILL / "assets/brand"))
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
if not a.avatar and not a.signature:
    ap.error("至少给 --avatar 或 --signature 其中一个")

if a.avatar:
    im = ImageOps.exif_transpose(Image.open(a.avatar)).convert("RGB")
    s = min(im.size); l = (im.width - s) // 2; t = (im.height - s) // 2
    im.crop((l, t, l + s, t + s)).resize((500, 500), Image.LANCZOS).save(out / "avatar.png")
    print(f"✓ 头像 → {out / 'avatar.png'}（500×500）")

if a.signature:
    g = ImageOps.autocontrast(ImageOps.exif_transpose(Image.open(a.signature)).convert("L"), cutoff=1)
    hist = g.histogram(); total = sum(hist)
    if a.threshold is None:                      # Otsu：自动找纸和字之间的分界
        sum_all = sum(i * h for i, h in enumerate(hist)); wb = sb = 0; best = (0, 128)
        for i, h in enumerate(hist):
            wb += h
            if wb == 0 or wb == total: continue
            sb += i * h; mb = sb / wb; mf = (sum_all - sb) / (total - wb)
            var = wb * (total - wb) * (mb - mf) ** 2
            if var > best[0]: best = (var, i)
        thr = best[1]
    else:
        thr = a.threshold
    # 比分界暗的是字：越暗越不透明；分界附近留一点过渡，笔画边缘不起锯齿
    soft = 24
    alpha = g.point(lambda v: 255 if v <= thr - soft else (0 if v >= thr else int(255 * (thr - v) / soft)))
    box = alpha.getbbox()
    if not box: raise SystemExit("✗ 没找到字：照片太暗或太亮，试试 --threshold")
    pad = 8
    box = (max(0, box[0] - pad), max(0, box[1] - pad), min(g.width, box[2] + pad), min(g.height, box[3] + pad))
    alpha = alpha.crop(box)
    sig = Image.new("RGBA", alpha.size, (255, 255, 255, 0)); sig.putalpha(alpha)
    w = round(sig.width * 380 / sig.height)
    sig.resize((w, 380), Image.LANCZOS).save(out / "signature.png")
    print(f"✓ 签名 → {out / 'signature.png'}（{w}×380，白字透明底；分界 {thr}）")

print("下一步：bash scripts/install.sh，让装好的 skill 用上新的图。")
