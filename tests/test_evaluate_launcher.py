"""The public launcher selects environments without changing evaluation arguments."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "scripts/evaluate.py"


class EvaluationLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="evaluation launcher ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.script = self.root / "scripts/evaluate.py"
        self.script.parent.mkdir()
        shutil.copyfile(SOURCE, self.script)
        (self.root / ".environments").mkdir()
        self.python = self.root / "model environment/bin/python"
        self.python.parent.mkdir(parents=True)
        self.python.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "print(json.dumps({'args':sys.argv[1:], 'env':dict(os.environ)}))\n"
            "sys.exit(7)\n"
        )
        self.python.chmod(0o755)
        for benchmark in ("robomimic", "gr1", "simpler", "pi05", "cosmos"):
            profile = dict(
                python=str(self.python),
                model_python=str(self.python),
                simulator_python=str(self.root / benchmark / "bin/python"),
                native_root=str(self.root / "native source"),
                native_client=str(self.root / "native source/client.py"),
            )
            (self.root / f".environments/{benchmark}.json").write_text(
                json.dumps(profile)
            )

    def run_launcher(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(self.script), *args],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_every_backend_forwards_arguments_and_exit_status(self):
        for benchmark in ("robomimic", "gr1", "simpler", "pi05", "cosmos"):
            with self.subTest(benchmark=benchmark):
                result = self.run_launcher(
                    benchmark, "--checkpoint", "weights with spaces.pt"
                )
                self.assertEqual(result.returncode, 7, result.stderr)
                child = json.loads(result.stdout)
                args = child["args"]
                self.assertEqual(args[-2:], ["--checkpoint", "weights with spaces.pt"])
                if benchmark in ("gr1", "simpler", "cosmos"):
                    self.assertEqual(
                        args[args.index("--simulator-python") + 1],
                        str(self.root / benchmark / "bin/python"),
                    )
                if benchmark in ("pi05", "cosmos"):
                    self.assertEqual(args[2], benchmark)
                    self.assertEqual(child["env"]["MUJOCO_GL"], "egl")

    def test_explicit_runtime_overrides_are_kept(self):
        result = self.run_launcher(
            "gr1", "--simulator-python=/custom/sim", "--model-python", "/custom/model"
        )
        args = json.loads(result.stdout)["args"]
        self.assertNotIn("--simulator-python", args)
        self.assertIn("--simulator-python=/custom/sim", args)
        self.assertEqual(args.count("--model-python"), 1)
        self.assertEqual(args[args.index("--model-python") + 1], "/custom/model")

    def test_uv_environment_does_not_leak_into_evaluator(self):
        result = self.run_launcher(
            "pi05",
            env={
                **os.environ,
                "VIRTUAL_ENV": "/temporary/uv",
                "UV_PROJECT_ENVIRONMENT": "/other",
                "MUJOCO_GL": "osmesa",
            },
        )
        env = json.loads(result.stdout)["env"]
        self.assertNotIn("VIRTUAL_ENV", env)
        self.assertNotIn("UV_PROJECT_ENVIRONMENT", env)
        self.assertEqual(env["MUJOCO_GL"], "osmesa")
        self.assertEqual(env["PATH"].split(os.pathsep)[0], str(self.python.parent))

    def test_missing_installation_gives_the_install_command(self):
        (self.root / ".environments/gr1.json").unlink()
        result = self.run_launcher("gr1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("uv run scripts/install.py gr1", result.stderr)


if __name__ == "__main__":
    unittest.main()
