"""
emg_analysis.py
Author: S. Sasmitha

sEMG signal processing pipeline and voluntary vs motor-actuated comparison.

Paper (Section IV-D):
  - 8 differential sEMG electrodes over major flexor/extensor groups
  - Multi-channel DAQ, all channels color-coded consistently
  - Pipeline: bandpass (20-450 Hz) → notch (50 Hz) → rectify → RMS envelope
  - Result: voluntary RMS ≈ 3× actuated RMS (mean across channels)
  - Confirms passive rehabilitation with reduced muscular effort
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import signal as sp
from typing import Optional

from src.config import EMG


class EMGProcessor:
    """
    Multi-channel sEMG processing pipeline.

    Pipeline
    --------
    1. 4th-order Butterworth bandpass  (20–450 Hz)
    2. IIR notch filter                (50 Hz power-line)
    3. Full-wave rectification
    4. RMS sliding-window envelope     (50 ms window)
    5. Per-channel normalisation       (max = 1.0)
    """

    def __init__(self):
        nyq = EMG.FS / 2.0
        lo, hi = EMG.BP_LO / nyq, EMG.BP_HI / nyq
        self._b_bp, self._a_bp = sp.butter(4, [lo, hi], btype="band")
        self._b_nf, self._a_nf = sp.iirnotch(EMG.NOTCH / nyq, EMG.NOTCH_Q)

    # ── Processing ─────────────────────────────────────────────────────────────

    def process(self, raw: np.ndarray) -> np.ndarray:
        """
        Full pipeline: raw ADC → normalised RMS envelope.

        Parameters
        ----------
        raw : (n_samples, n_channels) raw ADC values

        Returns
        -------
        env : (n_samples, n_channels) normalised envelope in [0, 1]
        """
        # Bandpass → notch → rectify
        filt = sp.filtfilt(self._b_bp, self._a_bp, raw, axis=0)
        filt = sp.filtfilt(self._b_nf, self._a_nf, filt, axis=0)
        rect = np.abs(filt)

        # RMS envelope
        win    = max(1, int(EMG.RMS_WIN_MS * EMG.FS / 1000))
        kernel = np.ones(win) / win
        env    = np.apply_along_axis(
            lambda x: np.convolve(x, kernel, mode="same"), 0, rect
        )

        # Normalise per channel
        mx = env.max(axis=0, keepdims=True)
        mx[mx == 0] = 1.0
        return env / mx

    def rms(self, sig: np.ndarray) -> float:
        return float(np.sqrt(np.mean(sig ** 2)))

    # ── Comparison (paper Section IV-D) ────────────────────────────────────────

    def compare(self, voluntary: np.ndarray,
                actuated: np.ndarray) -> dict:
        """
        Compute per-channel RMS ratio voluntary / actuated.

        Paper result: mean ratio ≈ 3×
        """
        n_ch = min(voluntary.shape[1], actuated.shape[1], len(EMG.LABELS))
        results = {}
        for ch in range(n_ch):
            v = self.rms(voluntary[:, ch])
            a = self.rms(actuated[:, ch])
            results[EMG.LABELS[ch]] = {
                "voluntary_rms": round(v, 6),
                "actuated_rms":  round(a, 6),
                "ratio":         round(v / a, 3) if a > 0 else float("inf"),
            }
        finite = [v["ratio"] for v in results.values()
                  if np.isfinite(v["ratio"])]
        results["mean_rms_ratio"] = round(np.mean(finite), 3) if finite else 0
        return results


# ── Reproduction of paper Figure 8 ────────────────────────────────────────────

def plot_emg_comparison(
    voluntary:   np.ndarray,
    actuated:    np.ndarray,
    n_ch:        int = 4,
    save_path:   Optional[str] = None,
):
    """
    Reproduces the dual-panel EMG amplitude vs time figure (paper Fig. 8).

    Colours match the paper: blue, orange, green, red for the four
    channels shown (Brachioradialis, Extensor Carpi Ulnaris,
    Tendon of Biceps Brachii, Flexor Digitorum Superficialis).
    """
    colours = ["tab:blue", "tab:orange", "tab:green", "tab:red"]
    t_v = np.arange(voluntary.shape[0]) / EMG.FS
    t_a = np.arange(actuated.shape[0])  / EMG.FS

    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    fig.suptitle("EMG Signal Comparison — Amplitude vs Time",
                 fontsize=13, fontweight="bold")

    for ch in range(min(n_ch, voluntary.shape[1])):
        axes[0].plot(t_v, voluntary[:, ch], color=colours[ch],
                     linewidth=0.6, label=EMG.LABELS[ch])
    axes[0].set_title("Voluntary Hand Movement", fontweight="bold")
    axes[0].set_ylabel("Amplitude (normalised)")
    axes[0].legend(fontsize=8, loc="upper right")
    axes[0].grid(linestyle="--", alpha=0.4)
    axes[0].set_ylim(-0.45, 0.45)

    for ch in range(min(n_ch, actuated.shape[1])):
        axes[1].plot(t_a, actuated[:, ch], color=colours[ch],
                     linewidth=0.6, label=EMG.LABELS[ch])
    axes[1].set_title("Motor-Actuated Movement", fontweight="bold")
    axes[1].set_xlabel("Time (s)")
    axes[1].set_ylabel("Amplitude (normalised)")
    axes[1].legend(fontsize=8, loc="upper right")
    axes[1].grid(linestyle="--", alpha=0.4)
    axes[1].set_ylim(-0.15, 0.15)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
    return fig


# ── Standalone ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    np.random.seed(42)
    fs = EMG.FS
    voluntary = np.random.randn(17 * fs, 4) * 0.12
    voluntary[:, 2] *= 2.0                        # dominant Biceps Brachii
    actuated  = np.random.randn(20 * fs, 4) * 0.04

    proc   = EMGProcessor()
    stats  = proc.compare(voluntary, actuated)
    print(f"Mean RMS ratio (voluntary / actuated): "
          f"{stats['mean_rms_ratio']:.2f}×")
    plot_emg_comparison(voluntary, actuated,
                        save_path="assets/screenshots/emg_output.png")
    print("Plot saved to assets/screenshots/emg_output.png")
