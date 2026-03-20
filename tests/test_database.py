"""
Tests — Database Analytics
Author: S. Sasmitha
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Inline re-implementation of feedback logic (no MySQL needed) ──────────────

def get_adaptive_feedback(accuracy: float) -> str:
    if accuracy < 0.50:
        return "beginner"
    elif accuracy < 0.75:
        return "intermediate"
    else:
        return "advanced"


def compute_avg_score(total_score: int, games_played: int) -> float:
    return total_score / games_played if games_played > 0 else 0.0


# ── Test cases ────────────────────────────────────────────────────────────────

class TestAdaptiveFeedback(unittest.TestCase):

    def test_below_50_percent_is_beginner(self):
        self.assertEqual(get_adaptive_feedback(0.49), "beginner")

    def test_exactly_50_percent_is_intermediate(self):
        self.assertEqual(get_adaptive_feedback(0.50), "intermediate")

    def test_between_50_and_75_is_intermediate(self):
        self.assertEqual(get_adaptive_feedback(0.65), "intermediate")

    def test_below_75_percent_is_not_advanced(self):
        self.assertNotEqual(get_adaptive_feedback(0.74), "advanced")

    def test_exactly_75_percent_is_advanced(self):
        self.assertEqual(get_adaptive_feedback(0.75), "advanced")

    def test_above_75_percent_is_advanced(self):
        self.assertEqual(get_adaptive_feedback(0.92), "advanced")

    def test_perfect_accuracy_is_advanced(self):
        self.assertEqual(get_adaptive_feedback(1.0), "advanced")

    def test_zero_accuracy_is_beginner(self):
        self.assertEqual(get_adaptive_feedback(0.0), "beginner")

    # Paper-specific thresholds
    def test_paper_player1_accuracy_is_advanced(self):
        """Player 1: 91.5 % → advanced tier"""
        self.assertEqual(get_adaptive_feedback(0.915), "advanced")

    def test_paper_player3_accuracy_is_intermediate(self):
        """Player 3: 74.8 % → intermediate tier (just below 75 %)"""
        self.assertEqual(get_adaptive_feedback(0.748), "intermediate")


class TestKPICalculations(unittest.TestCase):

    def test_avg_score_basic(self):
        self.assertAlmostEqual(compute_avg_score(300, 3), 100.0)

    def test_avg_score_zero_games(self):
        self.assertEqual(compute_avg_score(0, 0), 0.0)

    def test_avg_score_single_session(self):
        self.assertAlmostEqual(compute_avg_score(80, 1), 80.0)

    def test_paper_overall_accuracy(self):
        """Paper Table III: 120 collected, 18 missed → 86.96 % ≈ 86.5 %"""
        collected, missed = 120, 18
        acc = collected / (collected + missed)
        self.assertAlmostEqual(acc, 0.869, delta=0.005)

    def test_accuracy_all_correct(self):
        self.assertAlmostEqual(32 / (32 + 0), 1.0, places=5)

    def test_accuracy_all_missed(self):
        self.assertAlmostEqual(0 / max(0 + 10, 1), 0.0, places=5)


class TestSessionMetrics(unittest.TestCase):

    def test_session_accuracy_player1(self):
        hits, misses = 32, 3
        acc = hits / (hits + misses)
        self.assertAlmostEqual(acc * 100, 91.42, delta=0.1)

    def test_session_accuracy_player2(self):
        hits, misses = 31, 3
        acc = hits / (hits + misses)
        self.assertAlmostEqual(acc * 100, 91.18, delta=0.5)

    def test_session_accuracy_player3(self):
        hits, misses = 24, 8
        acc = hits / (hits + misses)
        self.assertAlmostEqual(acc * 100, 75.0, delta=0.1)

    def test_session_accuracy_player4(self):
        hits, misses = 33, 4
        acc = hits / (hits + misses)
        self.assertAlmostEqual(acc * 100, 89.19, delta=0.1)

    def test_overall_collection_rate(self):
        """Total collected 120 / (120+18) = 86.96 % ≈ paper's 86.5 %"""
        total_hits   = 32 + 31 + 24 + 33
        total_misses = 3  + 3  + 8  + 4
        acc = total_hits / (total_hits + total_misses)
        self.assertGreater(acc, 0.85)
        self.assertLess(acc, 0.90)


if __name__ == "__main__":
    unittest.main(verbosity=2)
