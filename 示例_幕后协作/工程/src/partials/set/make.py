#!/usr/bin/env python3
"""把片场母版 master.html 按章生成 set_<章>.html（id 加每章自己的前缀，避免整片拼起来以后 id 撞车）。
改了 master.html 以后跑一次：python3 src/partials/set/make.py"""
from pathlib import Path
here = Path(__file__).resolve().parent
m = here.joinpath("master.html").read_text(encoding="utf8")
# 章 → 前缀（和场景里写的一致）
for act, p in {"actA": "a-s-", "actB": "b-s-", "actC": "c-s-", "actD": "d-s-", "actE": "e-s-", "actF": "f-s-", "actG": "g-s-", "actH": "h-s-", "actO": "o-s-"}.items():
    here.joinpath(f"set_{act}.html").write_text(m.replace("{P}", p), encoding="utf8")
print("ok")
