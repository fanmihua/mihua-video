# 踩过的坑

| 现象 | 原因 | 解决 |
|---|---|---|
| 推近时画面整体往下偏（镜头对准的东西跑到字幕上方），只在 scale ≠ 1 时出现 | 镜头画布外面套了一层做「虚化对焦」的容器，它没写定位、高度是 0；容器一加 `filter` 就成了里面绝对定位元素的参照，画布的 `inset:0` 跟着变成 1920×0，缩放中心从 (960,540) 跑到 (960,0)（滤镜补间结束停在 `blur(0px)` 也还是 filter，一直偏） | 凡是要做 filter / transform 的外层容器都写 `position:absolute; inset:0`，让它占满整屏 |
| 尺寸线、标注线画出来以后整条往上（或往左）偏了自己长度的一半，看着和被量的东西错位 | 「从中间往两头长」的缩放动画只在终点写了 `svgOrigin`：GSAP 的 smoothOrigin 为了不跳，补了一段位移，缩放回到 1 以后位移还在 | 起点、终点都写同一个 `svgOrigin`，再加 `smoothOrigin: false`；画完在预览或成片里放大看一眼线的两头是否落在被量元素的上下边 |
| 居中的小字（库名、小签）先居中出现，动画一结束跳成偏右 | 用 CSS `transform: translateX(-50%)` 居中，又给它做了 GSAP 的 `y` / `x` 动画：GSAP 接管 transform 以后把那半个宽度丢了 | 这类字只做淡入；要位移就用 `gsap.set(el, {xPercent: -50})` 居中、删掉 CSS 里的 translate，或者外面再包一层只管居中 |
| 整条时间线不动、标注一直显示、镜头不走 | 外壳或场景脚本运行时报错（比如读了一个不存在的 act），timeline 没注册 | `npx --yes hyperframes@<锁定版本> check` 看 Runtime 段的 page_error；外壳只读 build 注入的 SHELL，不要手写 act id |
| 字幕/标题不是阿里数黑，是系统黑体 | `@font-face { font-family: "ShuHei", sans-serif; … }` 写错——声明里的 family 名不能带兜底字体 | 声明只写 `"ShuHei"`；用的时候才写 `"ShuHei", sans-serif`。出片前放大一帧字幕确认笔画方正 |
| lint 报 `font_family_without_font_face: pingfang sc` | 用了系统字体名却没有声明 | 不要引用 PingFang SC；品牌字体缺失时去安装，而不是兜底 |
| lint 报 `template_literal_selector` | querySelector 里用了模板字符串 `` `#${id}` `` | 写成普通字符串 |
| lint 报 `invalid_parent_traversal_in_asset_path` | 子场景里用了 `../assets/` | 一律写 `assets/...`（相对工程根目录） |
| 视频在章节里播放位置错乱 | `<video data-start>` 外面又套了带 data-start 的容器 | 时间只写在 video 自己身上；场景内 data-start 是本章内秒数 |
| 文字逐字动画 / 计数器不生效 | 在 `.ch` span 或 inline 元素上做 transform；或者在已拆成 span 的元素上改 textContent | 拆字后不要再改 textContent；要切换文字就叠几层，用透明度切换 |
| 气泡/文字竖着一个字一行 | 绝对定位元素在 0 宽容器里收缩 | 给元素一个明确宽度 |
| 灰度 → 彩色的调色属性切回灰度后图片空白 | HyperFrames 调色通道在这种用法下有问题 | 用 CSS `filter: grayscale(var(--g))` |
| 同一元素两个动画重叠报 overlapping_gsap_tweens | 两段 tween 时间重叠 | 前一段缩短，或用 fromTo 明确起止 |
| 剪出浮起时背后窗口先闪一下黑 | 父层的 `filter` 从 none 补间到 `brightness() blur()`，起点没写全 | 压暗父层时用 `fromTo`，起止都写全（从 `brightness(1) blur(0px)` 到要的值）；改前改后就地切换那种（`motion-language.md` › 3.4b）不用 hfLift 压父层 |
| 镜头推近后画面发虚 | 素材被缩小过 / 推得太近 | 原生 4K 素材，推近 ≤1.8 倍 |
| 3D 轮播侧卡穿到正前卡前面 | 卡片间角度太小、半径太小 | 角度 ≥50°，半径 ≥1250px |
| snapshot 报 Navigation timeout | 4K 素材多，首次加载慢 | `--timeout 60000` |
| 截图联系表里一张图显示别的版本 | 用 `#hash` 切换页面状态，浏览器不重新加载 | 用 `?query` 传参 |
| 混音后开头纯音乐太小（只在有纯音乐开头时出现） | 只有音乐的段落响度被整体标准化压低 | mix.py 里开头段音乐抬到 2.8 倍；检查开头 ≈ 人声段 −3dB |
| 渲染完只想改声音 | 不需要重新渲染画面 | `ffmpeg -i 视频 -i 新混音 -map 0:v -map 1:a -c:v copy -c:a aac -b:a 320k` |
| 转写结尾出现乱码 | 模型把纯音乐当成了人声 | 检查人声轨对应段落是否静音即可，不是真问题 |
| tts_voice.py 报 CERTIFICATE_VERIFY_FAILED | python.org 安装的 Python 没有根证书 | 用 venv 的 python 运行（装了 certifi，脚本会自动用）；或运行一次 `/Applications/Python 3.x/Install Certificates.command` |
| tts_voice.py 说没有 FISH_API_KEY | 工程不在 `.voice_keys.env` 的下层目录 | 把 `FISH_API_KEY=…` 放进 `~/.config/mihua-video/keys.env`（任何位置的工程都能找到） |
| AI 配音把名字/术语读错 | 模型不认识专有名词 | 在那一行写 `显示 \| 读法`（`audio.md` › 读音）；名字读错也可以试 `--redo` 换一次 |
| AI 配音两句之间没有停顿、像一口气念完 | 一章是一次合成，换行不产生停顿 | 在需要停的地方加 `<pause>`（换话题写多少见 `audio.md` › 节奏），或把那句末尾改成句号/问号 |
| 某一章的样式全乱，别的章正常 | 两章引用同一个生成出来的 partial，里面的 class 是按章生成的，后生成的把前面的覆盖了 | 生成的 partial 按章分目录（`src/partials/snap/<act>/…`），每章只引用自己目录里的 |
| 线条/方块的方向或大小不对 | GSAP 解析 CSS 里写的复合 transform（如 `rotate(90deg) scaleX(0)`）出错 | CSS 里不写复合 transform，初始状态用 `gsap.set(el, { rotation: 90, scaleX: 0 })` |
| lint 报 `gsap_non_transform_motion` | tween 了 top / left | 改成 x / y |
| lint 报 `gsap_css_transform_conflict` | CSS 里写了 `translateX(-50%)`，GSAP 又在动 x | CSS 里去掉 transform，用 `gsap.set(el, { xPercent: -50 })` |
| `hyperframes check` 报版面重叠、对比度 | 真组件叠放、代码行号这类有意的设计也会被标出来 | lint 必须过；check 的列表看一眼再决定（deliver.sh 里 check 只提示、不拦） |
| 某一章的字体变成系统字体 | `@font-face` 只写在别的章里 | 字体声明放进每章都会引入的公共 css |
| 注释里写了 `<!--@@INCLUDE:…@@-->` 示例，build 报找不到文件 | build 会把任何地方的这个标记都当成引用（CSS 注释里也算） | 注释里不要写这个标记的完整形式 |
| DOM 快照里窄框的文字出现省略号（「+86」变「+…」），原页面没有 | 快照里的字比原页面略宽 | 先对照 real.png 确认原页面没有省略号，再给快照里那个元素加 `text-overflow: clip; overflow: visible` |
| 框、标注在它该出现之前就淡淡地挂着（开场第一秒、整章开头都有） | 同一个元素后面还有「闪一下」这类 `fromTo`，起始值不是 0（比如 `{ opacity: 0.25 }`）。fromTo 默认 `immediateRender: true`：一建好就把起始值套上去，最后建的那个说了算，所以从第 0 秒起元素就是 0.25 | 第二个及以后的 fromTo 加 `immediateRender: false`；或者改用 `to`（从当前值往暗闪再回来）。出片前截片头 0.5 秒和每章开头一帧，看有没有提前冒出来的框 |
| 一整段画面在预览里来回拖以后一直不出来（`display` 停在 none） | 「镜头外的段先隐藏」写成 `tl.set(el, {display:"none"}, 0)` 再在同一时刻 `tl.set(el, {display:"block"}, 0)`：同一时刻两个 set，跳着 seek（预览拖动、分段渲染）时后一个记下的起始值是 none，停在隐藏 | 起始状态用时间轴外的 `gsap.set` 定；`tl.set` 只放在大于 0 的时刻，同一时刻同一属性只写一次。在预览里乱序跳几个时刻，用 `getComputedStyle` 查一遍 |
| 4K 出完抽帧才发现：灰签、截图停在字幕区，字幕压在白底截图上看不清（比如开头的灰签被推近推进字幕区；截图推近到 2.6 倍后下半截铺到字幕区） | 换图、合并以后只跑了 `lint` 和 `check`（这两样都不查安全区），各章只放大看了框的那一块、没看整帧，就直接开渲；灰签的淡入还没走完就到了「收走」那一刻，淡入把透明度又拉回 1。出了片才发现，整片要重渲，白白浪费时间 | 出片前（合并、换图、改时间以后都算）在预览里跑一次 `tools/safezone_scan.js`（视口 3840×2160，整片每 0.5 秒 seek，约 10 秒列出压进字幕区 y>950 和顶部 y<110 的可见字和图，已按父层裁切算），逐条看：字、截图停在字幕区的改，甩镜头一闪、压暗小字没碰到字幕文字的可以留。改过的拍子截整帧看，不只放大局部。收走一个元素的时刻要晚于它所有淡入的结束，或者直接把淡入提前 |
| 成片里有一段放成了静帧样张（片头卡、章节卡样子，背后舞台空、字幕藏掉） | 出静帧时在场景里打开了 `const SAMPLE = true` 一类的样张开关，出完没改回 | 样张开关出完图当场改回 false；`deliver.sh` 出整片前会查 `src/scenes/*.html` 里开着的 SAMPLE / PREVIEW / STILL / DEBUG 开关，有就报出文件和行号并停下 |
| 「亮一下」闪完反而停在暗的状态 | `repeat` + `yoyo` 的总趟数是 repeat+1：repeat 是奇数时最后一趟往回走，停在起始值（`fromTo` 从 0.35 起、repeat 3 → 停在 0.35） | 用 `tl.to(el, { opacity: 0.35, repeat: 3, yoyo: true })` 从 1 往暗闪，奇数次 repeat 正好回到 1；或者 fromTo 配偶数 repeat。闪完截一帧确认 |
| 一条线还没画出来，终点已经露出一个小圆点（白心黑圈） | SVG 描线动画用 `stroke-dasharray = 长度`、`stroke-dashoffset = 长度` 藏线，但 `stroke-linecap: round` 的圆头在虚线段交界处照样画出来 | 画之前把整条线 `opacity: 0`，开画那一刻 `tl.set(p, { opacity: 1 })`；或者用默认的平头。截图看线的终点 |
| 录屏里鼠标圆点正好盖住要讲的那个数 / 那个词 | 录屏脚本点到某处（把光标放到「32」后面）以后指针就停在那里，说到这个数时它还挡着 | 录屏清单里点完紧跟一步 `{do:'move'}` 把指针挪开（`park`），重录那一段；剪出来的小块也会带着指针，同样要重裁。看录屏时专门截「点完以后、说到那个词」的那一刻 |
| 改稿后重录，录屏工具报「找不到：…」（比如开发者工具里展开下一层） | 录屏步骤的时间是按口播句子算的（`l31+0.2`）；某句改短以后，后一步的时间可能跑到前一步前面（先展开子节点、父节点还没展开） | 重录前把每段录屏的步骤时间按新时间轴算一遍，看先后顺序有没有反，反了就把步骤挪到下一句或调小偏移 |
| 一个元素念到时看不见（比如「画面上这一串」） | 后出场的整屏图层（开发者工具窗口）在 DOM 里排在它后面，把它盖住了；或者它飞走的时间按录屏打点算、改稿后提前了 | 给要露出的元素加 `z-index`，飞走时间取「打点时间」和「这句念完」里较晚的那个 |
| 改稿重录以后，荧光笔 / 框画在了别的代码行上，或者编辑器已经滚走了它还挂着 | 场景按口播节点（`C.l59+0.7`）画框，可录屏里那一步常常晚 0.5–1 秒（前一步挪指针要 0.6 秒、点开大文件要加载）；新配音句子挨得近，框就抢在滚动到位之前画上；框的停留时长是写死的，录屏已经滚到下一屏了框还在 | 场景里量位置的小工具顺手带两个时间：录屏打点里量到这一行的时刻（画面已到位）和下一次滚动 / 换文件的时刻；框、荧光笔、标注一律不早于前者、在后者前 0.3 秒左右收掉。重录后扫一遍每一屏停了多久（量完位置到下一次滚动不到 1 秒的，改录屏步骤：换文件挪进前面的停顿、能不滚就不滚） |
| 15 分钟以上的 4K 渲到一半报 `FATAL ERROR: Reached heap limit … JavaScript heap out of memory`，退出码 134 | 渲染进程的 Node 堆默认约 4 GB，长片截帧时用量跟着帧数涨（十几分钟的片子渲到一半就会爆）；和成片文件大小无关 | `tools/deliver.sh` 按电脑内存加 `NODE_OPTIONS=--max-old-space-size=…`（内存的一半、最多 12288，见 `tools/render_plan.sh`；只有几分钟的 1080p，窗口里视频多，渲到一半也会爆——和片长无关）；手动跑 render 时自己带上。内存小的电脑还爆，就降分辨率、把片子分成几段出。渲染要从头再来，所以长片一开始就带上 |
| `npx hyperframes …` 报 `404 Not Found - GET …/hyperframes-0.8.x.tgz` | 不带版本号的 npx 会去取 npm 上最新版；新版刚发布、安装包还没就位时就 404 | 一律用工程 `package.json` 里锁定的版本（本机有缓存）：`npx --yes hyperframes@<锁定版本> lint / snapshot / render …`。`tools/deliver.sh` 自动从 package.json 读锁定版本（读不到用 0.8.149）；工程里的 `tools/deliver.sh` 是建工程时复制的，是旧版就从 skill 的 `assets/kit/tools/deliver.sh` 拷一份过去 |
| 镜头推近以后，画布上的字发糊（推之前清楚） | 被镜头缩放的元素（或它的父层）设了 `will-change: transform`，浏览器按原来的大小栅格化，放大后不重绘 | 会被推近的画布、窗口、文字不要写 `will-change` |
| 一个容器连续变形时，新旧文字叠在一起 | 换字和容器变形用了同一段时间 | 旧字先出场、完全离开后新字再进；容器开始变以后新字才进，下次变之前先走 |
| 成片比混音小 1 dB（混音 -10.1 LUFS，成片 -11.1），render 日志有 `[INFO] Audio lowered by 1.0 dB to stay under −1 dBTP` | HyperFrames render 的音频固定 192k AAC、没有码率参数；-10 LUFS 的混音（真峰值 -1.3）压成 192k 后真峰值冒到约 -0.6，渲染器就整条降 1 dB | `tools/deliver.sh` 渲完自动换音轨：`ffmpeg -i 成片.mp4 -i <cfg.mix> -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 320k -movflags +faststart`（-10.1 LUFS / -1.1 dBTP，音画差 0 ms），最后量成片，响度离目标超过 0.5 或真峰值高于 -1 dBTP 就打 ⚠。工程里的 `tools/deliver.sh` 是旧版就从 skill 的 `assets/kit/tools/deliver.sh` 拷过去。不要降低限幅上限再拉回 -10：三成时间被多压 0.5 dB 以上，等于加压缩 |
| 配乐听着「一直是一个频率」 | 配乐是一组 4 小节和弦（约 10 秒）从头循环到尾，钢琴同一种弹法、鼓同一个节拍；十几分钟的片子停顿多，每停一下同一段循环就涌上来 | 用跟着口播走的 `make_music.py`：读 `film.json` 的停顿和 config 的章节，停顿里钢琴接一句、每章换和弦换调（`references/audio.md` › 配乐）。工程里的是旧的循环版就从 skill 的 `assets/kit/tools/make_music.py` 拷过去；换了配音就重跑 |
| snapshot 截出来窗口里的视频是对的，整片 `render` 出来窗口里只剩原片的一角（导航栏那块），像被放大了好几倍 | 场景里的 `<video>` 只写了 `width:100%; aspect-ratio:16/9`、没写高度。snapshot 按 CSS 排版，但 HyperFrames render（0.8.150）整片渲染时视频按素材原尺寸（4K）铺开，小窗口只露出左上角 | 场景里的 `<video>`（和替它停住的定格图）宽高一律写死像素（例 `width:590px; height:332px; object-fit:cover`），或者直接用品牌层 `.win .body > video` 的写法；不要只靠 `aspect-ratio` / 百分比。例子：示例工程 `src/scenes/actD.html` 里 `#d-pw` 的注释。出片前有视频的窗口不能只看 snapshot，要从渲出来的 mp4 里抽帧对（`python3 tools/module.py <章>` + `SAMPLE=1 sh tools/deliver.sh` 只渲那一章就够） |
| 单章预览 `SAMPLE=1 sh tools/deliver.sh video.config.<章>.json …` 在混音这步报错退出（`adelay` 参数不对 / `KeyError: 'actA'`） | 旧版的 `module.py` / `mix.py`：单章从原片中间开始，`voice_offset` 变成负数（从 177.48 秒开始 → `adelay=-173480`），ffmpeg 的 adelay 不收负数；单章配置还原样带着整片的 `rides`，引用了这一章里没有的 actA / actE | `mix.py` 遇到负偏移先 `atrim` 掉配音开头再对齐；`module.py` 只留这一章的 rides，跨出去的一头裁到章边（`<章>.start` / `<章>.end`，比如整片「配乐降 4 dB」变成这一章从头到尾），整段在别的章的丢掉。工程里的是旧版就从 skill 的 `assets/kit/tools/module.py`、`mix.py` 拷过去。单章预览会把 build 换成这一章：预览完要 `RES=1080 CONFIG=video.config.json node tools/build.mjs`（出 4K 前用默认 RES）恢复整片构建 |
