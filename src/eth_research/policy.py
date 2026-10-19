"""Causal decision gate from frozen V22 reported thresholds (not the original model)."""
from dataclasses import dataclass
from math import isfinite
from typing import Literal

Decision = Literal['UP', 'DOWN', 'NO_TRADE']

@dataclass(frozen=True)
class PolicyResult:
    direction: Decision
    average: float
    spread: float
    minimum_distance: float
    reason: str


def decide(expert_probs: tuple[float, float, float], expert_distances: tuple[float, float, float]) -> PolicyResult:
    """Apply public V22 decision rule to already-computed expert probabilities and distances.

    This does NOT reconstruct expert features, weights, or price feeds. Only completed
    decision-time values should be supplied. Trading is intentionally not implemented.
    """
    if len(expert_probs) != 3 or len(expert_distances) != 3:
        raise ValueError('exactly three expert probabilities and distances are required')
    if not all(isfinite(x) and 0 <= x <= 1 for x in expert_probs):
        raise ValueError('all expert probabilities must be finite and in [0,1]')
    if not all(isfinite(x) and x >= 0 for x in expert_distances):
        raise ValueError('all expert distances must be nonnegative and finite')
    avg = sum(expert_probs) / 3.0
    spread = max(expert_probs) - min(expert_probs)
    min_dist = min(expert_distances)
    if spread > 0.06:
        return PolicyResult('NO_TRADE', avg, spread, min_dist, 'EXPERT_DISAGREEMENT')
    if min_dist > 2.0:
        return PolicyResult('NO_TRADE', avg, spread, min_dist, 'OUT_OF_DISTRIBUTION')
    if avg >= 0.55:
        return PolicyResult('UP', avg, spread, min_dist, 'PASSED_ALL_GATES')
    if avg <= 0.45:
        return PolicyResult('DOWN', avg, spread, min_dist, 'PASSED_ALL_GATES')
    return PolicyResult('NO_TRADE', avg, spread, min_dist, 'INSUFFICIENT_DIRECTIONAL_EDGE')
