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
import unicodedata
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TODO_RE = re.compile(r"\[\[(?:待補充：|TODO:)")
# Markdown emphasis characters that can split a term without changing what the page shows.
IGNORED_CHARS = set("*`_~")


class BuildError(Exception):
    """A problem Ni can fix herself; `main` prints it and exits with 1."""


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise BuildError(f"{path} 不是 UTF-8 編碼。請用 UTF-8 重新存檔（或請 Claude Code 幫忙轉換）。") from None


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
    meta, body = parse_summary(_read(path))
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
    for line in _read(path).splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cell = line.strip("|").split("|")[0].strip()
        if cell and cell != "原文" and not set(cell) <= set("-: "):
            originals.append(cell)
    return originals


def _fold(text):
    """Fold `text` for leak matching and remember the 1-based line of each kept character.

    Composes Unicode (NFC), maps full-width forms to their plain forms (NFKC),
    ignores case, and drops whitespace and Markdown emphasis characters, so a
    term wrapped across lines, typed full-width, or split by `**` still matches.
    """
    chars, lines, line = [], [], 1
    for ch in unicodedata.normalize("NFC", text):
        if ch == "\n":
            line += 1
            continue
        for c in unicodedata.normalize("NFKC", ch).casefold():
            if not c.isspace() and c not in IGNORED_CHARS:
                chars.append(c)
                lines.append(line)
    return "".join(chars), lines


def find_leaks(projects_dir, originals):
    """Find every original term in the project folder names and summaries.

    Scans each folder's name (reported as line 0, since it reaches the page as
    the slug) and the full text, frontmatter included, of `summary.md` and
    `summary.en.md` in every folder (`_` folders too, so the example cannot
    leak either). Matching uses `_fold`. Returns `(path, line, term)` tuples.
    """
    terms = [(term, _fold(term)[0]) for term in originals]
    terms = [(term, folded) for term, folded in terms if folded]
    leaks = []
    for folder in sorted(Path(projects_dir).iterdir()):
        if not folder.is_dir():
            continue
        folded_name = _fold(folder.name)[0]
        leaks.extend((folder, 0, term) for term, folded in terms if folded in folded_name)
        for name in ("summary.md", "summary.en.md"):
            path = folder / name
            if not path.is_file():
                continue
            text, lines = _fold(_read(path))
            for term, folded in terms:
                seen, start = set(), text.find(folded)
                while start != -1:
                    if lines[start] not in seen:
                        seen.add(lines[start])
                        leaks.append((path, lines[start], term))
                    start = text.find(folded, start + 1)
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
    try:
        return _build(args)
    except BuildError as error:
        print(error, file=sys.stderr)
        return 1


def _build(args):
    if not args.redactions.is_file():
        print(f"找不到 {args.redactions.name}，略過外洩檢查。")
    leaks = find_leaks(args.projects, load_originals(args.redactions))
    if leaks:
        for path, number, term in leaks:
            where = f"資料夾名稱 {path.name}" if number == 0 else f"{path}:{number}"
            print(f"{where}: 發現原文「{term}」", file=sys.stderr)
        print("還有未替換的原文，沒有更新 data.js。請先修正上面的檔案或資料夾名稱再 build。",
              file=sys.stderr)
        return 1
    projects = scan_projects(args.projects)
    write_data_js(projects, args.out, datetime.now().astimezone().isoformat(timespec="seconds"))
    _report(projects)
    print(f"已寫入 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
