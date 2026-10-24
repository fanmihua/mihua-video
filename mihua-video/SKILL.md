---
name: mihua-video
description: AI 讲解视频工作流——用用户自己录的口播，或用用户的克隆声音（Fish Audio）按稿子自动配音，做成风格统一的 AE 质感讲解视频（深灰舞台、手写签名+头像、章节导航、阿里数黑字幕、真实截图/录屏上做镜头运动），输出成片（按电脑配置出 4K / 2K / 1080p）、字幕和封面，需要时分平台出两个版本。只要用户要做讲解视频、教程、案例拆解、作品展示、把口播/录屏剪成成片、给视频加字幕和配乐、AI 配音 / 不想自己录口播，就使用这个 skill，即使用户没提到 skill 或 HyperFrames。
---

# AI 讲解视频

| | 固定（每支视频一模一样） | 每支视频重新设计 |
|---|---|---|
| 是什么 | 固定的品牌层：舞台、签名 + 头像、章节导航、字幕、标注 / 框 / 窗口 / 代码面板样式、字体配色、混音和清晰度标准；封面的尺寸、舞台、签名头像、字体 | 内容：几章、每章讲什么、用哪些素材、镜头怎么走、哪里是重点；封面怎么排 |
| 在哪 | `assets/kit/`（theme.css、common.js、index.html 外壳、tools/、cover/）+ `references/brand-system.md` | 每个工程的 `src/scenes/*.html`、`timing/film.json`、`video.config*.json`、`cover/cover_34.html`、`cover_43.html` |
| 规则 | 不为单支视频改；真要改就改 skill，让以后所有视频一起变 | **不复制旧视频的场景、封面当模板**，按这支的口播和素材重新组合 |

签名和头像是用户自己的（`references/brand-system.md` › 换人使用）。资料包里和 `mihua-video/` 并排放着一个「示例工程」（`示例_幕后协作/工程/`；装好的 skill 副本里没有它，要到用户解压的资料包文件夹里找），是一支做完的 14 分钟讲解视频，只用来看一章怎么从口播落到镜头、config 怎么填，不复制它的场景。

## 依赖和安装
- **HyperFrames CLI**：写合成代码前读 hyperframes-core skill（和其他 skill 一样在 `~/.agents/skills` 或 `~/.claude/skills` 里按路径读；没装就 `npx hyperframes skills update hyperframes-core`）。工程里的命令一律用 `package.json` 锁定的版本：`npx --yes hyperframes@<锁定版本> lint / snapshot / render`（原因见 `pitfalls.md`）。
- **ffmpeg、python3、node**。Python 工具的环境 `~/.cache/mihua-video/venv` 由建工程的脚本自动建（fonttools、brotli、numpy、mlx-whisper、certifi），之后带 numpy / whisper 的工具都用 `~/.cache/mihua-video/venv/bin/python` 跑。
- **字体**：阿里妈妈数黑体、阿里巴巴普惠体（免费商用）要从 https://www.alibabafonts.com 下载安装（官方声明只授权下载和使用，仓库里不带；许可见 `assets/fonts/字体说明.md`）；`setup.sh` 会检查、缺了打开官网，建工程时脚本从系统里找到它们拷进工程。
- **AI 配音**（可选）：Fish Audio 的 API key + 用户自己的克隆声音。key 写成 `FISH_API_KEY=…`，放在 `~/.config/mihua-video/keys.env`（或工程上层目录的 `.voice_keys.env`）；不打印、不写进工程文件。克隆声音的 id 填进 `assets/brand/voice.json` 的 `reference_id`。不用 AI 配音，就用户自己录口播，这两样都不需要。
- **转写**（自己录口播出时间轴、AI 配音的读回检查）用 mlx-whisper，只支持 Apple 芯片（M 系列）的 Mac。
- **音效**：这份资料不带音效 mp3，建工程时脚本从 HyperFrames 的 media-use skill 里拷（没有就先 `npx hyperframes skills update media-use`）。
- **一次装好**：`bash scripts/setup.sh`——查系统、装 node / python3 / ffmpeg（有 Homebrew 时）、装字体、装这个 skill、装 hyperframes-core 和 media-use、建 Python 环境，最后列出要用户自己做的事；`--check` 只检查。只想同步改过的 skill：`bash scripts/install.sh`（装到 `~/.claude/skills`、`~/.codex/skills`，Cursor 也会从这两个文件夹读）。Claude Code / Codex / Cursor 都能用：每一步都是普通的 shell / python / node 命令。
- **换成用户自己的头像、签名**：用户给一张头像照片、一张白纸深色笔的手写签名照片，`~/.cache/mihua-video/venv/bin/python scripts/make_brand.py --avatar <图> --signature <图>` 裁好、抠成透明底，写进 `assets/brand/`，再跑 `install.sh`。
- 「给用户看」= 告诉用户文件路径（mp4、jpg、md），让用户自己打开；不要假设有内嵌预览面板。

## 怎么和用户配合
- **AI 主导执行**：录屏、剪辑、自查、渲染都由 AI 做，只在用户的关口和非用户不可的那一步叫用户，一次说清（`materials.md` › 录屏）。
- 关口给用户看能看、能播的东西，不给只有代码的半成品。
- 用户说一个感觉词（「像 PPT」「促销感」「眼睛跟不过来」）：先问清是哪个画面、哪一秒，再到对应的参考文件里找规则改。
- 请用户看片提意见按「时间点 + 问题」说；改完逐条回「改了 / 没改，因为…」。
- 一支做完、用户认可了再开下一支，不并行、不提前做下一支。为什么：同时做几支，每支的质量都会差很多。

## 主流程

开工先问清 **用在哪**：对外的自媒体视频，还是教程（`references/script.md` › 0）。画面风格一样，讲故事的方式不同；内容确认单里没写的，先问用户，不自己猜。为什么：猜错了，口播要整版重写。

> 建工程 → 选题、口播稿（自媒体先定封面字，跟稿子一起给用户看）【用户看】→ 配音【用户听第一章】→ 素材 → 内容确认单【用户点头】→ 分镜【用户看】→ 风格静帧【用户在预览里看】→ 场景 → 声音 → 自查 → 1080p 样片【用户看】→ 成片（4K / 2K / 1080p，看电脑配置）【用户看】→ 封面【先给方向】

用户已经认可的片子只是小修，直接出成片；不做审片表。同类视频风格已经定过的，静帧只给这支新出现的画面类型。下面按步骤写做什么、哪里是用户的关口、读哪份参考。

### 1. 建工程
项目放在用户指定的文件夹（比如 `~/Desktop/我的视频/`）下，一个视频一个 `年-月_主题` 文件夹，里面固定 `素材/`（用户给的原始素材）、`工程/`（HyperFrames 工程）、`成片/`（交付物）。
```bash
P="<用户指定的文件夹>/<年-月_主题>"
mkdir -p "$P/素材" "$P/成片" && bash <skill>/scripts/new_project.sh "$P/工程"
```
得到品牌层 + 工具（`src/scenes/` 是空的），`素材/` 里放好三份模板：`素材清单.md`、`内容确认单.md`、`交接.md`。
头像、签名、声音 id 从 skill 的 `assets/brand/` 拷进工程：第一次用之前，先让用户把这三样换成自己的（`brand-system.md` › 换人使用）；也可以用 `new_project.sh "$P/工程" --brand <放着 avatar.png、signature.png、voice.json 的文件夹>` 指定别的来源。

### 2. 选题和口播稿 → `references/script.md`
照 script.md 逐节写、逐节自查：先定场景（› 0）→ 自媒体走选题三问（› 1）、开头 3 秒（› 2），教程照 › 0 的结构和开头 → 技术说法对官方原文（› 3，交接里列对照表）→ 像本人说话（› 4）→ 讲清楚（› 5）→ 不对外的内容（› 6）→ 写完扫一遍（› 7，跑 `copy_check.py`）。稿子格式见 `audio.md` › script.md 写法。
**关口：稿子给用户看，改到用户满意再合成**——稿子就是成片口播。

### 3. 配音 → 时间轴 → `references/audio.md`
两条路产物一样（`assets/voice/voice.wav` + `timing/film.json`），先问用户这支用哪条：
- AI 配音：`polyphone_check.py` → `tts_voice.py --intro 0.5` → `pace_check.py` → 看「需要听一下的行」（`audio.md` › AI 配音 › 流程）。
- 用户自己录：`prep_voice.py` → `transcribe_voice.py --intro 0.5` → 人工过一遍 `film.json`，**以录音为准**（`audio.md` › 用户自己录）。

关口：让用户听一遍第一章；拿不准的读音剪成一段试听，一次给用户。

### 4. 素材 → `references/materials.md`
和用户一起填 `素材清单.md`（只有用户能给的 / 现成能用的 / AI 自己做的），请用户把素材直接放进 `素材/`、不放桌面；AI 整理进 `assets/`，在清单里打勾。缺什么问用户要，不拿不相关的凑。

### 5. 内容确认
填 `素材/内容确认单.md` 给用户过：用在哪（自媒体 / 教程）、选题三问（自媒体）、第一句和开头画面、每章一句话、要核实的技术说法、必须用真实素材的地方、**这支绝不出现的内容**、待用户决定的事。用户确认后写日期；之后要改方向，先改这张单子，再改画面。为什么：最费额度的不是渲染，是整片做完才改方向。

### 6. 分镜 → `references/motion-language.md`
按口播逐章设计：主角素材 → 镜头怎么走 → 标注写什么 → 怎么转到下一章，用表格给用户看，标出要用户决定的地方。不要一上来就写代码。

### 7. 静帧
挑一两章最有代表性的画面，搭到能看的程度（配音还没合成时用按字数估的临时时间轴），**在浏览器预览里给用户看，不出图**：`npm run dev`（`hyperframes preview`，Claude Desktop 里配进 `.claude/launch.json` 用 preview_start 打开），告诉用户看哪几个时刻（章 + 秒数），用户自己拖时间轴。风格在这一步定。
**看效果一律用预览，不用 `snapshot` 出图**：AI 自查、挑错、改完复看也是在预览里看：另开一个标签页打开 `http://localhost:<端口>/api/projects/<工程文件夹名>/preview`，视口设成和合成一样大（4K 构建 3840×2160），`await window.__player.seek(秒)` 后截屏，细节用放大截原尺寸局部；出没出画面、字有没有被切、框准不准，用 JS 量元素位置。只有真渲染才看得到的（`<video>` 帧、字体、声音）留到样片里查。
- 预览服务每次检测到文件变化都会自己跑一遍 lint（工程大的要十几分钟），连着 build 几次就叠出一堆 lint 进程，电脑会卡：看完就 `preview_stop` 关掉，build、渲染时不开。
- 为什么不出图：出图要排队、每次重新加载整片，静帧关能为出图等上几个小时；这一步只是确认效果。
- 真正渲染只在用户认可以后：样片、成片（§11），以及要交付的封面。`lint` 也只在渲染前跑一次，不每改一处跑。

### 8. 写场景 → `motion-language.md` › 6 场景骨架、`brand-system.md` › 可以按视频调整的参数
每个 act 一个 `src/scenes/<actId>.html`，所有时间从 `C`（这一章的口播节点）算，不写死秒数；只用 common.js 的动作和 theme.css 的组件。`video.config.json` 填 acts、aliases、chapters、navFrom / navUntil、sigAt、noCaptions。

### 9. 声音 → `references/audio.md`
```bash
~/.cache/mihua-video/venv/bin/python tools/make_music.py      # 跟着口播走的原创配乐；通用版加 --config video.config.neutral.json
node tools/build.mjs && python3 tools/mix.py && node tools/build.mjs
```
换了配音就重跑 `make_music.py`。成片 -10 LUFS，音效极少极轻。

### 10. 自查（给用户看之前，AI 自己先过一遍）
出静帧、样片、成片之前逐项过，消息里说一句「自查过了，改了哪几处」。为什么：很多修改意见 AI 自己就查得出来，先查掉能省用户一轮。在预览里拖到需要看的那一刻看（每章中点 + 清单涉及的时刻），放大看局部，不出图、不整片反复抽帧（§7）。
- [ ] `lint` 通过；`check` 的提示看一眼（真组件叠放、代码行号这类有意的重叠不用改）；分平台版本时 build 用 `forbid` 拦平台词
- [ ] 出片前在预览里跑 `tools/safezone_scan.js`：字幕区、顶部没有停着的字和截图（`pitfalls.md`）
- [ ] 开头照这支的场景（`script.md` › 0）：自媒体第一句是结果或痛点，没有纯音乐开头、没先打招呼、没念目录，钩子是这一支自己的画面（`script.md` › 2、`motion-language.md` › 4）；教程照 `script.md` › 0
- [ ] 片头 0.5 秒、每章开头截一帧：没有提前冒出来的框、标注（`pitfalls.md` 里 fromTo 那一行）
- [ ] 框对准真实内容、一眼看得见、不伸出卡片；标注圆点落在目标上（`motion-language.md` › 3.5）
- [ ] 录进去的真实界面本身对（`materials.md` › 真实）
- [ ] 卡片变白、背景变亮的地方，小字还看得见（`motion-language.md` › 3.10）
- [ ] 一个画面一个焦点；演示动作看得出来；每 3 句截一张，没有空屏；用了以前成片的窗口，裁掉了它自带的字幕（`motion-language.md` › 1、2、3.11、3.12）
- [ ] 口播提到的东西，画面上都放了真的那个（`motion-language.md` › 1）
- [ ] 参考作品标了出处（作者名不打码、不露网址）；他人姓名头像、水印、密钥打了码（`materials.md`）
- [ ] 「绝不出现」清单里的内容口播、画面、字幕都没有（`script.md` › 6）
- [ ] `pace_check.py` 全部达标，听一遍没有卡顿、剪断的字，换话题时画面也停一下（`audio.md` › 节奏）
- [ ] 多音字跑过 `polyphone_check.py`；技术说法和官方一致（`audio.md` › 读音、`script.md` › 3）
- [ ] 签名、头像、导航在，字幕是阿里数黑（放大一帧看笔画是否方正，`pitfalls.md`）
- [ ] 讲声音的地方真的听得到变化；音效不盖过人声（`audio.md` › 讲声音的地方）
- [ ] 窗口、卡片里的 `<video>` 宽高写死像素，而且**从真渲染的 mp4 里**抽帧看过（`pitfalls.md`）
- [ ] 分平台版本时：把成片音频转写一遍，确认没有平台词

### 11. 样片和成片
渲染在用户电脑上跑，不花 AI 额度，但会占满内存和 CPU。新版、大改版、用户还要对齐方向时，整片先出 1080p 样片（`DRAFT=1`，渲得快）；用户说没问题再出成片。用户已认可的片子小修直接出成片。
**成片多大看电脑配置，不默认 4K**：出成片前跑 `sh tools/render_plan.sh`，告诉用户这台电脑能出多大、大概要多久（内存 ≥32 GB → 4K，16–31 GB → 2K，<16 GB → 1080p；参考 M4 Max、36 GB，10 分钟的 4K 约 30 分钟）。`deliver.sh` 默认按这个建议出，超过建议就停下；`RES=1080 / 1440 / 2160` 可以指定，超过建议还要加 `FORCE=1`——用户没明确同意前不加，加之前讲清可能卡死、渲崩。为什么：配置不够硬出 4K，电脑会被吃满、渲到一半崩掉。
```bash
DRAFT=1 sh tools/deliver.sh video.config.json <名字> renders/样片      # 1080p 样片（顺带生成的 _审片表.md 不用给用户）
sh tools/deliver.sh video.config.json <名字> <项目>/成片               # 成片 + SRT（按电脑配置出 4K / 2K / 1080p）
```
- `deliver.sh` 自动用锁定版本、按电脑内存给渲染进程定上限、渲染时防睡眠、查硬盘空间、换 320k 音轨并核对 -10 LUFS（各自原因见 `pitfalls.md`）；手动跑 render 时自己照做。
- **改过以后再出，只渲改了的那几章**：同一个名字、同一个文件夹再跑一次 `deliver.sh`，它拿上一版成片出片时存的指纹（`timing/delivered/`）比，只重渲最早改动那一章到片尾、接回上一版（接缝自动逐帧核对）；画面没变就只换音轨；第一章、外壳（品牌层、签名头像、字体）变了或接不上，自动整片出。日志里 `·` 开头那行写着这次怎么出。所以小修**直接覆盖上一版**，不先删、不改名、不换文件夹；`FULL=1` 强制整片，`FROM=actC` 最早从这一章起。为什么：只改了最后一章也整片重渲，长片要等很久（大半花在编码上），只渲那一章几分钟就好。
- 平台版本：要分平台出两个版本时用 `video.config.neutral.json`（`forbid`、`textReplace` 见 `brand-system.md`），tts 稿子里 `[小红书]`（只进主版）/ `[通用]`（只进通用版）标签区分，`tts_voice.py --variant neutral` 出通用版口播，每个版本各跑一次 `deliver.sh`。
- 同时开几个 AI 对话时，同一时间只渲一个（看项目里约定的锁文件）。
- 自己拿不准一段新画面时，出单章预览只给自己看：`python3 tools/module.py actB` → `make_music.py --config video.config.actB.json` → `SAMPLE=1 sh tools/deliver.sh video.config.actB.json <名字>_actB renders/预览`；完了跑 `CONFIG=video.config.json node tools/build.mjs`（出样片前带 `RES=1080`）恢复整片构建。有视频窗口的章也用它从真渲染里抽帧核对。
- 成片只交原片（4K / 2K / 1080p）+ SRT，不另出压缩的上传版；1080p / 720p 只在用户明确要时用 `PREVIEW=1` 加出。还没配音时：`RES=1080 CONFIG=… node tools/build.mjs` 再 `npx --yes hyperframes@<锁定版本> render`。
- AI 配音的视频，发布时勾选平台的「AI 生成」声明。

### 12. 封面 → `references/cover.md`
成片定了以后单独做一轮：先给 2–3 个方向，用户选定再精做；主画面放结果，标题短；白、黑各一套（3:4 / 4:3）。
全部交付后，过程文件（预览、样片、联系表、快照、旧渲染）先跟用户确认一句，再挪进废纸篓（`/usr/bin/trash`）；项目里只留 素材 / 工程 / 成片。

## 底线（最常犯的，细则看指向）
1. 先分清用在哪（自媒体 / 教程，拿不准问用户）：自媒体第一句就给结果或痛点，不用纯音乐开头、不先打招呼、不念目录；教程不用痛点钩子，像老师讲课（`script.md` › 0、2）。
2. 技术说法和官方文档一致，名词用官方原名，拿不准的不说（`script.md` › 3）。
3. 做视频的人自己的私事、商业决定、没发布的东西不进视频（`script.md` › 6）。
4. 直接给结果、不写转折句、不念代码名、不要 AI 腔；自媒体口语、像本人说话，教程像老师讲课（`script.md` › 0、4）。
5. 换话题停够；语速用原速；不剪开配音塞静音（`audio.md` › 节奏）。
6. 口播提到什么，画面就放真的那个；界面不用代码重画（`motion-language.md` › 1、`materials.md`）。
7. 一个画面一个焦点；画面不空着等下一句（`motion-language.md` › 1、2）。
8. 框和标注量出来对准、一眼看得见：白底里用 `.outline.dark`，框做成被框元素的子元素（`motion-language.md` › 3.5）。
9. 不复制旧视频的场景和封面；品牌层不为单支视频改（本文件开头）。
10. 自媒体：封面放结果，标题写具体的东西 + 痛点或反差（`cover.md`）；教程标题用本来的名字（`script.md` › 5）。

## 慢了先量
渲染、预览、检查、配音，任何一步比预期慢，**先量各步骤用时、找出原因，再继续**；不把「等」当成正常，也不凭感觉说「画面复杂」。`deliver.sh` 每一步都打印用时（⏱ 那几行），渲完先看一眼。为什么：时间常常不花在以为的地方——合成文件嵌了大块网页快照时，一遍 lint 就要十几分钟、出片要跑好几遍，真正画帧只要几分钟。合成文件超过几 MB 就先查是什么撑大的。

## 省额度
渲染不花 AI 额度，花额度的是 agent 自己的上下文：截图、日志、长对话、一轮轮小改。
- **按阶段开新对话**：每过一个关口按模板更新 `素材/交接.md`（只写现在的状态），下一阶段开新对话从交接接着做。对话越长，每一句都更贵。
- **截图要精准**：只截改动处那几秒，放大看需要看的局部；不为「再确认一下」重复截同一刻。
- **渲染放后台、不盯日志**：跑完只看结尾的时长和响度那几行。
- **修改意见攒一批再改**：请用户看完一次列全，一轮改完再出下一版，不要「改一处、渲一次、看一次」。
- **能用文字确认的不渲染**：改稿、改时间轴、改标注文字，先给对照文本让用户确认，再动画面。

## 改这个 skill 的规矩
用户提的意见，问一句「以后也会遇到吗」；要以后都照做的，写进对应主题的 references 文件，**只写一处**：怎么做（能照着做）+ 一句为什么；新旧冲突就改掉旧的，只留现在的做法。SKILL.md 只在流程变了时改。改的是用户放 skill 源文件的那个文件夹，改完重跑 `bash scripts/install.sh`（装好的副本会被覆盖，不要直接改副本）。

## 参考文件
| 文件 | 管什么、什么时候读 |
|---|---|
| `references/script.md` | 先分清用在哪（自媒体 / 教程）、选题、开头 3 秒、说法和官方一致、像本人说话、讲清楚、不对外、写完扫一遍——写稿时 |
| `references/motion-language.md` | 画面原则、分镜方法、镜头词汇、框和标注、开场结尾、场景骨架——分镜、写场景之前（必读） |
| `references/materials.md` | 真实、清晰、录屏、打码、标出处 |
| `references/audio.md` | AI 配音、读音、自己录口播、节奏停顿、配乐、音效、混音 |
| `references/cover.md` | 封面的时机、方向、主画面、标题、版面、出图 |
| `references/brand-system.md` | 固定层每个元素的规格、config 里能调的参数、换成用户自己的头像签名声音 |
| `references/pitfalls.md` | 构建 / 渲染 / 录屏出怪问题时先查这里 |
| `assets/kit/templates/` | 素材清单、内容确认单、交接的模板（建工程时自动复制到 `素材/`） |
| `assets/kit/tools/copy_check.py` | 扫口播稿的转折句、AI 腔、问句、代码名（`script.md` › 7） |
| `assets/brand/` | 头像、签名、`voice.json`（占位，用户先换成自己的） |
| 示例工程（`示例_幕后协作/工程/`） | 一支完整成片的场景写法和 config（只参考，不复制） |
