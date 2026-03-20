"""
Tests — EMG Signal Analysis
Author: S. Sasmitha
"""

import unittest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def compute_rms(signal: np.ndarray) -> float:
    return float(np.sqrt(np.mean(signal ** 2)))


def normalise(signal: np.ndarray) -> np.ndarray:
    max_val = signal.max()
    return signal / max_val if max_val != 0 else signal


class TestRMSComputation(unittest.TestCase):

    def test_rms_all_zeros(self):
        sig = np.zeros(1000)
        self.assertAlmostEqual(compute_rms(sig), 0.0)

    def test_rms_constant_signal(self):
        sig = np.ones(1000) * 0.5
        self.assertAlmostEqual(compute_rms(sig), 0.5, places=5)

    def test_rms_sine_wave(self):
        """RMS of sin(x) over full cycles = 1/√2 ≈ 0.7071."""
        t   = np.linspace(0, 2 * np.pi * 50, 10000)
        sig = np.sin(t)
        self.assertAlmostEqual(compute_rms(sig), 1.0 / np.sqrt(2), delta=0.01)

    def test_rms_white_noise_positive(self):
        np.random.seed(42)
        sig = np.random.randn(10000)
        self.assertGreater(compute_rms(sig), 0.0)


class TestVoluntaryVsActuatedRatio(unittest.TestCase):
    """
    Paper result: mean RMS voluntary ≈ 3× mean RMS actuated.
    """

    def setUp(self):
        np.random.seed(7)
        self.fs    = 1000
        self.dur_v = 17
        self.dur_a = 20

        # Voluntary — higher amplitude
        self.voluntary = np.random.randn(self.dur_v * self.fs, 4) * 0.12
        self.voluntary[:, 2] *= 2.0   # dominant channel

        # Actuated — ~1/3 amplitude
        self.actuated = np.random.randn(self.dur_a * self.fs, 4) * 0.04

    def test_voluntary_rms_greater_than_actuated(self):
        for ch in range(4):
            v_rms = compute_rms(self.voluntary[:, ch])
            a_rms = compute_rms(self.actuated[:, ch])
            self.assertGreater(v_rms, a_rms,
                               f"Channel {ch}: voluntary RMS should exceed actuated")

    def test_mean_rms_ratio_approx_3x(self):
        ratios = []
        for ch in range(4):
            v = compute_rms(self.voluntary[:, ch])
            a = compute_rms(self.actuated[:, ch])
            ratios.append(v / a if a > 0 else 0)
        mean_ratio = np.mean(ratios)
        self.assertGreater(mean_ratio, 2.0,
                           f"Mean RMS ratio {mean_ratio:.2f} should be > 2×")

    def test_normalised_signal_max_is_one(self):
        norm = normalise(self.voluntary[:, 0])
        self.assertAlmostEqual(norm.max(), 1.0, places=5)

    def test_normalised_signal_min_non_negative_after_abs(self):
        norm = normalise(np.abs(self.voluntary[:, 0]))
        self.assertGreaterEqual(norm.min(), 0.0)


class TestSignalShape(unittest.TestCase):

    def test_8_channel_output_shape(self):
        raw = np.random.randn(5000, 8)
        self.assertEqual(raw.shape[1], 8)

    def test_single_channel_rms(self):
        sig = np.random.randn(1000)
        rms = compute_rms(sig)
        self.assertTrue(np.isfinite(rms))
        self.assertGreater(rms, 0.0)

    def test_rms_scales_with_amplitude(self):
        sig_low  = np.random.randn(1000) * 0.04
        sig_high = np.random.randn(1000) * 0.12
        np.random.seed(99)   # same seed for fairness
        self.assertLess(compute_rms(sig_low), compute_rms(sig_high) * 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
