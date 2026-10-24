# 示例工程：《用 AI 做一支讲解视频》

范米花儿发布过的一支讲解视频，14 分 48 秒，讲怎么用 AI 做视频：选题、口播、分镜、声音、风格、协作、省额度七章。画面全部由这个工程里的代码渲染出来。

这里是完整的工程源码，用来看一支片子从口播稿到画面是怎么落地的。**只看做法，不要复制场景改字**：你的视频内容、素材、镜头都应该不一样（`mihua-video/references/motion-language.md` 讲怎么重新设计）。

## 目录

| 位置 | 是什么 |
|---|---|
| `工程/script.md` | 口播稿（配音用的就是它）；开头的注释写了全片的画面方向，每章开头的注释写了这一章的画面怎么做 |
| `工程/src/scenes/act*.html` | 每章一个场景：actA 开场 · actB 选题 · actC 口播 · actD 分镜 · actE 声音 · actF 风格 · actG 协作 · actH 省额度 · actO 结尾 · actP 尾幕 |
| `工程/src/partials/set/` | 「微观片场」插画，全部用代码画：改 `master.html`，再跑 `python3 src/partials/set/make.py` 生成每章用的部分 |
| `工程/src/partials/kit.css`、`kit.js` | 这支片子自己的卡片版式、标注小工具（`pin`）、裁掉旧成片字幕的窗口（`.nocap`） |
| `工程/src/partials/` 其余 | 已经生成好的代码面板、声音波形 |
| `工程/video.config.json` | 章节、导航、签名出现的时机、配乐高光（`lifts`）、音量演示（`rides`） |
| `工程/timing/film.json` | 每一句在第几秒说的（按原配音量出来的） |
| `工程/music/music_follow.py` | 这支片子的配乐程序（跟着口播走）；skill 里的 `make_music.py` 是它的通用版 |
| `工程/cover/` | 封面页（3:4、4:3），出图方法见 `mihua-video/references/cover.md` |
| `工程/capture/` | 截官方文档、画声音波形的小脚本 |
| `工程/tools/` | 工具脚本，和 skill 里的一样（新工程用 skill 建） |
| `成片/` | 封面、字幕 |

## 缺了什么

| 缺的 | 为什么 | 现在是 |
|---|---|---|
| 范米花儿的头像、签名、以前视频的片段，和从这些片段截出来的画面、封面 | 个人品牌，不随仓库提供 | 同尺寸的灰色占位（头像签名是 skill 里的占位图）；场景照样能构建、版式不变，窗口里是灰的 |
| 原配音、配乐、混音 | 声音不随资料提供；配乐和混音可以重新生成 | 空的，按下面「用你的声音完整重做一遍」生成 |
| 参考作品、网站录屏、评论和群聊截图 | 是别人的东西 | 灰色占位，写着原作者或「不公开」 |
| 官方文档截图（`工程/assets/web/`） | 版权在各家官方 | 灰色占位；`capture/docs.mjs` 可以重新截 |
| 音效 | 不单独转发 | 空的，从 HyperFrames 的 media-use skill 拷 |

## 只看画面

1. 先让 AI 照资料首页装好（字体从 https://www.alibabafonts.com 下载安装后，把普惠体 Regular、Medium、Bold 和数黑体 Bold 拷进 `工程/assets/fonts/`，文件名照 `工程/video.config.json` 的 fonts 那一项改）。
2. 在 `工程/` 里：
   ```bash
   node tools/build.mjs
   npm run dev
   ```
   浏览器里会打开预览，拖时间轴看。还没有配音时，片子没有声音。

也可以直接让 AI 做：「打开示例_幕后协作/工程，帮我在浏览器里预览这个工程。」

## 用你的声音完整重做一遍

场景里所有动作都挂在口播句子上（`C.l12`、`C.ask` 这种），不写死秒数。换一个声音重新配音，时间轴变了，画面会自己跟上。

1. 在 Fish Audio 克隆你的声音，把 id 填进 `工程/voice.json`，key 写进 `~/.config/mihua-video/keys.env`。
2. 音效：把 media-use skill 里 `audio/assets/sfx/` 的三个 mp3 拷进 `工程/assets/sfx/`。
3. 在 `工程/` 里：
   ```bash
   ~/.cache/mihua-video/venv/bin/python tools/tts_voice.py --intro 4     # 这支开头留了 4 秒纯音乐；新做的视频按 skill 的规则写 --intro 0.5
   ~/.cache/mihua-video/venv/bin/python music/music_follow.py            # 配乐
   node tools/build.mjs && python3 tools/mix.py && node tools/build.mjs
   DRAFT=1 sh tools/deliver.sh video.config.json 我的版本 renders/样片   # 1080p，先看一遍
   sh tools/deliver.sh video.config.json 我的版本 renders/成片            # 4K
   ```
4. 声音那一章的波形（`src/partials/wave/`）是按原配音量出来的；换了声音，第 3 步做完以后跑 `~/.cache/mihua-video/venv/bin/python capture/make_waves.py` 重画，再 build。脚本里有两处要处理：克隆声音样本换成你自己的，或者删掉画 `e_clone` 的几行；没有 `bed_old.wav`（以前的循环配乐），就删掉画 `e_old` 的几行。

渲染在本机跑，15 分钟的 4K 片子要渲很久。遇到怪问题先查 `mihua-video/references/pitfalls.md`。

使用规则见资料里的「先看这个.md」。
