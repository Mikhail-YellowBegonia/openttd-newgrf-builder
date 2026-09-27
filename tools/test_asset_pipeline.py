import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.asset_pipeline import ManifestError, validate_manifest, write_lock
from tools.template import generate_template


class AssetPipelineTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "assets" / "approved").mkdir(parents=True)
        template_dir = self.root / "templates" / "test"
        spec = generate_template(template_dir, "1x1", 2)
        zoom = spec["zooms"]["zi4"]
        self.template_spec = "templates/test/spec.json"
        self.mask_path = "templates/test/zi4.mask.png"
        self.anchor = tuple(zoom["anchor"])
        self.image = self.root / "assets" / "approved" / "house.png"
        Image.new("RGBA", tuple(zoom["canvas"]), (255, 255, 255, 0)).save(self.image)
        self.manifest = self.root / "assets" / "manifest.csv"

    def tearDown(self):
        self.tempdir.cleanup()

    def write_manifest(self, **overrides):
        row = {
            "asset_id": "cn-town-1979_2000-midrise-001",
            "building_id": "cn_town_1979_001",
            "house_id": "128",
            "density": "town",
            "era": "1979_2000",
            "footprint": "1x1",
            "template_id": "isometric-1x1-h2",
            "template_spec": self.template_spec,
            "zoom_level": "zi4",
            "file_path": "assets/approved/house.png",
            "mask_path": self.mask_path,
            "anchor_x": str(self.anchor[0]),
            "anchor_y": str(self.anchor[1]),
            "rights_status": "approved",
            "qa_status": "approved",
            "sha256": hashlib.sha256(self.image.read_bytes()).hexdigest(),
            **overrides,
        }
        with self.manifest.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)

    def test_approved_png_is_buildable_and_locked(self):
        self.write_manifest()
        _, assets = validate_manifest(self.manifest)
        self.assertEqual(len(assets), 1)
        lock = self.root / "assets" / "manifests" / "manifest.lock.yaml"
        self.assertEqual(write_lock(self.manifest, lock), 1)
        self.assertIn("manifest_sha256:", lock.read_text(encoding="utf-8"))
        with Image.open(self.image) as image:
            dimensions = f"{image.width}x{image.height}"
        self.assertIn(f"dimensions: {dimensions}", lock.read_text(encoding="utf-8"))

    def test_unapproved_asset_does_not_require_a_file(self):
        self.write_manifest(
            rights_status="review", qa_status="pending", file_path=""
        )
        _, assets = validate_manifest(self.manifest)
        self.assertFalse(assets[0].is_buildable)

    def test_approved_asset_requires_matching_hash(self):
        self.write_manifest(sha256="0" * 64)
        with self.assertRaisesRegex(ManifestError, "sha256 mismatch"):
            validate_manifest(self.manifest)

    def test_sprite_outside_template_mask_is_rejected(self):
        with Image.open(self.image) as image:
            image.putpixel((0, 0), (255, 0, 0, 255))
            image.save(self.image)
        self.write_manifest(sha256="")
        with self.assertRaisesRegex(ManifestError, "maximum envelope mask"):
            validate_manifest(self.manifest)

    def test_duplicate_building_ids_are_rejected(self):
        self.write_manifest()
        columns = next(csv.reader([self.manifest.read_text(encoding="utf-8").splitlines()[0]]))
        duplicate = {
            column: "" for column in columns
        }
        duplicate.update(
            {
                "asset_id": "cn-town-1979_2000-midrise-002",
                "building_id": "cn_town_1979_001",
                "house_id": "129",
                "density": "town",
                "era": "1979_2000",
                "footprint": "1x1",
                "file_path": "assets/approved/house.png",
                "rights_status": "approved",
                "qa_status": "approved",
            }
        )
        with self.manifest.open("a", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=columns).writerow(duplicate)
        with self.assertRaisesRegex(ManifestError, "duplicate building_id"):
            validate_manifest(self.manifest)


if __name__ == "__main__":
    unittest.main()
