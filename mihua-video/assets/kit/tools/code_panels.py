#!/usr/bin/env python3
"""Render excerpts of REAL files (code, markdown, json) into <pre> partials for .code panels.

    python3 tools/code_panels.py tools/code_panels.json

code_panels.json:
  [{"name": "badge-tsx", "file": "/abs/path/badge.tsx", "from": 46, "to": 76},
   {"name": "cap-index", "file": "/abs/path/index.json", "find": "\"name\": \"Badge\"", "before": 1, "count": 24}]
→ src/partials/<name>.html, used in a scene as <!--@@INCLUDE:src/partials/<name>.html@@-->

Line numbers are the file's real ones. Highlight bars (.hl) go at top = 64 + (row − 1) × 23.25 px
inside the panel (row = position within the excerpt), height = rows × 23.25 px.
Never paraphrase or retype code: if the file changes, re-run this script.
"""
import html, json, re, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
out_dir = root / "src/partials"; out_dir.mkdir(parents=True, exist_ok=True)
KW = r"\b(export|function|const|let|return|import|from|interface|extends|type|true|false|null|async|await|def|class)\b"

def colour(s, kind):
    e = html.escape(s)
    if kind == "md":
        if s.lstrip().startswith("#"): return f'<span class="h">{e}</span>'
        if s.lstrip().startswith(">"): return f'<span class="c">{e}</span>'
        return re.sub(r"`([^`]+)`", r'<span class="s">`\1`</span>', e)
    if s.lstrip().startswith(("//", "/*", "*", "#")): return f'<span class="c">{e}</span>'
    # 先把字符串换成占位符，关键字只在字符串以外标；否则会把 <span class="s"> 里的 class 也标掉
    strs = []
    e = re.sub(r"(&#x27;[^&]*?&#x27;|&quot;[^&]*?&quot;)", lambda m: (strs.append(m.group(1)), f"\x00{len(strs) - 1}\x00")[1], e)
    e = re.sub(KW, r'<span class="k">\1</span>', e)
    return re.sub(r"\x00(\d+)\x00", lambda m: f'<span class="s">{strs[int(m.group(1))]}</span>', e)

for spec in json.loads(Path(sys.argv[1]).read_text(encoding="utf8")):
    path = Path(spec["file"]).expanduser()
    src = path.read_text(encoding="utf8").splitlines()
    if "find" in spec:
        hit = next(i for i, l in enumerate(src) if spec["find"] in l) + 1
        a = max(1, hit - spec.get("before", 0)); b = min(len(src), a + spec.get("count", 24) - 1)
    else:
        a, b = spec["from"], spec["to"]
    kind = "md" if path.suffix in (".md", ".markdown") else "code"
    rows = [f'<span class="n">{n}</span>{colour(src[n - 1], kind)}' for n in range(a, b + 1)]
    (out_dir / f"{spec['name']}.html").write_text("<pre>" + "\n".join(rows) + "</pre>", encoding="utf8")
    print(f"{spec['name']}: {path.name} L{a}–{b}  ({b - a + 1} rows)")
