#!/usr/bin/env bash
# 按这台电脑的配置，定成片最高出多少分辨率。渲染会占满内存和 CPU，配置不够还硬出 4K，电脑会卡死、渲到一半崩掉。
#   sh tools/render_plan.sh            # 单独跑：打印这台电脑的配置和建议
#   deliver.sh 出片前会自己调用它，超过建议的分辨率要加 FORCE=1 才放行
#
# 定的依据（我们只在 36 GB 内存的 M4 Max 上实测过：10 分钟的片子 4K 约 30 分钟，其中编码约 22 分钟）：
#   内存 ≥ 32 GB → 最高 4K（3840×2160）
#   内存 16–31 GB → 最高 2K（2560×1440），4K 没试过、按内存留余量
#   内存 < 16 GB → 只出 1080p（1920×1080）
RAM_GB=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 ))
CHIP=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || uname -m)
if [ "$RAM_GB" -ge 32 ]; then MAXRES=2160; elif [ "$RAM_GB" -ge 16 ]; then MAXRES=1440; else MAXRES=1080; fi
# 渲染进程的内存上限：给到内存的一半、最多 12 GB（长片 4K 默认 4 GB 会爆；给太多，内存小的电脑会被吃满）
HEAP_MB=$(( RAM_GB * 1024 / 2 )); [ "$HEAP_MB" -gt 12288 ] && HEAP_MB=12288; [ "$HEAP_MB" -lt 3072 ] && HEAP_MB=3072
res_name() { case "$1" in 2160) echo "4K";; 1440) echo "2K";; *) echo "1080p";; esac; }
disk_free_gb() { df -k "${1:-.}" 2>/dev/null | awk 'NR==2{print int($4/1048576)}'; }
on_battery() { pmset -g batt 2>/dev/null | grep -q "Battery Power"; }

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  echo "这台电脑：$CHIP · 内存 ${RAM_GB} GB · 硬盘剩 $(disk_free_gb .) GB"
  echo "成片最高建议：$(res_name $MAXRES)；渲染进程内存上限 $HEAP_MB MB"
  [ "$(uname -m)" != "arm64" ] && echo "⚠ 不是 Apple 芯片：转写用不了，渲染也会慢很多"
  on_battery && echo "⚠ 现在用的是电池：渲染前插上电源"
  echo "样片一律 1080p。出成片：sh tools/deliver.sh <config> <名字> <输出文件夹>（按上面的建议自动定分辨率）"
fi
