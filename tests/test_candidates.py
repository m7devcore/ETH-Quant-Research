"""Unit tests for candidate strategy engines and multi-horizon holding logic."""

import sys
from pathlib import Path

# Ensure src is on python path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import unittest
from eth_research.candidates import CandidateStrategyEngine, CandidateDecision
from eth_research.policy import PolicyResult


class TestCandidateStrategies(unittest.TestCase):
    def setUp(self):
        # 18 dummy features
        self.features = [0.0] * 18
        # Feature 10 (index 9) is ATR/price
        self.features[9] = 0.0025  # healthy volatility
        # Feature 17 (index 16) is 4H trend displacement
        self.features[16] = 0.5    # 4H Uptrend

    def test_baseline_pass(self):
        engine = CandidateStrategyEngine(strategy_id="Cand_A", holding_bars=1)
        pol = PolicyResult(direction="UP", reason="PASSED_ALL_GATES", average=0.56, spread=0.02, minimum_distance=0.8)
        dec = engine.evaluate_signal(0, 1000, pol, self.features)
        self.assertTrue(dec.tradeable)
        self.assertEqual(dec.policy_direction, "UP")
        self.assertEqual(dec.suggested_holding_bars, 1)

    def test_macro_filter_rejection(self):
        # DOWN signal in 4H Uptrend (features[16] > 0)
        engine = CandidateStrategyEngine(strategy_id="Cand_B", holding_bars=1, require_htf_alignment=True)
        pol = PolicyResult(direction="DOWN", reason="PASSED_ALL_GATES", average=0.44, spread=0.02, minimum_distance=0.8)
        dec = engine.evaluate_signal(0, 1000, pol, self.features)
        self.assertFalse(dec.tradeable)
        self.assertEqual(dec.policy_direction, "NO_TRADE")
        self.assertIn("HTF_MACRO_COUNTERTREND", dec.rejection_reason)

    def test_volatility_gate_rejection(self):
        # Low volatility: ATR/price = 0.0010 < threshold 0.0020
        low_vol_features = list(self.features)
        low_vol_features[9] = 0.0010
        engine = CandidateStrategyEngine(strategy_id="Cand_D", min_atr_price_ratio=0.0020)
        pol = PolicyResult(direction="UP", reason="PASSED_ALL_GATES", average=0.58, spread=0.02, minimum_distance=0.8)
        dec = engine.evaluate_signal(0, 1000, pol, low_vol_features)
        self.assertFalse(dec.tradeable)
        self.assertIn("LOW_VOLATILITY_TRAP", dec.rejection_reason)

    def test_abstention_on_insufficient_edge(self):
        engine = CandidateStrategyEngine(strategy_id="Cand_C", min_probability_edge=0.08) # requires >=0.58 or <=0.42
        pol = PolicyResult(direction="UP", reason="PASSED_ALL_GATES", average=0.55, spread=0.02, minimum_distance=0.8)
        dec = engine.evaluate_signal(0, 1000, pol, self.features)
        self.assertFalse(dec.tradeable)
        self.assertIn("INSUFFICIENT_PROBABILITY_EDGE", dec.rejection_reason)


if __name__ == "__main__":
    unittest.main()
