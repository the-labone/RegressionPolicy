#!/usr/bin/env python3
"""Export the original PDF vectors with matching axes and label baselines.

Requires Poppler's pdftocairo. Only presentation coordinates change; the source
PDFs, plotted vertices, tick values, and reported statistics are preserved.
"""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

FIGURES = Path(__file__).resolve().parents[1] / "assets" / "figures"
SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
SOURCE_HASHES = {
    "residual-heavy-tails": "6b31d6790c35f0ea0d865f6bab79edab5d6e7e9c2a0910218b26b96502a16dca",
    "residual-scales": "46cb19eccb2a8d7e5b79beb0430e41ccf2a6ed89b3bc0d81cf9c92ee26633e48",
}


def wrap(node, transform):
    group = ET.Element(f"{{{SVG}}}g", {"transform": transform})
    group.append(deepcopy(node))
    return group


def export(name, folder):
    source = FIGURES / f"{name}.pdf"
    if sha256(source.read_bytes()).hexdigest() != SOURCE_HASHES[name]:
        raise ValueError(f"Recheck alignment coordinates for the updated {source.name}.")
    path = folder / f"{name}.svg"
    subprocess.run([
        "pdftocairo", "-svg", str(source), str(path)
    ], check=True)
    return ET.parse(path).getroot()


def align_heavy_tails(source):
    nodes = list(source)
    # Guard the source structure before applying the measured PDF coordinates.
    assert len(nodes) == 195
    assert nodes[2].get("d", "").startswith("M 70.558594 160.558594")
    assert nodes[184].get("stroke-width") == "2"
    top, bottom = 61.03125, 168.671875
    scale = (bottom - top) / (160.558594 - 47.160156)
    offset = top - scale * 47.160156
    aligned = ET.Element(source.tag, source.attrib)
    aligned.extend(deepcopy(nodes[:2]))

    for index, node in enumerate(nodes[2:184], start=2):
        uses = list(node)
        if uses and all(child.tag == f"{{{SVG}}}use" for child in uses):
            baseline = sum(float(child.get("y", 0)) for child in uses) / len(uses)
            shift = offset + (scale - 1) * baseline
            if index in (72, 163):
                shift = 58.033 - baseline
            elif abs(baseline - 198.244375) < 0.01:
                shift = 206.872 - baseline
            elif abs(baseline - 177.869375) < 0.01:
                shift = 185.981 - baseline
            # Move text without stretching the glyphs.
            transform = f"translate(0 {shift:.8f})"
        else:
            transform = f"matrix(1 0 0 {scale:.8f} 0 {offset:.8f})"
        aligned.append(wrap(node, transform))

    # Give both figures a two-row dataset legend above the panel titles.
    legend_groups = [
        (184, 186, 37.078125, 56, 16.395),
        (186, 188, 156.457031, 218, 16.395),
        (188, 190, 228.882812, 346, 16.395),
        (190, 193, 302.007812, 144, 29.5),
        (193, 195, 395.214844, 280, 29.5),
    ]
    for start, end, old_x, new_x, baseline in legend_groups:
        transform = f"translate({new_x - old_x:.8f} {baseline - 17.54:.8f})"
        for node in nodes[start:end]:
            aligned.append(wrap(node, transform))
    return aligned


with tempfile.TemporaryDirectory() as directory:
    folder = Path(directory)
    for name in ("residual-heavy-tails", "residual-scales"):
        root = export(name, folder)
        assert root.get("viewBox") == "0 0 504 216"
        if name == "residual-heavy-tails":
            root = align_heavy_tails(root)
        root.insert(0, ET.Comment("Web layout derived from the original PDF vectors."))
        ET.ElementTree(root).write(
            FIGURES / f"{name}-aligned.svg", encoding="utf-8", xml_declaration=True
        )
