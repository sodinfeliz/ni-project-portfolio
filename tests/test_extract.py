import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import extract  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

DOCUMENT = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="{W}"><w:body>
<w:p><w:r><w:t>目標</w:t></w:r></w:p>
<w:p><w:r><w:t>提升</w:t></w:r><w:r><w:t>轉換率</w:t></w:r></w:p>
<w:tbl><w:tr>
<w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc>
</w:tr></w:tbl>
</w:body></w:document>"""

WORKBOOK = f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="{S}" xmlns:r="{R}"><sheets>
<sheet name="指標" sheetId="1" r:id="rId1"/>
<sheet name="時程" sheetId="2" r:id="rId2"/>
</sheets></workbook>"""

WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="worksheet"/>
<Relationship Id="rId2" Target="worksheets/sheet2.xml" Type="worksheet"/>
</Relationships>"""

SHARED = f"""<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="{S}"><si><t>轉換率</t></si><si><t>上線</t></si></sst>"""

SHEET1 = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="{S}"><sheetData>
<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1"><v>0.12</v></c><c r="C1"/></row>
</sheetData></worksheet>"""

SHEET2 = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="{S}"><sheetData>
<row r="1"><c r="A1" t="s"><v>1</v></c><c r="B1" t="inlineStr"><is><t>2024-06</t></is></c></row>
</sheetData></worksheet>"""


def make_docx(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", DOCUMENT)


def make_xlsx(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", WORKBOOK)
        z.writestr("xl/_rels/workbook.xml.rels", WORKBOOK_RELS)
        z.writestr("xl/sharedStrings.xml", SHARED)
        z.writestr("xl/worksheets/sheet1.xml", SHEET1)
        z.writestr("xl/worksheets/sheet2.xml", SHEET2)


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_docx_paragraphs_and_table(self):
        path = self.tmp / "prd.docx"
        make_docx(path)
        self.assertEqual(extract.extract_docx(path), "目標\n提升轉換率\nA\tB")

    def test_xlsx_two_sheets(self):
        path = self.tmp / "metrics.xlsx"
        make_xlsx(path)
        self.assertEqual(extract.extract_xlsx(path), "## 指標\n轉換率\t0.12\n## 時程\n上線\t2024-06")

    def test_extract_project_writes_then_skips_fresh(self):
        raw = self.tmp / "proj" / "raw"
        raw.mkdir(parents=True)
        make_docx(raw / "prd.docx")
        make_xlsx(raw / "metrics.xlsx")
        (raw / "notes.pdf").write_bytes(b"%PDF")
        written = extract.extract_project(self.tmp / "proj")
        self.assertEqual(sorted(p.name for p in written), ["metrics.xlsx.txt", "prd.docx.txt"])
        self.assertTrue((raw / "_extracted" / "prd.docx.txt").read_text(encoding="utf-8").startswith("目標"))
        self.assertEqual(extract.extract_project(self.tmp / "proj"), [])

    def test_extract_project_redoes_stale(self):
        raw = self.tmp / "proj" / "raw"
        raw.mkdir(parents=True)
        make_docx(raw / "prd.docx")
        extract.extract_project(self.tmp / "proj")
        os.utime(raw / "_extracted" / "prd.docx.txt", (1000, 1000))
        self.assertEqual(len(extract.extract_project(self.tmp / "proj")), 1)

    def test_extract_project_without_raw(self):
        self.assertEqual(extract.extract_project(self.tmp / "empty"), [])


if __name__ == "__main__":
    unittest.main()
