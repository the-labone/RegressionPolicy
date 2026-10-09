#!/usr/bin/env python3
"""Restyle the published tail/gradient figure without inventing experiment data.

Curve vertices and shaded polygons are recovered directly from the original
SVG. Its calibrated linear/log axes are inverted, including the SVG's affine
transform. Source paths can extend outside the original visible axes; the
same axis limits clip them here. The Gaussian is the published polyline,
not a newly fitted or analytical substitute. Shading denotes tail excess,
not confidence intervals. Source SVG/PDF files are never modified.

Dependencies for rendering: matplotlib, numpy. Extraction alone uses only
the standard library: python scripts/render_residual_gradients_web.py --extract-only
"""

from pathlib import Path
import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/figures/residual-gradients.svg"
DATA = ROOT / "assets/data/residual-gradients-web.json"
FIGURES = ROOT / "assets/figures"
NS = "{http://www.w3.org/2000/svg}"

SOURCE_COLORS = {
    "mse": "rgb(83.528137%, 36.862183%, 0%)",
    "flow": "rgb(0%, 44.7052%, 69.802856%)",
    "flow_low": "rgb(22.3526%, 59.214783%, 79.998779%)",
    "gaussian": "rgb(45.097351%, 47.842407%, 50.979614%)",
}
PALETTE = dict(ink="#202b3b", muted="#72766f", flow="#2b679a", mse="#c58b55",
               gaussian="#929991", rule="#e4e7e4", axis="#b8c0b9", tail="#eee7db")
AFFINE = (0.997183, 0.878873, 211.80169)
TAIL_Y_ONE = 156.398499
TAIL_Y_HUNDREDTH = 110.852231
GRADIENT_Y_ZERO = 43.948927
GRADIENT_Y_FORTY = 157.158453
AXIS_Y_BOTTOM = 42.534788
AXIS_Y_TOP = 157.158453
TAIL_X = [(58.966918, 201.328875, 213.190413),
          (517.105105, 659.467062, 671.328599)]
GRADIENT_X = [(283.047349, 437.270844), (741.181619, 895.405113)]


def vertices(path):
    d = path.get("d", "")
    if set(re.findall(r"[A-Za-z]", d)) - {"M", "L", "Z"}:
        raise ValueError("Expected an original polygon/polyline without Bezier resampling")
    return [list(map(float, p)) for p in re.findall(r"[ML]\s+([-\d.]+)\s+([-\d.]+)", d)]


def tail_point(point, dataset, svg_coordinates=False):
    x, y = point
    if svg_coordinates:
        scale, offset_x, offset_y = AFFINE
        x, y = (x - offset_x) / scale, (offset_y - y) / scale
    x0, x6, _ = TAIL_X[dataset]
    return [(x - x0) * 6 / (x6 - x0),
            10 ** ((y - TAIL_Y_ONE) * 2 / (TAIL_Y_ONE - TAIL_Y_HUNDREDTH))]


def gradient_point(point, dataset):
    x, y = point
    x0, x100 = GRADIENT_X[dataset]
    return [(x - x0) * 100 / (x100 - x0),
            (y - GRADIENT_Y_ZERO) * 40 / (GRADIENT_Y_FORTY - GRADIENT_Y_ZERO)]


def extract():
    source = ET.parse(SOURCE).getroot()
    datasets = [dict(name=name, tails={}, shading={}, gradients={})
                for name in ["RoboCasa-GR1", "Tool-Hang"]]
    reverse = {value: key for key, value in SOURCE_COLORS.items()}
    for child_index, node in enumerate(source):
        if node.tag == NS + "defs":
            continue
        for path in node.iter(NS + "path"):
            is_curve = path.get("stroke-width") in {"2", "1.9", "1.4"} and len(path.get("d", "")) > 100
            is_shade = path.get("fill-opacity") == "0.065"
            if not (is_curve or is_shade):
                continue
            raw = vertices(path)
            dataset = int(raw[0][0] > 450)
            series = reverse[path.get("fill") if is_shade else path.get("stroke")]
            kind = "shading" if is_shade else "gradients" if path.get("stroke-width") == "1.9" else "tails"
            convert = gradient_point if kind == "gradients" else tail_point
            points = [convert(point, dataset, True) if is_shade else convert(point, dataset) for point in raw]
            record = dict(points=points, source_vertices=raw, source_child=child_index,
                          source_path=path.get("d"), source_transform=path.get("transform"),
                          source_clip=node.get("clip-path"))
            if series in datasets[dataset][kind]:
                raise ValueError(f"Duplicate {dataset}/{kind}/{series}")
            datasets[dataset][kind][series] = record
    for dataset in datasets:
        assert set(dataset["tails"]) == {"flow", "mse", "gaussian"}
        assert set(dataset["shading"]) == {"flow", "mse"}
        assert set(dataset["gradients"]) == {"flow", "flow_low", "mse"}
        for line in dataset["gradients"].values():
            assert len(line["points"]) == 10
            assert all(abs(p[0] - (5 + i * 10)) < .002 for i, p in enumerate(line["points"]))
            assert abs(sum(p[1] for p in line["points"]) - 100) < .01
    data = dict(
        source=str(SOURCE.relative_to(ROOT)), source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        precision="Recovered from published SVG vertices; not original raw experiment precision.",
        semantics=dict(tail="Survival probability P(|Z| > |z|); logarithmic y axis.",
                       shading="Published tail-excess regions relative to Gaussian; not confidence intervals.",
                       gradient="Per-decile gradient share (%), ten residual RMS bins.",
                       flow_high_noise="t < 0.5", flow_low_noise="t > 0.5"),
        calibration=dict(affine=list(AFFINE), tail_x=TAIL_X, tail_y_one=TAIL_Y_ONE,
                         tail_y_hundredth=TAIL_Y_HUNDREDTH, gradient_x=GRADIENT_X,
                         gradient_y_zero=GRADIENT_Y_ZERO, gradient_y_forty=GRADIENT_Y_FORTY),
        limits=dict(tail_x=[0, (TAIL_X[0][2] - TAIL_X[0][0]) * 6 / (TAIL_X[0][1] - TAIL_X[0][0])],
                    tail_y=[tail_point([TAIL_X[0][0], AXIS_Y_BOTTOM], 0)[1],
                            tail_point([TAIL_X[0][0], AXIS_Y_TOP], 0)[1]],
                    gradient_x=[0, 100], gradient_y=[-.5, 40]),
        datasets=datasets,
    )
    DATA.write_text(json.dumps(data, indent=2) + "\n")
    return data


def render(data, variant="desktop", preview_dir=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.lines import Line2D
    from matplotlib.patches import Polygon
    import numpy as np

    regular = ROOT / "assets/fonts/source-sans-pro-regular.ttf"
    semibold = ROOT / "assets/fonts/source-sans-pro-semibold.ttf"
    for font in [regular, semibold]:
        font_manager.fontManager.addfont(str(font))
    family = font_manager.FontProperties(fname=str(regular)).get_name()
    matplotlib.rcParams.update({
        "font.family": family, "font.size": 16, "text.color": PALETTE["ink"],
        "axes.labelcolor": PALETTE["muted"], "xtick.color": PALETTE["muted"],
        "ytick.color": PALETTE["muted"], "svg.fonttype": "path", "svg.hashsalt": "residual-gradients-web",
        "path.simplify": False, "path.snap": False,
    })
    mobile = variant == "mobile"
    stacked = variant != "desktop"
    geometry = {
        "desktop": dict(width=1040, height=300, row=0, group_width=552, group_gap=522,
                        x1=56, x2=306, plot_w=198, plot_h=180, top=66,
                        title_y=21, plot_title_y=49,
                        tick=14, label=14.5, legend=13, title=22, plot_title=16, metric=14),
        "tablet": dict(width=800, height=620, row=310, group_width=800, group_gap=0,
                       x1=66, x2=458, plot_w=310, plot_h=170, top=74,
                       title_y=23, plot_title_y=52,
                       tick=17, label=17, legend=15.5, title=23, plot_title=18, metric=17),
        "mobile": dict(width=600, height=754, row=374, group_width=600, group_gap=0,
                       x1=78, x2=358, plot_w=216, plot_h=220, top=75,
                       title_y=23, plot_title_y=53,
                       tick=20, label=21, legend=18, title=27, plot_title=21, metric=20),
    }[variant]
    g = geometry
    width, height = g["width"], g["height"]
    fig = plt.figure(figsize=(width / 72, height / 72), dpi=72, facecolor="none")
    tick_size, label_size, legend_size = g["tick"], g["label"], g["legend"]
    title_font = font_manager.FontProperties(fname=str(semibold), size=g["title"])

    def label(x, y, value, size=16, color="ink", **kwargs):
        return fig.text(x / width, 1 - y / height, value, fontsize=size,
                        color=PALETTE[color], **kwargs)

    def axes(x, y, w, h):
        ax = fig.add_axes([x / width, 1 - (y + h) / height, w / width, h / height], facecolor="none")
        for side in ["top", "right"]:
            ax.spines[side].set_visible(False)
        for side in ["bottom", "left"]:
            ax.spines[side].set_color(PALETTE["axis"])
            ax.spines[side].set_linewidth(.8)
        ax.tick_params(axis="both", labelsize=tick_size, length=0, pad=7)
        ax.minorticks_off()
        ax.grid(axis="y", color=PALETTE["rule"], linewidth=.65, zorder=0)
        ax.set_axisbelow(True)
        return ax

    for index, dataset in enumerate(data["datasets"]):
        base_x, base_y = (0, index * g["row"]) if stacked else (index * g["group_gap"], 0)
        label(base_x + g["group_width"] / 2, base_y + g["title_y"], dataset["name"],
              ha="center", fontproperties=title_font, size=g["title"])
        x1, x2, top, plot_w, plot_h = [g[k] for k in ["x1", "x2", "top", "plot_w", "plot_h"]]
        for x, title in [(x1, "Action residual tails"), (x2, "Gradient allocation")]:
            label(base_x + x + plot_w / 2, base_y + g["plot_title_y"], title, size=g["plot_title"], color="muted", ha="center")
        tail_ax = axes(base_x + x1, base_y + top, plot_w, plot_h)
        tail_ax.set_yscale("log")
        tail_ax.set_xlim(data["limits"]["tail_x"])
        tail_ax.set_ylim(data["limits"]["tail_y"])
        tail_ax.set_xticks([0, 2, 4, 6])
        tail_ax.set_yticks([1, .01, .0001], labels=["1", "10⁻²", "10⁻⁴"])
        tail_ax.minorticks_off()
        for shade in dataset["shading"].values():
            tail_ax.add_patch(Polygon(shade["points"], closed=True, facecolor=PALETTE["tail"],
                                     edgecolor="none", alpha=.32, zorder=1))
        tail_ax.axvline(3, color="#c5c8bd", linewidth=.8, linestyle=(0, (2, 3)), zorder=1)
        for key in ["gaussian", "mse", "flow"]:
            points = np.asarray(dataset["tails"][key]["points"])
            tail_ax.plot(points[:, 0], points[:, 1], color=PALETTE[key],
                         linewidth=2 if key == "gaussian" else 2.8,
                         linestyle=(0, (5, 4)) if key == "gaussian" else "-", zorder=3)
        tail_ax.set_xlabel("Standardized\nresidual |z|" if mobile else "Standardized residual |z|",
                           fontsize=label_size, labelpad=9)
        tail_ax.set_ylabel("Tail P(|Z| > |z|)", fontsize=g["metric"], labelpad=7)
        tail_ax.legend(
            [Line2D([], [], color=PALETTE[k], lw=2.5, ls="--" if k == "gaussian" else "-")
             for k in ["flow", "mse", "gaussian"]],
            ["Flow-Policy", "MSE-Policy", "Gaussian"], loc="upper right", frameon=False,
            fontsize=legend_size, handlelength=1.35, handletextpad=.45,
            borderaxespad=.25, labelspacing=.2, labelcolor=PALETTE["ink"],
        )

        grad_ax = axes(base_x + x2, base_y + top, plot_w, plot_h)
        grad_ax.set_xlim(data["limits"]["gradient_x"])
        grad_ax.set_ylim(data["limits"]["gradient_y"])
        grad_ax.set_xticks([0, 50, 100])
        grad_ax.set_yticks([0, 10, 20, 30, 40])
        gradient_specs = [("flow", "s", "-", "Flow-Policy (t < 0.5)"),
                          ("flow_low", "^", (0, (2.8, 1.6)), "Flow-Policy (t > 0.5)"),
                          ("mse", "o", "-", "MSE-Policy")]
        handles = []
        for key, marker, style, title in gradient_specs:
            color = PALETTE["mse" if key == "mse" else "flow"]
            points = np.asarray(dataset["gradients"][key]["points"])
            line, = grad_ax.plot(points[:, 0], points[:, 1], color=color, lw=2.7,
                                linestyle=style, marker=marker, ms=5 if not mobile else 6,
                                markeredgecolor="#fdfdfa", markeredgewidth=.6, label=title, zorder=3)
            handles.append(line)
        grad_ax.set_xlabel("Residual RMS\npercentile (%)" if mobile else "Residual RMS percentile (%)",
                           fontsize=label_size, labelpad=9)
        grad_ax.set_ylabel("Gradient share (%)", fontsize=g["metric"], labelpad=7)
        grad_ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=legend_size,
                       handlelength=1.35, handletextpad=.45,
                       borderaxespad=.25, labelspacing=.2, labelcolor=PALETTE["ink"])

    suffix = "" if variant == "desktop" else f"-{variant}"
    path = FIGURES / f"residual-gradients-web{suffix}.svg"
    # Check exported labels rather than silently cropping an axis or legend.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    from matplotlib.text import Text
    for item in fig.findobj(match=Text):
        if item.get_visible() and item.get_text():
            bounds = item.get_window_extent(renderer)
            if bounds.x0 < -.1 or bounds.y0 < -.1 or bounds.x1 > width + .1 or bounds.y1 > height + .1:
                raise ValueError(f"{variant}: clipped label {item.get_text()!r}: {bounds}")
    fig.savefig(path, transparent=True, metadata={
        "Date": None, "Creator": "render_residual_gradients_web.py",
        "Title": "Similar residual tails, different gradient allocation",
        "Description": "RoboCasa-GR1 and Tool-Hang: original log-survival curves, Gaussian reference, "
        "tail-excess shading and per-decile gradient shares. Exact vector-source extraction is "
        "documented in assets/data/residual-gradients-web.json. All text uses outlined Source Sans Pro.",
    })
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    if preview_dir:
        preview_dir.mkdir(parents=True, exist_ok=True)
        fig.savefig(preview_dir / f"residual-gradients-web{suffix}.png", dpi=144, facecolor="#fdfdfa")
    plt.close(fig)
    print(path.relative_to(ROOT), f"{width}×{height}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument("--preview-dir", type=Path)
    args = parser.parse_args()
    data = extract()
    if not args.extract_only:
        render(data, preview_dir=args.preview_dir)
        render(data, variant="tablet", preview_dir=args.preview_dir)
        render(data, variant="mobile", preview_dir=args.preview_dir)
