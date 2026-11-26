"""Android/Chaquopy bridge for the RavenNest Unity Extractor engine.

Kotlin copies the user's SAF selection into app-private files first, then calls
these functions with plain filesystem paths.  Every function returns a JSON
string so the Android UI does not need to understand Python objects.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def set_native_lib_dir(path: str) -> str:
    """Point the ctypes decoder bridge at Android's nativeLibraryDir."""

    if path:
        os.environ["RAVEN_NATIVE_LIB_DIR"] = str(path)
    return json.dumps({"ok": True, "native_lib_dir": os.environ.get("RAVEN_NATIVE_LIB_DIR", "")})


def _error(exc: Exception) -> str:
    return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)


def list_assets_json(path: str) -> str:
    try:
        from unity_extract import list_assets, load_env

        env = load_env(Path(path))
        assets = list_assets(env)
        return json.dumps(
            {"ok": True, "count": len(assets), "assets": assets},
            ensure_ascii=False,
        )
    except Exception as exc:  # JSON boundary: report, do not crash the UI thread
        return _error(exc)


def _write_progress(progress_path: str, payload: dict[str, Any]) -> None:
    if not progress_path:
        return
    try:
        target = Path(progress_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(target)
    except Exception:
        # Progress is best-effort; export correctness must not depend on it.
        pass


def export_assets_json(path: str, outdir: str, progress_path: str = "") -> str:
    try:
        from unity_extract import export_assets_with_summary, load_env

        _write_progress(
            progress_path,
            {"phase": "cargando", "processed": 0, "total": 0, "exported_count": 0, "skipped_count": 0},
        )
        env = load_env(Path(path))
        summary = export_assets_with_summary(
            env,
            Path(outdir),
            progress_callback=lambda payload: _write_progress(progress_path, payload),
        )
        return json.dumps(
            {
                "ok": True,
                "total_count": summary.total,
                "exported_count": summary.exported_count,
                "skipped_count": summary.skipped_count,
                "exported_sample": summary.exported_sample,
                "skipped": summary.skipped,
            },
            ensure_ascii=False,
        )
    except Exception as exc:  # JSON boundary: report, do not crash the UI thread
        _write_progress(
            progress_path,
            {"phase": "error", "processed": 0, "total": 0, "exported_count": 0, "skipped_count": 0, "error": str(exc)},
        )
        return _error(exc)


def health_json() -> str:
    try:
        decoder_source = "not installed"
        try:
            from unitypy_patch import install_unitypy_texture_patch

            decoder_source = install_unitypy_texture_patch()
        except Exception as exc:
            decoder_source = f"patch failed: {exc}"
        import UnityPy  # noqa: F401

        return json.dumps(
            {"ok": True, "unitypy": True, "decoder_source": decoder_source},
            ensure_ascii=False,
        )
    except Exception as exc:
        return _error(exc)
