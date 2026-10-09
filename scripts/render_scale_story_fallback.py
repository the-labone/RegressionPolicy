"""Render the task-average progress plot used before the animation loads.

uv run --with matplotlib python scripts/render_scale_story_fallback.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "assets/data/residual-scale-story.json").read_text())
font_manager.fontManager.addfont(ROOT / "assets/fonts/source-sans-pro-regular.ttf")
plt.rcParams.update({"font.family": "Source Sans Pro", "font.size": 14,
                     "svg.fonttype": "path", "svg.hashsalt": "residual-scale-story"})
fig = plt.figure(figsize=(640 / 72, 200 / 72), facecolor="none")
ax = fig.add_axes([.09, .27, .88, .64], facecolor="none")
ax.set(xlim=(0, 100), ylim=(0, .4), yticks=[0, .2, .4], xticks=[0, 50, 100])
ax.set_xticklabels(["0%", "50%", "100%"])
ax.set_xlabel("Episode progress", color="#72766f", labelpad=6)
ax.tick_params(length=0, pad=7, colors="#72766f")
for spine in ax.spines.values():
    spine.set_visible(False)
ax.grid(axis="y", color="#e4e7e0", linewidth=.7)
x, y = zip(*data["points"])
ax.plot(x, y, color="#b88c5e", linewidth=2.1, marker="o", markersize=4)
path = ROOT / "assets/figures/residual-scale-progress.svg"
fig.savefig(path, transparent=True, metadata={"Date": None,
    "Description": "Sweep into Pile task-average residual RMS over episode progress. "
                   "Original measured bins, not measurements of the example video."})
path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
