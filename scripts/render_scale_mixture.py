"""Draw a Gaussian scale-mixture illustration for the project page.

Run: uv run --with matplotlib --with numpy python scripts/render_scale_mixture.py

This is a constructed example, not an empirical fit. Three equally weighted,
zero-mean Gaussians have standard deviations (1, 2, 4) / sqrt(7). The mixture
and its Gaussian reference both have variance one. A finite Gaussian mixture
has heavier tails than that matched Gaussian, not power-law asymptotic tails.
"""
from pathlib import Path
import math
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/figures"
for name in ("regular", "semibold"):
    font_manager.fontManager.addfont(ROOT / f"assets/fonts/source-sans-pro-{name}.ttf")
plt.rcParams.update({
    "font.family": "Source Sans Pro", "font.size": 13,
    "svg.fonttype": "path", "svg.hashsalt": "gaussian-scale-mixture",
    "text.color": "#50545b", "axes.unicode_minus": False,
})
BLUE = "#2b679a"
ORANGE = "#b88c5e"
GOLD = "#ead48c"
GRAY = "#72766f"
SIGMAS = np.array([1., 2., 4.]) / math.sqrt(7)
X = np.linspace(-5, 5, 1201)
COMPONENTS = np.array([
    np.exp(-X**2 / (2 * sigma**2)) / (sigma * math.sqrt(2 * math.pi)) / 3
    for sigma in SIGMAS
])
MIXTURE = COMPONENTS.sum(axis=0)
GAUSSIAN = np.exp(-X**2 / 2) / math.sqrt(2 * math.pi)


def density(x, sigma):
    return math.exp(-x*x / (2*sigma*sigma)) / (sigma * math.sqrt(2*math.pi))


def axes_style(ax, ymax):
    ax.set_facecolor("none")
    ax.set(xlim=(-5, 5), ylim=(0, ymax))
    ax.set_yticks([])
    ax.set_xticks([])
    for spine in ("left", "right", "top"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#c5c3bd")
    ax.spines["bottom"].set_linewidth(0.7)


def components(ax):
    axes_style(ax, 0.395)
    for y, color in zip(COMPONENTS, ("#8fb0c9", "#5988b0", BLUE)):
        ax.fill_between(X, 0, y, color=color, alpha=0.045, linewidth=0)
        ax.plot(X, y, color=color, lw=2.1, solid_capstyle="round")


def pooled(ax):
    axes_style(ax, 0.69)
    ax.fill_between(X, 0, MIXTURE, color=BLUE, alpha=0.04, linewidth=0)
    # Highlight both tails, using the same threshold as the empirical panel a.
    for left, right in ((-5, -3), (3, 5)):
        ax.axvspan(left, right, ymax=0.21, color=GOLD, alpha=0.26, linewidth=0)
        mask = (X >= left) & (X <= right)
        ax.fill_between(X, 0, MIXTURE, where=mask, color=GOLD, alpha=0.85, linewidth=0)
    ax.plot(X, GAUSSIAN, color=ORANGE, lw=1.8, dashes=(4, 3), zorder=3)
    ax.plot(X, MIXTURE, color=BLUE, lw=2.7, zorder=4, solid_capstyle="round")
    # Magnify the right tail without distorting the density in the main plot.
    inset = ax.inset_axes([0.69, 0.36, 0.31, 0.41])
    inset.set_facecolor("#f6efd7")
    inset.plot(X, MIXTURE, color=BLUE, lw=1.8)
    inset.plot(X, GAUSSIAN, color=ORANGE, lw=1.4, dashes=(3, 2))
    inset.set(xlim=(2.8, 5), ylim=(0, 0.019), xticks=[], yticks=[])
    for name, spine in inset.spines.items():
        spine.set_visible(name in ("left", "bottom"))
        spine.set_color("#ddcda2")
        spine.set_linewidth(0.6)
    inset.set_title("Tail zoom", fontsize=12, color="#967239", pad=5)
    tail_x = 3.55
    tail_y = sum(density(tail_x, s) for s in SIGMAS) / 3
    ax.annotate("", xy=(tail_x, tail_y + 0.01), xytext=(3.8, 0.245),
                arrowprops={"arrowstyle": "-", "color": "#b69a65", "lw": 0.9,
                            "connectionstyle": "arc3,rad=-0.18"})


def accessible_svg(path):
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    ns = "{http://www.w3.org/2000/svg}"
    tree = ET.parse(path)
    root = tree.getroot()
    title = ET.Element(ns + "title", {"id": "scale-mixture-title"})
    title.text = "Different Gaussian scales produce heavier-than-Gaussian tails"
    desc = ET.Element(ns + "desc", {"id": "scale-mixture-description"})
    desc.text = (
        "Illustrative example, not experimental data. Left: three equally weighted, "
        "zero-mean Gaussian components with standard deviations 1, 2, and 4 divided "
        "by the square root of 7. Right: their mixture (solid blue), compared with "
        "a Gaussian of the same mean and variance (dashed orange). Both have variance "
        "one. Shaded regions mark residual magnitudes above three. Tail probability "
        "is 1.576 percent for the mixture and 0.270 percent for the Gaussian. "
        "An inset magnifies the right tail over residuals 2.8 to 5. "
        "The component panel uses a different vertical scale for legibility. "
        "Finite Gaussian mixtures are not power-law-tailed distributions."
    )
    root.insert(0, title)
    root.insert(1, desc)
    root.set("role", "img")
    root.set("aria-labelledby", "scale-mixture-title scale-mixture-description")
    tree.write(path, encoding="unicode", xml_declaration=True)
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")


def render():
    width, height = 460, 156
    fig = plt.figure(figsize=(width / 72, height / 72), facecolor="none")
    left = fig.add_axes([0.015, 0.08, 0.40, 0.66])
    right = fig.add_axes([0.555, 0.08, 0.43, 0.66])
    labels = [(0.215, 0.91, "Different scales"), (0.770, 0.91, "Heavier tails")]
    arrow = FancyArrowPatch((0.443, 0.40), (0.523, 0.40),
                            transform=fig.transFigure, arrowstyle="->",
                            color="#a4a89e", lw=1.2, mutation_scale=11)
    components(left)
    pooled(right)
    for x, y, label in labels:
        fig.text(x, y, label, ha="center", va="center", fontsize=16, color=GRAY)
    fig.add_artist(arrow)
    path = OUT / "gaussian-scale-mixture.svg"
    fig.savefig(path, transparent=True, metadata={"Date": None})
    accessible_svg(path)
    plt.close(fig)


if __name__ == "__main__":
    assert math.isclose(float(np.mean(SIGMAS**2)), 1.0)
    assert math.isclose(float(np.trapezoid(MIXTURE, X)), 1.0, abs_tol=0.0004)
    tail_mix = sum(math.erfc(3 / (s * math.sqrt(2))) for s in SIGMAS) / 3
    tail_gaussian = math.erfc(3 / math.sqrt(2))
    print(f"Illustration: tail mass {tail_mix:.6%} vs {tail_gaussian:.6%}; {tail_mix / tail_gaussian:.2f}×")
    render()
