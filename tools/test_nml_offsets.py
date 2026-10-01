"""Regression checks for mapping artwork anchors to House sprite offsets."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from house.nml_gen import _sprite_block
from tools.template import generate_template


class HouseOffsetTest(unittest.TestCase):
    def test_full_sprite_uses_north_tile_corner_at_every_zoom(self) -> None:
        expected_normal = {
            "1x1": (-96, -288),
            "1x2": (-112, -288),
            "2x1": (-112, -288),
            "2x2": (-128, -288),
        }
        with tempfile.TemporaryDirectory() as temporary:
            for footprint, (xrel, yrel) in expected_normal.items():
                with self.subTest(footprint=footprint):
                    template_dir = Path(temporary) / footprint
                    generate_template(template_dir, footprint=footprint, height_tiles=8)
                    template = json.loads((template_dir / "spec.json").read_text(encoding="utf-8"))
                    paths = {zoom: Path(f"{zoom}.png") for zoom in ("normal", "zi2", "zi4")}
                    nml = "\n".join(_sprite_block("sample", paths, template))
                    for zoom, scale in (("normal", 1), ("zi2", 2), ("zi4", 4)):
                        canvas = template["zooms"][zoom]["canvas"]
                        self.assertIn(
                            f"[0, 0, {canvas[0]}, {canvas[1]}, {xrel * scale}, {yrel * scale}, NOCROP]",
                            nml,
                        )


if __name__ == "__main__":
    unittest.main()
