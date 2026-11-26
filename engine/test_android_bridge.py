import json
import os
import tempfile
import unittest
from pathlib import Path

import android_bridge


class AndroidBridgeTests(unittest.TestCase):
    def test_set_native_lib_dir_returns_json(self):
        payload = json.loads(android_bridge.set_native_lib_dir("/tmp/native"))
        self.assertTrue(payload["ok"])
        self.assertEqual(os.environ["RAVEN_NATIVE_LIB_DIR"], "/tmp/native")

    def test_list_empty_folder_returns_json_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = json.loads(android_bridge.list_assets_json(tmp))
            self.assertFalse(payload["ok"])
            self.assertIn("No Unity serialized files", payload["error"])

    def test_export_empty_folder_returns_json_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = json.loads(android_bridge.export_assets_json(tmp, str(Path(tmp) / "out")))
            self.assertFalse(payload["ok"])
            self.assertIn("No Unity serialized files", payload["error"])


if __name__ == "__main__":
    unittest.main()
