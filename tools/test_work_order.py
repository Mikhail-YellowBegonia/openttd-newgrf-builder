import json
import math
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.template import generate_template
from tools.work_order import process, preview, slice_sprite


class WorkOrderTest(unittest.TestCase):
    def test_process_maps_source_axes_to_template_and_removes_background(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template_dir = root / "templates" / "test"
            spec = generate_template(template_dir, "1x1", 2)
            canvas = tuple(spec["zooms"]["zi4"]["canvas"])
            source = root / "source.png"
            image = Image.new("RGBA", (400, 400), (20, 20, 20, 255))
            # A small opaque block in source coordinates around the calibration origin.
            for x in range(190, 211):
                for y in range(180, 221):
                    image.putpixel((x, y), (220, 180, 120, 255))
            image.save(source)
            order = {
                "schema": 1,
                "work_order_id": "test",
                "building_id": "test",
                "house_id": "128",
                "footprint": "1x1",
                "source": {"image": str(source)},
                "calibration": {
                    "source_origin": [200, 200],
                    "source_x_axis": [20, 10],
                    "source_y_axis": [-20, 10],
                    "source_z_axis": [0, -20],
                    "target_template": str(template_dir / "spec.json"),
                },
                "processing": {"background": {"method": "flood_fill", "tolerance": 4}},
            }
            order_path = root / "order.json"
            order_path.write_text(json.dumps(order), encoding="utf-8")
            output = root / "out.png"
            process(order_path, output)
            with Image.open(output) as result:
                self.assertEqual(result.size, canvas)
                self.assertEqual(result.mode, "RGBA")
                self.assertIsNotNone(result.getchannel("A").getbbox())

    def test_preview_writes_an_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            Image.new("RGBA", (100, 100), (0, 0, 0, 255)).save(source)
            order = {
                "schema": 1,
                "work_order_id": "test",
                "building_id": "test",
                "house_id": "128",
                "footprint": "1x1",
                "source": {"image": str(source)},
                "calibration": {
                    "source_origin": [50, 70],
                    "source_x_axis": [20, 10],
                    "source_y_axis": [-20, 10],
                    "source_z_axis": [0, -20],
                    "target_template": "unused",
                },
                "processing": {},
            }
            order_path = root / "order.json"
            order_path.write_text(json.dumps(order), encoding="utf-8")
            output = root / "preview.png"
            preview(order_path, output)
            self.assertTrue(output.is_file())

    def test_process_and_slice_support_a_two_by_two_template(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template_dir = root / "templates" / "test"
            spec = generate_template(template_dir, "2x2", 2)
            source = root / "source.png"
            Image.new("RGBA", (400, 400), (220, 180, 120, 255)).save(source)
            order = {
                "schema": 1,
                "work_order_id": "test-2x2",
                "building_id": "test-2x2",
                "house_id": "128",
                "footprint": "2x2",
                "source": {"image": str(source)},
                "calibration": {
                    "source_origin": [200, 200],
                    "source_x_axis": [-20, -10],
                    "source_y_axis": [20, -10],
                    "ground_tile_size": 22.36,
                    "axis_scope": "tile",
                    "target_template": str(template_dir / "spec.json"),
                },
                "processing": {"background": {"method": "none"}},
            }
            order_path = root / "order.json"
            order_path.write_text(json.dumps(order), encoding="utf-8")
            fitted = root / "fitted.png"
            process(order_path, fitted)
            output_dir = root / "slices"
            slice_sprite(order_path, fitted, output_dir)
            self.assertEqual(len(list(output_dir.glob("tile-*.png"))), 4)
            self.assertTrue((output_dir / "slices.json").is_file())

    def test_affine_projection_maps_source_ground_basis_exactly(self):
        from tools.work_order import _basis_transform

        source_x = (-math.cos(math.radians(30)), -math.sin(math.radians(30)))
        source_y = (math.cos(math.radians(30)), -math.sin(math.radians(30)))
        target_x = (-0.5, -0.25)
        target_y = (0.5, -0.25)
        transform = _basis_transform(source_x, source_y, target_x, target_y)
        self.assertAlmostEqual(transform[1], 0.0, places=6)
        self.assertAlmostEqual(transform[2], 0.0, places=6)

    def test_source_projection_angle_keeps_canonical_vertical_axis(self):
        from tools.work_order import _effective_ground_axes

        x_axis, y_axis, _ = _effective_ground_axes(
            {
                "source_x_axis": [-520, -288],
                "source_y_axis": [532, -301],
                "ground_tile_size": 611.25,
                "source_projection_angle_deg": 29.75,
            }
        )
        self.assertAlmostEqual(x_axis[0], -y_axis[0], places=6)
        self.assertAlmostEqual(x_axis[1], y_axis[1], places=6)


if __name__ == "__main__":
    unittest.main()
