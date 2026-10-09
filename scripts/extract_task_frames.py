#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["imageio-ffmpeg>=0.6", "pillow>=11"]
# ///
"""Extract evenly spaced video frames into one lightweight WebP sprite per task.

Run with:
    uv run scripts/extract_task_frames.py --source-dir ~/Downloads

The original clips are only read; generated web assets are written to
assets/task-frames. A first/middle/last inspection sheet is written to /tmp.
"""

import argparse
import json
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw


TASKS = (
    ("close_drawer", "Close Drawer"),
    ("open_drawer", "Open Drawer"),
    ("sweep_into_pile", "Sweep into Pile"),
)
FRAME_COUNT = 21
COLUMNS = 7
ROWS = 3


def extract_task(source: Path, destination: Path, task_id: str, label: str):
    video = source / f"{task_id}.mp4"
    source_count, duration = imageio_ffmpeg.count_frames_and_secs(str(video))
    selected_indices = [
        round(i * (source_count - 1) / (FRAME_COUNT - 1))
        for i in range(FRAME_COUNT)
    ]
    frame_stream = imageio_ffmpeg.read_frames(str(video), pix_fmt="rgb24")
    metadata = next(frame_stream)
    source_size = metadata["size"]
    frame_lookup = {}
    selected = set(selected_indices)
    for index, raw_frame in enumerate(frame_stream):
        if index in selected:
            frame = Image.frombytes("RGB", source_size, raw_frame)
            frame.thumbnail((480, 480), Image.Resampling.LANCZOS)
            frame_lookup[index] = frame

    frames = [frame_lookup[index] for index in selected_indices]
    width, height = frames[0].size
    sprite = Image.new("RGB", (width * COLUMNS, height * ROWS))
    for index, frame in enumerate(frames):
        sprite.paste(frame, ((index % COLUMNS) * width, (index // COLUMNS) * height))
    sprite_path = destination / f"{task_id}.webp"
    sprite.save(sprite_path, "WEBP", quality=82, method=6)

    record = {
        "id": task_id,
        "label": label,
        "sprite": f"assets/task-frames/{task_id}.webp",
        "frameWidth": width,
        "frameHeight": height,
        "frameCount": FRAME_COUNT,
        "columns": COLUMNS,
        "rows": ROWS,
        "durationSeconds": duration,
        "sourceFrameCount": source_count,
        "sourceFps": metadata["fps"],
        "frames": [
            {
                "index": index,
                "progress": index / (FRAME_COUNT - 1),
                "timeSeconds": round(source_index / metadata["fps"], 3),
                "column": index % COLUMNS,
                "row": index // COLUMNS,
            }
            for index, source_index in enumerate(selected_indices)
        ],
    }
    return record, frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path.home() / "Downloads")
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path(__file__).resolve().parents[1] / "assets" / "task-frames",
    )
    parser.add_argument(
        "--inspection-path", type=Path,
        default=Path("/tmp/task-frames-inspection.jpg"),
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"version": 1, "tasks": []}
    inspection = Image.new("RGB", (3 * 256, 3 * 292), "#fdfdfa")
    draw = ImageDraw.Draw(inspection)
    for row, (task_id, label) in enumerate(TASKS):
        record, frames = extract_task(args.source_dir, args.output_dir, task_id, label)
        manifest["tasks"].append(record)
        for column, index in enumerate((0, 10, 20)):
            frame = frames[index].copy()
            frame.thumbnail((256, 256), Image.Resampling.LANCZOS)
            x, y = column * 256, row * 292
            inspection.paste(frame, (x, y + 28))
            draw.text((x + 8, y + 8), f"{label} · {index * 5}%", fill="#26364d")
        print(
            f"{task_id}: {record['sourceFrameCount']} source frames, "
            f"{record['durationSeconds']} s, "
            f"{record['frameWidth']}×{record['frameHeight']} tiles, "
            f"{(args.output_dir / (task_id + '.webp')).stat().st_size:,} bytes"
        )
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    inspection.save(args.inspection_path, quality=90)
    print(f"Inspection sheet: {args.inspection_path}")


if __name__ == "__main__":
    main()
