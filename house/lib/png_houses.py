"""Build House definitions directly from approved PNG assets.

This is the main art path for the project. The old VOX/GoRender experiment is
kept outside this module and is never imported by the default generator.
"""

from __future__ import annotations

from pathlib import Path

import grf
from PIL import Image

from house.lib import AHouse, AMultiTileHouse
from tools.asset_pipeline import Asset, validate_manifest


_DENSITY_NAMES = {
    "rural": "STR_HOUSE_RURAL",
    "town": "STR_HOUSE_TOWN",
    "urban": "STR_HOUSE_TOWN",
    "highrise": "STR_HOUSE_TOWN",
}


def _asset_path(manifest_path: Path, asset: Asset) -> Path:
    path = Path(asset.file_path)
    return path if path.is_absolute() else manifest_path.parent.parent / path


def _sprite_variants(path: Path, *, anchor_shift=(0, 0)) -> list[grf.AlternativeSprites]:
    """Derive all runtime zooms from the zi4 master with nearest-neighbour."""

    with Image.open(path) as source:
        master = source.convert("RGBA")
        sprites = []
        for zoom, scale in ((grf.ZOOM_NORMAL, 1), (grf.ZOOM_2X, 2), (grf.ZOOM_4X, 4)):
            image = master if scale == 4 else master.resize(
                (master.width // (4 // scale), master.height // (4 // scale)),
                Image.Resampling.NEAREST,
            )
            sprites.append(
                grf.ImageSprite(
                    image.copy(),
                    xofs=-(image.width // 2),
                    yofs=-image.height + anchor_shift[1] * scale,
                    zoom=zoom,
                    crop=False,
                )
            )
        sprite = grf.AlternativeSprites(*sprites)
    return [sprite for _ in range(8)]


def _empty_variants() -> list[grf.AlternativeSprites]:
    """Transparent affiliated-tile graphics for a full-canvas source sprite."""

    sprites = []
    for zoom in (grf.ZOOM_NORMAL, grf.ZOOM_2X, grf.ZOOM_4X):
        sprites.append(
            grf.ImageSprite(
                Image.new("RGBA", (1, 1), (0, 0, 0, 0)),
                xofs=0,
                yofs=0,
                zoom=zoom,
                crop=False,
            )
        )
    sprite = grf.AlternativeSprites(*sprites)
    return [sprite for _ in range(8)]


def _house(asset: Asset, manifest_path: Path) -> AHouse:
    values = asset.values
    footprint = values.get("footprint", "1x1")
    if footprint == "2x2":
        path = _asset_path(manifest_path, asset)
        # The template anchor is the south corner of the complete footprint;
        # the north tile's local south corner is one tile (32 normal pixels)
        # above it.  Shift the full-canvas sprite down by that amount when it
        # is attached to the north tile.
        full = _sprite_variants(path, anchor_shift=(0, 32))
        empty = _empty_variants()
        return AMultiTileHouse(
            id=int(values["house_id"], 0),
            name=_DENSITY_NAMES.get(values["density"], "STR_HOUSE_TOWN"),
            tile_sprites=[full, empty, empty, empty],
            flags=0x11,  # 2x2 size bit plus NOT_SLOPED
            substitute_ids=[20, 21, 22, 23],
            availability_mask=0xF81F,
            population=1,
            probability=16,
        )
    return AHouse(
        id=int(values["house_id"], 0),
        name=_DENSITY_NAMES.get(values["density"], "STR_HOUSE_TOWN"),
        sprites=_sprite_variants(_asset_path(manifest_path, asset)),
        flags=0x1,
        substitute=0x06,
        availability_mask=0xF81F,
        population=1,
        probability=16,
    )


def load_png_houses(manifest_path: Path, strings=None) -> list[AHouse]:
    """Validate the manifest and return only approved PNG-backed houses."""

    _, assets = validate_manifest(manifest_path)
    return [_house(asset, manifest_path) for asset in assets if asset.is_buildable]
