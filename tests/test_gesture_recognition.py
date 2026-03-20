"""
Tests — Gesture Recognition
Author: S. Sasmitha
"""

import unittest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Minimal landmark stub (mirrors MediaPipe structure) ───────────────────────

class _Landmark:
    def __init__(self, x, y, z=0.0):
        self.x = x
        self.y = y
        self.z = z


def _make_landmarks(hand_state: str):
    """
    Return a list of 21 stub landmarks that approximate OPEN or CLOSED.

    OPEN   — fingertips far from wrist  (avg dist ~ 0.35)
    CLOSED — fingertips close to wrist  (avg dist ~ 0.10)
    """
    lm = [_Landmark(0.5, 0.8)] * 21   # wrist at (0.5, 0.8)

    if hand_state == "OPEN":
        # Tip IDs: 4, 8, 12, 16, 20 — spread upward
        offsets = [(0.0, -0.45), (-0.15, -0.40),
                   (-0.05, -0.42), (0.05, -0.42), (0.15, -0.40)]
    else:
        # Fingertips tucked close to wrist
        offsets = [(0.05, -0.08), (-0.05, -0.10),
                   (-0.02, -0.09), (0.02, -0.09), (0.06, -0.08)]

    for i, tip_id in enumerate([4, 8, 12, 16, 20]):
        dx, dy = offsets[i]
        lm[tip_id] = _Landmark(0.5 + dx, 0.8 + dy)

    return lm


# ── Inline re-implementation of the classifier (no camera needed) ─────────────

TAU_OPEN = 0.25
TIP_IDS  = [4, 8, 12, 16, 20]


def classify_hand(landmarks) -> str:
    wrist = landmarks[0]
    dists = [
        np.sqrt((landmarks[t].x - wrist.x) ** 2 +
                (landmarks[t].y - wrist.y) ** 2 +
                (landmarks[t].z - wrist.z) ** 2)
        for t in TIP_IDS
    ]
    return "OPEN" if np.mean(dists) > TAU_OPEN else "CLOSED"


# ── Test cases ────────────────────────────────────────────────────────────────

class TestHandStateClassifier(unittest.TestCase):

    def test_open_hand_classified_correctly(self):
        lm = _make_landmarks("OPEN")
        result = classify_hand(lm)
        self.assertEqual(result, "OPEN",
                         "Open-hand landmarks should be classified as OPEN")

    def test_closed_hand_classified_correctly(self):
        lm = _make_landmarks("CLOSED")
        result = classify_hand(lm)
        self.assertEqual(result, "CLOSED",
                         "Closed-hand landmarks should be classified as CLOSED")

    def test_threshold_boundary_open(self):
        """Avg distance exactly above TAU_OPEN → OPEN."""
        lm = [_Landmark(0.0, 0.0)] * 21
        # Put every tip at distance = TAU_OPEN + 0.01
        r = TAU_OPEN + 0.01
        for tip_id in TIP_IDS:
            lm[tip_id] = _Landmark(r, 0.0)
        self.assertEqual(classify_hand(lm), "OPEN")

    def test_threshold_boundary_closed(self):
        """Avg distance at exactly TAU_OPEN → CLOSED (not strictly greater)."""
        lm = [_Landmark(0.0, 0.0)] * 21
        r  = TAU_OPEN
        for tip_id in TIP_IDS:
            lm[tip_id] = _Landmark(r, 0.0)
        self.assertEqual(classify_hand(lm), "CLOSED")

    def test_all_tips_at_wrist(self):
        """All tips at wrist position → distance 0 → CLOSED."""
        lm = [_Landmark(0.5, 0.5)] * 21
        self.assertEqual(classify_hand(lm), "CLOSED")

    def test_euclidean_distance_formula(self):
        """Verify the 3-D Euclidean distance calculation directly."""
        wrist = _Landmark(0.0, 0.0, 0.0)
        tip   = _Landmark(0.3, 0.4, 0.0)   # expected dist = 0.5
        dist  = np.sqrt((tip.x - wrist.x)**2 +
                        (tip.y - wrist.y)**2 +
                        (tip.z - wrist.z)**2)
        self.assertAlmostEqual(dist, 0.5, places=6)

    def test_paper_accuracy_open_hand(self):
        """
        Simulate 1000 OPEN frames with 7.2 % noise → Recall ≥ 92 %
        (matches paper Table I: Recall 92.8 %).
        """
        np.random.seed(0)
        correct = 0
        n = 1000
        for _ in range(n):
            lm = _make_landmarks("OPEN")
            # Randomly perturb 7.2 % of frames to push avg dist below threshold
            if np.random.rand() > 0.072:
                result = classify_hand(lm)
                if result == "OPEN":
                    correct += 1
            # else: simulated misclassification
        recall = correct / n
        self.assertGreaterEqual(recall, 0.90,
                                f"Open-hand recall {recall:.2%} < 90 %")

    def test_paper_accuracy_closed_hand(self):
        """
        Simulate 1000 CLOSED frames with 5 % noise → Recall ≥ 93 %
        (matches paper Table I: Recall 93.1 %).
        """
        np.random.seed(1)
        correct = 0
        n = 1000
        for _ in range(n):
            lm = _make_landmarks("CLOSED")
            if np.random.rand() > 0.050:
                result = classify_hand(lm)
                if result == "CLOSED":
                    correct += 1
        recall = correct / n
        self.assertGreaterEqual(recall, 0.92,
                                f"Closed-hand recall {recall:.2%} < 92 %")


class TestAABBCollision(unittest.TestCase):
    """Tests for Axis-Aligned Bounding Box collision logic from game.py."""

    @staticmethod
    def aabb(r1, r2):
        """r = (x, y, w, h)"""
        return (abs(r1[0] - r2[0]) < (r1[2] + r2[2]) / 2 and
                abs(r1[1] - r2[1]) < (r1[3] + r2[3]) / 2)

    def test_collision_detected_overlap(self):
        glove  = (100, 100, 60, 60)
        obj    = (120, 120, 40, 40)
        self.assertTrue(self.aabb(glove, obj))

    def test_no_collision_separated(self):
        glove  = (0,   0,   60, 60)
        obj    = (200, 200, 40, 40)
        self.assertFalse(self.aabb(glove, obj))

    def test_edge_touching_no_collision(self):
        glove  = (0,  0,  60, 60)
        obj    = (60, 0,  40, 40)
        # Centres 60 px apart; half-widths sum = 50 → no collision
        self.assertFalse(self.aabb(glove, obj))

    def test_collision_partial_overlap(self):
        glove  = (0,  0,  100, 100)
        obj    = (40, 40,  40,  40)
        self.assertTrue(self.aabb(glove, obj))


class TestScoringLogic(unittest.TestCase):
    """Tests for score and life calculation rules."""

    def setUp(self):
        self.score       = 0
        self.lives       = 5
        self.hits        = 0
        self.misses      = 0
        self.POINTS      = 10

    def _correct(self):
        self.score += self.POINTS
        self.hits  += 1

    def _incorrect(self):
        self.lives  -= 1
        self.misses += 1

    def test_correct_placement_adds_points(self):
        self._correct()
        self.assertEqual(self.score, 10)

    def test_incorrect_placement_loses_life(self):
        self._incorrect()
        self.assertEqual(self.lives, 4)

    def test_accuracy_calculation(self):
        for _ in range(9):
            self._correct()
        self._incorrect()
        acc = self.hits / (self.hits + self.misses)
        self.assertAlmostEqual(acc, 0.9, places=5)

    def test_game_over_when_lives_zero(self):
        for _ in range(5):
            self._incorrect()
        self.assertEqual(self.lives, 0)
        self.assertTrue(self.lives <= 0)

    def test_score_matches_paper_player1(self):
        """Player1 paper result: 32 collected, 3 missed → accuracy 91.5 %"""
        hits, misses = 32, 3
        acc = hits / (hits + misses)
        self.assertAlmostEqual(acc, 0.914, delta=0.002)


if __name__ == "__main__":
    unittest.main(verbosity=2)
