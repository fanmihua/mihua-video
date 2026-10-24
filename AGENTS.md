# 给 AI 的接手说明：AI 讲解视频工作流

用户是设计师，不写代码。你的目标：让用户**开箱即用**——能自动做的你都做完，只把非用户不可的事一次说清、一件一件带着做。回复用中文，说人话，不让用户自己敲命令、不让用户复制报错。

这个文件夹里：
- `mihua-video/`：做讲解视频的 skill（流程、规则、工具、品牌层）。做视频时照 `mihua-video/SKILL.md`。
- `示例_幕后协作/`：一支做完的 14 分钟讲解视频的完整工程，只当参考（`示例_幕后协作/README.md`）。
- `先看这个.md`：给用户看的「必须你来做的事」。`配音设置.md`：配音的几条路和价格。

## 一、用户说「帮我装好」时

1. 跑 `bash mihua-video/scripts/setup.sh`。它会自动：查系统、装 node / python3 / ffmpeg（有 Homebrew 时）、查字体（缺了会打开阿里巴巴字体官网，请用户下载安装 Regular、Medium、Bold 三个字重的普惠体和数黑体）、装这个 skill（`~/.claude/skills`、`~/.codex/skills`）、装 HyperFrames 的 hyperframes-core 和 media-use、建 Python 环境、下载转写模型（第一次要下载约 6 GB），最后列出「要你自己做的」。可以反复跑，装过的会跳过；`--check` 只检查。
   开始前先跟用户说一句：装的时候 Codex 会弹好几次「批准」，看清是装软件、跑这个文件夹里的脚本就批准；第一次要下载约 6 GB，等一会儿。
2. 有报错，你自己看、自己修，修好再跑一次。下载慢或连不上（大陆网络常见），先重试一次，再换国内镜像，**只对这一次命令生效，不改用户的全局设置**：
   - npm / npx：命令前加 `npm_config_registry=https://registry.npmmirror.com`
   - pip：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple …`
   - Hugging Face（转写模型）：`HF_ENDPOINT=https://hf-mirror.com`（setup.sh 已经会自动换）
   - Homebrew：`HOMEBREW_API_DOMAIN=https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles/api HOMEBREW_BOTTLE_DOMAIN=https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles brew install …`
   只有下面这些要用户来：
   - **没有 Homebrew**：装它要输入电脑密码。告诉用户：打开「终端」，粘贴 https://brew.sh 首页那一行命令，回车，输入开机密码（输入时不显示），装完回来说一声。然后你再跑 setup.sh。
   - **系统弹出授权窗口**（比如允许访问文件夹）：请用户点「允许」。
3. 装好以后，主动带用户做「换成自己的」（下面二、三），再问要不要先看示例（四）。

## 二、头像和签名

现在 `mihua-video/assets/brand/` 里是灰色占位图。请用户给你两张图：
- 头像：一张照片，脸在中间（正方形最好）。
- 签名：白纸上用深色笔写的手写问候（比如「嗨，我是 + 名字」），拍照或扫描，字要清楚、纸上别有别的东西。

拿到以后：
```bash
~/.cache/mihua-video/venv/bin/python mihua-video/scripts/make_brand.py --avatar <头像> --signature <签名照片>
bash mihua-video/scripts/install.sh
```
把生成的 `signature.png` 放到深色底上给用户看一眼（白字、透明底、四周没有多余的边）；纸上有阴影没抠干净，加 `--threshold` 调。

## 三、配音

先问用户选哪条路（详细见 `配音设置.md`，可以把那份的要点讲给用户听）：
- **自己录口播**：不用配任何东西。做视频时请用户照稿子录好，把音频文件放进工程的 `素材/`，照 skill 的「用户自己录」那条路做。
- **AI 配音（Fish Audio 克隆声音）**：
  1. 请用户在 https://fish.audio 注册、按 `配音设置.md` 选好方案并付费（这一步只能用户做）。
  2. API key：你建好文件、打开给用户粘贴，**不要让用户把 key 发在聊天里**：
     ```bash
     mkdir -p ~/.config/mihua-video && f=~/.config/mihua-video/keys.env
     [ -f "$f" ] || printf 'FISH_API_KEY=\n' > "$f"; chmod 600 "$f"; open -e "$f"
     ```
     请用户在 Fish Audio 网站的 API Keys 页面复制 key，粘在 `FISH_API_KEY=` 后面、保存。之后不要打印这个文件的内容。
  3. 克隆声音：请用户录 2–3 段自己说话的录音（每段 10–30 秒，安静、不要背景音乐，说中文），发给你。你用 Fish Audio 的创建声音模型接口（`POST https://api.fish.audio/model`，`type=tts`、`train_mode=fast`、`visibility=private`，文档 https://docs.fish.audio/api-reference/endpoint/model/create-model ）建一个**私有**的声音，把返回的 id 写进 `mihua-video/assets/brand/voice.json` 的 `reference_id`，再跑 `bash mihua-video/scripts/install.sh`。接口报权限或余额的错，就请用户在网站上克隆（设成私有），把声音 id 发给你。
  4. 先用一句话试听：建一个临时工程或在示例工程里，合成一两句给用户听，确认是自己的声音。想先免费试，把 `voice.json` 的 `model` 改成 `s2.1-pro-free`（官方的免费开发模型，有用量限制）。

## 四、先看示例（可选）

```bash
cd 示例_幕后协作/工程 && node tools/build.mjs && npm run dev
```
浏览器里会打开预览，告诉用户拖时间轴看；看完关掉预览服务。示例没有配音，是没声音的。

## 五、开始做视频

用户说「做一支视频」时，照 `mihua-video/SKILL.md` 的主流程走：先问清用在哪（自媒体还是教程）、讲什么、给谁看，建工程，从口播稿开始，每一关停下来给用户看。用户第一次用，每一关开始时用一句话告诉用户这一关要看什么。第一支建议先做一两分钟的短片：额度用得少、渲染快，先把流程走通。

## 六、出片（保护用户的电脑）

渲染在用户电脑上跑，会占满内存和 CPU。配置不够硬出 4K，电脑会卡死、渲到一半崩掉。
- 出成片前，在工程里跑 `sh tools/render_plan.sh`，用一句话告诉用户：这台电脑能出多大（内存 ≥32 GB 出 4K，16–31 GB 出 2K，<16 GB 出 1080p）、大概要等多久（参考：M4 Max、36 GB，10 分钟的 4K 约 30 分钟；芯片越老越慢）、要插电别合盖。
- `deliver.sh` 默认就按这台电脑的建议出；超过建议它会停下。**用户没明确同意前，不要加 `FORCE=1`**；要加，先讲清可能卡死、渲崩，并请用户关掉别的软件、插上电源。
- 样片一律 1080p；成片前先出样片给用户看。
- 改完再出：同一个名字、同一个文件夹再跑 `deliver.sh`，它只重渲改动的那一章到片尾、接回上一版（第一章或外壳变了才整片出）。所以不要先删旧成片、不要改名。
- 渲染放后台跑，不要盯着日志；跑完看结尾的时长和响度。渲染时电脑会防睡眠（`caffeinate`），合盖仍会睡眠。

## 注意
- 不要改 `示例_幕后协作/` 里的东西当成用户的新视频；新视频一律用 `mihua-video/scripts/new_project.sh` 建。
- 用户提的意见以后都要照做的，写进 `mihua-video/references/` 对应的文件（规矩见 SKILL.md 最后），改完跑 install.sh。
