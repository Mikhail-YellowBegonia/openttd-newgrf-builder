#!/usr/bin/env python3
"""Local HTTP workbench for the semi-automatic building workflow.

The browser owns the human-in-the-loop steps.  This small server keeps files in
the repository and delegates deterministic image work to ``tools.work_order``.
It intentionally uses only the Python standard library plus the project's
existing Pillow based tools.
"""

from __future__ import annotations

import base64
import csv
import json
import mimetypes
import shutil
import subprocess
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
WEB_ROOT = ROOT / "web"
WORKBENCH_ROOT = Path(__file__).resolve().parent
WORK_ORDERS = ROOT / "assets" / "work_orders"
GENERATED = ROOT / "assets" / "generated"
WORK = ROOT / "assets" / "work"
APPROVED = ROOT / "assets" / "approved"
MANIFEST = ROOT / "assets" / "manifest.csv"
REFERENCES = ROOT / "assets" / "references"

for directory in (WORK_ORDERS, GENERATED, WORK, APPROVED):
    directory.mkdir(parents=True, exist_ok=True)


def safe_id(value: object) -> str:
    text = str(value or "").strip()
    if not text or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in text):
        raise ValueError("work_order_id may contain only letters, digits, '-' and '_'")
    return text


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    candidate = path if path.is_absolute() else ROOT / path
    candidate = candidate.resolve()
    if candidate != ROOT and ROOT not in candidate.parents:
        raise ValueError("path escapes the repository")
    return candidate


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def decode_data_url(value: object) -> bytes | None:
    if not value:
        return None
    text = str(value)
    if "," not in text or not text.startswith("data:"):
        raise ValueError("image upload must be a data URL")
    header, encoded = text.split(",", 1)
    if ";base64" not in header:
        raise ValueError("image upload must use base64 data")
    try:
        return base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise ValueError("invalid base64 image upload") from exc


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def order_path(order_id: str) -> Path:
    return WORK_ORDERS / f"{safe_id(order_id)}.json"


def list_orders() -> list[dict]:
    orders = []
    for path in sorted(WORK_ORDERS.glob("*.json")):
        if path.parent.name == "archive":
            continue
        try:
            order = read_json(path)
            order["_path"] = relative_path(path)
            orders.append(order)
        except (OSError, json.JSONDecodeError):
            continue
    return orders


def manifest_rows() -> list[dict]:
    if not MANIFEST.is_file():
        return []
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def reference_assets() -> list[dict]:
    """Return checked-in image references available to the workbench."""
    assets = []
    for path in sorted(REFERENCES.glob("*.png")):
        if "grid" not in path.stem:
            continue
        name = path.stem
        labels = {
            "temporal8-2801-ttd-grid-zi4": ("Temporal8 · 1x1 · 一般", "ai_reference"),
            "temporal8-2801-ttd-grid-zi4-lowrise": ("Temporal8 · 1x1 · 低层变体", "ai_reference"),
            "openttd-isometric-grid-1x1-h8-zi4": ("OpenTTD 空网格 · 1x1", "template_grid"),
            "openttd-isometric-grid-2x2-h8-zi4": ("OpenTTD 空网格 · 2x2", "template_grid"),
            "ai-isometric-grid-120-2x2-h8-zi4": ("AI 120° 网格 · 2x2", "template_grid"),
        }
        label, role = labels.get(name, (name, "reference"))
        assets.append({"id": name, "label": label, "path": relative_path(path), "role": role})
    return assets


def save_order(payload: dict) -> dict:
    order = dict(payload.get("order") or {})
    work_order_id = safe_id(order.get("work_order_id"))
    order["schema"] = 1
    order["work_order_id"] = work_order_id
    order.setdefault("source", {})
    order.setdefault("references", {})
    order.setdefault("processing", {})
    order.setdefault("review", {})

    source_bytes = decode_data_url(payload.get("source_data_url"))
    if source_bytes is not None:
        source_path = GENERATED / f"{work_order_id}.png"
        source_path.write_bytes(source_bytes)
        order["source"]["image"] = relative_path(source_path)

    mask_bytes = decode_data_url(payload.get("mask_data_url"))
    if mask_bytes is not None:
        mask_path = WORK / f"{work_order_id}-mask.png"
        mask_path.write_bytes(mask_bytes)
        background = dict(order["processing"].get("background") or {})
        background.update({"method": "mask_file", "mask_file": relative_path(mask_path)})
        order["processing"]["background"] = background

    path = order_path(work_order_id)
    write_json(path, order)
    return {"order": order, "path": relative_path(path)}


def load_order(order_id: str) -> tuple[Path, dict]:
    path = order_path(order_id)
    if not path.is_file():
        raise FileNotFoundError(f"work order not found: {order_id}")
    return path, read_json(path)


def run_action(order_id: str, action: str) -> dict:
    from tools.work_order import preview, process, register, slice_sprite

    path, order = load_order(order_id)
    if action in {"process", "register"} and order.get("sprite_mode") == "four_direction":
        raise ValueError("four_direction is recorded in the work order, but directional sprite compilation is not connected yet")
    output = None
    deliverables = dict(order.get("deliverables") or {})
    if action == "preview":
        output = WORK / f"{order_id}-calibration.png"
        preview(path, output)
        deliverables["preview"] = relative_path(output)
    elif action == "process":
        output = WORK / f"{order_id}-zi4.png"
        process(path, output)
        deliverables["processed_zi4"] = relative_path(output)
    elif action == "slice":
        source = WORK / f"{order_id}-zi4.png"
        if not source.is_file():
            raise ValueError("process the work order before slicing")
        output = WORK / f"{order_id}-slices"
        slice_sprite(path, source, output)
        deliverables["slices"] = relative_path(output / "slices.json")
    elif action == "register":
        source = APPROVED / f"{order_id}-zi4.png"
        if not source.is_file():
            raise ValueError("approve the processed image before registering")
        register(path, MANIFEST, source)
        order = read_json(path)
        deliverables = dict(order.get("deliverables") or {})
        output = MANIFEST
    else:
        raise ValueError(f"unsupported action: {action}")
    order["deliverables"] = deliverables
    write_json(path, order)
    return {"action": action, "order": read_json(path), "output": relative_path(output) if output else None}


def approve_order(payload: dict) -> dict:
    path, order = load_order(payload.get("work_order_id"))
    review = dict(order.get("review") or {})
    review.update(
        {
            "rights_status": str(payload.get("rights_status") or review.get("rights_status") or "review"),
            "qa_status": str(payload.get("qa_status") or review.get("qa_status") or "pending"),
            "reviewer": str(payload.get("reviewer") or review.get("reviewer") or ""),
            "reviewed_at": str(payload.get("reviewed_at") or review.get("reviewed_at") or ""),
            "notes": str(payload.get("notes") or review.get("notes") or ""),
        }
    )
    order["review"] = review
    work_output = WORK / f"{order['work_order_id']}-zi4.png"
    approved_output = APPROVED / f"{order['work_order_id']}-zi4.png"
    if review["rights_status"] == "approved" and review["qa_status"] == "approved":
        if not work_output.is_file():
            raise ValueError("process the work order before approving it")
        shutil.copyfile(work_output, approved_output)
        order.setdefault("deliverables", {})["approved_zi4"] = relative_path(approved_output)
    write_json(path, order)
    return {"order": order, "approved": approved_output.is_file(), "path": relative_path(path)}


def build_package() -> dict:
    command = ["make", "package"]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    output = (completed.stdout + "\n" + completed.stderr).strip()
    if completed.returncode:
        raise RuntimeError(output or f"make package exited with {completed.returncode}")
    return {"command": " ".join(command), "output": output}


class WorkbenchHandler(BaseHTTPRequestHandler):
    server_version = "TTDBuildingWorkbench/0.1"

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("[workbench] " + (format % args) + "\n")

    def send_json(self, data: object, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_payload(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 50 * 1024 * 1024:
            raise ValueError("request is too large")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8") or "{}")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/state":
                self.send_json({"orders": list_orders(), "manifest": manifest_rows(), "references": reference_assets()})
                return
            if parsed.path == "/api/file":
                query = parse_qs(parsed.query)
                value = unquote(query.get("path", [""])[0])
                path = repo_path(value)
                if not path.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND, "file not found")
                    return
                body = path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            path = (WEB_ROOT / parsed.path.lstrip("/")).resolve()
            if parsed.path in ("", "/", "/workbench", "/workbench/"):
                path = WORKBENCH_ROOT / "index.html"
            elif not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "page not found")
                return
            body = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (OSError, ValueError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_HEAD(self) -> None:  # noqa: N802
        """Serve headers for browser/dev-server probes without duplicating bodies."""
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.end_headers()
            return
        path = WORKBENCH_ROOT / "index.html" if parsed.path in ("", "/", "/workbench", "/workbench/") else (WEB_ROOT / parsed.path.lstrip("/")).resolve()
        if not path.is_file() or (ROOT not in path.parents and path != ROOT):
            self.send_error(HTTPStatus.NOT_FOUND, "page not found")
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = self.read_payload()
            if self.path == "/api/save":
                result = save_order(payload)
            elif self.path == "/api/run":
                result = run_action(payload.get("work_order_id"), payload.get("action"))
            elif self.path == "/api/approve":
                result = approve_order(payload)
            elif self.path == "/api/build":
                result = build_package()
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "unknown API endpoint")
                return
            self.send_json(result)
        except FileNotFoundError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        except (OSError, ValueError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), WorkbenchHandler)
    print(f"TTD workbench: http://{args.host}:{args.port}/workbench/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
