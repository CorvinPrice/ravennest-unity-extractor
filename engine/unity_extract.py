#!/usr/bin/env python3
"""RavenNest Unity Extractor - MVP engine.

Scope: inspect a user's own Unity serialized files / bundles, list
Texture2D and Sprite assets, and export them as PNG using UnityPy.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, Iterator, List, Dict, Tuple, Any

SUPPORTED_TYPES = {"Texture2D", "Sprite"}
UNITY_FILE_PATTERNS = (
    re.compile(r"^level\d+$"),
    re.compile(r"^sharedassets\d+\.assets$"),
    re.compile(r".*\.assets$"),
    re.compile(r".*\.bundle$"),
    re.compile(r".*\.unity3d$"),
)


def type_name(obj: Any) -> str:
    t = getattr(obj, "type", None)
    name = getattr(t, "name", None)
    if isinstance(name, str):
        return name
    if isinstance(t, str):
        return t
    return ""


def read_obj(obj: Any) -> Any:
    read = getattr(obj, "read", None)
    if callable(read):
        return read()
    parse_as_object = getattr(obj, "parse_as_object", None)
    if callable(parse_as_object):
        return parse_as_object()
    return obj


def sanitize_name(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = name.strip("._-")
    return name or "asset"


def asset_name(obj: Any, data: Any = None) -> str:
    if data is None:
        try:
            data = read_obj(obj)
        except Exception:
            data = None
    for source in (data, obj):
        for attr in ("name", "m_Name"):
            name = getattr(source, attr, None)
            if isinstance(name, str) and name.strip():
                return sanitize_name(name)
    path_id = getattr(obj, "path_id", "unknown")
    return sanitize_name(f"asset_{path_id}")


def iter_supported_objects(env: Any) -> Iterator[Any]:
    for obj in getattr(env, "objects", []) or []:
        if type_name(obj) in SUPPORTED_TYPES:
            yield obj


def list_assets(env: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for obj in iter_supported_objects(env):
        rows.append(
            {
                "name": asset_name(obj),
                "type": type_name(obj),
                "path_id": getattr(obj, "path_id", None),
            }
        )
    return rows


def get_image(data: Any) -> Any:
    image = getattr(data, "image", None)
    if callable(image):
        image = image()
    return image


def unique_png_path(outdir: Path, base_name: str, used: set[str]) -> Path:
    base = sanitize_name(base_name)
    candidate = f"{base}.png"
    index = 2
    while candidate.lower() in used:
        candidate = f"{base}_{index}.png"
        index += 1
    used.add(candidate.lower())
    return outdir / candidate


def export_assets(env: Any, outdir: Path) -> Tuple[List[Path], List[Dict[str, Any]]]:
    outdir.mkdir(parents=True, exist_ok=True)
    exported: List[Path] = []
    skipped: List[Dict[str, Any]] = []
    used: set[str] = set()

    for obj in iter_supported_objects(env):
        name = asset_name(obj)
        try:
            data = read_obj(obj)
            image = get_image(data)
            if image is None:
                skipped.append({"name": name, "type": type_name(obj), "reason": "no image"})
                continue
            target = unique_png_path(outdir, name, used)
            image.save(target)
            exported.append(target)
        except Exception as exc:  # keep MVP resilient per-asset
            skipped.append({"name": name, "type": type_name(obj), "reason": str(exc)})

    return exported, skipped


def is_unity_input_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if any(pattern.match(path.name) for pattern in UNITY_FILE_PATTERNS):
        return True
    try:
        with path.open("rb") as fh:
            header = fh.read(8)
    except OSError:
        return False
    return header.startswith((b"UnityFS", b"UnityWeb", b"UnityRaw"))


def collect_inputs(path: Path) -> List[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(p for p in path.rglob("*") if is_unity_input_file(p))
    return []


def load_env(path: Path) -> Any:
    inputs = collect_inputs(path)
    if not inputs:
        raise RuntimeError(f"No Unity serialized files or bundles found under: {path}")

    try:
        from unitypy_patch import install_unitypy_texture_patch

        install_unitypy_texture_patch()
    except Exception:
        # Listing should still work if the texture converter patch cannot load;
        # export will surface the concrete decoder error per asset.
        pass

    try:
        import UnityPy  # type: ignore
    except ImportError as exc:
        raise RuntimeError("UnityPy is not installed. Install engine/requirements.txt first.") from exc

    return UnityPy.load(*[str(p) for p in inputs])


def cmd_list(args: argparse.Namespace) -> int:
    env = load_env(Path(args.path))
    for row in list_assets(env):
        print(f"{row['name']}\t{row['type']}\t{row['path_id']}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    env = load_env(Path(args.path))
    exported, skipped = export_assets(env, Path(args.outdir))
    for path in exported:
        print(path)
    for row in skipped:
        print(f"SKIP\t{row['name']}\t{row['type']}\t{row['reason']}", file=sys.stderr)
    print(f"Exported: {len(exported)}  Skipped: {len(skipped)}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RavenNest Unity Extractor MVP")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List Texture2D and Sprite assets")
    p_list.add_argument("path", help="Unity file, bundle, or *_Data folder")
    p_list.set_defaults(func=cmd_list)

    p_export = sub.add_parser("export", help="Export Texture2D and Sprite assets as PNG")
    p_export.add_argument("path", help="Unity file, bundle, or *_Data folder")
    p_export.add_argument("outdir", help="Output folder for PNG files")
    p_export.set_defaults(func=cmd_export)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return args.func(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
