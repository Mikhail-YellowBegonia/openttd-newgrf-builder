#!/usr/bin/env python3
"""Generate deterministic OpenTTD building sprite templates.

The template separates the transparent sprite from the maximum drawable
envelope.  A model or an artist may use ``guide.png`` as a reference, while
post-processing must clip the final RGBA image with ``mask.png``.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


TILE_WIDTH = 64
TILE_HEIGHT = 32
METRES_PER_TILE = 40
ZOOMS = {"normal": 1, "zi2": 2, "zi4": 4}
MASTER_ZOOM = "zi4"


def _parse_footprint(value: str) -> tuple[int, int]:
    try:
        width, depth = (int(part) for part in value.lower().split("x", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError("footprint must look like 1x1 or 2x3") from exc
    if width < 1 or depth < 1 or width > 16 or depth > 16:
        raise ValueError("footprint dimensions must be between 1 and 16 tiles")
    return width, depth


def _project(x: float, y: float, scale: int, origin: tuple[float, float]) -> tuple[int, int]:
    ox, oy = origin
    return round(ox + (x - y) * TILE_WIDTH / 2 * scale), round(
        oy + (x + y) * TILE_HEIGHT / 2 * scale
    )


def _geometry(width: int, depth: int, height_tiles: int, scale: int) -> dict[str, object]:
    margin_x = TILE_WIDTH * scale
    top_margin = TILE_HEIGHT * scale
    bottom_margin = TILE_HEIGHT * scale
    ground_width = (width + depth) * TILE_WIDTH * scale / 2
    canvas_width = round(ground_width + margin_x * 2)
    height_px = height_tiles * TILE_HEIGHT * scale
    ground_y = top_margin + height_px
    ground_points = [
        _project(0, 0, scale, (canvas_width / 2, ground_y)),
        _project(width, 0, scale, (canvas_width / 2, ground_y)),
        _project(width, depth, scale, (canvas_width / 2, ground_y)),
        _project(0, depth, scale, (canvas_width / 2, ground_y)),
    ]
    canvas_height = ground_points[2][1] + bottom_margin
    top_points = [(x, y - height_px) for x, y in ground_points]
    tile_polygons = {}
    for tile_x in range(width):
        for tile_y in range(depth):
            tile_polygons[f"{tile_x},{tile_y}"] = [
                list(_project(tile_x, tile_y, scale, (canvas_width / 2, ground_y))),
                list(_project(tile_x + 1, tile_y, scale, (canvas_width / 2, ground_y))),
                list(_project(tile_x + 1, tile_y + 1, scale, (canvas_width / 2, ground_y))),
                list(_project(tile_x, tile_y + 1, scale, (canvas_width / 2, ground_y))),
            ]
    return {
        "canvas": (canvas_width, canvas_height),
        "ground_points": ground_points,
        "top_points": top_points,
        "height_px": height_px,
        # The sprite origin is the lower ground corner.  This is the point
        # where the building touches the tile and is the natural reference
        # for a work-order calibration.
        "anchor": ground_points[2],
        "tile_polygons": tile_polygons,
    }


def _draw_mask(path: Path, geometry: dict[str, object]) -> None:
    image = Image.new("L", geometry["canvas"], 0)
    draw = ImageDraw.Draw(image)
    ground = geometry["ground_points"]
    top = geometry["top_points"]
    envelope = [top[0], top[1], ground[1], ground[2], ground[3], top[3]]
    draw.polygon(envelope, fill=255)
    draw.polygon(top, fill=255)
    image.save(path)


def _draw_guide(path: Path, geometry: dict[str, object], width: int, depth: int, scale: int) -> None:
    image = Image.new("RGBA", geometry["canvas"], (0, 0, 0, 255))
    draw = ImageDraw.Draw(image)
    ground = geometry["ground_points"]
    top = geometry["top_points"]
    envelope = [top[0], top[1], ground[1], ground[2], ground[3], top[3]]
    draw.polygon(envelope, fill=(255, 255, 255, 255))
    draw.line(envelope + [envelope[0]], fill=(210, 210, 210, 255), width=max(1, scale))

    # One ground edge is exactly one 40 m tile edge. Draw a red double-ended
    # arrow like the supplied reference image; this is the only scale cue in
    # the guide so the white area remains an unambiguous maximum envelope.
    p0, p1 = ground[0], ground[1]
    red = (245, 45, 35, 255)
    arrow_width = max(2, 2 * scale)
    draw.line((*p0, *p1), fill=red, width=arrow_width)
    arrow_len = 10 * scale
    arrow_angle = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for point, direction in ((p0, arrow_angle), (p1, arrow_angle + math.pi)):
        tip_x, tip_y = point
        left = (
            tip_x + arrow_len * math.cos(direction + math.pi / 6),
            tip_y + arrow_len * math.sin(direction + math.pi / 6),
        )
        right = (
            tip_x + arrow_len * math.cos(direction - math.pi / 6),
            tip_y + arrow_len * math.sin(direction - math.pi / 6),
        )
        draw.polygon([(tip_x, tip_y), left, right], fill=red)
    mid_x, mid_y = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
    draw.text((round(mid_x - 16 * scale), round(mid_y + 8 * scale)), "40m", fill=red)
    image.save(path)


def generate_template(output: Path, footprint: str = "1x1", height_tiles: int = 8) -> dict[str, object]:
    width, depth = _parse_footprint(footprint)
    if height_tiles < 1 or height_tiles > 64:
        raise ValueError("height must be between 1 and 64 tiles")
    output.mkdir(parents=True, exist_ok=True)
    zoom_specs = {}
    master_geometry = _geometry(width, depth, height_tiles, ZOOMS[MASTER_ZOOM])
    master_mask = output / f"{MASTER_ZOOM}.mask.png"
    master_guide = output / f"{MASTER_ZOOM}.guide.png"
    _draw_mask(master_mask, master_geometry)
    _draw_guide(master_guide, master_geometry, width, depth, ZOOMS[MASTER_ZOOM])
    for name, scale in ZOOMS.items():
        geometry = _geometry(width, depth, height_tiles, scale)
        mask_name = f"{name}.mask.png"
        guide_name = f"{name}.guide.png"
        if name != MASTER_ZOOM:
            # These are machine-derived QA references, never additional art inputs.
            with Image.open(master_mask) as image:
                image.resize(geometry["canvas"], Image.Resampling.NEAREST).save(output / mask_name)
            with Image.open(master_guide) as image:
                image.resize(geometry["canvas"], Image.Resampling.NEAREST).save(output / guide_name)
        zoom_specs[name] = {
            "scale": scale,
            "canvas": list(geometry["canvas"]),
            "mask": mask_name,
            "guide": guide_name,
            "anchor": list(geometry["anchor"]),
            "tile_px": [TILE_WIDTH * scale, TILE_HEIGHT * scale],
            "tile_polygons": geometry["tile_polygons"],
            "derived_from": None if name == MASTER_ZOOM else MASTER_ZOOM,
            "resampling": None if name == MASTER_ZOOM else "nearest",
        }
    spec = {
        "schema": 1,
        "template_id": f"isometric-{footprint}-h{height_tiles}",
        "projection": "openttd_isometric",
        "metres_per_tile": METRES_PER_TILE,
        "footprint": footprint,
        "height_tiles": height_tiles,
        "height_metres": height_tiles * METRES_PER_TILE,
        "master_zoom": MASTER_ZOOM,
        "screen_projection": {
            "tile_edge_angle_deg": round(math.degrees(math.atan2(TILE_HEIGHT, TILE_WIDTH)), 6),
            "ground_corner_angle_deg": round(180 - 2 * math.degrees(math.atan2(TILE_HEIGHT, TILE_WIDTH)), 6),
            "note": "These are screen-space angles for the 2:1 OpenTTD tile projection; they are not the 120-degree world-axis angle.",
        },
        "generation_rule": "AI generates zi4 once; lower zooms are integer nearest-neighbour reductions",
        "guide_semantics": {
            "white": "maximum allowed drawing area; not required fill",
            "black": "outside the allowed drawing area",
            "red_arrow": "one ground tile edge = 40 metres",
        },
        "drawing_rule": "final RGBA alpha must be zero wherever the corresponding mask is zero",
        "zooms": zoom_specs,
    }
    (output / "spec.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return spec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--footprint", default="1x1")
    parser.add_argument("--height", type=int, default=8, dest="height_tiles")
    args = parser.parse_args()
    generate_template(args.output, args.footprint, args.height_tiles)
    print(f"generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
