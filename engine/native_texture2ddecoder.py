"""ctypes bridge for RavenNest's native Texture2D decoder library.

The native library exposes the same small surface UnityPy needs from
``texture2ddecoder``: BGRA8888 block decoders plus Crunch unpacking.  It is a
plain C ABI shared library, so Chaquopy can load it from the APK's jniLibs
without needing a Python C-extension wheel for every ABI.
"""

from __future__ import annotations

import ctypes
import os
import platform
from pathlib import Path
from types import ModuleType
from typing import Iterable, Optional

LIB_BASENAME = "libraven_texture2ddecoder.so"


def _abi_name() -> str:
    machine = platform.machine().lower()
    if machine in {"aarch64", "arm64"}:
        return "arm64-v8a"
    if machine in {"x86_64", "amd64"}:
        return "x86_64"
    if machine.startswith("arm"):
        return "armeabi-v7a"
    return machine


def _candidate_paths(explicit: Optional[str | os.PathLike[str]] = None) -> Iterable[Path]:
    if explicit:
        yield Path(explicit)
    env_lib = os.environ.get("RAVEN_TEXTURE2DDECODER_LIB")
    if env_lib:
        yield Path(env_lib)
    env_dir = os.environ.get("RAVEN_NATIVE_LIB_DIR")
    if env_dir:
        yield Path(env_dir) / LIB_BASENAME

    here = Path(__file__).resolve()
    root = here.parent.parent
    abi = _abi_name()
    yield root / "native" / "build" / "host" / LIB_BASENAME
    yield root / "native" / "build" / f"android-{abi}" / LIB_BASENAME
    yield root / "android" / "app" / "src" / "main" / "jniLibs" / abi / LIB_BASENAME
    yield here.parent / LIB_BASENAME
    yield Path.cwd() / LIB_BASENAME


def _load_library(explicit: Optional[str | os.PathLike[str]] = None) -> ctypes.CDLL:
    errors: list[str] = []
    for path in _candidate_paths(explicit):
        try:
            if path.is_file():
                return ctypes.CDLL(str(path))
        except OSError as exc:
            errors.append(f"{path}: {exc}")
    try:
        return ctypes.CDLL(LIB_BASENAME)
    except OSError as exc:
        errors.append(f"{LIB_BASENAME}: {exc}")
    raise ImportError("Raven native texture decoder not found: " + "; ".join(errors))


class NativeTexture2DDecoder(ModuleType):
    """Module-shaped wrapper around libraven_texture2ddecoder."""

    __version__ = "raven-native-1"

    def __init__(self, lib: ctypes.CDLL):
        super().__init__("texture2ddecoder")
        self._lib = lib
        self._bind()

    def _bind(self) -> None:
        lib = self._lib
        decode_argtypes = [
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_uint32,
            ctypes.c_int32,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_uint32,
        ]
        for name in (
            "raven_decode_bc1",
            "raven_decode_bc3",
            "raven_decode_bc4",
            "raven_decode_bc5",
            "raven_decode_bc6",
            "raven_decode_bc7",
            "raven_decode_atc_rgb4",
            "raven_decode_atc_rgba8",
            "raven_decode_etc1",
            "raven_decode_etc2",
            "raven_decode_etc2a1",
            "raven_decode_etc2a8",
            "raven_decode_eacr",
            "raven_decode_eacr_signed",
            "raven_decode_eacrg",
            "raven_decode_eacrg_signed",
        ):
            fn = getattr(lib, name)
            fn.argtypes = decode_argtypes
            fn.restype = ctypes.c_int
        lib.raven_decode_pvrtc.argtypes = [
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_uint32,
            ctypes.c_int32,
            ctypes.c_int32,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_uint32,
        ]
        lib.raven_decode_pvrtc.restype = ctypes.c_int
        lib.raven_decode_astc.argtypes = [
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_uint32,
            ctypes.c_int32,
            ctypes.c_int32,
            ctypes.c_int32,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_uint32,
        ]
        lib.raven_decode_astc.restype = ctypes.c_int
        for name in ("raven_unpack_crunch", "raven_unpack_unity_crunch"):
            fn = getattr(lib, name)
            fn.argtypes = [
                ctypes.POINTER(ctypes.c_ubyte),
                ctypes.c_uint32,
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
                ctypes.POINTER(ctypes.c_uint32),
            ]
            fn.restype = ctypes.c_int
        lib.raven_free.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
        lib.raven_free.restype = None

    @staticmethod
    def _input(data: bytes | bytearray | memoryview) -> tuple[ctypes.Array, int]:
        raw = bytes(data)
        if not raw:
            raise ValueError("empty texture data")
        buf = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        return buf, len(raw)

    def _decode(self, fn_name: str, data: bytes | bytearray | memoryview, width: int, height: int, *extra: int) -> bytes:
        if width <= 0 or height <= 0:
            raise ValueError("texture dimensions must be positive")
        in_buf, in_size = self._input(data)
        out_size = int(width) * int(height) * 4
        out_buf = (ctypes.c_ubyte * out_size)()
        fn = getattr(self._lib, fn_name)
        ok = fn(in_buf, in_size, int(width), int(height), *[int(x) for x in extra], out_buf, out_size)
        if not ok:
            raise RuntimeError(f"{fn_name} failed")
        return bytes(out_buf)

    def decode_bc1(self, data, width, height):
        return self._decode("raven_decode_bc1", data, width, height)

    def decode_bc3(self, data, width, height):
        return self._decode("raven_decode_bc3", data, width, height)

    def decode_dxt1(self, data, width, height):
        return self.decode_bc1(data, width, height)

    def decode_dxt5(self, data, width, height):
        return self.decode_bc3(data, width, height)

    def decode_bc2(self, data, width, height):
        return self.decode_bc3(data, width, height)

    def decode_bc4(self, data, width, height):
        return self._decode("raven_decode_bc4", data, width, height)

    def decode_bc5(self, data, width, height):
        return self._decode("raven_decode_bc5", data, width, height)

    def decode_bc6(self, data, width, height):
        return self._decode("raven_decode_bc6", data, width, height)

    def decode_bc7(self, data, width, height):
        return self._decode("raven_decode_bc7", data, width, height)

    def decode_atc_rgb4(self, data, width, height):
        return self._decode("raven_decode_atc_rgb4", data, width, height)

    def decode_atc_rgba8(self, data, width, height):
        return self._decode("raven_decode_atc_rgba8", data, width, height)

    def decode_etc1(self, data, width, height):
        return self._decode("raven_decode_etc1", data, width, height)

    def decode_etc2(self, data, width, height):
        return self._decode("raven_decode_etc2", data, width, height)

    def decode_etc2a1(self, data, width, height):
        return self._decode("raven_decode_etc2a1", data, width, height)

    def decode_etc2a8(self, data, width, height):
        return self._decode("raven_decode_etc2a8", data, width, height)

    def decode_eacr(self, data, width, height):
        return self._decode("raven_decode_eacr", data, width, height)

    def decode_eacr_signed(self, data, width, height):
        return self._decode("raven_decode_eacr_signed", data, width, height)

    def decode_eacrg(self, data, width, height):
        return self._decode("raven_decode_eacrg", data, width, height)

    def decode_eacrg_signed(self, data, width, height):
        return self._decode("raven_decode_eacrg_signed", data, width, height)

    def decode_pvrtc(self, data, width, height, is2bpp=False):
        return self._decode("raven_decode_pvrtc", data, width, height, 1 if is2bpp else 0)

    def decode_astc(self, data, width, height, block_width, block_height):
        return self._decode("raven_decode_astc", data, width, height, int(block_width), int(block_height))

    def _unpack(self, fn_name: str, data: bytes | bytearray | memoryview, level_index: int = 0) -> bytes:
        in_buf, in_size = self._input(data)
        out_ptr = ctypes.POINTER(ctypes.c_ubyte)()
        out_size = ctypes.c_uint32(0)
        fn = getattr(self._lib, fn_name)
        ok = fn(in_buf, in_size, int(level_index), ctypes.byref(out_ptr), ctypes.byref(out_size))
        if not ok or not out_ptr or out_size.value == 0:
            raise RuntimeError(f"{fn_name} failed")
        try:
            return ctypes.string_at(out_ptr, out_size.value)
        finally:
            self._lib.raven_free(out_ptr)

    def unpack_crunch(self, data, level_index: int = 0):
        return self._unpack("raven_unpack_crunch", data, level_index)

    def unpack_unity_crunch(self, data, level_index: int = 0):
        return self._unpack("raven_unpack_unity_crunch", data, level_index)


def load_native_texture2ddecoder(path: Optional[str | os.PathLike[str]] = None) -> NativeTexture2DDecoder:
    return NativeTexture2DDecoder(_load_library(path))
