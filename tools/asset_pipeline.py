#!/usr/bin/env python3
"""Validate the asset manifest and produce a deterministic lock file.

The project keeps the human-editable CSV as its input format so it remains
easy to review in a spreadsheet. This module is deliberately dependency-light:
it uses the standard library for manifest and lock handling and imports Pillow
only when a referenced PNG needs to be inspected.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REQUIRED_COLUMNS = {
    "asset_id",
    "building_id",
    "house_id",
    "density",
    "era",
    "footprint",
    "template_id",
    "template_spec",
    "zoom_level",
    "file_path",
    "mask_path",
    "anchor_x",
    "anchor_y",
    "rights_status",
    "qa_status",
}
MASTER_ZOOM = "zi4"
APPROVED_RIGHTS = "approved"
APPROVED_QA = "approved"
ALLOWED_RIGHTS = {"unknown", "review", "approved", "rejected"}
ALLOWED_QA = {"pending", "failed", "approved"}


class ManifestError(ValueError):
    """Raised when the manifest cannot safely enter a build."""


@dataclass(frozen=True)
class Asset:
    """A normalized row from the asset manifest."""

    values: dict[str, str]
    row_number: int

    @property
    def asset_id(self) -> str:
        return self.values["asset_id"]

    @property
    def file_path(self) -> str:
        return self.values.get("file_path", "")

    @property
    def is_buildable(self) -> bool:
        return (
            self.values.get("rights_status") == APPROVED_RIGHTS
            and self.values.get("qa_status") == APPROVED_QA
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_digest(path: Path) -> str:
    """Hash the exact CSV bytes so lock files identify their source."""

    return _sha256(path)


def read_manifest(path: Path) -> tuple[list[str], list[Asset]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - set(columns))
        if missing:
            raise ManifestError(
                f"{path}: missing required columns: {', '.join(missing)}"
            )

        assets = []
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ManifestError(f"row {row_number}: too many CSV fields")
            values = {key: (value or "").strip() for key, value in row.items()}
            if not any(values.values()):
                continue
            assets.append(Asset(values=values, row_number=row_number))
    return columns, assets


def _check_unique(assets: Iterable[Asset], field: str) -> None:
    seen: dict[str, int] = {}
    for asset in assets:
        value = asset.values.get(field, "")
        if not value:
            continue
        if value in seen:
            raise ManifestError(
                f"rows {seen[value]} and {asset.row_number}: duplicate {field}={value!r}"
            )
        seen[value] = asset.row_number


def _validate_png(path: Path) -> dict[str, object]:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise ManifestError("Pillow is required to validate referenced PNG files") from exc

    try:
        with Image.open(path) as image:
            if image.format != "PNG":
                raise ManifestError(f"{path}: expected PNG, got {image.format}")
            width, height = image.size
            if width <= 0 or height <= 0:
                raise ManifestError(f"{path}: image dimensions must be positive")
            if "A" not in image.getbands():
                raise ManifestError(f"{path}: final sprite must have an alpha channel")
            return {
                "width": width,
                "height": height,
                "mode": image.mode,
                "format": image.format,
            }
    except OSError as exc:
        raise ManifestError(f"{path}: unreadable image: {exc}") from exc


def _resolve_asset_path(manifest_path: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else manifest_path.parent.parent / candidate


def _validate_template(
    manifest_path: Path,
    values: dict[str, str],
    image_path: Path,
    image_info: dict[str, object],
) -> None:
    template_spec = values.get("template_spec", "")
    zoom_level = values.get("zoom_level", "")
    mask_path_value = values.get("mask_path", "")
    if not template_spec or not zoom_level or not mask_path_value:
        raise ManifestError("approved PNG needs template_spec, zoom_level, and mask_path")
    if zoom_level != MASTER_ZOOM:
        raise ManifestError(f"approved source art must be the {MASTER_ZOOM} master zoom")
    spec_path = _resolve_asset_path(manifest_path, template_spec)
    if not spec_path.is_file():
        raise ManifestError(f"missing template spec {spec_path}")
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        if values.get("template_id") != spec.get("template_id"):
            raise ManifestError(
                f"template_id {values.get('template_id')!r} does not match {spec.get('template_id')!r}"
            )
        zoom_spec = spec["zooms"][zoom_level]
        expected_size = tuple(zoom_spec["canvas"])
        expected_anchor = tuple(zoom_spec["anchor"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ManifestError(f"invalid template spec or zoom {zoom_level!r}: {exc}") from exc

    if (image_info["width"], image_info["height"]) != expected_size:
        raise ManifestError(f"{image_path}: dimensions must match {zoom_level} template {expected_size}")
    try:
        anchor = (int(values["anchor_x"]), int(values["anchor_y"]))
    except (TypeError, ValueError) as exc:
        raise ManifestError("anchor_x and anchor_y must be integers") from exc
    if anchor != expected_anchor:
        raise ManifestError(f"anchor {anchor} does not match template anchor {expected_anchor}")

    mask_path = _resolve_asset_path(manifest_path, mask_path_value)
    if not mask_path.is_file():
        raise ManifestError(f"missing sprite mask {mask_path}")
    from PIL import Image, ImageChops

    try:
        with Image.open(mask_path) as mask_image, Image.open(image_path) as sprite_image:
            mask = mask_image.convert("L")
            alpha = sprite_image.convert("RGBA").getchannel("A")
            if mask.size != expected_size:
                raise ManifestError(f"{mask_path}: mask dimensions must be {expected_size}")
            outside_alpha = ImageChops.multiply(alpha, ImageChops.invert(mask))
            if outside_alpha.getbbox() is not None:
                raise ManifestError(f"{image_path}: nontransparent pixels exceed the maximum envelope mask")
    except OSError as exc:
        raise ManifestError(f"cannot read mask or sprite image: {exc}") from exc


def validate_manifest(manifest_path: Path) -> tuple[list[str], list[Asset]]:
    columns, assets = read_manifest(manifest_path)
    for field in ("asset_id", "building_id", "house_id"):
        _check_unique(assets, field)

    for asset in assets:
        values = asset.values
        for field in ("asset_id", "building_id", "house_id", "density", "era", "footprint"):
            if not values.get(field):
                raise ManifestError(f"row {asset.row_number}: {field} is required")
        if values.get("rights_status") not in ALLOWED_RIGHTS:
            raise ManifestError(
                f"row {asset.row_number}: invalid rights_status={values.get('rights_status')!r}"
            )
        if values.get("qa_status") not in ALLOWED_QA:
            raise ManifestError(
                f"row {asset.row_number}: invalid qa_status={values.get('qa_status')!r}"
            )

        if not asset.is_buildable:
            continue
        if not asset.file_path:
            raise ManifestError(f"row {asset.row_number}: approved asset needs file_path")
        file_path = _resolve_asset_path(manifest_path, asset.file_path)
        if not file_path.is_file():
            raise ManifestError(f"row {asset.row_number}: missing file {file_path}")
        image_info = _validate_png(file_path)
        _validate_template(manifest_path, values, file_path, image_info)
        expected_sha = values.get("sha256", "")
        actual_sha = _sha256(file_path)
        if expected_sha and expected_sha != actual_sha:
            raise ManifestError(
                f"row {asset.row_number}: sha256 mismatch for {file_path} "
                f"(manifest {expected_sha}, actual {actual_sha})"
            )
        values["sha256"] = actual_sha
        values["dimensions"] = f"{image_info['width']}x{image_info['height']}"

    return columns, assets


def _yaml_scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or any(char in text for char in ":#{}[],&*!|>'\"%@`\n"):
        return json.dumps(text, ensure_ascii=False)
    return text


def _yaml_dump(value: object, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{prefix}{key}:")
                lines.extend(_yaml_dump(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(item)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                first, *rest = _yaml_dump(item, indent + 2)
                lines.append(f"{prefix}- {first.lstrip()}")
                lines.extend(rest)
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
        return lines
    return [f"{prefix}{_yaml_scalar(value)}"]


def write_lock(manifest_path: Path, lock_path: Path) -> int:
    columns, assets = validate_manifest(manifest_path)
    entries = []
    for asset in assets:
        if not asset.is_buildable:
            continue
        values = asset.values
        entry = {key: values[key] for key in columns if values.get(key)}
        for key in ("sha256", "dimensions"):
            if values.get(key):
                entry[key] = values[key]
        entries.append(entry)
    lock = {
        "schema": 1,
        "manifest": str(manifest_path),
        "manifest_sha256": _manifest_digest(manifest_path),
        "entries": entries,
    }
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("\n".join(_yaml_dump(lock)) + "\n", encoding="utf-8")
    return len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "lock"))
    parser.add_argument("--manifest", type=Path, default=Path("assets/manifest.csv"))
    parser.add_argument(
        "--lock", dest="lock_path", type=Path, default=Path("assets/manifests/manifest.lock.yaml")
    )
    args = parser.parse_args()
    try:
        if args.command == "validate":
            _, assets = validate_manifest(args.manifest)
            buildable = sum(asset.is_buildable for asset in assets)
            print(f"validated {len(assets)} asset record(s); {buildable} buildable")
        else:
            count = write_lock(args.manifest, args.lock_path)
            print(f"wrote {count} buildable asset record(s) to {args.lock_path}")
    except ManifestError as exc:
        print(f"asset validation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
