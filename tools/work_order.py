#!/usr/bin/env python3
"""Create and process a basic building art work order.

The first version deliberately keeps the human in the loop.  A work order
records the source image, the two ground-axis calibration vectors and the
review metadata.  The tool then performs repeatable colour adjustment,
connected background removal, uniform fitting to a zi4 template and mask
application.  It produces one final zi4 RGBA sprite; lower zooms remain a
build-time derivative.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageDraw


SCHEMA = 1
MASTER_ZOOM = "zi4"


def _vec(value: object, name: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} must be [x, y]")
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain numbers") from exc


def _point(value: object, name: str) -> tuple[int, int]:
    x, y = _vec(value, name)
    return round(x), round(y)


def _inverse_2x2(matrix: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    a, b, c, d = matrix
    determinant = a * d - b * c
    if abs(determinant) < 1e-9:
        raise ValueError("calibration axes are collinear")
    return d / determinant, -b / determinant, -c / determinant, a / determinant


def _matmul(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    a, b, c, d = left
    e, f, g, h = right
    return a * e + b * g, a * f + b * h, c * e + d * g, c * f + d * h


def _basis_transform(
    source_x: tuple[float, float],
    source_y: tuple[float, float],
    target_x: tuple[float, float],
    target_y: tuple[float, float],
) -> tuple[float, float, float, float]:
    source = (source_x[0], source_y[0], source_x[1], source_y[1])
    target = (target_x[0], target_y[0], target_x[1], target_y[1])
    return _matmul(target, _inverse_2x2(source))


def _template(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        zoom = data["zooms"][MASTER_ZOOM]
        canvas = tuple(int(v) for v in zoom["canvas"])
        anchor = tuple(float(v) for v in zoom["anchor"])
        tile_px = tuple(float(v) for v in zoom["tile_px"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid zi4 template spec: {path}") from exc
    if len(canvas) != 2 or len(anchor) != 2 or len(tile_px) != 2:
        raise ValueError(f"invalid zi4 template geometry: {path}")
    mask_name = zoom["mask"]
    return {
        "data": data,
        "path": path,
        "canvas": canvas,
        "anchor": anchor,
        "tile_px": tile_px,
        "mask": path.parent / mask_name,
    }


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_order(path: Path) -> dict[str, object]:
    order = json.loads(path.read_text(encoding="utf-8"))
    if order.get("schema") != SCHEMA:
        raise ValueError(f"unsupported work order schema: {order.get('schema')!r}")
    required = ("work_order_id", "building_id", "house_id", "footprint", "source", "calibration", "processing")
    missing = [key for key in required if key not in order]
    if missing:
        raise ValueError(f"work order missing fields: {', '.join(missing)}")
    _point(order["calibration"]["source_origin"], "source_origin")
    for key in ("source_x_axis", "source_y_axis"):
        _vec(order["calibration"][key], key)
    if order["calibration"].get("target_template") is None:
        raise ValueError("calibration.target_template is required")
    return order


def _target_basis(template: dict[str, object], calibration: dict[str, object]) -> tuple[tuple[float, float], tuple[float, float]]:
    tile_w, tile_h = template["tile_px"]
    width, depth = (int(part) for part in str(template["data"]["footprint"]).split("x", 1))
    # source axes may describe one tile or the complete foundation.  The
    # latter lets a 2x2 work order reuse the same measurements as its 1x1
    # pipeline test without changing the calibration numbers.
    if calibration.get("axis_scope", "tile") == "footprint":
        first_scale, second_scale = depth, width
    else:
        first_scale = second_scale = 1
    # Both ground directions start at the lower anchor corner and point to the
    # two upper corners of the isometric tile.
    return (
        (-tile_w * first_scale / 2, -tile_h * first_scale / 2),
        (tile_w * second_scale / 2, -tile_h * second_scale / 2),
    )


def _effective_ground_axes(calibration: dict[str, object]) -> tuple[tuple[float, float], tuple[float, float], float]:
    raw_x = _vec(calibration["source_x_axis"], "source_x_axis")
    raw_y = _vec(calibration["source_y_axis"], "source_y_axis")
    length_x = math.hypot(*raw_x)
    length_y = math.hypot(*raw_y)
    if length_x <= 0 or length_y <= 0:
        raise ValueError("ground axes must have positive length")
    side = float(calibration.get("ground_tile_size") or max(length_x, length_y))
    if side <= 0:
        raise ValueError("ground_tile_size must be positive")
    projection_angle = calibration.get("source_projection_angle_deg")
    if projection_angle is not None:
        angle = math.radians(float(projection_angle))
        # Canonical orthographic basis: both ground edges are symmetric around
        # the screen vertical. This absorbs small manual measurement errors
        # without introducing a lean into vertical walls.
        cosine, sine = math.cos(angle), math.sin(angle)
        raw_x = (-cosine, -sine)
        raw_y = (cosine, -sine)
        length_x = length_y = 1.0
    return (
        (raw_x[0] * side / length_x, raw_x[1] * side / length_x),
        (raw_y[0] * side / length_y, raw_y[1] * side / length_y),
        side,
    )


def _similarity_transform(
    source_x: tuple[float, float],
    source_y: tuple[float, float],
    target_x: tuple[float, float],
    target_y: tuple[float, float],
) -> tuple[float, float, float, float]:
    # Fit one rotation to both measured edges.  The source image is allowed
    # to be a little off the project's 2:1 OpenTTD projection, so we minimize
    # the combined angular error while keeping the transform uniform.
    dot = sum(a * b for a, b in zip(source_x, target_x)) + sum(a * b for a, b in zip(source_y, target_y))
    cross = source_x[0] * target_x[1] - source_x[1] * target_x[0]
    cross += source_y[0] * target_y[1] - source_y[1] * target_y[0]
    angle = math.atan2(cross, dot)
    scale = math.hypot(*target_x) / math.hypot(*source_x)
    cosine, sine = math.cos(angle) * scale, math.sin(angle) * scale
    return cosine, -sine, sine, cosine


def _remove_background(image: Image.Image, tolerance: int) -> Image.Image:
    """Remove connected pixels similar to border colours.

    This is intentionally conservative and deterministic.  A difficult image
    can supply a hand-painted alpha mask in the work order instead.
    """

    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    seen = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()
    seeds = {(x, y) for x in range(width) for y in (0, height - 1)}
    seeds.update({(x, y) for y in range(height) for x in (0, width - 1)})
    # A small border sample keeps the flood fill fast on large AI outputs and
    # still handles gradients better than comparing against one corner pixel.
    step_x = max(1, width // 32)
    step_y = max(1, height // 32)
    colour_points = {(x, y) for x in range(0, width, step_x) for y in (0, height - 1)}
    colour_points.update({(x, y) for y in range(0, height, step_y) for x in (0, width - 1)})
    colours = [pixels[x, y][:3] for x, y in colour_points]

    def similar(rgb: tuple[int, int, int]) -> bool:
        return any(sum((rgb[index] - colour[index]) ** 2 for index in range(3)) <= tolerance * tolerance * 3 for colour in colours)

    for x, y in seeds:
        if similar(pixels[x, y][:3]):
            queue.append((x, y))
            seen[y * width + x] = 1
    while queue:
        x, y = queue.popleft()
        pixels[x, y] = (*pixels[x, y][:3], 0)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                index = ny * width + nx
                if not seen[index] and similar(pixels[nx, ny][:3]):
                    seen[index] = 1
                    queue.append((nx, ny))
    return rgba


def _apply_alpha_mask(image: Image.Image, mask_path: Path) -> Image.Image:
    with Image.open(mask_path) as source_mask:
        mask = source_mask.convert("L")
    if mask.size != image.size:
        raise ValueError(f"alpha mask size {mask.size} does not match image {image.size}")
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgba.putalpha(ImageChops.multiply(alpha, mask))
    return rgba


def _tile_envelope_mask(template: dict[str, object], tile_key: str) -> Image.Image:
    zoom = template["data"]["zooms"][MASTER_ZOOM]
    polygon = zoom["tile_polygons"].get(tile_key)
    if not polygon:
        raise ValueError(f"template has no tile polygon {tile_key!r}")
    height_px = int(template["data"]["height_tiles"] * template["tile_px"][1])
    ground = [tuple(int(v) for v in point) for point in polygon]
    top = [(x, y - height_px) for x, y in ground]
    envelope = [top[0], top[1], ground[1], ground[2], ground[3], top[3]]
    mask = Image.new("L", tuple(template["canvas"]), 0)
    ImageDraw.Draw(mask).polygon(envelope, fill=255)
    return mask


def _fit_to_template(image: Image.Image, order: dict[str, object], template: dict[str, object]) -> Image.Image:
    calibration = order["calibration"]
    source_origin = _vec(calibration["source_origin"], "source_origin")
    source_x, source_y, _ = _effective_ground_axes(calibration)
    target_origin = tuple(template["anchor"])
    target_x, target_y = _target_basis(template, calibration)
    projection_mode = calibration.get("projection_mode", "uniform")
    if projection_mode == "orthographic_affine":
        # Convert a 30-degree orthographic source to the 2:1 OpenTTD
        # projection. Parallel lines remain parallel; this is not a
        # perspective warp.
        transform = _basis_transform(source_x, source_y, target_x, target_y)
    elif projection_mode == "uniform":
        transform = _similarity_transform(source_x, source_y, target_x, target_y)
    else:
        raise ValueError("calibration.projection_mode must be uniform or orthographic_affine")
    inverse = _inverse_2x2(transform)
    ia, ib, ic, id_ = inverse
    # source = inverse(target - target_origin) + source_origin
    tx, ty = target_origin
    sx, sy = source_origin
    offset_x = sx - ia * tx - ib * ty
    offset_y = sy - ic * tx - id_ * ty
    return image.transform(
        tuple(template["canvas"]),
        Image.Transform.AFFINE,
        (ia, ib, offset_x, ic, id_, offset_y),
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    )


def preview(order_path: Path, output: Path) -> None:
    order = load_order(order_path)
    root = order_path.parent.parent.parent if order_path.parent.name == "work_orders" else Path.cwd()
    source_path = _resolve(root, order["source"]["image"])
    with Image.open(source_path) as source:
        image = source.convert("RGBA")
    calibration = order["calibration"]
    origin = _point(calibration["source_origin"], "source_origin")
    x_axis, y_axis, _ = _effective_ground_axes(calibration)
    width, depth = (int(part) for part in str(order["footprint"]).split("x", 1))
    if calibration.get("axis_scope", "tile") == "footprint":
        x_axis = tuple(value / depth for value in x_axis)
        y_axis = tuple(value / width for value in y_axis)
    draw = ImageDraw.Draw(image)
    colour = (245, 45, 35, 255)

    def point(x: float, y: float) -> tuple[int, int]:
        return round(origin[0] + x * x_axis[0] + y * y_axis[0]), round(origin[1] + x * x_axis[1] + y * y_axis[1])

    for x in range(width + 1):
        draw.line([point(x, 0), point(x, depth)], fill=colour, width=2)
    for y in range(depth + 1):
        draw.line([point(0, y), point(width, y)], fill=colour, width=2)
    draw.ellipse((origin[0] - 6, origin[1] - 6, origin[0] + 6, origin[1] + 6), fill=(40, 220, 80, 255))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def process(order_path: Path, output: Path) -> None:
    order = load_order(order_path)
    root = order_path.parent.parent.parent if order_path.parent.name == "work_orders" else Path.cwd()
    source_path = _resolve(root, order["source"]["image"])
    template_path = _resolve(root, order["calibration"]["target_template"])
    template = _template(template_path)
    if template["data"].get("footprint") != order["footprint"]:
        raise ValueError(
            f"work-order footprint {order['footprint']} does not match template {template['data'].get('footprint')}"
        )
    with Image.open(source_path) as source:
        image = source.convert("RGBA")

    settings = order["processing"]
    saturation = float(settings.get("saturation", 1.0))
    if not math.isclose(saturation, 1.0):
        image = ImageEnhance.Color(image).enhance(saturation)
    background = settings.get("background", {})
    if background.get("method") == "flood_fill":
        image = _remove_background(image, int(background.get("tolerance", 24)))
    elif background.get("method") == "mask_file":
        image = _apply_alpha_mask(image, _resolve(root, background["mask_file"]))
    elif background.get("method", "none") != "none":
        raise ValueError("processing.background.method must be none, flood_fill, or mask_file")

    fitted = _fit_to_template(image, order, template)
    fitted = _apply_alpha_mask(fitted, template["mask"])
    output.parent.mkdir(parents=True, exist_ok=True)
    fitted.save(output)


def slice_sprite(order_path: Path, source_path: Path, output_dir: Path) -> None:
    """Split a fitted multi-tile sprite into per-tile masked images.

    Each output keeps the complete template canvas so pixels crossing a tile
    boundary are preserved.  The accompanying JSON records the tile key and
    ground polygon; a later House compiler can crop or attach offsets without
    losing this coordinate system.
    """

    order = load_order(order_path)
    root = order_path.parent.parent.parent if order_path.parent.name == "work_orders" else Path.cwd()
    template = _template(_resolve(root, order["calibration"]["target_template"]))
    if template["data"].get("footprint") != order["footprint"]:
        raise ValueError("work-order footprint does not match its template")
    width, depth = (int(part) for part in str(order["footprint"]).split("x", 1))
    with Image.open(source_path) as source:
        image = source.convert("RGBA")
    if image.size != tuple(template["canvas"]):
        raise ValueError(f"fitted sprite must have size {template['canvas']}, got {image.size}")
    output_dir.mkdir(parents=True, exist_ok=True)
    tiles = []
    for tile_y in range(depth):
        for tile_x in range(width):
            key = f"{tile_x},{tile_y}"
            mask = _tile_envelope_mask(template, key)
            tile = image.copy()
            tile.putalpha(ImageChops.multiply(tile.getchannel("A"), mask))
            filename = f"tile-{tile_x}-{tile_y}.png"
            tile.save(output_dir / filename)
            tiles.append(
                {
                    "tile": [tile_x, tile_y],
                    "key": key,
                    "file": filename,
                    "canvas": list(template["canvas"]),
                    "ground_polygon": template["data"]["zooms"][MASTER_ZOOM]["tile_polygons"][key],
                }
            )
    (output_dir / "slices.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "source": str(source_path),
                "template_id": template["data"]["template_id"],
                "footprint": order["footprint"],
                "tiles": tiles,
                "status": "art-split-only; House compiler integration pending",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def register(order_path: Path, manifest_path: Path, approved_path: Path) -> None:
    """Register an approved work-order output in the build manifest."""

    order = load_order(order_path)
    if order["footprint"] not in {"1x1", "2x2"}:
        raise ValueError("registration currently supports only 1x1 and 2x2 buildings")
    review = order.get("review", {})
    if review.get("rights_status") != "approved" or review.get("qa_status") != "approved":
        raise ValueError("work order must have approved rights_status and qa_status before registration")
    if not approved_path.is_file():
        raise ValueError(f"missing approved zi4 sprite: {approved_path}")
    root = manifest_path.parent.parent if manifest_path.parent.name == "assets" else manifest_path.parent
    template_path = _resolve(root, order["calibration"]["target_template"])
    template = _template(template_path)
    with Image.open(approved_path) as image:
        if image.mode != "RGBA":
            raise ValueError("approved sprite must be RGBA")
        if image.size != tuple(template["canvas"]):
            raise ValueError(f"approved sprite must have size {template['canvas']}, got {image.size}")
        with Image.open(template["mask"]) as mask_image:
            mask = mask_image.convert("L")
        outside = ImageChops.multiply(image.getchannel("A"), ImageChops.invert(mask))
        if outside.getbbox() is not None:
            raise ValueError("approved sprite has opaque pixels outside the template mask")
        image_size = image.size
    digest = hashlib.sha256(approved_path.read_bytes()).hexdigest()
    try:
        relative_asset = approved_path.relative_to(root).as_posix()
        relative_template = template_path.relative_to(root).as_posix()
        relative_mask = Path(template["mask"]).relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("approved sprite, template, and mask must be inside the repository") from exc
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows = list(reader)
    required = {"asset_id", "building_id", "house_id", "template_id", "file_path", "mask_path", "rights_status", "qa_status"}
    if not required.issubset(columns):
        raise ValueError(f"manifest is missing columns: {', '.join(sorted(required - set(columns)))}")
    asset_id = str(order["work_order_id"])
    if any(row.get("asset_id") == asset_id for row in rows):
        raise ValueError(f"manifest already contains asset_id={asset_id!r}")
    for field in ("building_id", "house_id"):
        if any(row.get(field) == str(order[field]) for row in rows):
            raise ValueError(f"manifest already contains {field}={order[field]!r}")
    row = {column: "" for column in columns}
    row.update(
        {
            "asset_id": asset_id,
            "building_id": str(order["building_id"]),
            "house_id": str(order["house_id"]),
            "building_family": str(order.get("building_family", "")),
            "density": str(order.get("density", "")),
            "era": str(order.get("era", "")),
            "footprint": str(order.get("footprint", "")),
            "template_id": str(template["data"]["template_id"]),
            "template_spec": relative_template,
            "zoom_level": MASTER_ZOOM,
            "file_path": relative_asset,
            "mask_path": relative_mask,
            "anchor_x": str(round(template["anchor"][0])),
            "anchor_y": str(round(template["anchor"][1])),
            "generator_type": "ai_image",
            "model": str(order.get("source", {}).get("generator", {}).get("model", "")),
            "model_version": str(order.get("source", {}).get("generator", {}).get("model_version", "")),
            "prompt_version": str(order.get("source", {}).get("generator", {}).get("prompt_version", "")),
            "seed": str(order.get("source", {}).get("generator", {}).get("seed", "")),
            "style_reference_uri": str(order.get("references", {}).get("style", "")),
            "architecture_reference_uri": str(order.get("references", {}).get("architecture", "")),
            "sketch_reference_uri": str(order.get("references", {}).get("sketch", "")),
            "postprocess_status": "approved",
            "sha256": digest,
            "dimensions": f"{image_size[0]}x{image_size[1]}",
            "zoom_levels": "zi4,zi2,normal",
            "rights_status": "approved",
            "qa_status": "approved",
            "reviewer": str(review.get("reviewer", "")),
            "reviewed_at": str(review.get("reviewed_at", "")),
            "notes": str(review.get("notes", "")),
        }
    )
    row = {column: row[column] for column in columns}
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows + [row])
    deliverables = {**order.get("deliverables", {}), "approved_zi4": relative_asset, "mask": relative_mask}
    if order["footprint"] == "2x2":
        slices = Path(relative_asset).parent / (Path(relative_asset).stem.replace("-zi4", "-slices")) / "slices.json"
        if (root / slices).is_file():
            deliverables["slices"] = slices.as_posix()
    order["deliverables"] = deliverables
    order_path.write_text(json.dumps(order, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def init_order(output: Path, args: argparse.Namespace) -> None:
    order = {
        "schema": SCHEMA,
        "work_order_id": args.work_order_id,
        "building_id": args.building_id,
        "house_id": str(args.house_id),
        "building_family": args.building_family,
        "density": args.density,
        "era": args.era,
        "footprint": args.footprint,
        "height_tiles": args.height_tiles,
        "source": {"image": args.source_image, "generator": {"provider": "", "model": "", "prompt_version": "", "seed": ""}},
        "references": {"style": "", "architecture": "", "sketch": ""},
        "calibration": {
            "source_origin": [0, 0],
            "source_x_axis": [128, 64],
            "source_y_axis": [-128, 64],
            "ground_tile_size": None,
            "ground_tile_policy": "square_max",
            "projection_mode": "uniform",
            "target_template": args.template,
            "notes": "Replace the calibration vectors after marking the source image.",
        },
        "processing": {"saturation": 1.0, "background": {"method": "flood_fill", "tolerance": 24}},
        "deliverables": {"preview": "", "approved_zi4": "", "mask": ""},
        "review": {"rights_status": "review", "qa_status": "pending", "reviewer": "", "notes": ""},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(order, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init")
    init.add_argument("--output", type=Path, required=True)
    init.add_argument("--work-order-id", required=True)
    init.add_argument("--building-id", required=True)
    init.add_argument("--house-id", required=True)
    init.add_argument("--source-image", required=True)
    init.add_argument("--template", required=True)
    init.add_argument("--footprint", default="1x1")
    init.add_argument("--height-tiles", type=int, default=8)
    init.add_argument("--building-family", default="")
    init.add_argument("--density", default="urban")
    init.add_argument("--era", default="post_2000")
    init.set_defaults(func=lambda args: init_order(args.output, args))

    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("order", type=Path)
    preview_parser.add_argument("--output", type=Path, required=True)
    preview_parser.set_defaults(func=lambda args: preview(args.order, args.output))

    process_parser = subparsers.add_parser("process")
    process_parser.add_argument("order", type=Path)
    process_parser.add_argument("--output", type=Path, required=True)
    process_parser.set_defaults(func=lambda args: process(args.order, args.output))

    slice_parser = subparsers.add_parser("slice")
    slice_parser.add_argument("order", type=Path)
    slice_parser.add_argument("source", type=Path, help="processed full-canvas zi4 PNG")
    slice_parser.add_argument("--output-dir", type=Path, required=True)
    slice_parser.set_defaults(func=lambda args: slice_sprite(args.order, args.source, args.output_dir))

    register_parser = subparsers.add_parser("register")
    register_parser.add_argument("order", type=Path)
    register_parser.add_argument("--manifest", type=Path, default=Path("assets/manifest.csv"))
    register_parser.add_argument("--approved", type=Path, required=True)
    register_parser.set_defaults(func=lambda args: register(args.order, args.manifest, args.approved))

    args = parser.parse_args()
    try:
        args.func(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
