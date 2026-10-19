"""Reconstructed V22 (V22-R) Model Architecture, Training, and Inference Engine.

Notice:
This is a research reconstruction designated V22-R.
It is explicitly NOT identical to the original missing frozen V22 checkpoint.
All training and normalization are performed strictly on Study regimes without
lookahead or data leakage.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from eth_research.data import Candle
from eth_research.features import FeatureRow, extract_features
from eth_research.policy import PolicyResult, decide


def sigmoid(z: float) -> float:
    """Standard numerically stable logistic sigmoid."""
    if z >= 40.0:
        return 1.0
    elif z <= -40.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


@dataclasses.dataclass
class NormalizationStats:
    means: List[float]
    stds: List[float]

    def transform(self, features: Sequence[float]) -> List[float]:
        if len(features) != len(self.means):
            raise ValueError(f"Feature dimension mismatch: expected {len(self.means)}, got {len(features)}")
        return [
            (f - m) / (s if s > 1e-12 else 1.0)
            for f, m, s in zip(features, self.means, self.stds)
        ]

    def normalized_rms_distance(self, features: Sequence[float]) -> float:
        """Compute root-mean-square normalized distance from the expert training distribution."""
        z = self.transform(features)
        mean_sq = sum(val * val for val in z) / len(z)
        return math.sqrt(mean_sq)


def compute_normalization_stats(matrix: List[List[float]]) -> NormalizationStats:
    """Compute population mean and standard deviation across training samples."""
    m = len(matrix)
    if m == 0:
        raise ValueError("Cannot compute normalization stats for empty matrix")
    n = len(matrix[0])
    means = [0.0] * n
    for row in matrix:
        for j in range(n):
            means[j] += row[j]
    means = [val / m for val in means]

    stds = [0.0] * n
    for row in matrix:
        for j in range(n):
            diff = row[j] - means[j]
            stds[j] += diff * diff
    stds = [math.sqrt(val / m) for val in stds]
    return NormalizationStats(means=means, stds=stds)


@dataclasses.dataclass
class LogisticExpert:
    name: str
    regimes: str
    intercept: float
    weights: List[float]
    norm_stats: NormalizationStats
    sample_count: int

    def predict_probability(self, raw_features: Sequence[float]) -> float:
        """Predict UP probability using standardized features."""
        z = self.norm_stats.transform(raw_features)
        logit = self.intercept + sum(w * val for w, val in zip(self.weights, z))
        return sigmoid(logit)

    def compute_distance(self, raw_features: Sequence[float]) -> float:
        """Calculate normalized RMS feature distance to training support."""
        return self.norm_stats.normalized_rms_distance(raw_features)


def train_logistic_expert(
    name: str,
    regimes: str,
    feature_matrix: List[List[float]],
    labels: List[int],
    gradient_steps: int = 260,
    learning_rate: float = 0.04,
    l2_reg: float = 0.20,
) -> LogisticExpert:
    """Train single logistic expert with L2 regularization on standardized inputs."""
    m = len(labels)
    if m == 0 or len(feature_matrix) != m:
        raise ValueError("Invalid feature matrix or label vector")
    n = len(feature_matrix[0])

    norm_stats = compute_normalization_stats(feature_matrix)
    norm_X = [norm_stats.transform(row) for row in feature_matrix]

    weights = [0.0] * n
    intercept = 0.0

    for _ in range(gradient_steps):
        # Forward pass & error
        errors = [0.0] * m
        for i in range(m):
            logit = intercept + sum(weights[j] * norm_X[i][j] for j in range(n))
            p = sigmoid(logit)
            errors[i] = p - labels[i]

        grad_b = sum(errors) / m
        grad_w = [
            sum(errors[i] * norm_X[i][j] for i in range(m)) / m + l2_reg * weights[j]
            for j in range(n)
        ]

        intercept -= learning_rate * grad_b
        for j in range(n):
            weights[j] -= learning_rate * grad_w[j]

    return LogisticExpert(
        name=name,
        regimes=regimes,
        intercept=intercept,
        weights=weights,
        norm_stats=norm_stats,
        sample_count=m,
    )


@dataclasses.dataclass
class V22ReconstructedModel:
    expert_a: LogisticExpert  # V16-V21
    expert_b: LogisticExpert  # V10-V15
    expert_c: LogisticExpert  # V4-V9
    decision_thresholds: Dict[str, float] = dataclasses.field(
        default_factory=lambda: {
            "up_gte": 0.55,
            "down_lte": 0.45,
            "spread_lte": 0.06,
            "min_distance_lte": 2.0,
        }
    )

    def evaluate_features(self, raw_features: Sequence[float]) -> Tuple[PolicyResult, Tuple[float, float, float], Tuple[float, float, float]]:
        """Run 3-expert evaluation and apply frozen V22 decision gates."""
        p_a = self.expert_a.predict_probability(raw_features)
        p_b = self.expert_b.predict_probability(raw_features)
        p_c = self.expert_c.predict_probability(raw_features)

        d_a = self.expert_a.compute_distance(raw_features)
        d_b = self.expert_b.compute_distance(raw_features)
        d_c = self.expert_c.compute_distance(raw_features)

        policy_res = decide((p_a, p_b, p_c), (d_a, d_b, d_c))
        return policy_res, (p_a, p_b, p_c), (d_a, d_b, d_c)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize reconstruction model to dictionary."""
        return {
            "status": "RECONSTRUCTED_V22_R_NOT_OFFICIAL_FROZEN_V22",
            "asset": "ETHUSDT USD-M PERPETUAL",
            "experts": {
                "A": {
                    "name": self.expert_a.name,
                    "regimes": self.expert_a.regimes,
                    "sample_count": self.expert_a.sample_count,
                    "intercept": self.expert_a.intercept,
                    "weights": self.expert_a.weights,
                    "mean": self.expert_a.norm_stats.means,
                    "sd": self.expert_a.norm_stats.stds,
                },
                "B": {
                    "name": self.expert_b.name,
                    "regimes": self.expert_b.regimes,
                    "sample_count": self.expert_b.sample_count,
                    "intercept": self.expert_b.intercept,
                    "weights": self.expert_b.weights,
                    "mean": self.expert_b.norm_stats.means,
                    "sd": self.expert_b.norm_stats.stds,
                },
                "C": {
                    "name": self.expert_c.name,
                    "regimes": self.expert_c.regimes,
                    "sample_count": self.expert_c.sample_count,
                    "intercept": self.expert_c.intercept,
                    "weights": self.expert_c.weights,
                    "mean": self.expert_c.norm_stats.means,
                    "sd": self.expert_c.norm_stats.stds,
                },
            },
            "decision_rule": self.decision_thresholds,
        }

    def save_json(self, filepath: Path) -> str:
        """Save to JSON and return SHA-256."""
        payload = self.to_dict()
        data = json.dumps(payload, indent=2).encode("utf-8")
        checksum = hashlib.sha256(data).hexdigest()
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(data.decode("utf-8"))
        return checksum

    @classmethod
    def load_json(cls, filepath: Path) -> V22ReconstructedModel:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        exp = data["experts"]
        exp_a = LogisticExpert(
            name=exp["A"].get("name", "Expert_A"),
            regimes=exp["A"].get("regimes", "V16-V21"),
            intercept=exp["A"]["intercept"],
            weights=exp["A"].get("weights", exp["A"].get("w")),
            norm_stats=NormalizationStats(means=exp["A"]["mean"], stds=exp["A"]["sd"]),
            sample_count=exp["A"].get("sample_count", 0),
        )
        exp_b = LogisticExpert(
            name=exp["B"].get("name", "Expert_B"),
            regimes=exp["B"].get("regimes", "V10-V15"),
            intercept=exp["B"]["intercept"],
            weights=exp["B"].get("weights", exp["B"].get("w")),
            norm_stats=NormalizationStats(means=exp["B"]["mean"], stds=exp["B"]["sd"]),
            sample_count=exp["B"].get("sample_count", 0),
        )
        exp_c = LogisticExpert(
            name=exp["C"].get("name", "Expert_C"),
            regimes=exp["C"].get("regimes", "V4-V9"),
            intercept=exp["C"]["intercept"],
            weights=exp["C"].get("weights", exp["C"].get("w")),
            norm_stats=NormalizationStats(means=exp["C"]["mean"], stds=exp["C"]["sd"]),
            sample_count=exp["C"].get("sample_count", 0),
        )
        return cls(expert_a=exp_a, expert_b=exp_b, expert_c=exp_c, decision_thresholds=data.get("decision_rule", {}))
