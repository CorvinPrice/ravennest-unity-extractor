"""Runtime patch that lets UnityPy export compressed textures on Android.

UnityPy's Texture2DConverter imports native helper packages at module import
time.  On Android we do not ship those desktop wheels.  This patch installs
small stubs plus Raven's decoder (native ctypes bridge when the .so is
present, pure ETC/EAC/ATC fallback otherwise) before UnityPy tries to decode a
Texture2D or Sprite.

The patch is deliberately defensive across UnityPy versions: Android pins
UnityPy 1.7.43 (the py3-none-any wheel Chaquopy can install), while desktop
tests may run a newer UnityPy.  The core engine API used by RavenNest
(``UnityPy.load``, ``env.objects``, ``obj.type.name``, ``obj.read()`` and
``data.image``) is present in both, but converter internals differ.
"""

from __future__ import annotations

import importlib
import os
import sys
from types import ModuleType
from typing import Any

_PATCHED = False
_DECODER_SOURCE = "not installed"


def _astc_encoder_stub() -> ModuleType:
    module = ModuleType("astc_encoder")

    class _Unavailable:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("astc_encoder is not bundled; ASTC decode uses Raven's texture decoder")

    class _EnumValue:
        def __init__(self, name):
            self.name = name

    class _ASTCType:
        U8 = _EnumValue("U8")

    class _ASTCProfile:
        LDR = _EnumValue("LDR")
        HDR = _EnumValue("HDR")

    class _ASTCConfigFlags:
        USE_DECODE_UNORM8 = _EnumValue("USE_DECODE_UNORM8")

    class _ASTCSwizzle:
        @staticmethod
        def from_str(value):
            return value

    module.ASTCImage = _Unavailable
    module.ASTCContext = _Unavailable
    module.ASTCConfig = _Unavailable
    module.ASTCType = _ASTCType
    module.ASTCProfile = _ASTCProfile
    module.ASTCConfigFlags = _ASTCConfigFlags
    module.ASTCSwizzle = _ASTCSwizzle
    return module


def _fmod_stub() -> ModuleType:
    module = ModuleType("fmod_toolkit")

    def raw_to_wav(*args, **kwargs):
        raise RuntimeError("FMOD audio conversion is not bundled in the texture exporter")

    module.raw_to_wav = raw_to_wav
    return module


def _pyfmodex_stub() -> ModuleType:
    module = ModuleType("pyfmodex")

    def _unavailable(*args, **kwargs):
        raise RuntimeError("FMOD audio conversion is not bundled in the texture exporter")

    module.System = _unavailable
    return module


def _etcpak_stub() -> ModuleType:
    module = ModuleType("etcpak")

    def _unavailable(*args, **kwargs):
        raise RuntimeError("etcpak compression is not bundled; texture export only needs decoding")

    for name in (
        "compress_etc1",
        "compress_etc2",
        "compress_etc2a1",
        "compress_etc2a8",
        "compress_eacr",
        "compress_eacr_signed",
        "compress_eacrg",
        "compress_eacrg_signed",
        # Names used by UnityPy 1.7.43's Texture2DConverter.image_to_texture2d.
        "compress_to_dxt1",
        "compress_to_dxt5",
        "compress_to_etc1",
        "compress_to_etc2_rgb",
        "compress_to_etc2_rgba",
    ):
        setattr(module, name, _unavailable)
    return module


def _load_decoder() -> tuple[Any, str]:
    forced = os.environ.get("RAVEN_TEXTURE2DDECODER", "").lower()
    if forced == "pure":
        from pure_texture_decoders import as_module

        return as_module(), "raven pure ETC/EAC/ATC fallback"
    if forced != "native":
        try:
            import texture2ddecoder  # type: ignore

            return texture2ddecoder, "texture2ddecoder wheel"
        except Exception:
            pass
    try:
        from native_texture2ddecoder import load_native_texture2ddecoder

        return load_native_texture2ddecoder(), "raven native ctypes bridge"
    except Exception:
        from pure_texture_decoders import as_module

        return as_module(), "raven pure ETC/EAC/ATC fallback"


def _install_decoder_aliases(decoder: Any) -> None:
    """Add old texture2ddecoder names used by older UnityPy converters."""

    aliases = {
        "decode_dxt1": "decode_bc1",
        "decode_dxt5": "decode_bc3",
        "decode_bc2": "decode_bc3",
    }
    for alias, target in aliases.items():
        if not hasattr(decoder, alias) and hasattr(decoder, target):
            try:
                setattr(decoder, alias, getattr(decoder, target))
            except Exception:
                pass


def _install_stub_if_missing(name: str, factory) -> bool:
    if name in sys.modules:
        return False
    try:
        importlib.import_module(name)
        return False
    except Exception:
        sys.modules[name] = factory()
        return True


def _install_tkinter_stub() -> bool:
    """Stub tkinter for UnityPy 1.7.43 on Android/Chaquopy.

    UnityPy 1.7.43's ``UnityPy/classes/GameObject.py`` starts with
    ``from tkinter.messagebox import NO`` even though the constant is unused.
    Chaquopy has no tkinter, so that stray desktop import makes the whole
    ``import UnityPy`` fail before any asset can be listed.  Install a tiny
    package stub only when the real tkinter is unavailable.
    """

    if "tkinter.messagebox" in sys.modules and sys.modules["tkinter.messagebox"] is not None:
        return False
    try:
        importlib.import_module("tkinter.messagebox")
        return False
    except Exception:
        pass

    tkinter = ModuleType("tkinter")
    tkinter.__path__ = []  # mark as a package so submodule imports resolve
    messagebox = ModuleType("tkinter.messagebox")
    messagebox.NO = "no"
    messagebox.YES = "yes"
    messagebox.OK = "ok"
    messagebox.CANCEL = "cancel"
    messagebox.ABORT = "abort"
    messagebox.RETRY = "retry"
    messagebox.IGNORE = "ignore"

    def _unavailable(*args, **kwargs):
        raise RuntimeError("tkinter is not bundled on Android")

    for name in (
        "showinfo",
        "showwarning",
        "showerror",
        "askquestion",
        "askokcancel",
        "askyesno",
        "askretrycancel",
    ):
        setattr(messagebox, name, _unavailable)
    tkinter.messagebox = messagebox
    sys.modules["tkinter"] = tkinter
    sys.modules["tkinter.messagebox"] = messagebox
    return True


def _astc_compressed_size(converter: Any, width: int, height: int, block_size: Any) -> int:
    helper = getattr(converter, "calculate_astc_compressed_size", None)
    if callable(helper):
        return int(helper(width, height, block_size))
    block_width, block_height = int(block_size[0]), int(block_size[1])
    return ((width + block_width - 1) // block_width) * ((height + block_height - 1) // block_height) * 16


def _patch_converter_table(converter: Any, astc_via_decoder: Any) -> None:
    table = getattr(converter, "CONV_TABLE", None)
    if not isinstance(table, dict):
        return
    for texture_format, value in list(table.items()):
        format_name = getattr(texture_format, "name", str(texture_format))
        if not str(format_name).startswith("ASTC"):
            continue
        if isinstance(value, tuple):
            table[texture_format] = (astc_via_decoder, *value[1:])
        elif isinstance(value, list):
            table[texture_format] = [astc_via_decoder, *value[1:]]
        elif callable(value):
            table[texture_format] = astc_via_decoder


def install_unitypy_texture_patch() -> str:
    """Patch UnityPy's texture converter and return the decoder source name."""

    global _PATCHED, _DECODER_SOURCE
    if _PATCHED:
        return _DECODER_SOURCE

    _install_tkinter_stub()
    decoder, source = _load_decoder()
    _install_decoder_aliases(decoder)
    if sys.modules.get("texture2ddecoder") is not decoder:
        sys.modules["texture2ddecoder"] = decoder
    astc_stubbed = _install_stub_if_missing("astc_encoder", _astc_encoder_stub)
    _install_stub_if_missing("fmod_toolkit", _fmod_stub)
    _install_stub_if_missing("pyfmodex", _pyfmodex_stub)
    _install_stub_if_missing("etcpak", _etcpak_stub)

    try:
        converter = importlib.import_module("UnityPy.export.Texture2DConverter")
    except Exception as exc:
        _PATCHED = True
        _DECODER_SOURCE = f"{source} (converter patch unavailable: {exc})"
        return _DECODER_SOURCE

    try:
        converter.texture2ddecoder = decoder
    except Exception:
        pass

    def astc_via_decoder(image_data, width, height, block_size, hdr=False):
        from PIL import Image

        if not hasattr(decoder, "decode_astc"):
            raise RuntimeError("ASTC decode requires libraven_texture2ddecoder.so")
        texture_size = _astc_compressed_size(converter, width, height, block_size)
        if len(image_data) < texture_size:
            raise ValueError(f"Invalid ASTC data size: {len(image_data)} < {texture_size}")
        decoded = decoder.decode_astc(
            bytes(image_data[:texture_size]), width, height, int(block_size[0]), int(block_size[1])
        )
        return Image.frombytes("RGBA", (width, height), decoded, "raw", "BGRA")

    try:
        converter.astc = astc_via_decoder
    except Exception:
        pass
    _patch_converter_table(converter, astc_via_decoder)

    if astc_stubbed and hasattr(converter, "get_astc_context"):
        def _no_astc_encoder_context(*args, **kwargs):
            raise RuntimeError("ASTC compression/contexts are not bundled; export decode uses Raven's texture decoder")

        converter.get_astc_context = _no_astc_encoder_context
    _PATCHED = True
    _DECODER_SOURCE = source
    return source
