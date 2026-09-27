#!/usr/bin/env python3
"""Generate a crisp OpenTTD-style isometric reference grid.

The grid is drawn directly in pixel space with Pillow.  It uses the tile
geometry from a project template and deliberately avoids antialiasing so an
image model sees stable, exact projection lines.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path.cwd()


def _line_intercepts(anchor: tuple[int, int], edge: tuple[int, int], subdivisions: int):
    """Return the two line-family constants for the lattice around anchor."""

    step_x = edge[0] / subdivisions
    step_y = edge[1] / subdivisions
    if step_x != int(step_x) or step_y != int(step_y):
        raise ValueError("tile edge must divide evenly by subdivisions")
    step_x = int(step_x)
    step_y = int(step_y)
    # For slopes +1/2 and -1/2, the two families are y - x/2 and y + x/2.
    c_plus = anchor[1] - anchor[0] // 2
    c_minus = anchor[1] + anchor[0] // 2
    spacing = step_y + step_x // 2
    return c_plus, c_minus, spacing


def _draw_family(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    constant: int,
    slope: int,
    spacing: int,
    subdivisions: int,
    major_width: int,
    medium_width: int,
    minor_color: tuple[int, int, int],
    medium_color: tuple[int, int, int],
    major_color: tuple[int, int, int],
) -> None:
    """Draw one family of slope +1/2 or -1/2 lines without antialiasing."""

    # A canvas of width W intersects constants in this range, with a margin.
    min_constant = -height - width // 2 - spacing * 2
    max_constant = height + width // 2 + spacing * 2
    first = (min_constant - constant) // spacing - 1
    last = (max_constant - constant) // spacing + 1
    x0 = -2 * height - 2 * spacing
    x1 = width + 2 * height + 2 * spacing
    for index in range(first, last + 1):
        current = constant + index * spacing
        if slope > 0:
            y0 = current + x0 // 2
            y1 = current + x1 // 2
        else:
            y0 = current - x0 // 2
            y1 = current - x1 // 2
        # Tile boundaries are every `subdivisions` minor lines.  Quarter-tile
        # lines are a middle weight to make spatial blocks easier to read.
        if index % subdivisions == 0:
            color, line_width = major_color, major_width
        elif index % (subdivisions // 2) == 0:
            color, line_width = medium_color, medium_width
        else:
            color, line_width = minor_color, 1
        draw.line([(x0, y0), (x1, y1)], fill=color, width=line_width)


def generate_grid(
    template_path: Path,
    output_path: Path,
    zoom: str = "zi4",
    subdivisions: int = 8,
) -> dict[str, object]:
    spec = json.loads(template_path.read_text(encoding="utf-8"))
    zoom_spec = spec["zooms"][zoom]
    canvas = tuple(zoom_spec["canvas"])
    anchor = tuple(zoom_spec["anchor"])
    tile_width, tile_height = zoom_spec["tile_px"]
    edge = (tile_width // 2, tile_height // 2)
    if subdivisions < 2 or subdivisions & (subdivisions - 1):
        raise ValueError("subdivisions must be a power of two >= 2")

    image = Image.new("RGB", canvas, (242, 244, 240))
    draw = ImageDraw.Draw(image)
    c_plus, c_minus, spacing = _line_intercepts(anchor, edge, subdivisions)
    minor = (184, 207, 205)
    medium = (111, 157, 157)
    major = (45, 91, 105)
    _draw_family(
        draw,
        canvas[0],
        canvas[1],
        c_plus,
        +1,
        spacing,
        subdivisions,
        major_width=2,
        medium_width=1,
        minor_color=minor,
        medium_color=medium,
        major_color=major,
    )
    _draw_family(
        draw,
        canvas[0],
        canvas[1],
        c_minus,
        -1,
        spacing,
        subdivisions,
        major_width=2,
        medium_width=1,
        minor_color=minor,
        medium_color=medium,
        major_color=major,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    metadata = {
        "schema": 1,
        "template": str(template_path),
        "template_id": spec.get("template_id"),
        "zoom": zoom,
        "canvas": list(canvas),
        "anchor": list(anchor),
        "tile_px": [tile_width, tile_height],
        "tile_edge_px": list(edge),
        "subdivisions_per_tile_edge": subdivisions,
        "antialiasing": False,
        "background_rgb": [242, 244, 240],
        "minor_grid_rgb": list(minor),
        "medium_grid_rgb": list(medium),
        "major_grid_rgb": list(major),
    }
    output_path.with_suffix(".json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--template",
        type=Path,
        default=ROOT / "templates/isometric-2x2-h8/spec.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "assets/references/openttd-isometric-grid-2x2-h8-zi4.png",
    )
    parser.add_argument("--zoom", default="zi4", choices=("normal", "zi2", "zi4"))
    parser.add_argument("--subdivisions", type=int, default=8)
    args = parser.parse_args()
    metadata = generate_grid(args.template, args.output, args.zoom, args.subdivisions)
    print(
        f"generated {args.output} ({metadata['canvas'][0]}x{metadata['canvas'][1]}, "
        f"{metadata['subdivisions_per_tile_edge']} subdivisions/tile edge, antialiasing off)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
