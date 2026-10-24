#!/usr/bin/env bash
# 一次装好做视频需要的一切，能自动的都自动做；做不了的列在最后，交给用户。
#
#   bash scripts/setup.sh            # 装 + 检查（可以反复跑，装过的会跳过）
#   bash scripts/setup.sh --check    # 只检查，不装
#
# 做的事：查系统 → 装 node / python3 / ffmpeg（有 Homebrew 才能自动装）→ 字体装进系统 → 装这个 skill
#        → 装 HyperFrames 的 skill（hyperframes-core、media-use）→ 建 Python 环境 → 查头像、签名、声音配好没有。
set -uo pipefail
CHECK=0; [ "${1:-}" = "--check" ] && CHECK=1
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$HOME/.cache/mihua-video/venv"
TODO=()      # 要用户自己做的
WARN=()      # 不影响出片、但要知道的
ok()   { echo "  ✓ $*"; }
miss() { echo "  ✗ $*"; }

echo "→ 系统"
if [ "$(uname -s)" != "Darwin" ]; then
  miss "不是 macOS：这套只在 Mac 上用过"; WARN+=("不是 macOS，下面的步骤可能走不通")
elif [ "$(uname -m)" != "arm64" ]; then
  miss "不是 Apple 芯片：转写（mlx-whisper）用不了"; WARN+=("不是 Apple 芯片：自己录口播的对时间、AI 配音的读回检查用不了")
else ok "macOS · Apple 芯片"; fi

echo "→ node / python3 / ffmpeg"
need=()
for c in node npx python3 ffmpeg ffprobe; do
  if command -v "$c" >/dev/null 2>&1; then ok "$c"; else miss "$c"; need+=("$c"); fi
done
if [ ${#need[@]} -gt 0 ] && [ $CHECK = 0 ]; then
  if command -v brew >/dev/null 2>&1; then
    pkgs=()
    for c in "${need[@]}"; do case "$c" in node|npx) pkgs+=(node);; python3) pkgs+=(python);; ffmpeg|ffprobe) pkgs+=(ffmpeg);; esac; done
    pkgs=($(printf "%s\n" "${pkgs[@]}" | sort -u))
    echo "  装：${pkgs[*]}（Homebrew）"; brew install "${pkgs[@]}"
  else
    TODO+=("装 Homebrew：打开「终端」，粘贴 https://brew.sh 首页那一行命令，回车，按提示输入电脑开机密码（输入时屏幕上不显示）。装好以后跟 AI 说「Homebrew 装好了，继续」。")
  fi
fi

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
echo "→ 字体（阿里妈妈数黑体、阿里巴巴普惠体：免费商用，要你从官网下载安装，仓库里不带）"
fmiss=0
for f in AlimamaShuHeiTi-Bold.otf Alibaba-PuHuiTi-Regular.ttf Alibaba-PuHuiTi-Medium.ttf Alibaba-PuHuiTi-Bold.ttf; do
  hit="$(font_find "$f")"
  if [ -n "$hit" ]; then ok "${f%.*}（$(basename "$hit")）"; else miss "${f%.*}"; fmiss=1; fi
done
if [ $fmiss = 1 ]; then
  TODO+=("装字体：在打开的 https://www.alibabafonts.com 下载「阿里巴巴普惠体」（要常规 Regular、中黑 Medium、粗体 Bold 三个字重）和「更多免费字体」里的「阿里妈妈数黑体」，双击字体文件安装。装好以后跟 AI 说「字体装好了」，它会再查一遍。")
  [ $CHECK = 0 ] && command -v open >/dev/null 2>&1 && open "https://www.alibabafonts.com" 2>/dev/null || true
fi

echo "→ 这个 skill（mihua-video）"
if [ $CHECK = 0 ]; then bash "$SKILL/scripts/install.sh" | sed 's/^/  /'
else for b in "$HOME/.claude/skills" "$HOME/.codex/skills"; do [ -f "$b/mihua-video/SKILL.md" ] && ok "$b/mihua-video" || miss "$b/mihua-video"; done; fi

echo "→ HyperFrames 的 skill（写合成代码的规则、音效）"
if command -v npx >/dev/null 2>&1; then
  for s in hyperframes-core media-use; do
    found=""; for b in "$HOME/.agents/skills" "$HOME/.claude/skills" "$HOME/.codex/skills"; do [ -d "$b/$s" ] && found="$b/$s"; done
    if [ -n "$found" ]; then ok "$s"
    elif [ $CHECK = 0 ]; then npx --yes hyperframes skills update "$s" >/dev/null 2>&1 && ok "${s}（装好了）" || { miss "$s 没装上"; WARN+=("$s 没装上：联网后让 AI 跑 npx --yes hyperframes skills update $s"); }
    else miss "$s"; fi
  done
else miss "没有 npx，先装 node"; fi

echo "→ Python 环境（配乐、转写、字体压缩）"
if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "import numpy, mlx_whisper, certifi, fontTools, PIL" 2>/dev/null; then ok "$VENV"
elif [ $CHECK = 0 ] && command -v python3 >/dev/null 2>&1; then
  echo "  建环境，第一次要下载约 1 GB，等几分钟……"
  python3 -m venv "$VENV" && "$VENV/bin/pip" -q install fonttools brotli numpy mlx-whisper certifi pillow && ok "${VENV}（建好了）" \
    || { miss "Python 环境没建好"; WARN+=("Python 环境没建好：检查网络后再跑一次 setup.sh"); }
else miss "Python 环境还没建"; fi

echo "→ 转写模型（whisper-large-v3-turbo，约 4.5 GB，自己录口播对时间、AI 配音读回检查都要用）"
MODEL="mlx-community/whisper-large-v3-turbo"
if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "from huggingface_hub import snapshot_download as s; s('$MODEL', local_files_only=True)" >/dev/null 2>&1; then ok "$MODEL"
elif [ $CHECK = 0 ] && [ -x "$VENV/bin/python" ]; then
  echo "  下载中，第一次要等一阵……"
  if "$VENV/bin/python" -c "from huggingface_hub import snapshot_download as s; s('$MODEL')" >/dev/null 2>&1; then ok "${MODEL}（下好了）"
  elif HF_ENDPOINT=https://hf-mirror.com "$VENV/bin/python" -c "from huggingface_hub import snapshot_download as s; s('$MODEL')" >/dev/null 2>&1; then ok "${MODEL}（从国内镜像 hf-mirror.com 下好了）"
  else miss "转写模型没下下来"; WARN+=("转写模型没下下来：检查网络（Hugging Face 在大陆常连不上），稍后再跑一次 setup.sh"); fi
else miss "转写模型还没下"; fi

echo "→ 头像、签名（$SKILL/assets/brand/）"
# 资料里自带的是灰色占位图：「头像」「你的签名」两个字的灰图，文件大小没变就是还没换
placeholder=0
for f in avatar.png:9816 signature.png:21403; do
  n="${f%%:*}"; sz="${f##*:}"; p="$SKILL/assets/brand/$n"
  if [ -f "$p" ] && [ "$(stat -f%z "$p")" != "$sz" ]; then ok "$n 已换成你的"
  else miss "$n 还是占位图"; placeholder=1; fi
done
[ $placeholder = 1 ] && TODO+=("给 AI 两张图：一张头像（方形最好）、一张手写签名的照片（白纸黑字，写「嗨，我是 + 你的名字」这类问候）。AI 用 scripts/make_brand.py 裁好、抠成透明底。")

echo "→ 配音（可选：不用 AI 配音就自己录口播）"
KEYF="$HOME/.config/mihua-video/keys.env"
voice_ok=1
if [ -n "${FISH_API_KEY:-}" ] || grep -q "^FISH_API_KEY=." "$KEYF" 2>/dev/null; then ok "Fish Audio API key"
else miss "还没有 Fish Audio API key"; voice_ok=0; fi
if grep -q '"reference_id": *"<' "$SKILL/assets/brand/voice.json" 2>/dev/null; then miss "voice.json 里还没有你的声音 id"; voice_ok=0
else ok "voice.json 里有声音 id"; fi
[ $voice_ok = 0 ] && TODO+=("配音选一条路（见资料里的「配音设置.md」）：自己录口播，这一项不用管；用 AI 配音，就去 Fish Audio 注册、付费，把 API key 粘进 AI 帮你打开的那个文件，再给 AI 两三段自己的录音，它来克隆声音。")

echo "→ 这台电脑能出多大的成片"
( . "$SKILL/assets/kit/tools/render_plan.sh"
  FREE=$(disk_free_gb "$HOME")
  echo "  $CHIP · 内存 ${RAM_GB} GB · 硬盘剩 ${FREE} GB → 成片最高建议 $(res_name $MAXRES)（样片一律 1080p）"
  [ -n "$FREE" ] && [ "$FREE" -lt 20 ] && echo "  ✗ 硬盘剩不到 20 GB：环境、模型和一支 4K 成片加起来要近 10 GB，先清出空间"
  true )

echo
if [ ${#WARN[@]} -gt 0 ]; then echo "要知道的："; for w in "${WARN[@]}"; do echo "  · $w"; done; fi
echo "要你自己做的："; for t in "${TODO[@]}"; do echo "  · $t"; done
echo "以后改了 mihua-video 文件夹里的东西（换头像签名、改规则），重新跑一次 bash scripts/install.sh。"
