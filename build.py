#!/usr/bin/env python3
"""把 projects/ 底下每個專案的 summary.md / summary.en.md 打包成 data.js。

portfolio.html 用 <script src="data.js"> 載入結果。這支程式只讀 summary，
永遠不碰 raw/ 和 context.md（設計文件 §9）。只用 Python 標準函式庫。

它也是去敏感化的第二道防線：任何 summary 裡只要還出現 redactions.md
「原文」欄的字串，就拒絕 build，舊的 data.js 保持不動（設計文件 §7）。

用法：python3 build.py [--projects DIR] [--out FILE] [--redactions FILE]
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TODO_RE = re.compile(r"\[\[(?:待補充：|TODO:)")


def parse_summary(text):
    """Split `text` into a frontmatter dict and the body after it.

    Only the simple YAML subset the summaries use is supported: `key: value`
    and `key: [a, b]`. Lines that are not a key-value pair are skipped, and a
    file without a leading `---` block returns `({}, text)` unchanged.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}, text
    meta = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if not sep or not key or " " in key:
            continue
        if value.startswith("[") and value.endswith("]"):
            meta[key] = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key] = value
    return meta, "\n".join(lines[end + 1:]).lstrip("\n")


def count_todos(text):
    """Count the `[[待補充：…]]` and `[[TODO: …]]` markers in `text`."""
    return len(TODO_RE.findall(text))


def _load(path, slug):
    if not path.is_file():
        return None
    meta, body = parse_summary(path.read_text(encoding="utf-8"))
    meta.setdefault("title", slug)
    return {"meta": meta, "body": body, "todos": count_todos(body)}


def scan_projects(projects_dir):
    """Return one dict per project folder under `projects_dir`.

    Folders starting with `_` (such as the bundled `_example`) are skipped.
    A folder without `summary.md` is `pending`. Projects are ordered by
    `period` descending, those without one last, then by slug.
    """
    projects = []
    for folder in sorted(Path(projects_dir).iterdir()):
        if not folder.is_dir() or folder.name.startswith(("_", ".")):
            continue
        zh_path, en_path = folder / "summary.md", folder / "summary.en.md"
        zh, en = _load(zh_path, folder.name), _load(en_path, folder.name)
        projects.append({
            "slug": folder.name,
            "status": "ready" if zh else "pending",
            "zh": zh,
            "en": en,
            "enStale": bool(zh and en and en_path.stat().st_mtime < zh_path.stat().st_mtime),
        })

    def period(p):
        return (p["zh"] or p["en"] or {}).get("meta", {}).get("period", "")

    projects.sort(key=lambda p: p["slug"])
    projects.sort(key=lambda p: (period(p) != "", period(p)), reverse=True)
    return projects


def load_originals(path):
    """Return the first cell of every row in the `redactions.md` table.

    The header row (`原文`) and the `|---|` separator are skipped, as are
    empty cells. A missing file returns an empty list.
    """
    path = Path(path)
    if not path.is_file():
        return []
    originals = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cell = line.strip("|").split("|")[0].strip()
        if cell and cell != "原文" and not set(cell) <= set("-: "):
            originals.append(cell)
    return originals


def find_leaks(projects_dir, originals):
    """Find every exact occurrence of an original term in the summaries.

    Scans the full text, frontmatter included, of `summary.md` and
    `summary.en.md` in every project folder (`_` folders too, so the example
    cannot leak either). Returns `(file, line, term)` with 1-based lines.
    """
    leaks = []
    for folder in sorted(Path(projects_dir).iterdir()):
        for name in ("summary.md", "summary.en.md"):
            path = folder / name
            if not path.is_file():
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                leaks.extend((path, number, term) for term in originals if term in line)
    return leaks


def write_data_js(projects, out, built_at):
    """Write `window.PORTFOLIO = {...};` to `out`."""
    payload = {"builtAt": built_at, "projects": projects}
    out.write_text("window.PORTFOLIO = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n",
                   encoding="utf-8")


def _report(projects):
    print(f"共 {len(projects)} 個專案")
    for p in projects:
        if p["status"] == "pending":
            print(f"  {p['slug']}: 尚未生成")
            continue
        todos = p["zh"]["todos"]
        line = f"  {p['slug']}: " + (f"缺 {todos} 項待補充" if todos else "完整")
        if p["en"] is None:
            line += "，英文版尚未生成"
        elif p["enStale"]:
            line += "，英文版比中文版舊"
        print(line)


def main(argv=None):
    parser = argparse.ArgumentParser(description="把 summary 打包成 data.js")
    parser.add_argument("--projects", type=Path, default=HERE / "projects")
    parser.add_argument("--out", type=Path, default=HERE / "data.js")
    parser.add_argument("--redactions", type=Path, default=HERE / "redactions.md")
    args = parser.parse_args(argv)

    if not args.projects.is_dir():
        print(f"找不到資料夾：{args.projects}", file=sys.stderr)
        return 1
    leaks = find_leaks(args.projects, load_originals(args.redactions))
    if leaks:
        for path, number, term in leaks:
            print(f"{path}:{number}: 發現原文「{term}」", file=sys.stderr)
        print("summary 裡還有未替換的原文，沒有更新 data.js。請先修正上面的檔案再 build。",
              file=sys.stderr)
        return 1
    projects = scan_projects(args.projects)
    write_data_js(projects, args.out, datetime.now().astimezone().isoformat(timespec="seconds"))
    _report(projects)
    print(f"已寫入 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
