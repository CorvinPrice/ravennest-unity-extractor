import tempfile
import unittest
from pathlib import Path

import unity_extract


class FakeType:
    def __init__(self, name):
        self.name = name


class FakeImage:
    def save(self, path):
        Path(path).write_bytes(b"PNG")


class FakeData:
    def __init__(self, name, image=None):
        self.name = name
        self.image = image


class FakeObj:
    def __init__(self, type_name, path_id, data):
        self.type = FakeType(type_name)
        self.path_id = path_id
        self._data = data

    def read(self):
        return self._data


class FakeEnv:
    def __init__(self, objects):
        self.objects = objects


class ParseOnlyObj:
    type = FakeType("Texture2D")
    path_id = 9

    def parse_as_object(self):
        data = FakeData("", FakeImage())
        data.m_Name = "Parsed Name"
        return data


class UnityExtractTests(unittest.TestCase):
    def test_list_filters_supported_types(self):
        env = FakeEnv([
            FakeObj("Texture2D", 1, FakeData("Hero", FakeImage())),
            FakeObj("Mesh", 2, FakeData("Ignored", FakeImage())),
            FakeObj("Sprite", 3, FakeData("Tile", FakeImage())),
        ])
        rows = unity_extract.list_assets(env)
        self.assertEqual([r["name"] for r in rows], ["Hero", "Tile"])
        self.assertEqual([r["type"] for r in rows], ["Texture2D", "Sprite"])

    def test_export_dedupes_names_and_skips_missing_image(self):
        env = FakeEnv([
            FakeObj("Texture2D", 1, FakeData("Same Name", FakeImage())),
            FakeObj("Sprite", 2, FakeData("Same Name", FakeImage())),
            FakeObj("Texture2D", 3, FakeData("NoImage", None)),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            exported, skipped = unity_extract.export_assets(env, Path(tmp))
            self.assertEqual([p.name for p in exported], ["Same_Name.png", "Same_Name_2.png"])
            self.assertEqual(len(skipped), 1)
            self.assertEqual(skipped[0]["name"], "NoImage")
            for path in exported:
                self.assertTrue(path.exists())

    def test_parse_as_object_and_m_name_fallbacks(self):
        rows = unity_extract.list_assets(FakeEnv([ParseOnlyObj()]))
        self.assertEqual(rows[0]["name"], "Parsed_Name")

    def test_collect_inputs_finds_unity_files_in_data_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "level0").write_bytes(b"x")
            (root / "sharedassets0.assets").write_bytes(b"x")
            (root / "sharedassets0.assets.resS").write_bytes(b"x")
            (root / "bundle_no_ext").write_bytes(b"UnityFS\x00")
            (root / "readme.txt").write_text("x")
            found = [p.name for p in unity_extract.collect_inputs(root)]
            self.assertEqual(found, ["bundle_no_ext", "level0", "sharedassets0.assets"])


if __name__ == "__main__":
    unittest.main()
