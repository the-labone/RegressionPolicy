#!/usr/bin/env python3
"""Reflow the paper's gradient SVG panels without redrawing their contents.

Run with Python 3; the generator only uses the standard library.  Each output
embeds the original glyphs, paths, colors and clipping definitions once, then
uses nested SVG viewports to compose a narrow layout.  No plotted values or
text are reconstructed.  Run again after replacing either source SVG.
"""

from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "assets" / "figures"
SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG)
ET.register_namespace("xlink", XLINK)


def element(tag, **attrs):
    return ET.Element(f"{{{SVG}}}{tag}", {key: str(value) for key, value in attrs.items()})


def document(name, width, height, expected_viewbox, title, description):
    source = ET.parse(FIGURES / f"{name}.svg").getroot()
    source_box = tuple(map(float, source.attrib["viewBox"].split()))
    if source_box != expected_viewbox:
        raise ValueError(f"{name}: source geometry changed; review the panel crop bounds")
    root = element("svg", width=width, height=height, viewBox=f"0 0 {width} {height}", role="img")
    root.set("aria-labelledby", f"{name}-mobile-title {name}-mobile-description")
    for tag, suffix, text in [("title", "title", title), ("desc", "description", description)]:
        node = element(tag, id=f"{name}-mobile-{suffix}")
        node.text = text
        root.append(node)
    definitions = element("defs")
    artwork = element("g", id=f"{name}-original-artwork")
    for child in source:
        if child.tag == f"{{{SVG}}}defs":
            definitions.extend(deepcopy(list(child)))
        else:
            artwork.append(deepcopy(child))
    definitions.append(artwork)
    root.append(definitions)
    return root, source_box


def panel(root, name, box, x, y, label):
    """Show an unscaled region of the original artwork at a new position."""
    sx, sy, width, height = box
    viewport = element("svg", x=x, y=y, width=width, height=height,
                       viewBox=f"{sx} {sy} {width} {height}", overflow="hidden")
    viewport.set("data-source-region", label)
    use = element("use")
    use.set(f"{{{XLINK}}}href", f"#{name}-original-artwork")
    viewport.append(use)
    root.append(viewport)


def write(root, name):
    path = FIGURES / f"{name}-mobile.svg"
    # Deterministic serialization preserves all original vector attributes.
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    print(f"{path.relative_to(ROOT)}: {root.get('width')} × {root.get('height')}")


def residual_gradients():
    name = "residual-gradients"
    width, panel_height, gap = 453.6, 212.4, 16
    root, _ = document(
        name, width, 2 * panel_height + gap, (0, 0, 907.2, 212.4),
        "Similar residual tails, different gradient allocation",
        "The original RoboCasa-GR1 and Tool-Hang panels are stacked vertically. "
        "All residual distributions, gradient allocations, axes and legends are unchanged.",
    )
    panel(root, name, (0, 0, width, panel_height), 0, 0, "RoboCasa-GR1")
    # The panel origins differ by slightly more than half the source width.
    # Use their actual offset so both outer borders and plot axes line up.
    second_origin = 456.84375
    panel(root, name, (second_origin, 0, 907.2 - second_origin, panel_height),
          0, panel_height + gap, "Tool-Hang")
    write(root, name)


def gradient_performance():
    name = "gradient-performance"
    width, body_height, row_gap = 267, 142, 18
    root, box = document(
        name, width, 344, (0, 0, 518.224857, 157.425875),
        "More balanced gradients, higher policy success",
        "The original four panels are arranged in two rows: RoboCasa-GR1 and Bridge, "
        "then Fractal and Tool-Hang. Shared y-axis labels are repeated on the second row. "
        "The unchanged residual-percentile label and policy legend appear below both rows.",
    )
    panel(root, name, (0, 0, width, body_height), 0, 0, "RoboCasa-GR1 and Bridge")
    # The source's first/third y-axes are at these x coordinates under this
    # exact source transform.  Align them without stretching either panel.
    axis_delta = (282.670987 - 29.614737) * 0.996366
    lower_x = width - axis_delta
    lower_y = body_height + row_gap
    panel(root, name, (width, 0, box[2] - width, body_height), lower_x, lower_y,
          "Fractal and Tool-Hang")
    # Copy vertical labels and y ticks separately. A full 28-unit strip would
    # paint over the left edge of Fractal's 58% x tick beneath the SR axis.
    panel(root, name, (0, 0, 15, body_height), 0, lower_y, "Repeated shared y-axis labels")
    panel(root, name, (15, 50, 13, 71), 15, lower_y + 50, "Repeated shared y-axis ticks")

    # The footer crops preserve the original outlined glyphs and line keys.
    # Separate viewports prevent the original one-line legend being cut off.
    panel(root, name, (33, 142, 102, 15), (width - 102) / 2, 306,
          "Residual percentile (%)")
    for crop, x, label in [
        ((148, 142, 78, 15), 9, "MSE-Policy"),
        ((240, 142, 79, 15), 96, "Flow-Policy"),
        ((333, 142, 73, 15), 184, "HT-Policy"),
    ]:
        panel(root, name, crop, x, 329, label)
    write(root, name)


if __name__ == "__main__":
    residual_gradients()
    gradient_performance()
