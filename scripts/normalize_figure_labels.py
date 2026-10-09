"""Use the website's loss/policy terminology in the paper's vector figures.

Requires PyMuPDF and Poppler. Original paper PDFs stay unchanged; *-web assets
change labels only. Axes, plotted data, and reported statistics are preserved.
The teaser uses the original paper PDF directly and is not normalized here.
"""
from pathlib import Path
import subprocess

import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "assets/figures"


def web_fonts(page):
    # Embed complete fonts so SVG conversion preserves regular and bold faces.
    page.insert_font(fontname="WebTimesRegular", fontbuffer=fitz.Font("tiro").buffer)
    page.insert_font(fontname="WebTimesBold", fontbuffer=fitz.Font("tibo").buffer)


def color(value):
    return tuple(((value >> shift) & 255) / 255 for shift in (16, 8, 0))


def erase(page, boxes):
    for box in boxes:
        page.add_redact_annot(fitz.Rect(box), fill=False)
    # Only labels in these measured regions are removed. Retain all graphics.
    page.apply_redactions(images=0, graphics=0)
    web_fonts(page)


def save_web(doc, name):
    pdf = FIGURES / f"{name}-web.pdf"
    svg = FIGURES / f"{name}-web.svg"
    doc.save(pdf, garbage=4, deflate=True)
    subprocess.run(["pdftocairo", "-svg", str(pdf), str(svg)], check=True)
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")


def scales():
    doc = fitz.open(FIGURES / "residual-scales.pdf")
    page = doc[0]
    web_fonts(page)
    # The source has two overlapping copies of this rotated y-axis label.
    erase(page, [(262, 43, 283, 186)])
    label = "MSE-Policy residual RMS"
    size = 13.5
    length = fitz.get_text_length(label, fontname="tiro", fontsize=size)
    page.insert_text((278.4, 114.5 + length / 2), label,
                     fontname="WebTimesRegular", fontsize=size, rotate=90)
    save_web(doc, "residual-scales")


def correlation():
    doc = fitz.open(FIGURES / "residual-correlation.pdf")
    page = doc[0]
    web_fonts(page)
    erase(page, [(85.7, 165.1, 113.6, 180.2), (220.7, 39.5, 240.4, 54.7)])
    # These points compare training objectives, so labels name the losses.
    page.insert_text((72, 180), "MSE-Loss", fontname="WebTimesRegular",
                     fontsize=12, color=color(8028037))
    page.insert_text((207, 47.5), "HT-Loss", fontname="WebTimesBold",
                     fontsize=12, color=color(35948))
    save_web(doc, "residual-correlation")


if __name__ == "__main__":
    scales()
    correlation()
    print("Rendered terminology-normalized scale and correlation figures.")
