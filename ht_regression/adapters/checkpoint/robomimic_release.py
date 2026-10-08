"""Load the compact RoboMimic HT checkpoints published on Hugging Face."""

from dataclasses import dataclass
from pathlib import Path

import torch

from ...data.robomimic import RobomimicNormalizer
from ...objectives.regression.HT import HTObjective
from ...pipelines import PolicyPipeline
from ...policies.from_scratch.action_chunk_policy import ActionChunkPolicyWithScale
from ...policies.from_scratch.backbones import TransformerBackbone, UNetBackbone

FORMAT = "praxis.robomimic.ht.state.v1"


@dataclass
class ReleasedCheckpoint:
    pipeline: PolicyPipeline
    config: dict
    state_key: str = "state_dict"


def load_released_checkpoint(path, *, device="cpu", weights="auto"):
    """Restore saved normalization and weights without a training dataset."""
    if weights not in ("auto", "model", "ema"):
        raise ValueError("weights must be auto, model, or ema.")
    saved = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(saved, dict) or saved.get("format") != FORMAT:
        raise ValueError("Expected a released RoboMimic HT state checkpoint.")
    config = saved["config"]
    if config.get("format") != FORMAT:
        raise ValueError("Release configuration and checkpoint formats disagree.")
    available = saved["metrics"]["weights"]
    if available not in ("model", "ema") or weights not in ("auto", available):
        raise ValueError(f"This release contains only {available!r} weights.")
    backbones = {"ht-t": TransformerBackbone, "ht-c": UNetBackbone}
    if config["backbone"] not in backbones:
        raise ValueError(f"Unsupported release backbone: {config['backbone']}")
    model = backbones[config["backbone"]](**config["model"])
    normalizer = RobomimicNormalizer(**config["normalizer"])
    policy = ActionChunkPolicyWithScale(model, normalizer, **config["policy"])
    pipeline = PolicyPipeline(policy, HTObjective(**config["objective"]))
    pipeline.load_state_dict(saved["state_dict"], strict=True)
    pipeline.to(device).eval().requires_grad_(False)
    return ReleasedCheckpoint(pipeline, config)
