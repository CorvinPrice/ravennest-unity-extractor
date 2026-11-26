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


def export_assets_json(path: str, outdir: str) -> str:
    try:
        from unity_extract import export_assets, load_env

        env = load_env(Path(path))
        exported, skipped = export_assets(env, Path(outdir))
        return json.dumps(
            {
                "ok": True,
                "exported_count": len(exported),
                "skipped_count": len(skipped),
                "exported": [str(p) for p in exported],
                "skipped": skipped,
            },
            ensure_ascii=False,
        )
    except Exception as exc:  # JSON boundary: report, do not crash the UI thread
        return _error(exc)


def health_json() -> str:
    try:
        import UnityPy  # noqa: F401

        decoder_source = "not installed"
        try:
            from unitypy_patch import install_unitypy_texture_patch

            decoder_source = install_unitypy_texture_patch()
        except Exception as exc:
            decoder_source = f"patch failed: {exc}"
        return json.dumps(
            {"ok": True, "unitypy": True, "decoder_source": decoder_source},
            ensure_ascii=False,
        )
    except Exception as exc:
        return _error(exc)
