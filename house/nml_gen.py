#!/usr/bin/env python3
"""Generate the project's human-readable NML and compile-ready sprite assets.

The manifest remains the source of truth.  This module only translates the
approved rows into ordinary NML; it does not reproduce the old grf-py object
model.  The generated NML is intentionally verbose so a person can audit the
House properties, sprite anchors, zooms, and multi-tile layout.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from PIL import Image

from tools.asset_pipeline import Asset, validate_manifest


ROOT = Path.cwd()
DEFAULT_MANIFEST = ROOT / "assets/manifest.csv"
DEFAULT_NML = ROOT / "building/building.nml"
DEFAULT_RESOURCES = ROOT / "building/resources/nml"

_DENSITY_NAMES = {
    "rural": "STR_HOUSE_RURAL",
    "town": "STR_HOUSE_TOWN",
    "urban": "STR_HOUSE_TOWN",
    "highrise": "STR_HOUSE_TOWN",
}


def _nml_string(value: str) -> str:
    """Return a quoted NML string literal."""

    return json.dumps(value, ensure_ascii=False)


def _identifier(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not result or result[0].isdigit():
        result = f"asset_{result}"
    return result.lower()


def _asset_path(manifest_path: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else manifest_path.parent.parent / candidate


def _load_template(manifest_path: Path, asset: Asset) -> dict:
    values = asset.values
    path = _asset_path(manifest_path, values["template_spec"])
    return json.loads(path.read_text(encoding="utf-8"))


def _write_zoom_images(source: Image.Image, template: dict, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for zoom, divisor in (("normal", 4), ("zi2", 2), ("zi4", 1)):
        width, height = template["zooms"][zoom]["canvas"]
        image = source if divisor == 1 else source.resize(
            (width, height), Image.Resampling.NEAREST
        )
        path = output_dir / f"full-{zoom}.png"
        image.save(path)
        paths[zoom] = path
    return paths


def _write_empty_images(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for zoom in ("normal", "zi2", "zi4"):
        path = output_dir / f"empty-{zoom}.png"
        if not path.exists():
            Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(path)
        paths[zoom] = path
    return paths


def _path_for_nml(path: Path) -> str:
    return path.as_posix()


def _sprite_offset(spec: dict, attachment_point: tuple[int, int]) -> tuple[int, int]:
    """Place a template point on the runtime tile's drawing origin.

    The art workflow calibrates against the full footprint's south anchor,
    while a House draws its full sprite from the north tile.  Both points are
    in the same template coordinate system.  Passing the actual attachment
    point here handles both X and Y for rectangular footprints.  A different
    feature, such as an object, can supply its own attachment point.
    """

    anchor_x, anchor_y = (int(value) for value in spec["anchor"])
    point_x, point_y = attachment_point
    shift_x, shift_y = anchor_x - point_x, anchor_y - point_y
    return -anchor_x + shift_x, -anchor_y + shift_y


def _house_attachment_point(spec: dict) -> tuple[int, int]:
    """The north ground corner of the House tile that owns the full sprite."""

    point = spec["tile_polygons"]["0,0"][0]
    return int(point[0]), int(point[1])


def _sprite_block(
    name: str,
    paths: dict[str, Path],
    template: dict,
    *,
    empty: bool = False,
) -> list[str]:
    lines: list[str] = []
    for index, (zoom, nml_zoom) in enumerate(
        (("normal", "ZOOM_LEVEL_NORMAL"), ("zi2", "ZOOM_LEVEL_IN_2X"), ("zi4", "ZOOM_LEVEL_IN_4X"))
    ):
        spec = template["zooms"][zoom]
        width, height = spec["canvas"] if not empty else (1, 1)
        xrel, yrel = _sprite_offset(spec, _house_attachment_point(spec)) if not empty else (0, 0)
        depth = "BIT_DEPTH_32BPP"
        if index == 0:
            lines.append(
                f"spriteset({name}, {nml_zoom}, {depth}, {_nml_string(_path_for_nml(paths[zoom]))}) {{"
            )
        else:
            lines.append(
                f"alternative_sprites({name}, {nml_zoom}, {depth}, "
                f"{_nml_string(_path_for_nml(paths[zoom]))}) {{"
            )
        lines.append(
            f"    [0, 0, {width}, {height}, {xrel}, {yrel}, NOCROP]"
        )
        lines.append("}")
    return lines


def _house_block(asset: Asset, manifest_path: Path, resource_root: Path) -> list[str]:
    values = asset.values
    asset_id = _identifier(values["asset_id"])
    house_id = int(values["house_id"], 0)
    footprint = values["footprint"]
    if footprint not in {"1x1", "2x2"}:
        raise ValueError(f"{asset.asset_id}: NML path currently supports only 1x1 and 2x2")

    template = _load_template(manifest_path, asset)
    width_tiles, depth_tiles = (int(part) for part in footprint.split("x", 1))
    # Sprite-layout extents are expressed in eighths of a tile.  The old
    # prototype used 16 for every building, which clips taller sprites at
    # runtime.  Use the declared footprint and template height envelope so
    # the whole approved image remains drawable in OpenTTD.
    xextent = 16 * width_tiles
    yextent = 16 * depth_tiles
    zextent = 8 * int(template.get("height_tiles", 8))
    source_path = _asset_path(manifest_path, values["file_path"])
    with Image.open(source_path) as source_image:
        source = source_image.convert("RGBA")
        resource_dir = resource_root / asset_id
        full_paths = _write_zoom_images(source, template, resource_dir)

    empty_paths = _write_empty_images(resource_root / "shared")
    full_name = f"{asset_id}_full"
    empty_name = f"{asset_id}_empty"
    full_layout = f"{asset_id}_full_layout"
    empty_layout = f"{asset_id}_empty_layout"
    switch_name = f"{asset_id}_layout"
    item_name = f"{asset_id}_house"
    rel_full_paths = {zoom: Path("building/resources/nml") / asset_id / path.name for zoom, path in full_paths.items()}
    rel_empty_paths = {zoom: Path("building/resources/nml") / "shared" / path.name for zoom, path in empty_paths.items()}

    lines: list[str] = [
        f"/* {asset.asset_id}: {values.get('building_id', '')}, {footprint}, House ID {house_id} */",
        f"/* approved source: {values['file_path']} */",
        f"/* template: {values['template_id']}; anchor and canvas come from its spec */",
    ]
    lines.extend(_sprite_block(full_name, rel_full_paths, template))
    if footprint == "2x2":
        lines.extend(_sprite_block(empty_name, rel_empty_paths, template, empty=True))
    lines.extend(
        [
            "",
            f"spritelayout {full_layout} {{",
            "    ground {",
            "        sprite: GROUNDSPRITE_NORMAL;",
            "    }",
            "    building {",
            f"        sprite: {full_name};",
            f"        xextent: {xextent};",
            f"        yextent: {yextent};",
            f"        zextent: {zextent};",
            "    }",
            "}",
        ]
    )
    if footprint == "2x2":
        lines.extend(
            [
                "",
                f"spritelayout {empty_layout} {{",
                "    ground {",
                "        sprite: GROUNDSPRITE_NORMAL;",
                "    }",
                "    building {",
                f"        sprite: {empty_name};",
                f"        xextent: {xextent};",
                f"        yextent: {yextent};",
                f"        zextent: {zextent};",
                "    }",
                "}",
                "",
                f"switch(FEAT_HOUSES, SELF, {switch_name}, house_tile) {{",
                f"    HOUSE_TILE_NORTH: {full_layout};",
                f"    {empty_layout};",
                "}",
            ]
        )

    name_string = _DENSITY_NAMES.get(values.get("density", ""), "STR_HOUSE_TOWN")
    lines.extend(
        [
            "",
            f"item(FEAT_HOUSES, {item_name}, {house_id}, HOUSE_SIZE_{footprint.upper()}) {{",
            "    property {",
            f"        substitute: {'20' if footprint == '2x2' else '6'};",
            f"        name: string({name_string});",
            "        /* NML probability 1 emits raw Action 0 probability 16. */",
            "        probability: 1;",
            "        population: 1;",
            "        availability_mask: [ALL_TOWNZONES, bitmask(CLIMATE_TEMPERATE, CLIMATE_ARCTIC, CLIMATE_TROPIC, CLIMATE_TOYLAND, ABOVE_SNOWLINE)];",
        ]
    )
    if footprint == "2x2":
        lines.extend(
            [
                "        /* NML emits 0x30, 0x20, 0x20, 0x20 for the four tiles. */",
                "        building_flags: 0x20;",
            ]
        )
    else:
        lines.append("        building_flags: bitmask(HOUSE_FLAG_NOT_SLOPED);")
    lines.extend(
        [
            "    }",
            "",
            "    graphics {",
            f"        default: {switch_name if footprint == '2x2' else full_layout};",
            "    }",
            "}",
        ]
    )
    return lines


def generate_nml(manifest_path: Path, output_path: Path, resource_root: Path) -> int:
    _, assets = validate_manifest(manifest_path)
    buildable = [asset for asset in assets if asset.is_buildable]
    if not buildable:
        raise ValueError("No approved PNG buildings found in the manifest")

    occupied: dict[int, str] = {}
    for asset in buildable:
        base_id = int(asset.values["house_id"], 0)
        count = 4 if asset.values["footprint"] == "2x2" else 1
        if base_id < 0 or base_id + count > 4096:
            raise ValueError(f"{asset.asset_id}: House ID range is outside 0..4095")
        for house_id in range(base_id, base_id + count):
            previous = occupied.setdefault(house_id, asset.asset_id)
            if previous != asset.asset_id:
                raise ValueError(f"House ID {house_id} is used by both {previous} and {asset.asset_id}")

    if resource_root.exists():
        shutil.rmtree(resource_root)
    resource_root.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "/* Generated by house.nml_gen from assets/manifest.csv. */",
        "/* Edit the manifest and source art, then regenerate this file. */",
        "",
        "grf {",
        '    grfid: "__\\03\\06";',
        "    name: string(STR_GRF_NAME);",
        "    desc: string(STR_GRF_DESC);",
        "    version: 0;",
        "    min_compatible_version: 0;",
        "}",
        "",
    ]
    for index, asset in enumerate(buildable):
        if index:
            lines.append("")
        lines.extend(_house_block(asset, manifest_path, resource_root))
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(buildable)


def build(manifest_path: Path = DEFAULT_MANIFEST, output_path: Path = DEFAULT_NML, resource_root: Path = DEFAULT_RESOURCES) -> int:
    count = generate_nml(manifest_path, output_path, resource_root)
    print(f"generated {output_path} for {count} buildable asset(s)")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_NML)
    parser.add_argument("--resources", type=Path, default=DEFAULT_RESOURCES)
    args = parser.parse_args()
    try:
        build(args.manifest, args.output, args.resources)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
