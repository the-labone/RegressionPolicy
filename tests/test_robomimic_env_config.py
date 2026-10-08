"""Standalone evaluation uses environment configs without opening training data."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import h5py
import numpy as np

from ht_regression.evaluation.robomimic.evaluate import main
from ht_regression.evaluation.robomimic.image_runner import RobomimicImageRunner
from ht_regression.evaluation.robomimic.state_runner import RobomimicStateRunner

CONFIGS = Path(__file__).resolve().parents[1] / "configs/evaluation/robomimic"
STATE_KEYS = ("object", "robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos")


class EnvironmentConfigTests(unittest.TestCase):
    def test_all_task_configs_work_without_hdf5(self):
        for task, state_dim, proprio_dim in (
            ("lift", 19, 9),
            ("can", 23, 9),
            ("square", 23, 9),
            ("transport", 59, 18),
            ("tool_hang", 53, 9),
        ):
            keys = STATE_KEYS
            if task == "transport":
                keys += ("robot1_eef_pos", "robot1_eef_quat", "robot1_gripper_qpos")
            for visual in (False, True):
                with (
                    self.subTest(task=task, visual=visual),
                    patch(
                        "h5py.File", side_effect=AssertionError("Dataset was opened")
                    ),
                ):
                    runner_type = (
                        RobomimicImageRunner if visual else RobomimicStateRunner
                    )
                    runner = runner_type(
                        dataset_path=None,
                        env_config=CONFIGS / f"{task}.json",
                        output_dir="unused",
                        obs_keys=keys[1:] if visual else keys,
                        action_space="abs",
                        n_train=0,
                        n_test=2,
                        test_start_seed=4200000,
                        **(
                            {"camera_shapes": {"agentview_image": (3, 84, 84)}}
                            if visual
                            else {}
                        ),
                    )
                    self.assertEqual(
                        runner.obs_dim, proprio_dim if visual else state_dim
                    )
                    self.assertEqual(runner.env_meta["env_version"], "1.2.0")
                    self.assertEqual(
                        [e["id"] for e in runner.episodes], [4200000, 4200001]
                    )
                    self.assertTrue(all(e["initial"] is None for e in runner.episodes))
                    self.assertIsNone(runner._evaluation_config()["dataset_path"])

    def test_config_and_dataset_preserve_the_same_test_protocol(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "data.hdf5"
            config = json.loads((CONFIGS / "lift.json").read_text())
            initial = np.arange(8, dtype=np.float64)
            with h5py.File(path, "w") as f:
                data = f.create_group("data")
                data.attrs["env_args"] = json.dumps(config["env_meta"])
                demo = data.create_group("demo_0")
                demo.create_dataset("states", data=initial[None])
                obs = demo.create_group("obs")
                for key in STATE_KEYS:
                    obs.create_dataset(key, data=np.zeros((1, config["obs_dims"][key])))
            settings = dict(
                output_dir=d,
                obs_keys=STATE_KEYS,
                action_space="abs",
                n_train=0,
                n_test=2,
                n_test_vis=1,
                test_start_seed=4200000,
            )
            dataset = RobomimicStateRunner(dataset_path=path, **settings)
            standalone = RobomimicStateRunner(
                dataset_path=None, env_config=CONFIGS / "lift.json", **settings
            )
            for name in ("env_meta", "obs_dim", "repair_observations", "episodes"):
                self.assertEqual(getattr(dataset, name), getattr(standalone, name))
            settings["n_train"] = 1
            training = RobomimicStateRunner(dataset_path=path, **settings)
            np.testing.assert_array_equal(
                training.episodes[0]["initial"]["states"], initial
            )
            self.assertEqual(training.episodes[1:], standalone.episodes)

    def test_missing_dimensions_version_mismatch_and_train_resets_are_rejected(self):
        settings = dict(
            dataset_path=None,
            env_config=CONFIGS / "lift.json",
            output_dir="unused",
            obs_keys=STATE_KEYS,
            action_space="abs",
            n_train=0,
            n_test=1,
        )
        for overrides, error in (
            ({"obs_keys": ("missing",)}, "dimensions"),
            ({"source_robosuite_version": "1.5.0"}, "conflicts"),
            ({"n_train": 1}, "require a dataset"),
            ({"dataset_path": "missing.hdf5"}, "either"),
        ):
            with (
                self.subTest(overrides=overrides),
                self.assertRaisesRegex(ValueError, error),
            ):
                RobomimicStateRunner(**(settings | overrides))

    def test_cli_replaces_training_demo_rollouts_with_test_only_settings(self):
        original = dict(evaluation=dict(n_train=6, n_train_vis=2, n_test=50, seed=41))
        loaded = SimpleNamespace(
            config=original, pipeline=object(), state_key="state_dict"
        )
        with (
            tempfile.TemporaryDirectory() as d,
            patch(
                "ht_regression.adapters.checkpoint.robomimic_release.load_released_checkpoint",
                return_value=loaded,
            ),
            patch(
                "ht_regression.evaluation.robomimic.evaluate.RobomimicStateRunner"
            ) as runner,
        ):
            before = copy.deepcopy(original)
            runner.return_value.run.return_value = {"test/num_episodes": 50}
            main(
                [
                    "--checkpoint",
                    "unused.pt",
                    "--checkpoint-format",
                    "release",
                    "--env-config",
                    str(CONFIGS / "lift.json"),
                    "--output-dir",
                    d,
                ]
            )
            settings = runner.call_args.kwargs
            self.assertIsNone(settings["dataset_path"])
            self.assertEqual(settings["n_train"], 0)
            self.assertEqual(settings["n_train_vis"], 0)
            self.assertEqual(settings["n_test"], 50)
            self.assertEqual(settings["seed"], 41)
            self.assertEqual(original, before)

    def test_dp_configs_override_saved_dataset_paths_for_both_modalities(self):
        for visual in (False, True):
            with (
                self.subTest(visual=visual),
                patch(
                    "h5py.File",
                    side_effect=AssertionError("Saved dataset path was opened"),
                ),
            ):
                target = (
                    "robomimic_image_runner.RobomimicImageRunner"
                    if visual
                    else "robomimic_lowdim_runner.RobomimicLowdimRunner"
                )
                loaded = SimpleNamespace(
                    config={
                        "task": {
                            "env_runner": {
                                "_target_": "diffusion_policy.env_runner." + target,
                                "dataset_path": "/unavailable/training/data.hdf5",
                                "n_train": 6,
                                "n_test": 50,
                            }
                        }
                    },
                    policy=SimpleNamespace(
                        obs_encoder=SimpleNamespace(
                            camera_shapes={"agentview_image": (3, 84, 84)}
                        )
                        if visual
                        else None
                    ),
                    obs_keys=STATE_KEYS[1:] if visual else STATE_KEYS,
                    action_space="abs",
                )
                runner_type = RobomimicImageRunner if visual else RobomimicStateRunner
                runner = runner_type.from_dp_checkpoint(
                    loaded,
                    output_dir="unused",
                    env_config=CONFIGS / "lift.json",
                    n_train=0,
                )
                self.assertIsNone(runner.dataset_path)
                self.assertEqual(len(runner.episodes), 50)


if __name__ == "__main__":
    unittest.main()
