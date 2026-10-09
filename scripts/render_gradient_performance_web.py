"""Redraw the paper's gradient-allocation comparison for the project page.

The source SVG remains untouched. Ten vertices per policy are recovered by
inverting each original linear axis; source coordinate rounding is retained.
Success rates preserve the original labeled diagnostic values, not averages
from the separate benchmark chart. Run with the existing plotting environment.
"""

from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/figures/gradient-performance.svg"
DATA_PATH = ROOT / "assets/data/gradient-performance-web.json"
OUT = ROOT / "assets/figures"
NS = "{http://www.w3.org/2000/svg}"
COLORS = {"MSE": "#c58b55", "Flow": "#2b679a", "HT": "#089b7a"}
SOURCE_COLORS = {
    "rgb(83.528137%, 36.862183%, 0%)": "MSE",
    "rgb(0%, 44.7052%, 69.802856%)": "Flow",
    "rgb(0%, 61.959839%, 45.097351%)": "HT",
}
DATASETS = [
    ("RoboCasa-GR1", {"MSE": "35.55", "Flow": "42.34", "HT": "50.01"}),
    ("Bridge", {"MSE": "58.51", "Flow": "62.06", "HT": "62.31"}),
    ("Fractal", {"MSE": "60.60", "Flow": "67.83", "HT": "65.25"}),
    ("Tool-Hang", {"MSE": "50.00", "Flow": "92.00", "HT": "90.91"}),
]
INK, MUTED, RULE = "#202b3b", "#72766f", "#e4e7e4"
for weight in ("regular", "semibold"):
    font_manager.fontManager.addfont(ROOT / f"assets/fonts/source-sans-pro-{weight}.ttf")
plt.rcParams.update({
    "font.family": "Source Sans Pro", "text.color": INK,
    "svg.fonttype": "path", "svg.hashsalt": "gradient-performance-web",
    "axes.unicode_minus": False,
})


def points(path):
    return [tuple(map(float, pair)) for pair in re.findall(r"[ML]\s*([-\d.]+)\s+([-\d.]+)", path)]


def extract():
    """Recover every plotted point and retain its source-coordinate provenance."""
    nodes = list(ET.parse(SOURCE).getroot().iter(NS + "path"))
    axes = []
    for node in nodes:
        pts = points(node.get("d", ""))
        if node.get("stroke-width") == "0.75" and len(pts) == 2:
            (x0, y0), (x1, y1) = pts
            if x0 == x1 and y1 > y0:
                axes.append((x0, y0, y1))
    axes.sort()
    assert len(axes) == 4
    records = []
    for (name, success), (xleft, yzero, yforty) in zip(DATASETS, axes):
        horizontal = [points(n.get("d", "")) for n in nodes
                      if n.get("stroke-width") == "0.75"]
        xright = next(p[1][0] for p in horizontal if len(p) == 2
                      and p[0] == (xleft, yzero) and p[1][1] == yzero)
        curves = {}
        for node in nodes:
            pts = points(node.get("d", ""))
            if node.get("stroke-width") != "1.8" or len(pts) != 10:
                continue
            if not xleft < pts[0][0] < xright:
                continue
            method = SOURCE_COLORS[node.get("stroke")]
            recovered_x = [(x - xleft) / (xright - xleft) * 100 for x, _ in pts]
            share = [(y - yzero) / (yforty - yzero) * 40 for _, y in pts]
            assert max(abs(a - b) for a, b in zip(recovered_x, range(5, 100, 10))) < 0.004
            assert abs(sum(share) - 100) < 0.025
            curves[method] = {
                "share_percent": share,
                "source_path_vertices": pts,
                "recovered_percentile_midpoints": recovered_x,
            }
        assert list(curves) == ["MSE", "Flow", "HT"]
        records.append({
            "dataset": name,
            "success_rate_percent": success,
            "source_axis": {"x_left": xleft, "x_right": xright,
                            "y_zero": yzero, "y_forty": yforty},
            "gradient_rms_share": curves,
        })
    return {
        "source_svg": "assets/figures/gradient-performance.svg",
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "provenance": "Linear-axis inversion of the original SVG's ten plotted vertices per curve; precision is limited by original SVG coordinate rounding, not raw measurements.",
        "quantity": "Each action-residual decile's share of summed per-sample parameter-gradient RMS (%)",
        "flow_gradient_regime": "t > 0.5 (low noise)",
        "success_rate_provenance": "Original two-decimal SR labels, assigned by colored markers; Fractal Flow 67.83 / HT 65.25 and Tool-Hang Flow 92.00 / HT 90.91.",
        "percentile_midpoints": list(range(5, 100, 10)),
        "percentile_bins": [[x, x + 10] for x in range(0, 100, 10)],
        "methods": [{"key": key, "label": key + "-Policy", "color": color}
                    for key, color in COLORS.items()],
        "datasets": records,
    }


def font(px, semibold=False):
    return font_manager.FontProperties(
        fname=ROOT / f"assets/fonts/source-sans-pro-{'semibold' if semibold else 'regular'}.ttf",
        size=px * .72,
    )


def annotate_svg(path, data):
    ET.register_namespace("", NS[1:-1])
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    tree = ET.parse(path)
    root = tree.getroot()
    title = ET.Element(NS + "title", id="gradient-performance-web-title")
    title.text = "More balanced gradients, higher policy success"
    description = ET.Element(NS + "desc", id="gradient-performance-web-description")
    description.text = data["quantity"] + ". Success-rate bars use a common 0–100% scale with exact values at right. Ten residual-decile midpoints from 5 to 95; all gradient plots share a 0–40% scale. Flow gradient curves use t > 0.5. " + "; ".join(
        row["dataset"] + " success rates: " + ", ".join(
            method + "-Policy " + value + "%" for method, value in row["success_rate_percent"].items())
        for row in data["datasets"])
    root.insert(0, description)
    root.insert(0, title)
    root.set("role", "img")
    root.set("aria-labelledby", "gradient-performance-web-title gradient-performance-web-description")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")


def render(data, mobile=False, tablet=False):
    # Slim success bars and gradient axes share left/right column edges.
    # Every success bar uses the same 0–100% scale; its exact value stays fixed
    # in the right-aligned value column so near-equal policies never collide.
    width, height = (560, 764) if mobile else (800, 700) if tablet else (1040, 350)
    stacked = mobile or tablet
    fig = plt.figure(figsize=(width / 100, height / 100), dpi=100)
    fig.patch.set_alpha(0)

    def text(x, y, content, px=15, weight=False, color=INK, **kwargs):
        return fig.text(x / width, 1 - y / height, content,
                        fontproperties=font(px, weight), color=color,
                        va="center", **kwargs)

    legend_px = 22 if mobile else 20 if tablet else 16
    legend_y = 20 if mobile else 16
    legend_positions = [66, 247, 429] if mobile else [192, 380, 565] if tablet else [333, 483, 646]
    for x, method in zip(legend_positions, COLORS):
        fig.add_artist(Line2D([(x - 30) / width, (x - 10) / width],
                              [1 - legend_y / height] * 2,
                              transform=fig.transFigure, color=COLORS[method],
                              linewidth=2, marker="o", markevery=[1], markersize=3))
        text(x, legend_y, method + "-Policy", legend_px,
             weight=method == "HT", color=MUTED)

    for index, row in enumerate(data["datasets"]):
        column = index % (2 if stacked else 4)
        rank = index // 2 if stacked else 0
        x0 = (16 + 278 * column) if mobile else (24 + 400 * column) if tablet else (19 + 255 * column)
        y0 = (58 + 346 * rank) if mobile else (51 + 312 * rank) if tablet else 45
        slot = 250 if mobile else 352 if tablet else 235
        plot_x = x0 + (36 if mobile else 35 if tablet else 29)
        plot_w = slot - (42 if mobile else 42 if tablet else 34)
        center = plot_x + plot_w / 2
        text(center, y0, row["dataset"], 24 if mobile else 23 if tablet else 21, True, ha="center")
        text(plot_x, y0 + (26 if mobile else 24 if tablet else 22), "Success rate (%)",
             19 if mobile else 17 if tablet else 13, color=MUTED)

        bar_width = plot_w - (67 if mobile else 59 if tablet else 54)
        for j, (method, value) in enumerate(row["success_rate_percent"].items()):
            bar_y = y0 + (49 + j * 24 if mobile else 43 + j * 21 if tablet else 39 + j * 17)
            bar_start = plot_x / width
            bar_end = (plot_x + bar_width) / width
            line_y = 1 - bar_y / height
            fig.add_artist(Line2D([bar_start, bar_end], [line_y] * 2,
                                  transform=fig.transFigure, color="#e9ece5",
                                  linewidth=3.2 if mobile else 3.0, solid_capstyle="round"))
            fig.add_artist(Line2D([bar_start, (plot_x + bar_width * float(value) / 100) / width],
                                  [line_y] * 2, transform=fig.transFigure, color=COLORS[method],
                                  linewidth=3.2 if mobile else 3.0, solid_capstyle="round"))
            text(plot_x + plot_w, bar_y, value,
                 22 if mobile else 19 if tablet else 15,
                 weight=method == "HT", ha="right",
                 color={"MSE": "#946739", "Flow": "#2b679a", "HT": "#087c67"}[method])

        plot_y = y0 + (146 if mobile else 131 if tablet else 93)
        plot_h = 132 if mobile else 130 if tablet else 155
        ax = fig.add_axes([plot_x / width, 1 - (plot_y + plot_h) / height,
                           plot_w / width, plot_h / height])
        ax.set_facecolor("none")
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 40)
        ax.set_xticks([0, 50, 100] if stacked else [0, 25, 50, 75, 100])
        ax.set_yticks([0, 20, 40] if stacked else [0, 10, 20, 30, 40])
        ax.tick_params(axis="both", length=0, pad=5 if mobile else 4, colors=MUTED)
        for label in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
            label.set_fontproperties(font(23 if mobile else 19 if tablet else 15))
        ax.grid(axis="y", linewidth=.65, color=RULE)
        ax.set_axisbelow(True)
        for side in ("left", "right", "top"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(RULE)
        ax.spines["bottom"].set_linewidth(.8)
        for method, curve in row["gradient_rms_share"].items():
            ax.plot(data["percentile_midpoints"], curve["share_percent"],
                    color=COLORS[method], linewidth=1.9 if mobile else 1.8,
                    marker="o", markersize=3.3 if mobile else 3,
                    markeredgewidth=.5, markeredgecolor="#fdfdfa",
                    zorder=3 if method == "HT" else 2)

    text(width / 2, height - (20 if mobile else 21), "Residual percentile (%)",
         23 if mobile else 20 if tablet else 15, color=MUTED, ha="center")
    if stacked:
        for y in ((181, 527) if mobile else (157, 469)):
            text(width / 2, y, "Gradient RMS share (%)", 19 if mobile else 17,
                 color=MUTED, ha="center")
    else:
        text(9, 215, "Gradient RMS share (%)", 14, color=MUTED,
             ha="center", rotation=90)
    name = "gradient-performance-web" + ("-mobile" if mobile else "-tablet" if tablet else "")
    fig.savefig(OUT / f"{name}.svg", transparent=True,
                metadata={"Date": None, "Creator": "Matplotlib"})
    annotate_svg(OUT / f"{name}.svg", data)
    fig.savefig(Path("/tmp") / f"{name}.png", dpi=150, facecolor="#fdfdfa")
    plt.close(fig)


if __name__ == "__main__":
    data = extract()
    DATA_PATH.write_text(json.dumps(data, indent=2) + "\n")
    render(data)
    render(data, mobile=True)
    render(data, tablet=True)
    print("Rendered gradient performance desktop/mobile/tablet SVGs from 120 exact source vertices.")
