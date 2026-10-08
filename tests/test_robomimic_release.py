"""Released checkpoints preserve normalization, inference, and strict loading."""

import tempfile
import unittest
from pathlib import Path

import torch

from ht_regression.adapters.checkpoint.robomimic_release import (
    FORMAT,
    load_released_checkpoint,
)
from ht_regression.data.robomimic import RobomimicNormalizer
from ht_regression.objectives.regression.HT import HTObjective
from ht_regression.pipelines import PolicyPipeline
from ht_regression.policies.from_scratch.action_chunk_policy import (
    ActionChunkPolicyWithScale,
)
from ht_regression.policies.from_scratch.backbones import (
    TransformerBackbone,
    UNetBackbone,
)


class ReleasedCheckpointTests(unittest.TestCase):
    def make_checkpoint(self, path, backbone):
        model = dict(obs_dim=3, action_dim=10, horizon=4, n_obs_steps=2)
        if backbone == "ht-t":
            model.update(n_layer=1, n_head=2, n_emb=8)
            model_type = TransformerBackbone
        else:
            model.update(diffusion_step_embed_dim=8, down_dims=[8, 16], n_groups=4)
            model_type = UNetBackbone
        config = dict(
            format=FORMAT,
            backbone=backbone,
            model=model,
            normalizer=dict(
                obs_dim=3, action_dim=10, action_space="abs", normalization="minmax"
            ),
            policy=dict(n_action_steps=2),
            objective=dict(nu=100, scale_bias=0.25, min_scale=0.001),
            evaluation=dict(seed=41, n_test=50),
        )
        normalizer = RobomimicNormalizer(**config["normalizer"])
        normalizer.obs_scale.fill_(2.5)
        normalizer.obs_offset.fill_(-0.7)
        normalizer.action_scale.fill_(3.0)
        normalizer.action_offset.fill_(0.2)
        policy = ActionChunkPolicyWithScale(
            model_type(**model), normalizer, **config["policy"]
        )
        pipeline = PolicyPipeline(policy, HTObjective(**config["objective"])).eval()
        saved = dict(
            format=FORMAT,
            config=config,
            state_dict=pipeline.state_dict(),
            metrics=dict(weights="ema"),
        )
        torch.save(saved, path)
        return pipeline, saved

    def test_both_backbones_restore_weights_and_inference_without_data(self):
        for backbone in ("ht-t", "ht-c"):
            with self.subTest(backbone=backbone), tempfile.TemporaryDirectory() as d:
                path = Path(d) / "release.pt"
                original, saved = self.make_checkpoint(path, backbone)
                restored = load_released_checkpoint(path)
                self.assertEqual(restored.config, saved["config"])
                self.assertFalse(restored.pipeline.training)
                self.assertTrue(
                    all(not p.requires_grad for p in restored.pipeline.parameters())
                )
                for key, value in original.state_dict().items():
                    actual = restored.pipeline.state_dict()[key]
                    if isinstance(value, torch.Tensor):
                        torch.testing.assert_close(actual, value, rtol=0, atol=0)
                    else:
                        self.assertEqual(actual, value)
                batch = {"obs": torch.randn(2, 2, 3)}
                with torch.no_grad():
                    expected = original.predict_action(batch)
                    actual = restored.pipeline.predict_action(batch)
                for key in expected:
                    torch.testing.assert_close(
                        actual[key], expected[key], rtol=1e-6, atol=1e-7
                    )
                torch.testing.assert_close(
                    restored.pipeline.policy.normalizer.obs_scale,
                    original.policy.normalizer.obs_scale,
                    rtol=0,
                    atol=0,
                )

    def test_wrong_weights_and_incomplete_state_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "release.pt"
            _, saved = self.make_checkpoint(path, "ht-t")
            with self.assertRaisesRegex(ValueError, "only 'ema'"):
                load_released_checkpoint(path, weights="model")
            del saved["state_dict"]["policy.normalizer.obs_scale"]
            torch.save(saved, path)
            with self.assertRaisesRegex(RuntimeError, "Missing key"):
                load_released_checkpoint(path)
            saved["format"] = "unsupported"
            torch.save(saved, path)
            with self.assertRaisesRegex(ValueError, "released RoboMimic"):
                load_released_checkpoint(path)


if __name__ == "__main__":
    unittest.main()
