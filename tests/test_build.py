import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "projects"


def run_main(*args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return build.main(list(args))


def read_portfolio(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    prefix = "window.PORTFOLIO = "
    assert text.startswith(prefix), text[:40]
    return json.loads(text[len(prefix):].rstrip().rstrip(";"))


class ParseTests(unittest.TestCase):
    def test_parse_frontmatter(self):
        meta, body = build.parse_summary("---\ntitle: A\ntags: [x, y]\n---\nbody")
        self.assertEqual(meta, {"title": "A", "tags": ["x", "y"]})
        self.assertEqual(body, "body")

    def test_parse_without_frontmatter(self):
        text = "> lead\n\n## 背景與問題\n"
        self.assertEqual(build.parse_summary(text), ({}, text))

    def test_parse_skips_malformed_lines(self):
        meta, _ = build.parse_summary("---\ntitle: A\nnot a pair\n---\nbody")
        self.assertEqual(meta, {"title": "A"})

    def test_count_todos(self):
        self.assertEqual(build.count_todos("[[待補充：a]] [[TODO: b]] [[待補充：c]]"), 3)


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.projects = {p["slug"]: p for p in build.scan_projects(FIXTURES)}

    def test_scan_statuses(self):
        ready = self.projects["checkout-revamp"]
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["zh"]["meta"]["title"], "結帳流程優化")
        self.assertEqual(ready["en"]["meta"]["title"], "Checkout Flow Revamp")
        self.assertEqual(ready["zh"]["todos"], 1)
        pending = self.projects["pending-one"]
        self.assertEqual(pending["status"], "pending")
        self.assertIsNone(pending["zh"])
        self.assertIsNone(pending["en"])

    def test_title_falls_back_to_slug(self):
        self.assertEqual(self.projects["會員分級"]["zh"]["meta"]["title"], "會員分級")

    def test_underscore_folders_skipped(self):
        self.assertNotIn("_skipme", self.projects)

    def test_order_period_desc_then_slug(self):
        slugs = [p["slug"] for p in build.scan_projects(FIXTURES)]
        self.assertEqual(slugs[0], "checkout-revamp")
        self.assertEqual(slugs[1:], sorted(slugs[1:]))


class StaleTests(unittest.TestCase):
    def test_en_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "checkout-revamp"
            shutil.copytree(FIXTURES / "checkout-revamp", dest)
            zh, en = dest / "summary.md", dest / "summary.en.md"
            os.utime(zh, (2000, 2000))
            os.utime(en, (1000, 1000))
            self.assertTrue(build.scan_projects(Path(tmp))[0]["enStale"])
            os.utime(en, (3000, 3000))
            self.assertFalse(build.scan_projects(Path(tmp))[0]["enStale"])


class MainTests(unittest.TestCase):
    def test_main_writes_data_js(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data.js"
            code = run_main("--projects", str(FIXTURES), "--out", str(out),
                            "--redactions", str(Path(tmp) / "none.md"))
            self.assertEqual(code, 0)
            data = read_portfolio(out)
            self.assertIn("builtAt", data)
            self.assertEqual(len(data["projects"]), 3)
            self.assertNotIn("CONTEXT-ONLY-SECRET", out.read_text(encoding="utf-8"))


REDACTIONS = """# 敏感詞對照表

| 原文 | 中文代稱 | English |
|---|---|---|
| 國泰人壽 | 某金融客戶 | a client |
| 月營收 3,200 萬 | 月營收數千萬等級 | revenue in the tens of millions |
|  | 空白列 | blank |
"""


class LeakTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.redactions = self.tmp / "redactions.md"
        self.redactions.write_text(REDACTIONS, encoding="utf-8")
        self.projects = self.tmp / "projects"
        project = self.projects / "leaky"
        project.mkdir(parents=True)
        (project / "summary.md").write_text("---\ntitle: 安全的標題\n---\n內容\n", encoding="utf-8")
        self.en = project / "summary.en.md"
        self.en.write_text("---\ntitle: 國泰人壽 app\n---\nbody\n", encoding="utf-8")

    def test_load_originals(self):
        self.assertEqual(build.load_originals(self.redactions), ["國泰人壽", "月營收 3,200 萬"])

    def test_load_originals_missing_file(self):
        self.assertEqual(build.load_originals(self.tmp / "nope.md"), [])

    def test_leak_in_en_title(self):
        leaks = build.find_leaks(self.projects, ["國泰人壽"])
        self.assertEqual(leaks, [(self.en, 2, "國泰人壽")])

    def test_main_refuses_on_leak(self):
        out = self.tmp / "data.js"
        out.write_text("OLD", encoding="utf-8")
        code = run_main("--projects", str(self.projects), "--out", str(out),
                        "--redactions", str(self.redactions))
        self.assertEqual(code, 1)
        self.assertEqual(out.read_text(encoding="utf-8"), "OLD")

    def test_no_redactions_file(self):
        out = self.tmp / "data.js"
        code = run_main("--projects", str(self.projects), "--out", str(out),
                        "--redactions", str(self.tmp / "nope.md"))
        self.assertEqual(code, 0)
        self.assertTrue(out.read_text(encoding="utf-8").startswith("window.PORTFOLIO"))


class LeakVariantTests(unittest.TestCase):
    """The leak check must survive the ways an original term can be disguised."""

    def leaks(self, text, terms, slug="proj"):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        project = tmp / slug
        project.mkdir()
        (project / "summary.en.md").write_text(text, encoding="utf-8")
        return build.find_leaks(tmp, terms)

    def test_case_insensitive(self):
        self.assertEqual(len(self.leaks("our client CATHAY did", ["Cathay"])), 1)

    def test_wrapped_across_lines_reports_first_line(self):
        hits = self.leaks("intro\n國泰\n人壽 rest", ["國泰人壽"])
        self.assertEqual([(h[1], h[2]) for h in hits], [(2, "國泰人壽")])

    def test_full_width_and_spacing(self):
        self.assertEqual(len(self.leaks("月營收３，２００ 萬", ["月營收 3,200 萬"])), 1)

    def test_markdown_split(self):
        self.assertEqual(len(self.leaks("**國泰**人壽", ["國泰人壽"])), 1)

    def test_decomposed_unicode(self):
        self.assertEqual(len(self.leaks("Cafe\u0301 Corp", ["Café Corp"])), 1)

    def test_folder_name_leak(self):
        hits = self.leaks("clean", ["Cathay"], slug="cathay-crm")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0][0].name, "cathay-crm")
        self.assertEqual(hits[0][1], 0)

    def test_replacement_marker_is_not_a_leak(self):
        self.assertEqual(self.leaks("a {{某金融客戶}} b", ["國泰人壽"]), [])


class RobustnessTests(unittest.TestCase):
    def test_non_utf8_summary_names_file_and_fails(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        project = tmp / "projects" / "big5"
        project.mkdir(parents=True)
        (project / "summary.md").write_bytes("標題".encode("big5"))
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = build.main(["--projects", str(tmp / "projects"), "--out", str(tmp / "d.js"),
                               "--redactions", str(tmp / "none.md")])
        self.assertEqual(code, 1)
        self.assertIn("summary.md", err.getvalue())
        self.assertIn("UTF-8", err.getvalue())

    def test_missing_redactions_is_announced(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            build.main(["--projects", str(FIXTURES), "--out", str(tmp / "d.js"),
                        "--redactions", str(tmp / "none.md")])
        self.assertIn("略過外洩檢查", out.getvalue())


if __name__ == "__main__":
    unittest.main()
