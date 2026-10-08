"""Test the standalone package using only PyTorch and the standard library."""

import math
import unittest

import torch
import torch.nn.functional as F
from torch import nn

from ht_loss import HTLoss, ht_loss


class HTLossTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(4)

    def test_scalar_regression_matches_student_t_density_and_gradients(self):
        for nu in (None, 2.0, 200.0):
            with self.subTest(nu=nu):
                mean = torch.randn(4, dtype=torch.float64, requires_grad=True)
                target = torch.randn_like(mean)
                raw_scale = torch.randn(4, dtype=torch.float64, requires_grad=True)
                sigma = F.softplus(raw_scale - 0.3) + 1e-3
                df = 4.0 if nu is None else nu
                density = torch.distributions.StudentT(df, mean, sigma)
                constant = (
                    math.lgamma(df / 2)
                    - math.lgamma((df + 1) / 2)
                    + 0.5 * math.log(df * math.pi)
                )
                expected = -density.log_prob(target) - constant
                actual = ht_loss(
                    mean, target, raw_scale, nu=nu, scale_bias=-0.3, reduction="none"
                )
                torch.testing.assert_close(actual, expected)
                expected_grads = torch.autograd.grad(
                    expected.sum(), (mean, raw_scale), retain_graph=True
                )
                actual_grads = torch.autograd.grad(actual.sum(), (mean, raw_scale))
                for a, b in zip(actual_grads, expected_grads):
                    torch.testing.assert_close(a, b)

    def test_joint_event_reductions_and_masks_with_empty_sample(self):
        mean = torch.randn(3, 2, 4, dtype=torch.float64, requires_grad=True)
        target = torch.randn_like(mean)
        raw_scale = torch.randn(3, 1, dtype=torch.float64, requires_grad=True)
        mask = torch.tensor(
            [
                [[1, 1, 0, 0], [0, 0, 0, 0]],
                [[1, 0, 1, 0], [1, 1, 1, 0]],
                [[0, 0, 0, 0], [0, 0, 0, 0]],
            ],
            dtype=torch.bool,
        )
        for nu in (None, 17):
            with self.subTest(nu=nu):
                losses = ht_loss(
                    mean, target, raw_scale, nu=nu, mask=mask, reduction="none"
                )
                for i in (0, 1):
                    selected = ht_loss(
                        mean[i][mask[i]].unsqueeze(0),
                        target[i][mask[i]].unsqueeze(0),
                        raw_scale[i : i + 1],
                        nu=nu,
                        reduction="sum",
                    )
                    torch.testing.assert_close(losses[i], selected)
                self.assertEqual(losses[2].item(), 0)
                total = HTLoss(nu, reduction="sum")(mean, target, raw_scale, mask=mask)
                average = HTLoss(nu)(mean, target, raw_scale, mask=mask)
                torch.testing.assert_close(total, losses.sum())
                torch.testing.assert_close(average, total / mask.sum())
                grad_mean, grad_scale = torch.autograd.grad(average, (mean, raw_scale))
                self.assertEqual(torch.count_nonzero(grad_mean[~mask]).item(), 0)
                self.assertEqual(grad_scale[2].item(), 0)

    def test_fractional_broadcast_weights_and_noncontiguous_inputs(self):
        mean = torch.randn(2, 3, 4, dtype=torch.float64).transpose(1, 2)
        target = torch.randn_like(mean)
        raw_scale = torch.randn(2, dtype=torch.float64)
        mask = torch.tensor([0.25, 1.0, 0.0], dtype=torch.float64)
        sigma = F.softplus(raw_scale) + 1e-3
        weights = mask.expand_as(mean)
        dimension = weights.reshape(2, -1).sum(1)
        residual = (
            (((mean - target) / sigma[:, None, None]).square() * weights)
            .reshape(2, -1)
            .sum(1)
        )
        expected = (
            (0.5 * (31 + dimension) * torch.log1p(residual / 31))
            + dimension * sigma.log()
        ).sum() / dimension.sum()
        torch.testing.assert_close(
            ht_loss(mean, target, raw_scale, nu=31, mask=mask), expected
        )
        # A scalar mask of one is equivalent to unmasked reduction.
        torch.testing.assert_close(
            ht_loss(mean, target, raw_scale),
            ht_loss(mean, target, raw_scale, mask=torch.tensor(1.0)),
        )

    def test_large_nu_matches_gaussian_nll(self):
        mean = torch.randn(3, 2, 4, dtype=torch.float64, requires_grad=True)
        target = torch.randn_like(mean)
        raw_scale = torch.randn(3, 1, dtype=torch.float64, requires_grad=True)
        sigma = F.softplus(raw_scale[:, :, None]) + 1e-3
        gaussian = (0.5 * ((mean - target) / sigma).square() + sigma.log()).mean()
        actual = ht_loss(mean, target, raw_scale, nu=1e12)
        torch.testing.assert_close(actual, gaussian, rtol=1e-8, atol=1e-9)
        grads = torch.autograd.grad(actual, (mean, raw_scale), retain_graph=True)
        reference = torch.autograd.grad(gaussian, (mean, raw_scale))
        for a, b in zip(grads, reference):
            torch.testing.assert_close(a, b, rtol=1e-8, atol=1e-9)

    def test_gradcheck_both_heads_and_target(self):
        args = (
            torch.randn(2, 2, 3, dtype=torch.float64, requires_grad=True),
            torch.randn(2, 2, 3, dtype=torch.float64, requires_grad=True),
            torch.randn(2, 1, dtype=torch.float64, requires_grad=True),
        )
        self.assertTrue(torch.autograd.gradcheck(HTLoss(nu=19), args))

    def test_low_precision_promotes_loss_arithmetic(self):
        for dtype in (torch.float16, torch.bfloat16):
            with self.subTest(dtype=dtype):
                mean = torch.full((2, 3, 4), 400, dtype=dtype, requires_grad=True)
                target = torch.zeros_like(mean)
                raw_scale = torch.zeros(2, 1, dtype=dtype, requires_grad=True)
                with torch.autocast("cpu", dtype=torch.bfloat16):
                    actual = ht_loss(mean, target, raw_scale, nu=200)
                expected = ht_loss(
                    mean.float(), target.float(), raw_scale.float(), nu=200
                )
                self.assertEqual(actual.dtype, torch.float32)
                torch.testing.assert_close(actual, expected, rtol=0, atol=0)
                actual.backward()
                self.assertTrue(torch.isfinite(mean.grad).all())
                self.assertTrue(torch.isfinite(raw_scale.grad).all())

    def test_plain_pytorch_model_trains_both_heads(self):
        encoder = nn.Sequential(nn.Linear(5, 16), nn.Tanh())
        mean_head = nn.Linear(16, 6)
        scale_head = nn.Linear(16, 1)
        nn.init.zeros_(scale_head.weight)
        nn.init.zeros_(scale_head.bias)
        modules = nn.ModuleList([encoder, mean_head, scale_head])
        optimizer = torch.optim.Adam(modules.parameters(), lr=1e-3)
        before = {k: v.clone() for k, v in modules.state_dict().items()}
        features = encoder(torch.randn(4, 5))
        prediction = mean_head(features).reshape(4, 2, 3)
        raw_scale = scale_head(features)
        loss = HTLoss(nu=200)(prediction, torch.randn_like(prediction), raw_scale)
        loss.backward()
        optimizer.step()
        for name, value in modules.state_dict().items():
            self.assertFalse(torch.equal(value, before[name]), name)

    def test_fullgraph_compile_preserves_forward_and_gradients(self):
        criterion = HTLoss(nu=200, validate_values=False)
        compiled = torch.compile(criterion, backend="eager", fullgraph=True)
        inputs = (
            torch.randn(2, 3, 4, requires_grad=True),
            torch.randn(2, 3, 4),
            torch.randn(2, 1, requires_grad=True),
        )
        for mask in (None, torch.tensor([[[1.0]], [[0.5]]])):
            expected = criterion(*inputs, mask=mask)
            actual = compiled(*inputs, mask=mask)
            torch.testing.assert_close(actual, expected)
            expected_grads = torch.autograd.grad(expected, (inputs[0], inputs[2]))
            actual_grads = torch.autograd.grad(actual, (inputs[0], inputs[2]))
            for a, b in zip(actual_grads, expected_grads):
                torch.testing.assert_close(a, b)

    def test_invalid_inputs_and_options(self):
        mean, target, scale = torch.ones(2, 3), torch.zeros(2, 3), torch.zeros(2, 1)
        for options in (
            {"nu": 0},
            {"nu": float("inf")},
            {"nu": torch.tensor(2.0)},
            {"scale_bias": float("nan")},
            {"min_scale": -1},
            {"reduction": "batchmean"},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                HTLoss(**options)
        for args, options in (
            ((mean, target[:, :1], scale), {}),
            ((mean, target, torch.zeros(2, 3)), {}),
            ((mean.to(torch.int32), target, scale), {}),
            ((torch.empty(0, 3), torch.empty(0, 3), torch.empty(0, 1)), {}),
            ((mean, target, torch.full_like(scale, float("nan"))), {}),
            ((mean, target, scale), {"mask": torch.zeros(2, 3)}),
            ((mean, target, scale), {"mask": -torch.ones(2, 3)}),
            ((mean, target, scale), {"mask": torch.ones(2)}),
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                ht_loss(*args, **options)


if __name__ == "__main__":
    unittest.main()
