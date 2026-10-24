#!/usr/bin/env bash
# Install (or update) this skill for every coding agent on this machine.
#
#   bash scripts/install.sh            # after editing the skill, run again to push the changes everywhere
#
# The skill is a plain Agent Skills folder (SKILL.md + references/ + scripts/ + assets/), so the same copy works in:
#   Claude Code → ~/.claude/skills/mihua-video
#   Codex       → ~/.codex/skills/mihua-video
#   Cursor      → reads both folders above (and ~/.cursor/skills, ~/.agents/skills) — nothing extra needed
# 你放 skill 源文件的那个文件夹（就是这个 mihua-video/）是唯一的源头；装到上面几处的副本每次都会被覆盖。
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
for base in "$HOME/.claude/skills" "$HOME/.codex/skills"; do
  mkdir -p "$base"
  [ "$(cd "$base" && pwd)/mihua-video" = "$SKILL" ] && continue
  rsync -a --delete --exclude "__pycache__" --exclude ".DS_Store" "$SKILL/" "$base/mihua-video/"
  echo "✓ $base/mihua-video"
done
echo "  Cursor picks it up from ~/.claude/skills or ~/.codex/skills. Restart open agent sessions to load the new version."
