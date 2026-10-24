#!/usr/bin/env bash
# Build → mix → check → render（按电脑配置出 4K / 2K / 1080p）+ SRT, for one version of the film.
#   sh tools/deliver.sh video.config.json 我的视频_小红书版 [out-dir]
# 渲染在本机跑（headless Chrome + ffmpeg），分辨率只影响渲染时间，不花 AI 额度；用 1080p 是为了每轮返工等得少。
#   SAMPLE=1  样片（单章预览、迷你样片）：外壳按 1080p 搭、直接渲 1080p
#   DRAFT=1   整片审片版：同样 1080p，用户看完整片提修改；改到确认了，才不带参数出一次 4K 定稿
#   默认      成片（只在审片版确认后出）：按这台电脑的配置自动定分辨率（tools/render_plan.sh：内存 ≥32 GB 出 4K，16–31 GB 出 2K，<16 GB 出 1080p）
#   RES=1080 / 1440 / 2160  指定成片分辨率；超过这台电脑的建议要再加 FORCE=1（会很慢，电脑可能卡）
#   确实需要从 4K 再转 1080p / 720p 时：PREVIEW=1 sh tools/deliver.sh …
# 同一个输出改过以后再出（成片、样片都一样）：自动和上一版成片比指纹，只重渲最早改动那一章到片尾、接回上一版（tools/patch_render.py）；
#   画面全没变只换音轨；第一章、外壳变了，或者接缝核对不过，就整片出。FULL=1 强制整片；FROM=actC 最早从这一章起
# Run once per platform version (e.g. video.config.json, video.config.neutral.json).
set -euo pipefail
# 每一步打印用时：慢的时候一看就知道卡在哪一步（常常卡在 lint，而不是画帧）
T0=$(date +%s); TS=$T0
lap() { local now; now=$(date +%s); printf "⏱ %-12s %3d 分 %02d 秒（累计 %d 分）\n" "$1" $(((now-TS)/60)) $(((now-TS)%60)) $(((now-T0)/60)); TS=$now; }
cd "$(dirname "$0")/.."
CFG="${1:?config}"; NAME="${2:?output name}"; OUT="${3:-renders/delivery}"
mkdir -p "$OUT"
. tools/render_plan.sh                 # 已经 cd 到工程根目录
if [ "${SAMPLE:-0}" = "1" ]; then OUTRES=1080; SUF="样片1080p"
elif [ "${DRAFT:-0}" = "1" ]; then OUTRES=1080; SUF="审片1080p"
else
  OUTRES="${RES:-$MAXRES}"
  case "$OUTRES" in 1080|1440|2160) ;; *) echo "✗ RES 只能是 1080、1440、2160"; exit 1;; esac
  SUF="$(res_name "$OUTRES")"
fi
echo "· 这台电脑：$CHIP · 内存 ${RAM_GB} GB · 这次出 $(res_name "$OUTRES")（建议最高 $(res_name "$MAXRES")）"
if [ "$OUTRES" -gt "$MAXRES" ] && [ "${FORCE:-0}" != "1" ]; then
  echo "✗ 这台电脑内存 ${RAM_GB} GB，建议最高出 $(res_name "$MAXRES")。出 $(res_name "$OUTRES") 会占满内存，电脑可能卡死、渲到一半崩掉。"
  echo "  改出 $(res_name "$MAXRES")：去掉 RES 重跑。一定要出 $(res_name "$OUTRES")：关掉别的软件、插上电源，再加 FORCE=1 重跑。"
  exit 1
fi
NEED_GB=10; [ "$OUTRES" = "2160" ] && NEED_GB=20
FREE_GB=$(disk_free_gb "$OUT")
if [ -n "$FREE_GB" ] && [ "$FREE_GB" -lt "$NEED_GB" ]; then
  echo "✗ 硬盘只剩 ${FREE_GB} GB，出 $(res_name "$OUTRES") 至少要留 ${NEED_GB} GB：先清出空间再出片"; exit 1
fi
on_battery && echo "⚠ 现在用的是电池：渲染会占满 CPU，先插上电源；渲染时别合上盖子（合盖会睡眠，渲染就停了）"
case "$OUTRES" in 2160) unset RES;; *) export RES="$OUTRES";; esac   # build.mjs：不设 RES 搭 4K 外壳
# 出整片前查样张 / 预览开关：出静帧时打开的 SAMPLE = true 忘了改回，成片里那几秒就会放成静帧样张
if [ "${SAMPLE:-0}" != "1" ]; then
  FLAGS=$(grep -nE '(const|let|var)[[:space:]]+[A-Za-z_]*(SAMPLE|PREVIEW|STILL|DEBUG)[A-Za-z_]*[[:space:]]*=[[:space:]]*(true|1)([^0-9]|$)' src/scenes/*.html 2>/dev/null || true)
  if [ -n "$FLAGS" ]; then
    echo "✗ 场景里还有样张 / 预览开关开着（出整片前改回 false）："; printf '%s\n' "$FLAGS" | cut -c1-160; exit 1
  fi
fi
CONFIG="$CFG" node tools/build.mjs            # timing → scenes + shell (needed before mixing)
python3 tools/mix.py "$CFG"                    # voice + music + sfx → one track at the target loudness
CONFIG="$CFG" node tools/build.mjs            # again, now with the mixed track mounted
lap "构建+混音"
# HyperFrames 一律用工程 package.json 里锁定的版本：不带版本号的 npx 会去取 npm 上最新版，
# 新版刚发布、安装包还没就位时会 404，渲染起不来
HF_PIN=$(grep -oE 'hyperframes@[0-9]+\.[0-9]+\.[0-9]+' package.json 2>/dev/null | head -1 || true)
HF="npx --yes ${HF_PIN:-hyperframes@0.8.149}"
echo "· HyperFrames：${HF_PIN:-hyperframes@0.8.149（package.json 里没找到锁定版本，用默认）}"
# 渲染进程的 Node 堆默认约 4 GB，会爆：十几分钟的 4K 长片会渲到一半爆掉；窗口里视频多的 1080p 也会爆。
# 上限按这台电脑的内存给（render_plan.sh：内存的一半、最多 12 GB），不把小内存的电脑吃满
if ! printf '%s' "${NODE_OPTIONS:-}" | grep -q "max-old-space-size"; then
  export NODE_OPTIONS="${NODE_OPTIONS:+$NODE_OPTIONS }--max-old-space-size=$HEAP_MB"
fi
# lint 不单独跑：check 和 render 里面各自都会跑一遍 lint，再单独跑就是第三遍；合成文件大时一遍十几分钟。
# render 加 --strict：lint 有 error 就停（原来单独那遍 lint 的作用）。
# check 里的版面重叠、对比度是提示：真组件叠放、重影、代码行号这类有意的设计也会被标出来，看一眼列表再决定
MP4="$OUT/${NAME}_${SUF}.mp4"
FP="timing/delivered/${NAME}_${SUF}.json"   # 上一版成片的指纹（出完才写，见文件末尾）
render() {   # $1 = 输出：整片 index.html，或 FROM 那一版
  $HF check || echo "⚠ hyperframes check 有提示（见上面列表）；继续渲染（lint 有 error 时 render --strict 会停）"
  lap "check"
  caffeinate -i $HF render --strict -q delivery --video-frame-format png -o "$1" --skill general-video
}
PLAN=full; DRIFT=""
[ "${FULL:-0}" = "1" ] || PLAN=$(python3 tools/patch_render.py plan "$MP4" "$FP" timing/fingerprint.json "${HF_PIN:-}" "${FROM:-}") || PLAN=full
case "$PLAN" in
  from\ *)
    set -- $PLAN; DRIFT=$4; TAIL="renders/.patch/${NAME}_${SUF}_$2起.mp4"; mkdir -p renders/.patch
    if FROM="$2" DRIFT="$DRIFT" CONFIG="$CFG" node tools/build.mjs && render "$TAIL" \
       && python3 tools/patch_render.py splice "$MP4" "$TAIL" "$3" timing/fingerprint.json "$MP4.joined.mp4"; then
      mv "$MP4.joined.mp4" "$MP4"; lap "render（$2 起）+ 接回"
    else
      echo "⚠ 只渲 $2 起没成（见上面），改成整片出"; rm -f "$MP4.joined.mp4"; DRIFT=""
      CONFIG="$CFG" node tools/build.mjs >/dev/null; render "$MP4"; lap "render"
    fi
    rm -rf renders/.patch
    CONFIG="$CFG" node tools/build.mjs >/dev/null   # 工程恢复成整片（预览、下次出片看的都是整片）
    ;;
  audio\ *) set -- $PLAN; DRIFT=$2 ;;
  *) render "$MP4"; lap "render" ;;
esac
# 换音轨：HyperFrames render 的音频固定 192k AAC，-10 LUFS 的混音压缩后真峰值冒过 -1 dBTP，
# 渲染器会整条降 1 dB（日志 Audio lowered by 1.0 dB），成片只剩 -11 LUFS。render 没有码率参数，
# 所以渲完把 mix.py 出的混音原样编成 320k AAC 换进去（画面直接复制，不重编；实测音画差 0 ms）
MIX=$(python3 -c "import json; print(json.load(open('$CFG')).get('mix','assets/mix/final.wav'))")
ffmpeg -v error -y -i "$MP4" -i "$MIX" -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 320k -movflags +faststart "$MP4.remux.mp4"
mv "$MP4.remux.mp4" "$MP4"
echo "· 音轨换成混音原样（$MIX → 320k AAC），保持 -10 LUFS"
if [ "${PREVIEW:-0}" = "1" ] && [ "$SUF" != "样片1080p" ] && [ "$SUF" != "审片1080p" ] && [ "$SUF" != "1080p" ]; then
  ffmpeg -v error -y -i "$OUT/${NAME}_${SUF}.mp4" -vf "scale=1920:1080:flags=lanczos" -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -c:a copy -movflags +faststart "$OUT/${NAME}_1080p.mp4"   # 音轨直接用 4K 那条 320k，不再压一次
  ffmpeg -v error -y -i "$OUT/${NAME}_${SUF}.mp4" -vf "scale=1280:720:flags=lanczos" -c:v libx264 -preset slow -crf 26 -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart "$OUT/${NAME}_预览720p.mp4"
fi
SRT=$(python3 -c "import json,sys; print(json.load(open('$CFG')).get('srt','renders/subtitles.srt'))")
cp "$SRT" "$OUT/${NAME}_字幕.srt"
[ "${DRAFT:-0}" = "1" ] && python3 tools/review_sheet.py "$CFG" "$OUT/${NAME}_审片表.md"   # 用户按「时间点 + 问题」写意见
# 核对成片：响度 = config 的 loudness（±0.5）、真峰值 ≤ -1 dBTP，不达标打 ⚠（不重渲，先查混音和上面换音轨那一步）
TARGET=$(python3 -c "import json; print(json.load(open('$CFG')).get('loudness', -10))")
for f in "$OUT/${NAME}_${SUF}.mp4"; do
  DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
  LOUD=$(ffmpeg -hide_banner -i "$f" -map 0:a:0 -af ebur128=peak=true -f null - 2>&1 | awk '$1=="I:"{i=$2} $1=="Peak:"{p=$2} END{print i, p}')
  python3 - "$(basename "$f")" "$DUR" "$TARGET" $LOUD <<'PY'
import sys
name, dur, target, *m = sys.argv[1:]
try: i, p = float(m[0]), float(m[1])
except (IndexError, ValueError): sys.exit(print(f"{name}  ⚠ 量不出响度（没有音轨？）") or 0)
ok = abs(i - float(target)) <= 0.5 and p <= -1.0
print(f"{name}  {float(dur):.1f}s · {i} LUFS（目标 {float(target):g}）· 真峰值 {p} dBTP（上限 -1）  "
      + ("✓" if ok else "⚠ 不达标：先看 mix.py 打印的混音响度，再看上面换音轨那一步有没有执行"))
PY
done
ls -la "$OUT" | grep "$NAME"
python3 tools/patch_render.py save "$MP4" timing/fingerprint.json "$FP" "${HF_PIN:-}" "$DRIFT"   # 下次改了再出时拿它比
lap "换音轨+核对"
