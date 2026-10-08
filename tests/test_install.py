"""Check that installation can be repeated without replacing user state."""

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/install.py"
SPEC = importlib.util.spec_from_file_location("install", SCRIPT)
install = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        contexts = contextlib.ExitStack()
        self.addCleanup(contexts.close)
        for name, path in (
            ("SOURCES", self.root / "sources"),
            ("ENVS", self.root / "envs"),
            ("PATCHES", self.root / "patches"),
        ):
            contexts.enter_context(patch.object(install, name, path))
        contexts.enter_context(contextlib.redirect_stdout(io.StringIO()))

    def test_dry_run_has_no_side_effects(self):
        for benchmark in ("robomimic", "gr1", "simpler", "pi05", "cosmos"):
            install.Installer(dry_run=True).install(benchmark)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_active_environment_is_not_modified(self):
        with patch.dict(
            os.environ, VIRTUAL_ENV="/unrelated", UV_PROJECT_ENVIRONMENT="/other"
        ):
            env = install.Installer().environment()
        self.assertNotIn("VIRTUAL_ENV", env)
        self.assertNotIn("UV_PROJECT_ENVIRONMENT", env)

    def make_venv(self, name="existing"):
        env = install.ENVS / name
        subprocess.run(
            [sys.executable, "-m", "venv", "--without-pip", str(env)], check=True
        )
        return env, env / "bin/python"

    def test_existing_environment_is_reused(self):
        env, python = self.make_venv()
        marker = env / "keep-me"
        marker.write_text("installed data")
        installer = install.Installer()
        with patch.object(
            installer, "run", side_effect=AssertionError("recreated environment")
        ):
            result = installer.venv(
                "existing", f"{sys.version_info.major}.{sys.version_info.minor}"
            )
        self.assertEqual(result, python)
        self.assertEqual(marker.read_text(), "installed data")

    def test_bundled_lock_bootstraps_only_missing_native_lock(self):
        source = self.root / "native"
        source.mkdir()
        bundled = self.root / "environments/gr00t.uv.lock"
        bundled.parent.mkdir()
        bundled.write_text("validated lock\n")
        installer = install.Installer()
        with patch.object(install, "ROOT", self.root), patch.object(installer, "run"):
            installer.sync(source, "gr00t", "3.12")
            self.assertEqual((source / "uv.lock").read_text(), "validated lock\n")
            (source / "uv.lock").write_text("existing lock\n")
            installer.sync(source, "gr00t", "3.12")
        self.assertEqual((source / "uv.lock").read_text(), "existing lock\n")

    def test_libero_config_isolation_and_empty_config_recovery(self):
        installer = install.Installer()
        startup_env = installer.environment()
        startup_env.pop("LIBERO_CONFIG_PATH", None)
        for name in ("pi05", "cosmos-libero"):
            env, python = self.make_venv(name)
            # Mimic LIBERO's import-time config requirement without installing
            # either simulator into the unit-test environments.
            source = self.root / name
            package = source / "libero"
            package.mkdir(parents=True)
            (package / "__init__.py").touch()
            (package / "libero.py").write_text(
                "import os\nfrom pathlib import Path\n"
                "config = Path(os.environ['LIBERO_CONFIG_PATH']) / 'config.yaml'\n"
                "assert config.exists(), 'would prompt for config on import'\n"
                "def set_libero_default_path():\n"
                "    config.write_text(__file__)\n"
            )
            installer.expose(python, source, "test_libero")
            cfg = env / "libero-config/config.yaml"
            cfg.parent.mkdir()
            cfg.touch()
            installer.configure_libero(python, name)
            self.assertEqual(cfg.read_text(), str(package / "libero.py"))
            selected = subprocess.check_output(
                [
                    str(python),
                    "-c",
                    "import os; print(os.environ['LIBERO_CONFIG_PATH'])",
                ],
                env=startup_env,
                text=True,
            ).strip()
            self.assertEqual(selected, str(cfg.parent))
            cfg.write_text("user configuration")
            installer.configure_libero(python, name)
            self.assertEqual(cfg.read_text(), "user configuration")

    def test_source_path_with_spaces_and_quotes_is_importable(self):
        _, python = self.make_venv()
        source = self.root / "source with ' quotes"
        source.mkdir()
        (source / "sample_install_module.py").write_text("value = 42\n")
        install.Installer().expose(python, source, "test_source")
        subprocess.run(
            [
                str(python),
                "-c",
                "import sample_install_module; assert sample_install_module.value == 42",
            ],
            cwd=self.root,
            check=True,
        )

    def test_patch_can_be_applied_twice_without_touching_other_files(self):
        source = self.root / "repo"
        source.mkdir()
        subprocess.run(["git", "init", "-q", str(source)], check=True)
        (source / "value.txt").write_text("before\n")
        (source / "keep.txt").write_text("user changes\n")
        install.PATCHES.mkdir()
        (install.PATCHES / "test.patch").write_text(
            "--- a/value.txt\n+++ b/value.txt\n@@ -1 +1 @@\n-before\n+after\n"
        )
        installer = install.Installer()
        installer.patch(source, "test.patch")
        installer.patch(source, "test.patch")
        self.assertEqual((source / "value.txt").read_text(), "after\n")
        self.assertEqual((source / "keep.txt").read_text(), "user changes\n")


if __name__ == "__main__":
    unittest.main()
