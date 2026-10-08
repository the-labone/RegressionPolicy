<h1 align="center">Residual Modeling for Regression Policies</h1>

<p align="center">
  <!-- Paper and Project Page URLs: pending. Keep the images adjacent for a continuous navigation bar. -->
  <picture><source media="(prefers-color-scheme: dark)" srcset="assets/readme/paper-dark.svg"><source media="(prefers-color-scheme: light)" srcset="assets/readme/paper.svg"><img src="assets/readme/paper.svg" width="90" height="36" alt="Paper"></picture><picture><source media="(prefers-color-scheme: dark)" srcset="assets/readme/project-page-dark.svg"><source media="(prefers-color-scheme: light)" srcset="assets/readme/project-page.svg"><img src="assets/readme/project-page.svg" width="138" height="36" alt="Project Page"></picture><a href="https://huggingface.co/collections/yuchen0187/regressionpolicy"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/readme/models-dark.svg"><source media="(prefers-color-scheme: light)" srcset="assets/readme/models.svg"><img src="assets/readme/models.svg" width="102" height="36" alt="Models"></picture></a>
</p>

This repository contains the code for **Residual Modeling Closes the Regression and Generative Policy Gap in Robot Learning**. We train a single pass regression model (HT-Policy) to achieve performance competitive with generative policies, with faster training and inference.

<p align="center">
  <a href="assets/teaser.pdf"><img src="assets/teaser.png" width="100%" alt="HT-Policy models heavy-tailed action residuals to close the performance gap with generative policies."></a>
</p>

## Release Plan

- [x] PyTorch implementation of HT-Loss
- [x] RoboMimic training and evaluation code
- [x] VLA evaluation code
- [x] HT-Policy checkpoints for RoboMimic state policies
- [x] HT-Policy checkpoints VLA/WAM models
- [ ] VLA/WAM training code
- [ ] HT-Policy checkpoints for RoboMimic vision policies
- [ ] Checkpoints trained with other objectives

## HT-Policy Demos

<p align="center">
  <img src="assets/videos/peel-note.gif" width="24%" alt="Peel Note — real-world robot demonstration">
  <img src="assets/videos/real-push.gif" width="24%" alt="Push T — real-world robot demonstration">
  <img src="assets/videos/robocasa-gr1.gif" width="24%" alt="Store Bottle — GR1 placing a bottle in a cabinet">
  <img src="assets/videos/tool-hang.gif" width="24%" alt="Tool Hang — simulation demonstration">
  <br>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/readme/demos-labels-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="assets/readme/demos-labels.svg">
    <img src="assets/readme/demos-labels.svg" width="98%" alt="Peel Note and Push T: Real World. Store Bottle and Tool Hang: Simulation.">
  </picture>
</p>

## Use HT-Loss

```bash
# From the repository root
uv pip install ./ht_loss
```

```python
from ht_loss import HTLoss

criterion = HTLoss()  # nu = 4d, where d = T * D
prediction, raw_scale = model(observations)  # [B, T, D], [B, 1]
loss = criterion(prediction, target, raw_scale)
loss.backward()
```

Add a scale head alongside your action head to predict `raw_scale` from shared features. Only PyTorch is required. See [HT-Loss](ht_loss) for the scale head example and options.

## Installation

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and clone the repository:

```bash
git clone https://github.com/the-labone/RegressionPolicy.git
cd RegressionPolicy
```

```bash
uv run scripts/install.py robomimic
```

**Options** — replace `robomimic` with your selection:

| Option | Environment |
| --- | --- |
| `robomimic` | RoboMimic training and evaluation |
| `gr1` | GR00T evaluation on RoboCasa-GR1 |
| `simpler` | GR00T evaluation on SimplerEnv |
| `pi05` | π0.5 evaluation on LIBERO |
| `cosmos` | Cosmos evaluation on LIBERO |

## Training

### Prepare dataset

```bash
# RoboMimic Lift PH — state observations
uv run scripts/download_robomimic.py --task lift --split ph --modality state

# RoboMimic Lift PH — image observations
uv run scripts/download_robomimic.py --task lift --split ph --modality vision
```

### Launch policy training

**HT-Policy · Transformer · State observations**

```bash
uv run --no-sync python -m ht_regression.training.train \
  experiment=robomimic/state/lift/ph/ht_transformer_nu200 \
  dataset.path=data/robomimic/lift/ph/low_dim_abs.hdf5
```

**HT-Policy · UNet · Image observations**

```bash
uv run --no-sync python -m ht_regression.training.train \
  experiment=robomimic/vision/lift/ph/ht_unet_nu200 \
  dataset.path=data/robomimic/lift/ph/image_abs.hdf5
```

| Argument | Options |
| --- | --- |
| `experiment=...` | [Task and backbone configurations](configs/experiment/robomimic) |
| `objective=...` | `ht`, `mse`, `flow`, `mip`, `diffusion` |

## Evaluation

### RoboMimic

Download and evaluate the released Lift PH HT-Policy with a Transformer backbone:

```bash
uv run scripts/download_checkpoint.py robomimic \
  --path state/ht/lift_ph/ht-transformer

uv run scripts/evaluate.py robomimic \
  --checkpoint checkpoints/robomimic/state/ht/lift_ph/ht-transformer/best_nu100_last10-100.0.pt \
  --checkpoint-format release \
  --env-config configs/evaluation/robomimic/lift.json \
  --device cuda \
  --output-dir evaluation_results/robomimic_lift
```
You can specify the checkpoint to evaluate with `--checkpoint`.

### GR00T

#### RoboCasa-GR1

```bash
uv run scripts/download_checkpoint.py gr00t \
  --path gr1/checkpoint-60000

uv run scripts/evaluate.py gr1 \
  --checkpoint checkpoints/gr00t/gr1/checkpoint-60000 \
  --output-dir evaluation_results/gr1
```

#### SimplerEnv

Set `simpler_suite` to `bridge` or `fractal`:

```bash
simpler_suite=bridge
uv run scripts/download_checkpoint.py gr00t \
  --path simpler/${simpler_suite}/checkpoint-20000

uv run scripts/evaluate.py simpler \
  --checkpoint checkpoints/gr00t/simpler/${simpler_suite}/checkpoint-20000 \
  --suite ${simpler_suite} \
  --output-dir evaluation_results/simpler_${simpler_suite}
```

### π0.5

```bash
uv run scripts/download_checkpoint.py pi05 \
  --path libero/checkpoint-30000/pretrained_model

uv run scripts/evaluate.py pi05 \
  --checkpoint checkpoints/pi05/libero/checkpoint-30000/pretrained_model \
  --output-dir evaluation_results/pi05
```

By default, all four LIBERO suites are evaluated. Add `--suite libero_10` to select one suite.

### Cosmos

```bash
uv run scripts/download_checkpoint.py cosmos --all

uv run scripts/evaluate.py cosmos \
  --checkpoint checkpoints/cosmos/libero_10/iter_000002000 \
  --method ht \
  --action-stats-path checkpoints/cosmos/libero_10/action_stats.json \
  --vae-path checkpoints/cosmos/assets/wan22_vae/Wan2.2_VAE.pth \
  --deterministic \
  --output-dir evaluation_results/cosmos
```
