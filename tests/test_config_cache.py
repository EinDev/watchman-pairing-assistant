import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "source"


def _load_main_module():
    customtkinter = types.ModuleType("customtkinter")
    customtkinter.CTk = type("CTk", (), {})
    customtkinter.CTkFrame = type("CTkFrame", (), {})
    customtkinter.CTkScrollableFrame = type("CTkScrollableFrame", (), {})
    customtkinter.CTkLabel = type("CTkLabel", (), {})
    customtkinter.CTkButton = type("CTkButton", (), {})
    customtkinter.CTkTextbox = type("CTkTextbox", (), {})
    customtkinter.END = "end"
    customtkinter.set_default_color_theme = lambda *args, **kwargs: None
    customtkinter.set_appearance_mode = lambda *args, **kwargs: None

    usb_util = types.ModuleType("usb_util")
    usb_util.find_hmd = lambda: []

    sys.modules["customtkinter"] = customtkinter
    sys.modules["usb_util"] = usb_util

    if str(SOURCE_DIR) not in sys.path:
        sys.path.insert(0, str(SOURCE_DIR))

    sys.modules.pop("main", None)
    return importlib.import_module("main")


class ConfigCacheTests(unittest.TestCase):
    def setUp(self):
        self.main = _load_main_module()
        self.app = types.SimpleNamespace(_config=None)
        self.app.load_config = lambda: self.main.App.load_config(self.app)

    def test_get_exe_path_uses_cached_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "watchman-pairing-assistant"
            config_dir.mkdir()
            config_path = config_dir / "config.json"
            config_path.write_text(json.dumps({
                "theme": "Dark",
                "lighthouse_console_path": "/tmp/lighthouse_console",
            }))

            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": temp_dir}, clear=False):
                with mock.patch.object(self.main.json, "load", wraps=self.main.json.load) as json_load:
                    first = self.main.App.get_exe_path(self.app)
                    second = self.main.App.get_exe_path(self.app)

            self.assertEqual(first, "/tmp/lighthouse_console")
            self.assertEqual(second, "/tmp/lighthouse_console")
            self.assertEqual(json_load.call_count, 1)

    def test_load_config_creates_default_config_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": temp_dir}, clear=False):
                first = self.main.App.load_config(self.app)
                second = self.main.App.load_config(self.app)

            config_path = Path(temp_dir) / "watchman-pairing-assistant" / "config.json"
            self.assertTrue(config_path.exists())
            self.assertIs(first, second)
            self.assertEqual(second["theme"], "Dark")


if __name__ == "__main__":
    unittest.main()
