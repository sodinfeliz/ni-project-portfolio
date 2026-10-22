#!/usr/bin/env python3
"""把專案 raw/ 裡的 .docx 和 .xlsx 轉成純文字，讓 Claude Code 讀得到。

Claude Code 可以直接讀 .pdf、.csv、.html，但 .docx 和 .xlsx 是壓縮過的
XML。這支程式把它們轉成 raw/_extracted/<原檔名>.txt。輸出仍在 raw/ 底下，
一樣是敏感資料（設計文件 §4、§7a）。只用 Python 標準函式庫。

用法：python3 tools/extract.py projects/<專案名>
"""

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _text(element, tag):
    return "".join(t.text or "" for t in element.iter(tag))


def extract_docx(path):
    """Return the text of a `.docx`: one line per paragraph, tab-separated table rows.

    Only the body's direct children are walked, so a paragraph inside a table
    cell is emitted once, as part of its row. Empty paragraphs are dropped.
    """
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(f"{W}body")
    if body is None:
        raise ValueError("找不到文件內容")
    lines = []
    for child in body:
        if child.tag == f"{W}p":
            text = _text(child, f"{W}t")
            if text.strip():
                lines.append(text)
        elif child.tag == f"{W}tbl":
            for row in child.iter(f"{W}tr"):
                cells = [" ".join(_text(p, f"{W}t") for p in tc.iter(f"{W}p")).strip()
                         for tc in row.iter(f"{W}tc")]
                if any(cells):
                    lines.append("\t".join(cells))
    return "\n".join(lines)


def _column_index(ref):
    letters = re.match(r"[A-Z]+", ref or "")
    if not letters:
        return None
    index = 0
    for ch in letters.group():
        index = index * 26 + ord(ch) - 64
    return index - 1


def _sheet_paths(z):
    """Return `(name, member path)` for each sheet, in workbook order."""
    workbook = ET.fromstring(z.read("xl/workbook.xml"))
    targets = {}
    if "xl/_rels/workbook.xml.rels" in z.namelist():
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        for rel in rels.iter(f"{PKG}Relationship"):
            target = rel.get("Target", "").lstrip("/")
            targets[rel.get("Id")] = target if target.startswith("xl/") else "xl/" + target
    sheets = []
    for number, sheet in enumerate(workbook.iter(f"{S}sheet"), 1):
        path = targets.get(sheet.get(f"{R}id"), f"xl/worksheets/sheet{number}.xml")
        sheets.append((sheet.get("name"), path))
    return sheets


def extract_xlsx(path):
    """Return every sheet of an `.xlsx` as `## <name>` followed by tab-separated rows.

    Shared and inline strings are resolved, numbers are kept as written, skipped
    columns become empty cells, and trailing empty cells are dropped.
    """
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = [_text(si, f"{S}t") for si in sst.iter(f"{S}si")]
        lines = []
        for name, member in _sheet_paths(z):
            lines.append(f"## {name}")
            sheet = ET.fromstring(z.read(member))
            for row in sheet.iter(f"{S}row"):
                cells = []
                for c in row.iter(f"{S}c"):
                    index = _column_index(c.get("r"))
                    if index is not None:
                        cells.extend([""] * (index - len(cells)))
                    kind, value = c.get("t"), c.find(f"{S}v")
                    if kind == "s" and value is not None:
                        cells.append(shared[int(value.text)])
                    elif kind == "inlineStr":
                        cells.append(_text(c, f"{S}t"))
                    else:
                        cells.append(value.text if value is not None and value.text else "")
                while cells and not cells[-1]:
                    cells.pop()
                if cells:
                    lines.append("\t".join(cells))
    return "\n".join(lines)


EXTRACTORS = {".docx": extract_docx, ".xlsx": extract_xlsx}


def extract_project(project_dir):
    """Convert each `.docx` / `.xlsx` directly under `raw/` into `raw/_extracted/`.

    A file whose `.txt` is newer than the source is skipped. A file that cannot
    be read (corrupt, encrypted by a sensitivity label, not really Office) is
    reported on stderr as `無法轉換 <name>：<reason>` and the rest still run.
    Returns the paths written; a project without `raw/` returns an empty list.
    """
    raw = Path(project_dir) / "raw"
    if not raw.is_dir():
        return []
    out_dir = raw / "_extracted"
    written = []
    for source in sorted(raw.iterdir()):
        extractor = EXTRACTORS.get(source.suffix.lower())
        if not extractor or not source.is_file():
            continue
        target = out_dir / (source.name + ".txt")
        if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
            continue
        try:
            text = extractor(source)
        except zipfile.BadZipFile:
            print(f"無法轉換 {source.name}：不是有效的 Office 檔案，可能有加密或敏感度標籤。"
                  "請改匯出成 PDF。", file=sys.stderr)
            continue
        except (KeyError, ValueError, IndexError, ET.ParseError) as error:
            print(f"無法轉換 {source.name}：檔案內容不完整（{error}）。請改匯出成 PDF。", file=sys.stderr)
            continue
        out_dir.mkdir(exist_ok=True)
        target.write_text(text, encoding="utf-8")
        written.append(target)
    return written


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("用法：python3 tools/extract.py projects/<專案名>", file=sys.stderr)
        return 2
    written = extract_project(Path(argv[0]))
    for path in written:
        print(path)
    if not written:
        print("沒有需要轉換的檔案")
    return 0


if __name__ == "__main__":
    sys.exit(main())
