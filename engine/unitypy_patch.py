"""Runtime patch that lets UnityPy export compressed textures on Android.

UnityPy's Texture2DConverter imports ``astc_encoder`` and
``texture2ddecoder`` at module import time, and UnityPy's export package also
imports an FMOD helper.  On Android we do not ship those desktop wheels.  This
patch installs small stubs plus Raven's decoder (native ctypes bridge when the
.so is present, pure ETC/EAC/ATC fallback otherwise) before UnityPy tries to
decode a Texture2D or Sprite.
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


def _install_stub_if_missing(name: str, factory) -> bool:
    if name in sys.modules:
        return False
    try:
        importlib.import_module(name)
        return False
    except Exception:
        sys.modules[name] = factory()
        return True


def install_unitypy_texture_patch() -> str:
    """Patch UnityPy's texture converter and return the decoder source name."""

    global _PATCHED, _DECODER_SOURCE
    if _PATCHED:
        return _DECODER_SOURCE

    decoder, source = _load_decoder()
    if sys.modules.get("texture2ddecoder") is not decoder:
        sys.modules["texture2ddecoder"] = decoder
    astc_stubbed = _install_stub_if_missing("astc_encoder", _astc_encoder_stub)
    _install_stub_if_missing("fmod_toolkit", _fmod_stub)

    converter = importlib.import_module("UnityPy.export.Texture2DConverter")
    converter.texture2ddecoder = decoder

    def astc_via_decoder(image_data, width, height, block_size, hdr=False):
        from PIL import Image

        if not hasattr(decoder, "decode_astc"):
            raise RuntimeError("ASTC decode requires libraven_texture2ddecoder.so")
        texture_size = converter.calculate_astc_compressed_size(width, height, block_size)
        if len(image_data) < texture_size:
            raise ValueError(f"Invalid ASTC data size: {len(image_data)} < {texture_size}")
        decoded = decoder.decode_astc(
            bytes(image_data[:texture_size]), width, height, int(block_size[0]), int(block_size[1])
        )
        return Image.frombytes("RGBA", (width, height), decoded, "raw", "BGRA")

    converter.astc = astc_via_decoder
    for texture_format, (_func, args) in list(converter.CONV_TABLE.items()):
        if texture_format.name.startswith("ASTC"):
            converter.CONV_TABLE[texture_format] = (astc_via_decoder, args)

    if astc_stubbed:
        def _no_astc_encoder_context(*args, **kwargs):
            raise RuntimeError("ASTC compression/contexts are not bundled; export decode uses Raven's texture decoder")

        converter.get_astc_context = _no_astc_encoder_context
    _PATCHED = True
    _DECODER_SOURCE = source
    return source
