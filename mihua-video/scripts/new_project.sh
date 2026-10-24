#!/usr/bin/env bash
# Scaffold a new AI 讲解视频 project: the fixed brand layer + tools, and NO scenes.
# Scenes are designed fresh for each video (references/motion-language.md).
#
#   bash scripts/new_project.sh <project-dir> [--brand <dir with avatar.png + signature.png>]
#
# Needs: node/npx (HyperFrames CLI), python3, ffmpeg. Creates once per machine:
#   ~/.cache/mihua-video/venv  (fonttools + brotli for font subsetting, numpy + mlx-whisper for music & transcription,
#   certifi for HTTPS to the voice API)
# Works the same from Claude Code, Codex or Cursor — everything is a plain shell / python / node command.
set -euo pipefail
DIR="${1:?usage: new_project.sh <project-dir> [--brand <dir>]}"; shift || true
BRAND=""
while [ $# -gt 0 ]; do case "$1" in --brand) BRAND="$2"; shift 2;; *) echo "unknown option $1"; exit 1;; esac; done
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
KIT="$SKILL/assets/kit"

if [ -e "$DIR" ] && [ -n "$(ls -A "$DIR" 2>/dev/null)" ]; then echo "✗ $DIR exists and is not empty"; exit 1; fi
echo "→ hyperframes init"
npx -y hyperframes init "$DIR" --non-interactive --example=blank --skill=general-video >/dev/null
DIR="$(cd "$DIR" && pwd)"
rm -f "$DIR/index.html"
mkdir -p "$DIR"/src/scenes "$DIR"/src/partials "$DIR"/tools "$DIR"/timing "$DIR"/renders \
         "$DIR"/assets/{img,video,web,cut,voice,music,mix,fonts,sfx}
cp "$KIT/src/theme.css" "$KIT/src/common.js" "$KIT/src/index.html" "$DIR/src/"
find "$KIT/tools" -maxdepth 1 -type f ! -name "*.pyc" -exec cp {} "$DIR/tools/" \;
mkdir -p "$DIR/cover" && cp "$KIT"/cover/* "$DIR/cover/"      # 封面品牌层 + 出图/量位置工具（references/cover.md）
cp "$KIT/video.config.json" "$KIT/video.config.neutral.json" "$KIT/sfx.json" "$DIR/"
# 素材清单 / 内容确认单 / 交接 模板 → 同级的 素材/（已有同名文件不覆盖）
MAT="$(dirname "$DIR")/素材"
if [ -d "$MAT" ]; then for f in "$KIT"/templates/*.md; do [ -e "$MAT/$(basename "$f")" ] || cp "$f" "$MAT/"; done
else echo "  ! no 素材/ next to $DIR — templates are in $KIT/templates/"; fi

echo "→ brand (avatar + handwritten greeting)"
SRC="${BRAND:-$SKILL/assets/brand}"
for f in avatar.png signature.png; do
  if [ -f "$SRC/$f" ]; then cp "$SRC/$f" "$DIR/assets/img/$f"; else echo "  ! $SRC/$f missing — add it to assets/img/"; fi
done

echo "→ fonts (阿里妈妈数黑体 + 阿里巴巴普惠体)"
# 字体按字重找：官网现在下载的普惠体 3.0 文件名是 AlibabaPuHuiTi-3-55-Regular 这种，2.0 是 Alibaba-PuHuiTi-Regular；都认
font_find() {   # font_find <要的名字> → 打印找到的文件路径（找不到打印空）
  case "$1" in
    AlimamaShuHeiTi-Bold.otf)   pats="*ShuHeiTi-Bold.* *ShuHeiTi*" ;;
    Alibaba-PuHuiTi-Regular.ttf) pats="*PuHuiTi*-55-* *PuHuiTi-Regular.*" ;;
    Alibaba-PuHuiTi-Medium.ttf)  pats="*PuHuiTi*-65-* *PuHuiTi-Medium.*" ;;
    Alibaba-PuHuiTi-Bold.ttf)    pats="*PuHuiTi*-85-* *PuHuiTi-Bold.*" ;;
  esac
  for d in "$SKILL/assets/fonts" "$HOME/Library/Fonts" /Library/Fonts "$HOME/.local/share/fonts" /usr/share/fonts; do
    for p in $pats; do for f in "$d"/$p; do [ -f "$f" ] && { echo "$f"; return; }; done; done
  done
}
for f in AlimamaShuHeiTi-Bold.otf Alibaba-PuHuiTi-Regular.ttf Alibaba-PuHuiTi-Medium.ttf Alibaba-PuHuiTi-Bold.ttf; do
  hit="$(font_find "$f")"   # 拷进工程时统一改成 config 里写的名字（字体子集化按内容读，不看扩展名）
  if [ -n "$hit" ]; then cp "$hit" "$DIR/assets/fonts/$f"; else echo "  ! ${f%.*} 没装 — 免费下载：https://www.alibabafonts.com ，装好后重跑这一步，或把字体文件拷进 assets/fonts/ 并改成 $f"; fi
done

echo "→ soft sound effects + cloned voice id (voice.json)"
# 音效是 Pixabay 的（见 assets/kit/sfx/CREDITS.txt）。这份资料不带音效 mp3（从 HyperFrames 的 media-use skill 拷）：下面去它的目录里找同样的三个文件
SFX_SRC="$KIT/sfx"
if ! ls "$SFX_SRC"/*.mp3 >/dev/null 2>&1; then
  for d in "$HOME/.agents/skills/media-use/audio/assets/sfx" "$HOME/.claude/skills/media-use/audio/assets/sfx" "$HOME/.codex/skills/media-use/audio/assets/sfx"; do
    ls "$d"/*.mp3 >/dev/null 2>&1 && { SFX_SRC="$d"; break; }
  done
fi
if ls "$SFX_SRC"/*.mp3 >/dev/null 2>&1; then for f in whoosh-short whoosh-cinematic click-soft; do [ -f "$SFX_SRC/$f.mp3" ] && cp "$SFX_SRC/$f.mp3" "$DIR/assets/sfx/"; done
else echo "  ! no sound effects found — run: npx hyperframes skills update media-use, then copy whoosh-short / whoosh-cinematic / click-soft .mp3 into assets/sfx/"; fi
[ -f "$SRC/voice.json" ] && cp "$SRC/voice.json" "$DIR/voice.json" || echo "  ! no voice.json in $SRC — AI 配音 (tools/tts_voice.py) needs one"

echo "→ python tools venv (once per machine)"
VENV="$HOME/.cache/mihua-video/venv"
if [ ! -x "$VENV/bin/pyftsubset" ] || ! "$VENV/bin/python" -c "import numpy, mlx_whisper, certifi" 2>/dev/null; then
  python3 -m venv "$VENV" && "$VENV/bin/pip" -q install fonttools brotli numpy mlx-whisper certifi
fi

python3 - "$DIR/package.json" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p))
d.setdefault("scripts", {}).update({
  "tts": "$HOME/.cache/mihua-video/venv/bin/python tools/tts_voice.py",
  "tts:neutral": "$HOME/.cache/mihua-video/venv/bin/python tools/tts_voice.py --variant neutral",
  "build": "node tools/build.mjs",
  "build:neutral": "CONFIG=video.config.neutral.json node tools/build.mjs",
  "mix": "python3 tools/mix.py video.config.json",
  "mix:neutral": "python3 tools/mix.py video.config.neutral.json",
  "cover": "node cover/render.mjs",
  "cover:measure": "node cover/measure.mjs"})
json.dump(d, open(p, "w"), indent=2, ensure_ascii=False)
PY
# Any agent (Claude Code, Codex, Cursor) opening this folder reads AGENTS.md / CLAUDE.md first.
# hyperframes init wrote long generic routing there; replace it with a few lines that send the agent to mihua-video.
HEAD="$(cat <<EOF
# AI 讲解视频工程（mihua-video）

做任何事之前先读 mihua-video skill 的 SKILL.md，按里面的流程走：$SKILL/SKILL.md
（也可能装在 ~/.claude/skills、~/.codex/skills、~/.cursor/skills 或 ~/.agents/skills 下的 mihua-video/）

- 品牌层（src/theme.css、src/common.js、src/index.html、tools/、cover/brand.css 和 cover.js）不为单支视频改；每支视频只新写
  src/scenes/*.html、script.md / timing/film.json、video.config*.json，以及封面页 cover/cover_34.html、cover_43.html。
- 口播两条路：用户自己录（tools/prep_voice.py → tools/transcribe_voice.py），或 AI 配音（script.md → tools/tts_voice.py，Fish Audio 克隆声音）。
- 要 numpy / mlx-whisper 的 Python 工具用 $VENV/bin/python 运行。
- 写合成代码时参考 hyperframes-core skill 的规则，不转去别的 HyperFrames 工作流；命令用 package.json 锁定的版本（npx --yes hyperframes@<版本>）。
- 回复用中文。
EOF
)"
for f in AGENTS.md CLAUDE.md; do printf '%s\n' "$HEAD" > "$DIR/$f"; done
echo "✓ ready: $DIR"
echo "  next: put materials in, prep the voice, transcribe, plan the storyboard — see SKILL.md"
