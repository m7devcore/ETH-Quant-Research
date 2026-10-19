"""Unit and deterministic property tests for V22-R reconstructed model and decision engine."""

import math
import tempfile
import unittest
from pathlib import Path

from eth_research.model import (
    LogisticExpert,
    NormalizationStats,
    V22ReconstructedModel,
    compute_normalization_stats,
    sigmoid,
    train_logistic_expert,
)
from eth_research.policy import decide


class TestModelInfrastructure(unittest.TestCase):
    def test_sigmoid_limits(self):
        self.assertEqual(sigmoid(50.0), 1.0)
        self.assertEqual(sigmoid(-50.0), 0.0)
        self.assertAlmostEqual(sigmoid(0.0), 0.5)

    def test_normalization_without_leakage(self):
        matrix = [
            [10.0, 100.0],
            [20.0, 200.0],
            [30.0, 300.0],
        ]
        stats = compute_normalization_stats(matrix)
        self.assertAlmostEqual(stats.means[0], 20.0)
        self.assertAlmostEqual(stats.means[1], 200.0)
        # Population std of [10, 20, 30]: sqrt((( -10)^2 + 0^2 + 10^2)/3) = sqrt(200/3) = 8.1649658
        expected_std = math.sqrt(200.0 / 3.0)
        self.assertAlmostEqual(stats.stds[0], expected_std)

        # Standardizing the mean should give 0.0
        z = stats.transform([20.0, 200.0])
        self.assertAlmostEqual(z[0], 0.0)
        self.assertAlmostEqual(z[1], 0.0)

    def test_training_determinism(self):
        # Synthetic dataset with 2 features and 4 samples
        X = [
            [1.0, -1.0],
            [2.0, -2.0],
            [-1.0, 1.0],
            [-2.0, 2.0],
        ]
        y = [1, 1, 0, 0]

        expert_1 = train_logistic_expert(
            name="Exp_1",
            regimes="Synthetic",
            feature_matrix=X,
            labels=y,
            gradient_steps=50,
            learning_rate=0.05,
            l2_reg=0.20,
        )
        expert_2 = train_logistic_expert(
            name="Exp_2",
            regimes="Synthetic",
            feature_matrix=X,
            labels=y,
            gradient_steps=50,
            learning_rate=0.05,
            l2_reg=0.20,
        )

        self.assertEqual(expert_1.intercept, expert_2.intercept)
        self.assertEqual(expert_1.weights, expert_2.weights)
        self.assertEqual(expert_1.norm_stats.means, expert_2.norm_stats.means)
        self.assertEqual(expert_1.norm_stats.stds, expert_2.norm_stats.stds)

    def test_serialization_and_reload(self):
        # Create a model and verify roundtrip JSON save & load
        stats = NormalizationStats(means=[0.0] * 18, stds=[1.0] * 18)
        exp_a = LogisticExpert("A", "V16-V21", 0.01, [0.05] * 18, stats, 7458)
        exp_b = LogisticExpert("B", "V10-V15", -0.01, [-0.05] * 18, stats, 7458)
        exp_c = LogisticExpert("C", "V4-V9", 0.00, [0.02] * 18, stats, 7458)
        model = V22ReconstructedModel(expert_a=exp_a, expert_b=exp_b, expert_c=exp_c)

        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "v22_test.json"
            checksum = model.save_json(fpath)
            self.assertTrue(len(checksum) == 64)

            loaded = V22ReconstructedModel.load_json(fpath)
            self.assertEqual(loaded.expert_a.intercept, exp_a.intercept)
            self.assertEqual(loaded.expert_b.weights, exp_b.weights)
            self.assertEqual(loaded.expert_c.sample_count, exp_c.sample_count)

    def test_decision_gates(self):
        stats = NormalizationStats(means=[0.0] * 18, stds=[1.0] * 18)
        # All experts outputting ~0.60
        exp_a = LogisticExpert("A", "V16-V21", 0.5, [0.0] * 18, stats, 7458)
        exp_b = LogisticExpert("B", "V10-V15", 0.5, [0.0] * 18, stats, 7458)
        exp_c = LogisticExpert("C", "V4-V9", 0.5, [0.0] * 18, stats, 7458)
        model = V22ReconstructedModel(expert_a=exp_a, expert_b=exp_b, expert_c=exp_c)

        # 1. Close to center -> dist < 2.0, spread = 0 -> UP
        pol, probs, dists = model.evaluate_features([0.0] * 18)
        self.assertEqual(pol.direction, "UP")
        self.assertEqual(pol.reason, "PASSED_ALL_GATES")

        # 2. Extreme out of distribution -> dist > 2.0 -> NO_TRADE
        pol_ood, probs_ood, dists_ood = model.evaluate_features([10.0] * 18)
        self.assertEqual(pol_ood.direction, "NO_TRADE")
        self.assertEqual(pol_ood.reason, "OUT_OF_DISTRIBUTION")


if __name__ == "__main__":
    unittest.main()
