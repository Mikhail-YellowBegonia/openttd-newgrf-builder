#!/usr/bin/env python3
"""Index decoded 32bpp real sprites from a GRFCodec NFO file."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from PIL import Image


IMAGE_RE = re.compile(
    r"^\s*(?:\|\s*)?(?P<path>\S+\.png)\s+(?P<depth>\d+bpp)\s+"
    r"(?P<x>-?\d+)\s+(?P<y>-?\d+)\s+(?P<w>\d+)\s+(?P<h>\d+)\s+"
    r"(?P<xrel>-?\d+)\s+(?P<yrel>-?\d+)\s+(?P<zoom>\S+)"
    r"(?:\s+(?P<flags>.*))?$"
)
BASE_RE = re.compile(r"^\s*(?P<number>\d+)\s+\*")


def catalog(nfo_path: Path, output_path: Path) -> dict:
    root = nfo_path.parent
    current_sprite = None
    records = []
    for line_number, line in enumerate(nfo_path.read_text(errors="replace").splitlines(), 1):
        base = BASE_RE.match(line)
        if base:
            current_sprite = int(base.group("number"))
        match = IMAGE_RE.match(line)
        if not match or match.group("depth") != "32bpp":
            continue
        item = match.groupdict()
        path = Path(item.pop("path"))
        item.update(
            {
                "nfo_line": line_number,
                "nfo_sprite": current_sprite,
                "file": path.name,
                "x": int(item["x"]),
                "y": int(item["y"]),
                "width": int(item["w"]),
                "height": int(item["h"]),
                "xrel": int(item["xrel"]),
                "yrel": int(item["yrel"]),
                "flags": item["flags"] or "",
            }
        )
        for key in ("w", "h"):
            item.pop(key, None)
        records.append(item)

    files = []
    for image_path in sorted(root.glob("*.32.png")):
        with Image.open(image_path) as image:
            files.append(
                {
                    "file": image_path.name,
                    "width": image.width,
                    "height": image.height,
                    "mode": image.mode,
                    "records": sum(record["file"] == image_path.name for record in records),
                }
            )
    result = {
        "schema": 1,
        "source_nfo": nfo_path.name,
        "source_directory": str(root),
        "records": records,
        "files": files,
        "summary": {
            "32bpp_records": len(records),
            "sprite_numbers": len({record["nfo_sprite"] for record in records}),
            "files": len(files),
            "zooms": dict(Counter(record["zoom"] for record in records)),
            "chunked_records": sum("chunked" in record["flags"] for record in records),
        },
    }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nfo", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.nfo.with_name("sprite-catalog.json")
    result = catalog(args.nfo, output)
    print(f"wrote {output}: {result['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
