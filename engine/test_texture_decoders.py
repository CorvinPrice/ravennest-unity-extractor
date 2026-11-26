import os
import random
import sys
import types
import unittest


def _native_or_skip(testcase):
    try:
        from native_texture2ddecoder import load_native_texture2ddecoder

        return load_native_texture2ddecoder()
    except Exception as exc:
        testcase.skipTest(f"native decoder unavailable: {exc}")


class PureDecoderTests(unittest.TestCase):
    def test_pure_etc_eac_atc_match_native_on_random_blocks(self):
        native = _native_or_skip(self)
        import pure_texture_decoders as pure

        rng = random.Random(20261126)
        cases = [
            ("decode_etc1", 8, ()),
            ("decode_etc2", 8, ()),
            ("decode_etc2a1", 8, ()),
            ("decode_etc2a8", 16, ()),
            ("decode_eacr", 8, ()),
            ("decode_eacr_signed", 8, ()),
            ("decode_eacrg", 16, ()),
            ("decode_eacrg_signed", 16, ()),
            ("decode_atc_rgb4", 8, ()),
            ("decode_atc_rgba8", 16, ()),
        ]
        width, height = 12, 8
        blocks = (width // 4) * (height // 4)
        for name, block_bytes, _args in cases:
            data = bytes(rng.randrange(256) for _ in range(blocks * block_bytes))
            with self.subTest(name=name):
                self.assertEqual(getattr(pure, name)(data, width, height), getattr(native, name)(data, width, height))

    def test_native_invalid_crunch_raises_not_crashes(self):
        native = _native_or_skip(self)
        with self.assertRaises(RuntimeError):
            native.unpack_unity_crunch(b"not a crunch stream")


class UnityPyPatchCompatibilityTests(unittest.TestCase):
    def test_tkinter_stub_satisfies_unitypy_1743_gameobject_import(self):
        import unitypy_patch

        old_modules = {name: sys.modules.get(name) for name in ("tkinter", "tkinter.messagebox")}
        try:
            sys.modules["tkinter"] = None
            sys.modules.pop("tkinter.messagebox", None)

            self.assertTrue(unitypy_patch._install_tkinter_stub())
            from tkinter.messagebox import NO

            self.assertEqual(NO, "no")
        finally:
            for name, module in old_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

    def test_patch_handles_old_converter_shape_and_decoder_aliases(self):
        import unitypy_patch

        old_patched = unitypy_patch._PATCHED
        old_source = unitypy_patch._DECODER_SOURCE
        old_modules = {name: sys.modules.get(name) for name in ("UnityPy", "UnityPy.export", "UnityPy.export.Texture2DConverter", "texture2ddecoder", "etcpak")}
        os.environ["RAVEN_TEXTURE2DDECODER"] = "pure"
        try:
            unitypy_patch._PATCHED = False
            unitypy_patch._DECODER_SOURCE = "not installed"
            unitypy = types.ModuleType("UnityPy")
            export = types.ModuleType("UnityPy.export")
            converter = types.ModuleType("UnityPy.export.Texture2DConverter")

            class FakeFormat:
                def __init__(self, name):
                    self.name = name

            astc_format = FakeFormat("ASTC_RGBA_4x4")
            dxt_format = FakeFormat("DXT1")
            converter.CONV_TABLE = {
                astc_format: (lambda *args: None, ((4, 4),)),
                dxt_format: lambda *args: None,
            }
            unitypy.export = export
            export.Texture2DConverter = converter
            sys.modules["UnityPy"] = unitypy
            sys.modules["UnityPy.export"] = export
            sys.modules["UnityPy.export.Texture2DConverter"] = converter
            sys.modules.pop("texture2ddecoder", None)
            sys.modules.pop("etcpak", None)

            source = unitypy_patch.install_unitypy_texture_patch()

            self.assertEqual(source, "raven pure ETC/EAC/ATC fallback")
            self.assertIs(converter.texture2ddecoder, sys.modules["texture2ddecoder"])
            self.assertTrue(hasattr(converter.texture2ddecoder, "decode_dxt1"))
            self.assertTrue(hasattr(converter.texture2ddecoder, "decode_dxt5"))
            self.assertEqual(converter.CONV_TABLE[astc_format][0], converter.astc)
            self.assertEqual(converter.CONV_TABLE[astc_format][1], ((4, 4),))
            self.assertIn("etcpak", sys.modules)
            self.assertTrue(hasattr(sys.modules["etcpak"], "compress_to_dxt1"))
        finally:
            unitypy_patch._PATCHED = old_patched
            unitypy_patch._DECODER_SOURCE = old_source
            for name, module in old_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module


class UnityPySyntheticTests(unittest.TestCase):
    def test_parse_image_data_exports_compressed_formats_with_native_patch(self):
        try:
            import UnityPy  # noqa: F401
            from PIL import Image
            from UnityPy.enums import BuildTarget, TextureFormat
            from UnityPy.export.Texture2DConverter import image_to_texture2d, parse_image_data
        except Exception as exc:
            self.skipTest(f"UnityPy synthetic test unavailable: {exc}")

        os.environ["RAVEN_TEXTURE2DDECODER"] = "native"
        from unitypy_patch import install_unitypy_texture_patch

        self.assertEqual(install_unitypy_texture_patch(), "raven native ctypes bridge")

        img = Image.new("RGBA", (16, 16))
        px = img.load()
        for y in range(16):
            for x in range(16):
                px[x, y] = (x * 16, y * 16, 128, 255)

        for fmt in (
            TextureFormat.DXT1,
            TextureFormat.DXT5,
            TextureFormat.BC7,
            TextureFormat.ETC2_RGBA8,
            TextureFormat.ASTC_RGBA_4x4,
        ):
            with self.subTest(format=fmt.name):
                data, _tex_format = image_to_texture2d(img, fmt)
                decoded = parse_image_data(data, 16, 16, fmt, (2022, 3, 0, 0), BuildTarget.UnknownPlatform)
                self.assertEqual(decoded.size, (16, 16))
                self.assertEqual(decoded.mode, "RGBA")


if __name__ == "__main__":
    unittest.main()
