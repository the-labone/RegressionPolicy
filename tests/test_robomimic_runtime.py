"""Legacy rendering configuration must stay local and work before first rollout."""

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "ht_regression/evaluation/robomimic/runtime.py"
)
SPEC = importlib.util.spec_from_file_location("robomimic_runtime", SOURCE)
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class RuntimeTests(unittest.TestCase):
    def test_external_environments_are_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            with (
                patch.object(runtime.sys, "prefix", folder),
                patch.object(runtime, "_handles", []),
                patch.object(runtime.ctypes, "CDLL") as load,
                patch.dict(os.environ, {"MUJOCO_GL": "egl"}, clear=True),
            ):
                runtime.configure_runtime()
                load.assert_not_called()
                self.assertEqual(dict(os.environ), {"MUJOCO_GL": "egl"})

    def test_local_runtime_preloads_osmesa_and_preserves_existing_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            prefix = Path(folder)
            root = prefix / "local runtime"
            libraries = root / "usr/lib/x86_64-linux-gnu"
            config = {"root": str(root), "mujoco_bin": str(prefix / "mujoco/bin")}
            (prefix / "robomimic-runtime.json").write_text(json.dumps(config))
            with (
                patch.object(runtime.sys, "prefix", folder),
                patch.object(runtime, "_handles", []),
                patch.object(runtime.ctypes, "CDLL") as load,
                patch.dict(os.environ, {"LD_LIBRARY_PATH": "/existing"}, clear=True),
            ):
                runtime.configure_runtime()
                configured = dict(os.environ)
                runtime.configure_runtime()
                self.assertEqual(dict(os.environ), configured)
                load.assert_called_once_with(
                    str(libraries / "libOSMesa.so.8"), runtime.ctypes.RTLD_GLOBAL
                )
                self.assertEqual(os.environ["MUJOCO_PY_FORCE_CPU"], "1")
                self.assertEqual(os.environ["MUJOCO_GL"], "osmesa")
                self.assertEqual(
                    os.environ["LD_LIBRARY_PATH"],
                    f"{libraries}:{config['mujoco_bin']}:/existing",
                )


if __name__ == "__main__":
    unittest.main()
