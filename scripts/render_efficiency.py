"""Render whole-model inference efficiency from the paper's RTX 5090 timings.

Requires matplotlib. Run: python scripts/render_efficiency.py
The connecting dots use a common relative-latency axis, while every endpoint
retains its absolute latency. Speedups are derived from the reported values.
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

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "assets/data/efficiency.json").read_text())
PERFORMANCE = json.loads((ROOT / "assets/data/performance.json").read_text())
OUT = ROOT / "assets/figures"
TEXT_SCALE = 1.17
COLORS = {method["key"]: method["color"] for method in PERFORMANCE["methods"]}
for name in ("regular", "semibold"):
    font_manager.fontManager.addfont(ROOT / f"assets/fonts/source-sans-pro-{name}.ttf")
plt.rcParams.update({
    "font.family": "Source Sans Pro",
    "text.color": "#202b3b",
    "svg.fonttype": "path",
    "svg.hashsalt": "ht-policy-efficiency",
    "axes.unicode_minus": False,
})


def font(size, semibold=False):
    weight = "semibold" if semibold else "regular"
    return font_manager.FontProperties(
        fname=ROOT / f"assets/fonts/source-sans-pro-{weight}.ttf", size=size * TEXT_SCALE)


def values(row):
    flow, ht = (Decimal(row["latency_ms"][key]) for key in ("Flow", "HT"))
    assert 0 < ht < flow
    return flow, ht, (flow / ht).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def accessible_svg(path):
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    ns = "{http://www.w3.org/2000/svg}"
    tree = ET.parse(path)
    root = tree.getroot()
    title = ET.Element(ns + "title", {"id": "efficiency-chart-title"})
    title.text = "Whole-model inference latency and HT-Policy speedup"
    description = ET.Element(ns + "desc", {"id": "efficiency-chart-description"})
    lines = ["NVIDIA RTX 5090, batch size 1. Lower latency is better."]
    for row in DATA["models"]:
        flow, ht, speedup = values(row)
        lines.append(f'{row["name"]}: Flow-Policy {flow} ms, HT-Policy {ht} ms; {speedup} times faster.')
    lines.extend([DATA["plot_normalization"], DATA["protocol"]])
    description.text = " ".join(lines)
    root.insert(0, title)
    root.insert(1, description)
    root.set("role", "img")
    root.set("aria-labelledby", "efficiency-chart-title efficiency-chart-description")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")


def render(mobile=False):
    fig = plt.figure(figsize=(4.8, 6.4) if mobile else (12.6, 4.5))
    fig.patch.set_alpha(0)
    # The mobile layout moves model names above each row to preserve label size.
    ax = fig.add_axes([0.08, 0.13, 0.67, 0.71] if mobile else [0.225, 0.20, 0.565, 0.62])
    ax.set_facecolor("none")
    ax.set_xlim(-3, 107)
    ax.set_ylim(-0.45, 2.5)
    ax.set_yticks([])
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.tick_params(axis="x", length=0, pad=10, colors="#72766f", labelsize=11 * TEXT_SCALE)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for x in (0, 25, 50, 75, 100):
        ax.axvline(x, color="#e4e7df", linewidth=0.7, linestyle=(0, (2, 5)), zorder=0)

    label_transform = ax.get_yaxis_transform()
    for i, row in enumerate(DATA["models"]):
        y = 2 - i
        flow, ht, speedup = values(row)
        relative_ht = float(ht / flow * 100)
        ax.plot([relative_ht, 100], [y, y], color="#d4ddd6", linewidth=5,
                solid_capstyle="round", zorder=1)
        ax.scatter([100], [y], s=90, facecolors=COLORS["Flow"], edgecolors="none", zorder=3)
        ax.scatter([relative_ht], [y], s=115, facecolors=COLORS["HT"], edgecolors="none", zorder=4)
        for x, value, key in ((100, flow, "Flow"), (relative_ht, ht, "HT")):
            ax.annotate(f"{value:,.2f} ms", (x, y), xytext=(0, -22),
                        textcoords="offset points", ha="right" if mobile and key == "Flow" else "center", va="top",
                        color=COLORS[key], fontproperties=font(11.5 if mobile else 12, key == "HT"))
        ax.text(0 if mobile else -0.37, y + (0.29 if mobile else 0), row["name"],
                transform=label_transform, va="center", ha="left", fontproperties=font(15, True))
        ax.text(1.18, y + 0.015, f"{speedup}×", transform=label_transform,
                ha="center", va="center", fontproperties=font(20 if mobile else 25, True),
                color=COLORS["HT"])
        ax.text(1.18, y - (0.18 if mobile else 0.30), "faster", transform=label_transform,
                ha="center", va="center", fontproperties=font(11), color="#72766f")

    fig.legend(handles=[Line2D([], [], marker="o", markersize=7.5,
                              linestyle="none", markeredgewidth=0,
                              color=COLORS[key], label=label)
                        for key, label in (("Flow", "Flow-Policy"), ("HT", "HT-Policy (ours)"))],
               loc="upper center", bbox_to_anchor=(0.5, 0.995), ncol=2,
               frameon=False, prop=font(12.5), handlelength=0.7,
               columnspacing=1.4 if mobile else 2.6, handletextpad=0.55)
    axis_caption = "Whole-model latency (% of Flow-Policy)" + ("\nlower is better" if mobile else " · lower is better")
    fig.text(0.5, 0.042 if mobile else 0.045, axis_caption,
             ha="center", va="center", fontproperties=font(11.5), color="#72766f")
    name = "efficiency-mobile" if mobile else "efficiency"
    fig.savefig(OUT / f"{name}.svg", transparent=True,
                metadata={"Date": None, "Creator": "Matplotlib"})
    accessible_svg(OUT / f"{name}.svg")
    if not mobile:
        fig.savefig(OUT / f"{name}.png", dpi=200, facecolor="#fdfdfa")
    plt.close(fig)


if __name__ == "__main__":
    render()
    render(mobile=True)
    print("Rendered efficiency.svg, efficiency-mobile.svg, and efficiency.png")
