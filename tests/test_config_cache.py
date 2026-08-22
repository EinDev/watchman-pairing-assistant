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

    def test_execute_subprocess_handles_missing_executable(self):
        logs = []
        app = types.SimpleNamespace(insert_log=logs.append)

        with mock.patch("main.subprocess.run", side_effect=FileNotFoundError):
            output = self.main.App.execute_subprocess(app, "serial", "C:/missing/lighthouse_console.exe")

        self.assertEqual(output, "")
        self.assertEqual(logs, ["Could not find lighthouse_console executable: C:/missing/lighthouse_console.exe"])

    def test_execute_subprocess_serial_handles_missing_executable(self):
        logs = []
        app = types.SimpleNamespace(insert_log=logs.append)

        with mock.patch("main.subprocess.Popen", side_effect=FileNotFoundError):
            self.main.App.execute_subprocess_serial(app, "abc", "pair", "C:/missing/lighthouse_console.exe")

        self.assertEqual(logs, ["Could not find lighthouse_console executable: C:/missing/lighthouse_console.exe"])

    def test_windows_default_lh_console_path_is_absolute(self):
        import ntpath
        with tempfile.TemporaryDirectory() as temp_dir:
            env = {
                "APPDATA": temp_dir,
                "ProgramFiles(x86)": r"C:\Program Files (x86)",
            }
            with mock.patch.dict(os.environ, env, clear=False):
                with mock.patch.object(self.main.sys, "platform", "win32"):
                    config = self.main.App.load_config(self.app)

        lh_path = config["lighthouse_console_path"]
        self.assertTrue(
            ntpath.isabs(lh_path),
            f"Expected absolute Windows path but got: {lh_path!r}",
        )

    def test_windows_migration_fixes_drive_relative_path(self):
        import ntpath
        broken_path = r"C:Program Files (x86)\Steam\steamapps\common\SteamVR\tools\lighthouse\bin\win64\lighthouse_console.exe"
        fixed_path = r"C:\Program Files (x86)\Steam\steamapps\common\SteamVR\tools\lighthouse\bin\win64\lighthouse_console.exe"

        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "watchman-pairing-assistant"
            config_dir.mkdir()
            config_path = config_dir / "config.json"
            config_path.write_text(json.dumps({
                "theme": "Dark",
                "lighthouse_console_path": broken_path,
            }))

            env = {"APPDATA": temp_dir}
            with mock.patch.dict(os.environ, env, clear=False):
                with mock.patch.object(self.main.sys, "platform", "win32"):
                    config = self.main.App.load_config(self.app)

        self.assertEqual(config["lighthouse_console_path"], fixed_path)
        self.assertTrue(ntpath.isabs(config["lighthouse_console_path"]))


if __name__ == "__main__":
    unittest.main()
