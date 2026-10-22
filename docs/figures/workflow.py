"""Workflow diagram for the README: who does each step, and which files stay local.

Concept diagram, no data. Three swim lanes (Ni, Claude Code, `build.py`) run
across six phases; the bottom rows are the files each step writes, coloured by
whether they must stay on Ni's computer (orange) or are safe to share (green).
The steps follow `AGENTS.md` and `docs/design.md` §5.

The palette mirrors the vault's `vault_style.py` (dark, transparent). GitHub's
README can be read in a light theme too, so the script renders a light twin and
the README picks one with `<picture>`.

Run:
    uv run --with matplotlib python docs/figures/workflow.py [preview-dir]
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parents[1] / "images"
PREVIEW = Path(sys.argv[1]) if len(sys.argv) > 1 else None

# Both Heiti weights register under one family name, so bold text points at
# the Medium file directly instead of asking for fontweight="bold".
HEITI = Path("/System/Library/Fonts/STHeiti Light.ttc")
HEITI_BOLD = Path("/System/Library/Fonts/STHeiti Medium.ttc")
REGULAR = font_manager.FontProperties(fname=HEITI) if HEITI.exists() else None
BOLD = font_manager.FontProperties(fname=HEITI_BOLD) if HEITI_BOLD.exists() else None
if HEITI.exists():
    font_manager.fontManager.addfont(str(HEITI))
plt.rcParams["font.family"] = ["Heiti TC", "Arial Unicode MS", "sans-serif"]

THEMES = {
    "dark": dict(fg="#d4d4d4", muted="#8a8a8a", grid="#4a4a4a", panel="#1e1e1e",
                 keep="#4cc38a", reject="#f78c3b", accent="#5aa9f0", badge_ink="#111111"),
    "light": dict(fg="#1f2328", muted="#656d76", grid="#d0d7de", panel="#ffffff",
                  keep="#1a7f52", reject="#c75a12", accent="#2f6fbf", badge_ink="#ffffff"),
}

W, H = 2.25, 1.0                    # step box
DX = 2.7                            # phase spacing
LANES = {"ni": 4.7, "claude": 3.0, "build": 1.3}   # lane centre y
LANE_H = 1.45
FILE_ROWS = (0.2, -0.35)            # file pill centres
PILL_W, PILL_H = 2.0, 0.42
PHASES = ["匯出", "讀取", "訪談", "寫概要", "檢查", "複習"]


def x_of(col):
    return col * DX


def blend(t, color, strength):
    """Blend `color` onto the panel colour, giving an opaque tint."""
    c = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    p = tuple(int(t["panel"][i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(p[k] + (c[k] - p[k]) * strength):02x}" for k in range(3))


def step(ax, t, col, lane, title, body, tint=None):
    x, y = x_of(col), LANES[lane] - H / 2
    face = t["panel"] if tint is None else blend(t, tint, 0.16)
    edge = t["grid"] if tint is None else blend(t, tint, 0.55)
    ax.add_patch(FancyBboxPatch((x, y), W, H, boxstyle="round,pad=0,rounding_size=0.1",
                                fc=face, ec=edge, lw=1.2, zorder=3))
    ax.text(x + W / 2, y + H * 0.66, title, ha="center", va="center", fontsize=10.5,
            fontproperties=BOLD, color=t["fg"] if tint is None else tint, zorder=4)
    ax.text(x + W / 2, y + H * 0.3, body, ha="center", va="center", fontsize=8.2,
            color=t["muted"], zorder=4)


def pill(ax, t, cx, cy, text, local):
    color = t["reject"] if local else t["keep"]
    ax.add_patch(FancyBboxPatch((cx - PILL_W / 2, cy - PILL_H / 2), PILL_W, PILL_H,
                                boxstyle="round,pad=0,rounding_size=0.21",
                                fc=blend(t, color, 0.18), ec=blend(t, color, 0.6), lw=1.1, zorder=3))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=8.6, color=color,
            family="monospace" if "." in text or "/" in text else None, zorder=4)


def arrow(ax, t, p0, p1, label=None, lpos=None, both=False, color=None, rad=0.0, ha="center", backing=None):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="<|-|>" if both else "-|>", mutation_scale=11,
                                 color=color or t["muted"], lw=1.3, shrinkA=2, shrinkB=2,
                                 connectionstyle=f"arc3,rad={rad}", zorder=2))
    if label:
        box = None if backing is None else dict(boxstyle="round,pad=0.25", fc=backing, ec="none")
        ax.text(*lpos, label, ha=ha, va="center", fontsize=8.2, color=color or t["muted"], zorder=4, bbox=box)


def tether(ax, t, x, y_top, y_bottom):
    ax.plot([x, x], [y_bottom, y_top], color=t["grid"], lw=1, ls=(0, (2, 2.5)), zorder=1)


def draw(theme):
    t = THEMES[theme]
    fig, ax = plt.subplots(figsize=(12.6, 6.2))
    ax.set_xlim(-1.75, x_of(5) + W + 0.1)
    ax.set_ylim(-0.75, 6.25)
    ax.axis("off")

    # Lanes: a faint band each, named in the left gutter.
    names = {"ni": "你", "claude": "Claude Code", "build": "build.py"}
    for lane, cy in LANES.items():
        ax.add_patch(FancyBboxPatch((-1.7, cy - LANE_H / 2), x_of(5) + W + 1.75, LANE_H,
                                    boxstyle="round,pad=0,rounding_size=0.14",
                                    fc=blend(t, t["grid"], 0.28), ec="none", zorder=0))
        if lane == "build":
            ax.text(-1.55, cy, names[lane], ha="left", va="center", fontsize=10, fontweight="bold",
                    color=t["fg"], family="monospace")
        else:
            ax.text(-1.55, cy, names[lane], ha="left", va="center", fontsize=10.5,
                    fontproperties=BOLD, color=t["fg"])

    # Phase numbers across the top.
    for i, name in enumerate(PHASES):
        ax.text(x_of(i) + W / 2, 5.85, f"{i + 1}  {name}", ha="center", va="center",
                fontsize=9, color=t["muted"])

    ni, cc, bd = LANES["ni"], LANES["claude"], LANES["build"]
    step(ax, t, 0, "ni", "匯出公司文件", "PRD 和 Sheet", tint=t["accent"])
    step(ax, t, 2, "ni", "回答問題", "一次一題，可跳過", tint=t["accent"])
    step(ax, t, 3, "ni", "確認內容", "訪談整理、中文概要", tint=t["accent"])
    step(ax, t, 5, "ni", "打開作品集", "複習、補齊待補充", tint=t["accent"])
    step(ax, t, 1, "claude", "讀完文件", "先把檔案轉成文字")
    step(ax, t, 2, "claude", "訪談", "只問文件沒寫的事")
    step(ax, t, 3, "claude", "寫概要", "中文確認後寫英文")
    step(ax, t, 4, "build", "外洩檢查", "比對原文清單")

    # Main path.
    band = blend(t, t["grid"], 0.28)
    arrow(ax, t, (x_of(0) + W / 2, ni - H / 2), (x_of(1), cc), "說「整理 <專案>」",
          (x_of(0) + W / 2 + 0.3, (ni + cc) / 2 - 0.02), ha="left", rad=0.25, backing=band)
    arrow(ax, t, (x_of(1) + W, cc), (x_of(2), cc))
    arrow(ax, t, (x_of(2) + W / 2, cc + H / 2), (x_of(2) + W / 2, ni - H / 2), both=True)
    arrow(ax, t, (x_of(2) + W, cc), (x_of(3), cc))
    arrow(ax, t, (x_of(3) + W / 2, cc + H / 2), (x_of(3) + W / 2, ni - H / 2), both=True)
    arrow(ax, t, (x_of(3) + W, cc - 0.25), (x_of(4), bd + 0.25))
    arrow(ax, t, (x_of(4) + W, bd + 0.25), (x_of(5) + W / 2, ni - H / 2), "沒有原文\n更新 data.js",
          (x_of(5) + 0.62, cc - 0.15), color=t["keep"], ha="left")
    # The leak check sends the work back until no original term is left.
    arrow(ax, t, (x_of(4), bd - 0.2), (x_of(3) + W * 0.7, cc - H / 2), "還有原文：修正後重跑",
          (x_of(3) + W * 0.42, bd - 0.42), color=t["reject"], rad=-0.45, ha="center", backing=band)

    # Files each step writes.
    files = [(0, "ni", 0, "raw/", True),
             (2, "claude", 0, "context.md", True),
             (2, "claude", 1, "redactions.md", True),
             (3, "claude", 0, "summary.md", False),
             (3, "claude", 1, "summary.en.md", False),
             (4, "build", 0, "data.js", False)]
    for col, lane, row, name, local in files:
        cx = x_of(col) + W / 2
        if row == 0:
            tether(ax, t, cx, LANES[lane] - H / 2, FILE_ROWS[0] + PILL_H / 2)
        pill(ax, t, cx, FILE_ROWS[row], name, local)

    # Legend for the file colours.
    lx = x_of(5) + 0.05
    for i, (label, local) in enumerate((("只留在本機", True), ("可以分享", False))):
        cy = FILE_ROWS[i]
        color = t["reject"] if local else t["keep"]
        ax.add_patch(FancyBboxPatch((lx, cy - 0.12), 0.38, 0.24, boxstyle="round,pad=0,rounding_size=0.12",
                                    fc=blend(t, color, 0.18), ec=blend(t, color, 0.6), lw=1.1))
        ax.text(lx + 0.52, cy, label, ha="left", va="center", fontsize=8.6, color=t["muted"],
                fontproperties=REGULAR)

    out = OUT / f"workflow-{theme}.png"
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight", transparent=True)
    if PREVIEW is not None:
        PREVIEW.mkdir(parents=True, exist_ok=True)
        fig.savefig(PREVIEW / f"workflow-{theme}.png", dpi=150, bbox_inches="tight", facecolor=t["panel"])
    plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    for name in THEMES:
        draw(name)
