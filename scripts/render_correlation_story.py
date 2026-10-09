"""Restyle the paper's correlation plot for the residual-story animation.

No experiment values are fabricated or read off a raster image. The eight
marker centers and horizontal confidence intervals are recovered directly
from residual-correlation-web.svg. Linear axes are calibrated from that
file's tick coordinates; resulting values preserve the published figure's
vector precision, rather than claiming unavailable raw experiment precision.
The source PDF remains the full-resolution evidence link.

Run with Python 3; no third-party dependencies are required.
"""
from pathlib import Path
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/figures/residual-correlation-web.svg"
OUTPUT = ROOT / "assets/figures/residual-correlation-story.svg"
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)

PALETTE = {
    "ink": "#303633", "muted": "#72766f", "blue": "#2b679a",
    "green": "#479b82", "sand": "#b88c5e", "rule": "#e4e7e4",
}
# Order is the order of the horizontal intervals in the source figure.
LABELS = ["MSE-Loss", "RMSE", "Huber", "Hetero-Huber", "Hetero-RMSE",
          "HG", "Student-t", "HT-Loss"]
COLORS = ["muted", "blue", "sand", "sand", "blue", "blue", "sand", "green"]
OFFSETS = [(12, 29, "start"), (-12, -16, "end"), (12, 31, "start"),
           (13, 23, "start"), (-11, -19, "end"), (13, 8, "start"),
           (-11, -15, "end"), (13, -16, "start")]


def add(parent, tag, text=None, **attrs):
    node = ET.SubElement(parent, f"{{{NS}}}{tag}", {
        key.replace("_", "-"): str(value) for key, value in attrs.items()
    })
    if text is not None:
        node.text = text
    return node


def rounded(value):
    return f"{value:.4f}".rstrip("0").rstrip(".")


def source_points():
    source = ET.parse(SOURCE).getroot()
    paths = list(source.iter(f"{{{NS}}}path"))
    intervals = [path for path in paths
                 if path.get("fill") == "none" and path.get("stroke-width") == "1.4"]
    markers = [path for path in paths
               if path.get("fill-rule") == "nonzero" and path.get("stroke-width") == "0.65"
               and path.get("stroke") == "rgb(100%, 100%, 100%)"]
    assert len(intervals) == len(markers) == len(LABELS), "Source figure changed"
    # Tick vertices in the untransformed SVG path coordinates. The common
    # affine SVG transform cancels when converting into data coordinates.
    x_value = lambda x: 1 + (x - 72.650182) / (275.151652 - 72.650182)
    y_value = lambda y: 35 + 20 * (y - 48.404226) / (202.468328 - 48.404226)
    points = []
    for label, interval, marker in zip(LABELS, intervals, markers):
        vertices = list(map(float, re.findall(r"-?\d+(?:\.\d+)?", interval.get("d"))))
        assert len(vertices) == 4 and vertices[1] == vertices[3]
        # Both the circle and the HT star start at their center x-coordinate.
        # Unlike the errorbar midpoint, this preserves asymmetric intervals.
        center_x = float(re.search(r"M\s+([-\d.]+)", marker.get("d")).group(1))
        points.append({"label": label, "x": x_value(center_x), "y": y_value(vertices[1]),
                       "lo": x_value(vertices[0]), "hi": x_value(vertices[2])})
    return points


def main():
    points = source_points()
    root = ET.Element(f"{{{NS}}}svg", {
        "viewBox": "0 0 640 472", "width": "640", "height": "472",
        "role": "img", "aria-labelledby": "correlation-story-description",
        "font-family": "Source Sans Pro, Arial, sans-serif",
    })
    add(root, "title", "Residual fit correlates with policy success", id="correlation-story-description")
    add(root, "desc", "Eight training objectives on RoboCasa-GR1. Marker positions and "
        "horizontal confidence intervals are reproduced from the paper figure. "
        "Spearman correlation is 0.86 and Pearson correlation is 0.83. "
        "The dashed line is a linear fit across the eight objectives.")
    add(root, "metadata", "Source: residual-correlation-web.svg; extracted by "
        "scripts/render_correlation_story.py. X: calibrated mean joint log-likelihood "
        "per action dimension (nat/dim). Intervals: 2000 task-stratified episode "
        "bootstrap samples with fitted scale fixed. SVG coordinate precision only.")
    defs = add(root, "defs")
    # The paper's source axes span x=.86..2.14, y=34.5..55.6.
    sx = lambda x: 70 + (x - .86) / 1.28 * 532
    sy = lambda y: 400 - (y - 34.5) / 21.1 * 300
    add(root, "text", "RoboCasa-GR1 · calibrated scale", x=70, y=25,
        fill=PALETTE["muted"], font_size=18)
    add(root, "text", "ρ = 0.86     r = 0.83", x=602, y=25,
        text_anchor="end", fill=PALETTE["muted"], font_size=18)

    # Light rules and direct labels match the task-progress animation.
    for value in [35, 40, 45, 50, 55]:
        y = sy(value)
        add(root, "line", x1=70, x2=602, y1=rounded(y), y2=rounded(y),
            stroke=PALETTE["rule"], stroke_width=1.2)
        add(root, "text", str(value), x=55, y=rounded(y + 6), text_anchor="end",
            fill=PALETTE["muted"], font_size=19)
    for value in [1, 1.25, 1.5, 1.75, 2]:
        add(root, "text", f"{value:.2f}", x=rounded(sx(value)), y=429,
            text_anchor="middle", fill=PALETTE["muted"], font_size=19)
    add(root, "text", "Success rate (%)", x=70, y=75,
        fill=PALETTE["muted"], font_size=20)
    add(root, "text", "Mean log-likelihood", x=336, y=465, text_anchor="middle",
        fill=PALETTE["muted"], font_size=20)

    mean_x = sum(point["x"] for point in points) / len(points)
    mean_y = sum(point["y"] for point in points) / len(points)
    slope = sum((point["x"] - mean_x) * (point["y"] - mean_y) for point in points) / sum(
        (point["x"] - mean_x) ** 2 for point in points)
    left, right = min(p["x"] for p in points), max(p["x"] for p in points)
    clip_x, clip_width = sx(left) - 5, sx(right) - sx(left) + 10
    clip = add(defs, "clipPath", id="correlation-story-trend-reveal", clipPathUnits="userSpaceOnUse")
    add(clip, "rect", x=rounded(clip_x), y=0, width=rounded(clip_width), height=472,
        data_correlation_trend_clip="true", data_full_width=rounded(clip_width))
    trend = add(root, "g", clip_path="url(#correlation-story-trend-reveal)")
    add(trend, "path", d=f"M {rounded(sx(left))} {rounded(sy(mean_y + slope * (left - mean_x)))} "
        f"L {rounded(sx(right))} {rounded(sy(mean_y + slope * (right - mean_x)))}",
        fill="none", stroke=PALETTE["blue"], stroke_width=3.5,
        stroke_dasharray="9 7", stroke_linecap="round", stroke_opacity=.6,
        data_correlation_trend="true")

    for point, color_name, (dx, dy, anchor) in zip(points, COLORS, OFFSETS):
        color = PALETTE[color_name]
        x, y, lo, hi = sx(point["x"]), sy(point["y"]), sx(point["lo"]), sx(point["hi"])
        group = add(root, "g", data_objective=point["label"])
        add(group, "title", f'{point["label"]}: likelihood ≈{point["x"]:.3f}; '
            f'success ≈{point["y"]:.2f}%')
        # Preserve interval endpoints, but avoid caps protruding around the
        # small marker and making its silhouette look polygonal on the page.
        add(group, "path", d=f"M {rounded(lo)} {rounded(y)} H {rounded(hi)}",
            fill="none", stroke=color, stroke_width=1.4, stroke_opacity=.6,
            stroke_linecap="round")
        if point["label"] == "HT-Loss":
            add(group, "circle", cx=rounded(x), cy=rounded(y), r=10,
                fill=color, fill_opacity=.08)
        add(group, "circle", cx=rounded(x), cy=rounded(y), r=5,
            fill=color, stroke="#fdfdfa", stroke_width=1.6,
            paint_order="stroke fill", shape_rendering="geometricPrecision")
        add(group, "text", point["label"], x=rounded(x + dx), y=rounded(y + dy),
            text_anchor=anchor,
            fill="#16846b" if point["label"] == "HT-Loss" else color if point["label"] == "MSE-Loss" else PALETTE["ink"],
            font_size=19, font_weight=600 if point["label"] == "HT-Loss" else 400)

    ET.indent(root, space="  ")
    OUTPUT.write_text(ET.tostring(root, encoding="unicode") + "\n")
    print(f"Rendered {OUTPUT.relative_to(ROOT)} from {len(points)} source-vector markers.")


if __name__ == "__main__":
    main()
