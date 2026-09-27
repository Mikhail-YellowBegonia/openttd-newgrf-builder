import tempfile
import unittest
from pathlib import Path

from PIL import Image
from PIL import ImageChops

from tools.template import generate_template


class TemplateTest(unittest.TestCase):
    def test_template_has_matching_guides_masks_and_scale(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            spec = generate_template(output, "2x1", 6)
            self.assertEqual(spec["metres_per_tile"], 40)
            self.assertEqual(spec["master_zoom"], "zi4")
            self.assertEqual(spec["zooms"]["normal"]["resampling"], "nearest")
            for zoom in ("normal", "zi2", "zi4"):
                zoom_spec = spec["zooms"][zoom]
                with Image.open(output / zoom_spec["mask"]) as mask:
                    self.assertEqual(mask.size, tuple(zoom_spec["canvas"]))
                with Image.open(output / zoom_spec["guide"]) as guide:
                    self.assertEqual(guide.size, tuple(zoom_spec["canvas"]))
            with Image.open(output / "zi4.mask.png") as master, Image.open(output / "normal.mask.png") as derived:
                expected = master.resize(derived.size, Image.Resampling.NEAREST)
                self.assertIsNone(ImageChops.difference(expected, derived).getbbox())
            self.assertEqual(spec["zooms"]["zi2"]["tile_px"], [128, 64])


if __name__ == "__main__":
    unittest.main()
