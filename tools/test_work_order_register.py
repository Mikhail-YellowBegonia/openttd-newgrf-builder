import csv
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.template import generate_template
from tools.work_order import process, register


class WorkOrderRegisterTest(unittest.TestCase):
    def test_approved_order_registers_the_processed_sprite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assets" / "generated").mkdir(parents=True)
            (root / "assets" / "approved").mkdir()
            (root / "templates" / "test").mkdir(parents=True)
            template_dir = root / "templates" / "test"
            spec = generate_template(template_dir, "1x1", 2)
            source = root / "assets" / "generated" / "source.png"
            Image.new("RGBA", (200, 200), (40, 40, 40, 255)).save(source)
            order = {
                "schema": 1,
                "work_order_id": "asset-001",
                "building_id": "building-001",
                "house_id": "128",
                "footprint": "1x1",
                "source": {"image": "assets/generated/source.png"},
                "calibration": {
                    "source_origin": [100, 100],
                    "source_x_axis": [20, 10],
                    "source_y_axis": [-20, 10],
                    "source_z_axis": [0, -20],
                    "target_template": "templates/test/spec.json",
                },
                "processing": {"background": {"method": "none"}},
                "review": {"rights_status": "approved", "qa_status": "approved"},
            }
            order_path = root / "assets" / "work_orders" / "asset-001.json"
            order_path.parent.mkdir()
            order_path.write_text(json.dumps(order), encoding="utf-8")
            output = root / "assets" / "approved" / "asset-001.png"
            process(order_path, output)
            manifest = root / "assets" / "manifest.csv"
            with manifest.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["asset_id", "building_id", "house_id", "density", "era", "footprint", "template_id", "template_spec", "zoom_level", "file_path", "mask_path", "anchor_x", "anchor_y", "rights_status", "qa_status", "sha256", "dimensions", "zoom_levels", "postprocess_status"])
                writer.writeheader()
            register(order_path, manifest, output)
            with manifest.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["asset_id"], "asset-001")
            self.assertEqual(rows[0]["rights_status"], "approved")
            self.assertEqual(rows[0]["dimensions"], f"{spec['zooms']['zi4']['canvas'][0]}x{spec['zooms']['zi4']['canvas'][1]}")


if __name__ == "__main__":
    unittest.main()
