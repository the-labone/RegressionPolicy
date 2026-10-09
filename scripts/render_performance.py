"""Render the website's performance summary from traceable paper results.

Requires matplotlib. Run from any directory:
    python scripts/render_performance.py
The JSON retains the reported means; only labels are rounded to one decimal.
"""
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import json
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.path import Path as PlotPath
from matplotlib.patches import PathPatch

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "assets/data/performance.json").read_text())
OUT = ROOT / "assets/figures"
TEXT_SCALE = 1.17
for filename in ("source-sans-pro-regular.ttf", "source-sans-pro-semibold.ttf"):
    font_manager.fontManager.addfont(ROOT / "assets/fonts" / filename)
REGULAR = font_manager.FontProperties(fname=ROOT / "assets/fonts/source-sans-pro-regular.ttf")
SEMIBOLD = font_manager.FontProperties(fname=ROOT / "assets/fonts/source-sans-pro-semibold.ttf")
plt.rcParams.update({
    "font.family": "Source Sans Pro", "font.size": 11,
    "text.color": "#202b3b", "axes.labelcolor": "#50545b",
    "xtick.color": "#202b3b", "ytick.color": "#69717b",
    "svg.fonttype": "path", "svg.hashsalt": "ht-policy-performance",
    "axes.unicode_minus": False,
})


def value(row, method):
    if "components" in row:
        values = [Decimal(item["values"][method]) for item in row["components"]]
        return sum(values) / len(values)
    return Decimal(row["values"][method])


def label(number, real_world=False):
    precision = Decimal("1") if real_world else Decimal("0.1")
    return str(number.quantize(precision, rounding=ROUND_HALF_UP))


def font(size, semibold=False):
    return font_manager.FontProperties(
        fname=(SEMIBOLD if semibold else REGULAR).get_file(), size=size * TEXT_SCALE)


def rounded_bar(ax, center, height, color):
    """Round only the top corners, keeping the baseline and true height exact."""
    left, right = center - 0.1025, center + 0.1025
    # Convert a small physical radius to data units for both plot layouts.
    radius = 2.6 * ax.figure.dpi / 72
    pixels_x = ax.bbox.width / (ax.get_xlim()[1] - ax.get_xlim()[0])
    pixels_y = ax.bbox.height / (ax.get_ylim()[1] - ax.get_ylim()[0])
    rx, ry = min(radius / pixels_x, 0.07), min(radius / pixels_y, height / 2)
    vertices = [(left, 0), (right, 0), (right, height - ry),
                (right, height), (right - rx, height), (left + rx, height),
                (left, height), (left, height - ry), (left, 0), (left, 0)]
    codes = [PlotPath.MOVETO, PlotPath.LINETO, PlotPath.LINETO,
             PlotPath.CURVE3, PlotPath.CURVE3, PlotPath.LINETO,
             PlotPath.CURVE3, PlotPath.CURVE3, PlotPath.LINETO, PlotPath.CLOSEPOLY]
    ax.add_patch(PathPatch(PlotPath(vertices, codes), facecolor=color,
                          edgecolor="none", zorder=3))


def draw_panel(ax, rows, title, *, mobile=False, real_world=False, inline=False):
    ax.set_facecolor("none")
    ax.set_ylim(0, 116)
    ax.set_xlim(-0.6, len(rows) - 0.4)
    ax.set_yticks([0, 50, 100])
    ax.tick_params(axis="y", length=0, pad=7, labelsize=10 * TEXT_SCALE)
    ax.tick_params(axis="x", length=0, pad=9 if inline else 12)
    ax.grid(axis="y", color="#e6e9e4", linewidth=0.65,
            linestyle=(0, (3, 4)), zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "left", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#d3d9d3")
    ax.spines["bottom"].set_linewidth(0.7)
    ax.set_xticks(range(len(rows)), [row["benchmark"] for row in rows],
                  fontproperties=font(12, True))
    ax.text(0, 1.075, title, transform=ax.transAxes,
            fontproperties=font(17, True), color="#192f50", va="baseline")
    ax.text(1, 1.07, "Success rate (%)", transform=ax.transAxes,
            fontproperties=font(10.5), color="#727970", va="baseline", ha="right")
    for j, method in enumerate(DATA["methods"]):
        positions = [i + (j - 1) * (0.30 if mobile else 0.26) for i in range(len(rows))]
        means = [value(row, method["key"]) for row in rows]
        for x, mean in zip(positions, means):
            rounded_bar(ax, x, float(mean), method["color"])
            ours = method["key"] == "HT"
            ax.text(x, float(mean) + 3.2, label(mean, real_world),
                    ha="center", va="bottom", fontproperties=font(14.5 if mobile else 10.5, ours),
                    color="#087c67" if ours else "#525d68",
                    bbox={"boxstyle": "round,pad=0.16,rounding_size=0.3",
                          "facecolor": "#e8f4ef", "edgecolor": "none"} if ours else None)
    for i, row in enumerate(rows):
        if "model" in row:
            ax.text(i, -0.14 if inline else -0.18, row["model"], transform=ax.get_xaxis_transform(),
                    ha="center", va="top", fontproperties=font(11), color="#69717b")


def accessible_svg(path):
    # Keep the plot self-describing when opened or downloaded separately.
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    ns = "{http://www.w3.org/2000/svg}"
    tree = ET.parse(path)
    root = tree.getroot()
    title = ET.Element(ns + "title", {"id": "performance-title"})
    title.text = "Policy performance in simulation and the real world"
    description = ET.Element(ns + "desc", {"id": "performance-description"})
    parts = []
    for section in ("simulation", "real_world"):
        for row in DATA[section]:
            name = row["benchmark"] + (" / " + row["model"] if "model" in row else "")
            parts.append(name + ": " + ", ".join(
                f'{"Diffusion Policy" if method["key"] == "Flow" and row.get("generative_baseline") == "DP" else method["key"] + "-Policy"} {value(row, method["key"])}%'
                for method in DATA["methods"]))
    description.text = "; ".join(parts) + ". SimplerEnv is the unweighted mean of Bridge and Fractal. LIBERO with pi0.5 is the four-suite average. RoboMimic averages best-checkpoint success over state/image observations and U-Net/Transformer backbones, following the paper teaser."
    root.insert(0, title)
    root.insert(1, description)
    root.set("role", "img")
    root.set("aria-labelledby", "performance-title performance-description")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")


def render(mobile=False, inline=False):
    if mobile:
        fig, axes = plt.subplots(3, 1, figsize=(6.2, 11.6 if inline else 12.1))
        fig.subplots_adjust(left=0.075, right=0.985, bottom=0.052 if inline else 0.05,
                            top=0.95 if inline else 0.925, hspace=0.40 if inline else 0.43)
        draw_panel(axes[0], DATA["simulation"][:3], "Simulation", mobile=True, inline=inline)
        draw_panel(axes[1], DATA["simulation"][3:], "", mobile=True, inline=inline)
        draw_panel(axes[2], DATA["real_world"], "Real World", mobile=True, real_world=True, inline=inline)
    else:
        fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.1 if inline else 4.65),
                                 gridspec_kw={"width_ratios": [5, 3]})
        fig.subplots_adjust(left=0.035, right=0.99, bottom=0.15 if inline else 0.17,
                            top=0.855 if inline else 0.795, wspace=0.16)
        draw_panel(axes[0], DATA["simulation"], "Simulation", inline=inline)
        draw_panel(axes[1], DATA["real_world"], "Real World", real_world=True, inline=inline)
    # Embedded charts share a compact HTML heading/legend row with the subsection.
    # Downloads retain their legend so the figure remains self-contained.
    if not inline:
        legend = fig.legend(handles=[Line2D([], [], marker="o", markersize=8,
                                      linestyle="none", markeredgewidth=0,
                                      color=m["color"], label=m["label"])
                                  for m in DATA["methods"]],
                        loc="upper center", bbox_to_anchor=(0.5, 1),
                        ncol=3, frameon=False, fontsize=12.5 * TEXT_SCALE,
                        handlelength=0.7, handleheight=0.85,
                        columnspacing=1.4 if mobile else 2.6, handletextpad=0.55)
        legend.get_texts()[-1].set_fontproperties(SEMIBOLD)
        legend.get_texts()[-1].set_fontsize(12.5 * TEXT_SCALE)
    name = "performance-mobile" if mobile else "performance"
    if inline:
        name += "-inline"
    fig.savefig(OUT / f"{name}.svg", transparent=True,
                metadata={"Date": None, "Creator": "Matplotlib"})
    accessible_svg(OUT / f"{name}.svg")
    if not mobile and not inline:
        fig.savefig(OUT / "performance.png", dpi=200, facecolor="#fdfdfa")
    plt.close(fig)


def render_tablet_inline():
    """Keep all five simulation benchmarks readable at intermediate widths."""
    fig, axes = plt.subplots(2, 1, figsize=(9.6, 7.4))
    fig.subplots_adjust(left=0.05, right=0.99, bottom=0.075, top=0.925, hspace=0.46)
    draw_panel(axes[0], DATA["simulation"], "Simulation", inline=True)
    draw_panel(axes[1], DATA["real_world"], "Real World", real_world=True, inline=True)
    path = OUT / "performance-tablet-inline.svg"
    fig.savefig(path, transparent=True, metadata={"Date": None, "Creator": "Matplotlib"})
    accessible_svg(path)
    plt.close(fig)


if __name__ == "__main__":
    for group in ("simulation", "real_world"):
        for row in DATA[group]:
            for method in DATA["methods"]:
                assert 0 <= value(row, method["key"]) <= 100
    render()
    render(mobile=True)
    render(inline=True)
    render(mobile=True, inline=True)
    render_tablet_inline()
    print("Rendered standalone and inline desktop/mobile/tablet performance SVGs, and performance.png")
