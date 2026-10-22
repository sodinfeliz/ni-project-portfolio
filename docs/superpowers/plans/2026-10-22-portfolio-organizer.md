# Portfolio Organizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the folder-based tool that lets Ni turn exported company project files into redacted, interview-ready bilingual summaries, browsed in one offline HTML page.

**Architecture:** Claude Code does all the reading, interviewing and writing, steered by `AGENTS.md`. Two stdlib-only Python scripts do the deterministic parts: `tools/extract.py` turns `.docx`/`.xlsx` exports into text the agent can read, and `build.py` packs every `summary.md` / `summary.en.md` into `data.js`, refusing to build if any original sensitive term leaks through. `portfolio.html` is a fixed file opened over `file://` that loads `data.js` with a `<script>` tag and renders it.

**Tech Stack:** Python 3.9+ standard library only (tests use `unittest`); one self-contained HTML file with inline CSS and vanilla JS; no CDN, no packages.

**Spec:** `docs/design.md` (Traditional Chinese). Section numbers below (§) refer to it.

## Global Constraints

- Python: 3.9+ standard library only, for scripts and tests. No `pip install` anywhere.
- `portfolio.html`: one file, works over `file://`, loads only `data.js` via `<script src="data.js">`; no `fetch`, no external URLs (no CDN, no web fonts; system fonts only).
- `build.py` never opens anything under `raw/` and never reads `context.md` (§9).
- Sensitive files never enter `data.js`: `raw/` (incl. `raw/_extracted/`), `context.md`, `redactions.md` (§7a).
- Inline markers, exact syntax (§8): TODO `[[待補充：…]]` / `[[TODO: …]]`; redacted `{{…}}`.
- Summary headings (§8), zh: `背景與問題`, `我的角色`, `關鍵決策與取捨`, `成果與衡量`, `學到什麼`, `面試追問`; en: `Background & Problem`, `My Role`, `Key Decisions & Trade-offs`, `Results & Measurement`, `Lessons`, `Likely Interview Questions`.
- Frontmatter keys: `title` (required), `period`, `tags` (optional, `[a, b]` list).
- All user-facing copy (README, AGENTS.md prose, page UI) in Traditional Chinese; the page's EN mode switches only content, UI labels may stay Chinese.
- Test command for every Python task: `python3 -m unittest discover -s tests -v`.

## Review Focus

- **Summary without frontmatter or with a malformed line**: build still succeeds; title falls back to the folder name. Test in Task 1.
- **Project folder with only `raw/` or `context.md`**: listed as `pending`, shown greyed out, never crashes the build. Test in Task 1.
- **An original term hiding in the English summary or in the frontmatter `title`**: leak check scans the whole file text of both summaries, not only the body. Test in Task 2.
- **Chinese folder name** (Ni ignores the kebab-case advice): build works, the page's `#hash` round-trips via `encodeURIComponent`. Tests in Task 1 and Task 4.
- **Summary text containing `<`, `&`, or `<script>`**: rendered as text, never as HTML. Check in Task 4.

---

## File Structure

| File | Responsibility |
|---|---|
| `build.py` | Scan `projects/`, parse summaries, leak check, write `data.js` |
| `tools/extract.py` | `.docx` / `.xlsx` in `raw/` to text in `raw/_extracted/` |
| `portfolio.html` | Render `window.PORTFOLIO`: sidebar, reader, 中/EN toggle, markers |
| `tests/test_build.py` | Tests for `build.py` |
| `tests/test_extract.py` | Tests for `tools/extract.py` (fixtures generated in-test with `zipfile`) |
| `tests/fixtures/projects/` | Fictional projects used by tests and by the page check |
| `AGENTS.md`, `CLAUDE.md` | Agent workflow rules; `CLAUDE.md` is one line `@AGENTS.md` |
| `templates/context.md` | Interview field template (§6) |
| `redactions.md` | Not committed (gitignored); README explains how it starts |
| `README.md` | Ni's setup and usage guide (§11) |

---

### Task 1: `build.py` Scans Projects and Writes `data.js`

**Files:**
- Create: `build.py`, `tests/test_build.py`, `tests/__init__.py` (empty)
- Create fixtures: `tests/fixtures/projects/checkout-revamp/summary.md`, `.../summary.en.md`, `tests/fixtures/projects/會員分級/summary.md` (no frontmatter), `tests/fixtures/projects/pending-one/context.md`

**Interfaces:**
- Produces (in `build.py`):
  - `parse_summary(text: str) -> tuple[dict, str]`: frontmatter dict and body. Supports `key: value` and `key: [a, b]`; no `---` block means `({}, text)`; unparseable lines are skipped.
  - `count_todos(text: str) -> int`: number of `[[待補充：` plus `[[TODO:` occurrences.
  - `scan_projects(projects_dir: Path) -> list[dict]`: one dict per subfolder, shape below, ordered by `period` descending (projects without one last), then slug.
  - `write_data_js(projects: list[dict], out: Path, built_at: str) -> None`: writes `window.PORTFOLIO = <json>;` with `ensure_ascii=False`.
  - `main(argv: list[str] | None = None) -> int`: CLI `python3 build.py [--projects DIR] [--out FILE]`, defaults `projects/` and `data.js` beside `build.py`. Prints a summary (project count, TODO count per project, stale EN list). Returns exit code.
- Project dict:
  ```python
  {"slug": str, "status": "ready" | "pending",
   "zh": {"meta": dict, "body": str, "todos": int} | None,
   "en": {"meta": dict, "body": str, "todos": int} | None,
   "enStale": bool}   # True when summary.en.md mtime < summary.md mtime
  ```
  `status` is `"ready"` when `summary.md` exists, else `"pending"`. When `meta` has no `title`, set `meta["title"] = slug`. `built_at` is ISO 8601 with local offset.

- [ ] **Step 1: Write fixtures and failing tests** in `tests/test_build.py`:
  - `test_parse_frontmatter`: `parse_summary("---\ntitle: A\ntags: [x, y]\n---\nbody")` returns `({"title": "A", "tags": ["x", "y"]}, "body")`.
  - `test_parse_without_frontmatter`: returns `({}, text)`.
  - `test_count_todos`: `"[[待補充：a]] [[TODO: b]] [[待補充：c]]"` gives `3`.
  - `test_scan_statuses`: on the fixtures dir, `checkout-revamp` is `ready` with both languages; `pending-one` is `pending` with `zh is None`; `會員分級` has `meta["title"] == "會員分級"`.
  - `test_en_stale`: copy a fixture to a temp dir, `os.utime` the EN file older than ZH, assert `enStale is True`; reversed gives `False`.
  - `test_main_writes_data_js`: run `main(["--projects", fixtures, "--out", tmp/"data.js"])`, assert exit `0`, file starts with `window.PORTFOLIO = `, and the JSON after it contains no text from `context.md` (put the marker string `CONTEXT-ONLY-SECRET` in the fixture's `context.md`).
- [ ] **Step 2: Run tests, expect failure** (`ModuleNotFoundError: build` or missing names).
- [ ] **Step 3: Implement the interfaces above in `build.py`.** Import from tests by adding the repo root to `sys.path` in `tests/__init__.py`.
- [ ] **Step 4: Run tests, expect all pass.**
- [ ] **Step 5: Commit** `feat: build.py packs summaries into data.js`.

### Task 2: Leak Check Against `redactions.md`

**Files:**
- Modify: `build.py`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: `scan_projects`, `main` from Task 1.
- Produces:
  - `load_originals(path: Path) -> list[str]`: first cell of every table row in `redactions.md`, skipping the header row (`原文`) and the `|---|` separator, stripped, empty cells dropped. Missing file returns `[]`.
  - `find_leaks(projects_dir: Path, originals: list[str]) -> list[tuple[Path, int, str]]`: `(file, 1-based line, term)` for every exact, case-sensitive occurrence in the full text (frontmatter included) of each `summary.md` and `summary.en.md`.
  - `main` gains `--redactions FILE` (default `redactions.md` beside `build.py`). When `find_leaks` is non-empty: print each as `<file>:<line>: 發現原文「<term>」`, do **not** write or touch the output file, return `1`.

- [ ] **Step 1: Write failing tests:**
  - `test_load_originals`: table with header, separator and rows `| 國泰人壽 | 某金融客戶 | a client |`, `| 月營收 3,200 萬 | … | … |` gives `["國泰人壽", "月營收 3,200 萬"]`.
  - `test_leak_in_en_title`: temp project whose `summary.en.md` frontmatter is `title: 國泰人壽 app`; `find_leaks` returns one hit on line 2 of that file.
  - `test_main_refuses_on_leak`: an existing `data.js` with content `OLD`; `main` returns `1` and the file still reads `OLD`.
  - `test_no_redactions_file`: missing file means build succeeds.
- [ ] **Step 2: Run tests, expect failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run tests, expect all pass.**
- [ ] **Step 5: Commit** `feat: build.py refuses to build when an original term leaks`.

### Task 3: `tools/extract.py` Turns `.docx` and `.xlsx` into Text

**Files:**
- Create: `tools/extract.py`, `tests/test_extract.py`

**Interfaces:**
- Produces:
  - `extract_docx(path: Path) -> str`: text of `word/document.xml`; each `w:p` becomes one line (its `w:t` runs joined); table rows (`w:tr`) become one line with cells joined by `\t`.
  - `extract_xlsx(path: Path) -> str`: for each sheet in `xl/workbook.xml` order, a line `## <sheet name>` then one line per row, cells joined by `\t`, shared strings resolved from `xl/sharedStrings.xml`, inline strings and numbers as written. Empty trailing cells dropped.
  - `extract_project(project_dir: Path) -> list[Path]`: for every `.docx`/`.xlsx` directly under `project_dir/raw/`, write `raw/_extracted/<original filename>.txt` (UTF-8) unless the `.txt` is newer than the source; return the paths written. Missing `raw/` returns `[]`.
  - CLI: `python3 tools/extract.py projects/<slug>` prints each written path, or `沒有需要轉換的檔案`.

- [ ] **Step 1: Write failing tests.** Build fixtures in-test with `zipfile` writing minimal XML (namespaces `http://schemas.openxmlformats.org/wordprocessingml/2006/main` and `http://schemas.openxmlformats.org/spreadsheetml/2006/main`):
  - `test_docx_paragraphs_and_table`: two paragraphs (`目標`, `提升轉換率` split across two `w:t` runs) and a 1x2 table (`A`, `B`) give `"目標\n提升轉換率\nA\tB"`.
  - `test_xlsx_two_sheets`: sheets `指標` and `時程`, a shared string and a number, with an inline string `2024-06` on sheet `時程`, give `"## 指標\n轉換率\t0.12\n## 時程\n上線\t2024-06"`.
  - `test_extract_project_skips_fresh`: second run returns `[]`.
- [ ] **Step 2: Run tests, expect failure.**
- [ ] **Step 3: Implement with `zipfile` and `xml.etree.ElementTree`.**
- [ ] **Step 4: Run tests, expect all pass.**
- [ ] **Step 5: Commit** `feat: extract.py converts docx and xlsx exports to text`.

### Task 4: `portfolio.html` Renders the Portfolio

**Files:**
- Create: `portfolio.html`
- Modify fixture `tests/fixtures/projects/checkout-revamp/summary.md` so it covers every construct: blockquote, all six headings, a list, a table, bold, italic, inline code, both markers, and the literal text `a < b & <script>alert(1)</script>`.

**Interfaces:**
- Consumes: `window.PORTFOLIO` shape from Task 1 (`builtAt`, `projects[]`).
- Produces (inline `<script>`, plain functions so they can be called from the console):
  - `escapeHtml(s: string): string`
  - `renderMarkdown(md: string): string`: escapes first, then supports headings, paragraphs, `-` lists, `> ` blockquote, pipe tables, `**bold**`, `*italic*`, `` `code` ``, `[[待補充：…]]`/`[[TODO: …]]` as `<mark class="todo">`, `{{…}}` as `<span class="redacted" title="已替換">`.
  - `splitSections(md: string): {lead: string, sections: {title: string, body: string}[]}`: text before the first `## ` is the lead (elevator pitch, shown on top); each `## ` starts a collapsible `<details open>`.

Behaviour (§10):
- Sidebar lists projects in `projects` order: title, period, a badge `缺 N 項` when the current language's `todos > 0`; `pending` items greyed with `尚未生成`. Footer: `更新：<builtAt formatted as YYYY-MM-DD HH:mm>`.
- Reader shows the selected project in the current language. EN missing: `英文版尚未生成`. `enStale`: banner `英文版比中文版舊，請重新生成`.
- Top-right toggle `中 / EN`, default 中; choice saved in `localStorage` key `portfolio.lang`, wrapped in try/catch.
- Selected project in `location.hash` as `encodeURIComponent(slug)`; reload restores it; default is the first `ready` project.
- `window.PORTFOLIO` undefined: whole page shows `找不到 data.js，請先在這個資料夾執行 python3 build.py`.
- Light and dark via `prefers-color-scheme`; readable at 375px wide (sidebar collapses above the reader).

- [ ] **Step 1: Build fixture data**: `python3 build.py --projects tests/fixtures/projects --out data.js`; expect exit `0`.
- [ ] **Step 2: Implement `portfolio.html`.**
- [ ] **Step 3: Verify in the browser pane** by opening `file:///…/ni-project-portfolio/portfolio.html` and running, via the JS console, assertions that:
  - `document.querySelectorAll('nav li').length === 3`;
  - the `<script>alert(1)</script>` text appears in `textContent` and no injected `<script>` element exists inside the reader;
  - `mark.todo` and `span.redacted` exist;
  - navigating to `#%E6%9C%83%E5%93%A1%E5%88%86%E7%B4%9A` selects `會員分級`;
  - clicking EN then reloading keeps EN.

  Also take one screenshot in light, one in dark, and one at 375px.
- [ ] **Step 4: Verify the missing-data state**: rename `data.js` aside, reload, expect the `找不到 data.js` message; restore it.
- [ ] **Step 5: Delete the fixture `data.js`** (it is gitignored, but leave the root clean) **and commit** `feat: portfolio.html renders summaries offline`.

### Task 5: Agent Rules, Templates and README

**Files:**
- Create: `AGENTS.md`, `CLAUDE.md` (exactly `@AGENTS.md`), `templates/context.md`, `README.md`

**Interfaces:**
- Consumes: CLI commands from Tasks 1–3 (`python3 build.py`, `python3 tools/extract.py projects/<slug>`), markers and headings from Global Constraints.

Content requirements:
- `AGENTS.md` (Traditional Chinese), with the no-fabrication rule as the first and highest-priority rule, then:
  - start of every session: run `python3 build.py`;
  - triggers 「整理 `<專案名>`」 and 「更新 `<專案名>`」 running the seven steps of §5 in order, including `tools/extract.py` before reading `raw/`, one question per message, required fields first, accepting 跳過/不記得, confirming `context.md` and the zh summary with Ni before moving on;
  - redaction rules of §7 (ask before keeping anything sensitive, numbers to ranges by default, add new terms to `redactions.md` in all three columns, mark every replacement with `{{…}}`);
  - the exact summary skeleton of §8 in both languages, with 3–5 interview questions (zh: local-company follow-ups; en: "Tell me about a time…" style);
  - what to do when `build.py` reports a leak (fix the summary, rerun);
  - the §7a list of files that must never be copied, shared or committed.
- `templates/context.md`: the six fields of §6, each a `## ` heading, required ones marked `（必填）`.
- `README.md` (Traditional Chinese): the five sections of §11, in that order, including `python3 --version`, `xcode-select --install` / `brew install python`, export formats (PRD to PDF, Sheet to xlsx), export before leaving, how to start a project, open `portfolio.html`, and the safety rules naming `raw/`, `context.md`, `redactions.md` and synced folders. Mention `redactions.md` is created by Claude Code on first use.

- [ ] **Step 1: Write the four files.**
- [ ] **Step 2: Check `AGENTS.md` against §5–§8 and §7a**, listing each requirement and the line that covers it; fix gaps.
- [ ] **Step 3: Dry run**: in a scratch copy of the repo, create `projects/checkout-revamp/raw/prd.txt` with a short fictional PRD (problem, two options A and B, no results), start a fresh Claude Code session there, say 「整理 checkout-revamp」, and confirm it runs the build first, runs extract, summarizes what it read, then asks exactly one question. Stop after the first question; delete the scratch copy.
- [ ] **Step 4: Run the full test suite**, expect all pass.
- [ ] **Step 5: Commit** `docs: agent workflow, context template and README`.
