import os
import random
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
