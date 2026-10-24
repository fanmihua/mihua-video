# 示例工程：用 AI 做一支讲解视频（mihua-video）

这是用 mihua-video skill 做的一支完整视频的工程，只当参考。做任何事之前先读 skill：资料里的 `../../mihua-video/SKILL.md`（装好以后也在 ~/.claude/skills 或 ~/.codex/skills 下的 mihua-video/）。这个示例怎么看、缺了哪些素材，见 `../README.md`。

- 品牌层（src/theme.css、src/common.js、src/index.html、tools/、cover/brand.css 和 cover.js）不为单支视频改；这支片子自己的东西在 src/scenes/、src/partials/、video.config*.json、script.md、cover/cover_34.html、cover_43.html。
- 场景里所有时间都从口播节点 `C.*` 算：换了配音、重新生成 timing/film.json，画面会跟着走。
- 要 numpy / mlx-whisper 的 Python 工具用 ~/.cache/mihua-video/venv/bin/python 运行。
- 写合成代码时参考 hyperframes-core skill 的规则；命令用 package.json 锁定的版本（npx --yes hyperframes@0.8.150）。
- 用户要做自己的视频时，用 skill 的 `scripts/new_project.sh` 新建工程，不要在这个示例里改字。
- 回复用中文。
