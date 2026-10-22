# Ni 的專案作品集整理器：設計文件

日期：2026-10-22

## 1. 目的

Ni 是 PM，即將離職。她想在離開前把在公司做過的專案整理好，帶走當作品集，並用來準備面試。中文公司和外商她都會面試。

這個工具是一個資料夾。Ni 把每個專案的公司文件放進去，由 Claude Code 依照 `AGENTS.md` 的規則先訪談她，再產出每個專案的面試導向概要（中英各一份）。最後用一個單一 HTML 頁面瀏覽所有專案。

這個頁面主要是 Ni **自己複習**用，不是寄給面試官的作品集網站。

## 2. 目標、非目標與反目標

**目標**
- 每個專案產出一份 PM 面試導向的概要：問題、角色、決策與取捨、成果、反思、可能的追問。
- 概要經過去敏感化，帶出公司也安全。
- 新增專案的流程固定、可重複，Ni 離職後能自己用 Claude Code 維護。
- 中英雙語，預設中文。

**非目標（這一版不做）**
- HTML 內不呼叫任何 AI，也不需要 API key。
- 不串接 Google Docs 或 Sheets 的 API。文件由 Ni 手動匯出。
- 不做練習模式（問答卡）、不架網站、不匯出 PDF。

**反目標（就算功能正常也算失敗）**
- **捏造內容**：資料裡沒有的事實、數字或成果被寫成像真的一樣。面試被追問時會出包，這是最嚴重的失敗。
- **原始資料外洩到輸出**：`raw/` 的內容（未去敏感化的原文、客戶名稱、金額）出現在 `data.js` 或 `portfolio.html` 裡。
- **Ni 自己用不起來**：需要你在場才能新增專案或更新頁面。

## 3. 資料夾結構

```
ni-project-portfolio/
  AGENTS.md                 Claude Code 的工作規則（訪談、生成、去敏感化、build）
  CLAUDE.md                 只有一行 `@AGENTS.md`，讓 Claude Code 會載入 AGENTS.md
  README.md                 給 Ni 的 setup 與使用說明
  redactions.md             敏感詞對照表（中英代稱）
  templates/
    context.md              context.md 的欄位模板
  projects/
    <專案名>/
      raw/                  公司文件匯出（只放本機，永遠不進輸出）
      context.md            訪談整理結果
      summary.md            中文概要（output）
      summary.en.md         英文概要（output）
  build.py                  掃描 projects/，產生 data.js
  tools/extract.py          把 raw/ 的 .docx/.xlsx 轉成純文字（只用標準函式庫）
  .gitignore                排除 projects/（_example 除外）、redactions.md、data.js
  data.js                   build 產物，portfolio.html 用 <script> 載入
  portfolio.html            固定的單一頁面
  docs/design.md            本文件
```

`<專案名>` 是資料夾名稱，用英文 kebab-case（例如 `member-tier-revamp`）。顯示名稱則來自 summary 的 frontmatter。

`CLAUDE.md` 是我的決定：Claude Code 預設讀的是 `CLAUDE.md`，不會自動讀 `AGENTS.md`。

## 4. 輸入：`raw/`

Ni 把公司文件匯出後放進 `raw/`：
- Google Doc 的 PRD：建議匯出成 `.pdf`（Claude Code 可以直接讀）。
- Google Sheet：建議匯出成 `.xlsx`，因為它保留所有分頁；匯出成 `.csv` 只會帶走目前那一頁。
- 專案相關的 `.html` 檔。

Claude Code 可以直接讀 `.pdf`、`.csv`、`.html`，但讀不了 `.docx` 和 `.xlsx`（它們是壓縮過的 XML）。所以附一個 `tools/extract.py`，只用標準函式庫（`zipfile`、`xml`），把 `raw/` 裡的 `.docx` 和 `.xlsx` 轉成純文字，輸出到 `raw/_extracted/`。AGENTS.md 規定讀取 `raw/` 之前先跑它。`raw/_extracted/` 屬於 `raw/`，一樣是敏感資料。

README 要提醒 Ni：離職後就會失去公司帳號，所以要在離職前完成匯出。

## 5. 流程：整理一個專案

觸發方式是 Ni 在 Claude Code 裡說「整理 `<專案名>`」之類的話。AGENTS.md 要定義這個觸發，以及以下步驟：

1. **檢查輸入**：如果 `raw/` 是空的，就停下來，告訴 Ni 要放什麼。
2. **讀完 `raw/`**：先在對話中簡短說明讀到什麼（專案大意、文件清單）。
3. **訪談**：一次只問一題。
   - 只問文件裡沒有的事。問法要帶上文件的上下文，例如「PRD 規劃了 A、B 兩案，最後上線的是哪個？為什麼？」
   - 必填欄位先問，選填欄位後問。
   - Ni 可以回「跳過」或「不記得」，這時該欄位標記為待補充，不追問到底。
   - 遇到看起來敏感的詞（客戶名、金額、內部代號、未公開計畫），先問 Ni 要怎麼代稱，並把答案加進 `redactions.md`（中英都要）。
4. **寫入 `context.md`**：照 `templates/context.md` 的欄位整理回答，先給 Ni 看過、確認後再存檔。
5. **生成 `summary.md`（中文）**：來源只有 `raw/` 和 `context.md`，並套用 `redactions.md`。Ni 確認之後才進下一步。
6. **生成 `summary.en.md`**：從確認後的中文版產生，改寫成英文面試的講法，不逐字翻譯。
7. **跑 `python3 build.py`**，並回報結果。

**更新既有專案**：Ni 說「更新 `<專案名>`」或手動改了 summary 之後，Claude Code 只重做受影響的步驟。例如中文版改了，就重新產生英文版並 build。

**每次開始工作時**，Claude Code 都先跑一次 `build.py`。這樣就算 Ni 手動改過檔案，`data.js` 也會是最新的。

## 6. `context.md` 欄位

模板放在 `templates/context.md`。

| 欄位 | 必填 | 內容 |
|---|---|---|
| 我的角色 | 是 | 負責什麼、跟誰合作、團隊大小 |
| 最後結果 | 是 | 有沒有上線、成效、用什麼指標衡量；沒有數字時寫定性結果 |
| 最難的一個決策 | 是 | 當時的選項、最後選了哪個、為什麼 |
| 專案時間 | 否 | 起訖時間，粗略即可（例如 2024 Q2–Q4） |
| 如果重來 | 否 | 會怎麼做不一樣 |
| 想強調的點 | 否 | 面試時特別想講的部分 |

缺少必填欄位時仍然可以生成概要，但缺漏處要標成待補充（見 §8），側欄也會顯示這個專案缺幾項。

## 7. 去敏感化：`redactions.md`

格式是一張 Markdown 表格。Claude Code 用它做替換，`build.py` 用它的「原文」欄做外洩檢查：

```markdown
| 原文 | 中文代稱 | English |
|---|---|---|
| 國泰人壽 | 某金融客戶 | a financial-services client |
| 月營收 3,200 萬 | 月營收數千萬等級 | monthly revenue in the tens of millions (TWD) |
```

規則：
- 在 summary 裡，每個被替換的詞都用 §8 的記號標出來。
- 具體數字預設改寫成比例、區間或數量級，除非 Ni 明確說可以保留。
- 表格以外看起來敏感的內容，Claude Code 要先問 Ni，不可以自行判斷保留。

**`build.py` 做機械式的外洩檢查**：除了 Claude Code 會套用這張表，`build.py` 也會讀表格的「原文」欄。只要任何 summary 出現其中一個字串，就拒絕產生 `data.js`，並印出是哪個檔案、哪一行。這是第二道防線，因為 LLM 套用替換可能會漏。

## 7a. 哪些檔案是敏感的

以下內容都視為和 `raw/` 一樣敏感，只能留在 Ni 的電腦，不分享、不同步：
- `raw/`（包含 `raw/_extracted/`）；
- `context.md`：存的是訪談原話，**不做去敏感化**，因為它是 Ni 自己的筆記，也是 summary 的來源；
- `redactions.md`：本身就是一份原文清單。

可以帶出去或分享的只有 `summary.md`、`summary.en.md`、`data.js`、`portfolio.html`。

工具附 `.gitignore`，排除整個 `projects/`（只保留虛構的 `_example`）和 `redactions.md`。summary 雖然可以分享，也不進 git（2026-10-22 決定）：這個 repo 只放工具，Ni 的內容屬於她自己，由她自行備份；這也避免沒被列進 `redactions.md` 的敏感詞永久留在 git 歷史裡。README 也要提醒她：不要把這個資料夾放在 iCloud Drive（包括已同步的「桌面」和「文件」）、Dropbox、Google Drive 這類同步資料夾裡，否則 `raw/` 一樣會離開電腦。

## 8. Output 格式：`summary.md` / `summary.en.md`

兩份檔案結構相同，語言不同。

```markdown
---
title: 會員分級改版
period: 2024 Q2–Q4
tags: [成長, 數據]
---

> 電梯簡報：兩三句話講完這個專案。

## 背景與問題
## 我的角色
## 關鍵決策與取捨
## 成果與衡量
## 學到什麼
## 面試追問
```

- `title` 必填；`period` 和 `tags` 選填。
- 英文版的段落標題用 `Background & Problem`、`My Role`、`Key Decisions & Trade-offs`、`Results & Measurement`、`Lessons`、`Likely Interview Questions`。
- **面試追問**：三到五題，每題附回答重點。中文版的問法偏台灣公司常見的追問，英文版偏外商常見的問法（例如 "Tell me about a time…"）。

**行內記號**（這兩種語法是我的決定）：
- **待補充**：`[[待補充：最後的轉換率]]`，英文版寫成 `[[TODO: final conversion rate]]`。
- **已替換**：`{{某金融客戶}}`，英文版寫成 `{{a financial-services client}}`。

**不可捏造**：資料中找不到的事實、數字和成果一律標成待補充。這條要在 AGENTS.md 裡寫成最高優先的規則。

## 9. `build.py`

- 只用 Python 3.9 以上的標準函式庫，不裝任何套件。
- 掃描 `projects/*/`，讀取 `summary.md` 和 `summary.en.md`，解析 frontmatter 和內文。
- 產生 `data.js`，內容是 `window.PORTFOLIO = {...}`，包含：
  - build 時間；
  - 每個專案的 `slug`、`zh` 與 `en`（各自的 frontmatter 和 Markdown 原文，沒有該檔就是 `null`）；
  - 待補充記號的數量；
  - `enStale` 旗標：`summary.en.md` 比 `summary.md` 舊時為 true。
- 只有 `raw/` 和 `context.md`、沒有 `summary.md` 的專案也要列出，標成「尚未生成」。
- **絕不讀取 `raw/` 和 `context.md`。** `data.js` 只能包含 summary 的內容。
- 會讀 `redactions.md` 的「原文」欄，做 §7 的外洩檢查；發現原文時拒絕 build。
- 在終端機印出摘要：幾個專案、各專案缺幾項待補充、哪些英文版過期。

## 10. `portfolio.html`

一個固定的單一檔，直接雙擊用 `file://` 開啟。它用 `<script src="data.js">` 載入資料，不用 `fetch`，也不載入任何外部資源（CDN、字型等），以確保離線可用、資料不外流。

**版面 A：側欄清單加閱讀區**
- **左側欄**：專案清單，每項顯示標題和期間。
  - 有待補充的專案，旁邊顯示缺幾項。
  - 尚未生成的專案顯示為灰色。
  - 側欄底部顯示 build 時間。
- **右側閱讀區**：顯示選中專案的概要。
  - 電梯簡報置頂。
  - 每個 `##` 段落都可以收合，預設全部展開。
- **右上角「中 / EN」切換**：預設中文。選擇記在 `localStorage`，用 try/catch 包起來，失敗也不影響使用。
  - 英文版不存在時，顯示「英文版尚未生成」。
  - `enStale` 為 true 時，顯示「英文版比中文版舊，請重新生成」。
- **行內記號的呈現**：
  - 待補充：醒目的標籤樣式。
  - 已替換：淡色底，滑鼠移上去顯示「已替換」。
- **右側欄**（2026-10-22 加入）：螢幕寬度 1180px 以上時，內文右邊有一欄固定的「本頁」段落導覽（標出正在讀的段落）和「待補充」清單（點擊跳到該處並閃一下）；較窄時隱藏。整體視覺（2026-10-22 改版）採只有暗色的簡潔科技風：石墨黑底加淡格線、細線框的段落卡、青綠色重點，待補充用琥珀色虛線標籤，已替換的詞用斜線網底，面試追問排成問答卡。頂列顯示目前專案的路徑。
- **找不到 `data.js` 時**：頁面顯示「請先在這個資料夾跑 `python3 build.py`」。
- **Markdown 渲染**：內嵌一個小型渲染器，支援標題、段落、清單、粗體、斜體、引言、表格、行內程式碼，再加上上述兩種行內記號。完整的 CommonMark 支援不是必要的。
- 選中的專案記在網址的 hash（`#member-tier-revamp`），重新整理後會停在同一個專案。

視覺風格交給 builder 決定，原則是乾淨、適合長時間閱讀。2026-10-22 起只做暗色，不再跟隨系統的亮色模式。

## 11. README.md

寫給 Ni 看的，用繁體中文，步驟要能照著做：
1. **Setup**：
   - 用 `python3 --version` 確認有 Python。
   - 沒有的話，用 `xcode-select --install` 或 `brew install python` 安裝。
   - 確認 Claude Code 可以使用。
2. **匯出公司文件**：Google Doc、Sheet 各要怎麼匯出、放到哪裡。提醒要在離職前完成。
3. **新增一個專案**：建立 `projects/<專案名>/raw/`、放入檔案，再對 Claude Code 說「整理 `<專案名>`」。
4. **看作品集**：雙擊 `portfolio.html`。內容沒更新的話，請 Claude Code 跑一次 build。
5. **安全提醒**：
   - 要分享或備份時，只帶 `portfolio.html` 和 `data.js`，或只帶 summary。不要帶 `raw/`、`context.md`、`redactions.md`。
   - 不要把資料夾放進 iCloud、Dropbox、Google Drive 等同步資料夾（見 §7a）。
   - 公司對帶走文件的規定由 Ni 自己確認。

## 12. 交給 builder 決定的事

- `portfolio.html` 的視覺風格、配色和字型（只能用系統字型）。
- Markdown 渲染器的實作方式。
- `build.py` 解析 frontmatter 的方式（只需支援本文件用到的簡單 YAML 子集）。
- AGENTS.md 的實際措辭，但 §5 到 §8 的規則都必須涵蓋。
- 要不要提供一個示範專案（例如 `projects/example/`，內容是虛構的，用來確認頁面能正常顯示）。

## 13. 我做的決定（請你確認）

- 加一個 `CLAUDE.md`，內容是 `@AGENTS.md`。
- 待補充和已替換的記號語法（§8）。
- 專案資料夾名稱用英文 kebab-case。
- 繁體中文。
- 每次開始工作時，Claude Code 都先跑一次 build。
- PRD 建議匯出 PDF，Sheet 建議匯出 xlsx；`.docx` 和 `.xlsx` 用自帶的 `tools/extract.py` 轉成文字，不裝套件。
- `build.py` 讀 `redactions.md` 做外洩檢查，發現原文就拒絕 build（推翻了原本「build.py 不讀 redactions.md」的說法）。
- `context.md` 和 `redactions.md` 跟 `raw/` 一樣視為敏感；`context.md` 保留原話、不去敏感化。
- 附 `.gitignore`，README 提醒不要放在同步資料夾。

另外修正我先前說過的一點：頁面沒辦法自己發現「`summary.md` 比 `data.js` 新」，因為 `file://` 讀不到檔案的修改時間。所以改由 Claude Code 每次開始工作時先 build 來保證頁面是最新的。頁面上只顯示 build 時間，以及英文版是否過期。
