"""
analytics_dashboard.py
Author: S. Sasmitha

Generates the per-player progress dashboard from MySQL session data.
Falls back to demo data matching the paper's Table III when offline.

Usage
-----
    python src/analytics_dashboard.py --player Player1
    python src/analytics_dashboard.py --player Player1 --save reports/p1.png
"""

import argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch

try:
    from src.database import DatabaseManager
except ImportError:
    from database import DatabaseManager

# Paper Table III data (used as demo / offline fallback)
_PAPER_DATA = {
    "Player1": (91.5, 32, 3),
    "Player2": (90.3, 31, 3),
    "Player3": (74.8, 24, 8),
    "Player4": (89.3, 33, 4),
}

C = {"score": "#2196F3", "acc": "#4CAF50", "dur": "#FF9800",
     "bg": "#F5F7FA", "grid": "#DEDEDE"}


def _demo_data(player: str) -> dict:
    sessions   = [1, 2, 3]
    acc_base   = _PAPER_DATA.get(player, ("Player1", (86.5, 30, 5)))[0] \
                 if isinstance(_PAPER_DATA.get(player), tuple) \
                 else 86.5
    accs = [max(0, acc_base - 5), acc_base, min(100, acc_base + 2)]
    return {
        "player":       player,
        "sessions":     sessions,
        "scores":       [80, 90, 100],
        "accuracies":   accs,
        "durations":    [120, 130, 125],
        "avg_score":    90.0,
        "games_played": 3,
    }


def fetch_history(player: str) -> dict:
    db = DatabaseManager()
    if db._cursor is None:
        db.close()
        return _demo_data(player)
    try:
        db._cursor.execute(
            "SELECT session_id, score, accuracy, duration_sec "
            "FROM game_sessions WHERE player_name=%s "
            "ORDER BY session_id ASC", (player,)
        )
        rows  = db._cursor.fetchall()
        stats = db.get_player_stats(player) or {}
    finally:
        db.close()
    if not rows:
        return _demo_data(player)
    return {
        "player":       player,
        "sessions":     [r[0] for r in rows],
        "scores":       [r[1] for r in rows],
        "accuracies":   [r[2] * 100 for r in rows],
        "durations":    [r[3] for r in rows],
        "avg_score":    stats.get("avg_score", 0),
        "games_played": stats.get("games_played", len(rows)),
    }


def build_dashboard(player: str, save_path: str = None):
    data = fetch_history(player)
    x    = list(range(1, len(data["sessions"]) + 1))

    fig = plt.figure(figsize=(16, 9), facecolor="white")
    fig.suptitle(
        f"Rehabilitation Progress Dashboard — {data['player']}",
        fontsize=15, fontweight="bold", y=0.97
    )
    gs = gridspec.GridSpec(2, 3, figure=fig,
                           hspace=0.45, wspace=0.35,
                           left=0.07, right=0.97,
                           top=0.90, bottom=0.10)

    # KPI row
    ax_k = fig.add_subplot(gs[0, :])
    ax_k.axis("off")
    kpis = [
        ("Games Played",    str(data["games_played"]),            C["score"]),
        ("Avg Score",       f"{data['avg_score']:.1f}",           C["acc"]),
        ("Latest Accuracy", f"{data['accuracies'][-1]:.1f}%",     C["dur"]),
        ("Overall Accuracy",f"{np.mean(data['accuracies']):.1f}%","#9C27B0"),
    ]
    x0 = 0.02
    for label, val, col in kpis:
        fp = FancyBboxPatch((x0, .08), .20, .80,
                             boxstyle="round,pad=0.02",
                             facecolor=col, alpha=.14,
                             edgecolor=col, linewidth=1.5,
                             transform=ax_k.transAxes, clip_on=False)
        ax_k.add_patch(fp)
        ax_k.text(x0 + .10, .65, val, ha="center", va="center",
                  fontsize=20, fontweight="bold", color=col,
                  transform=ax_k.transAxes)
        ax_k.text(x0 + .10, .24, label, ha="center", va="center",
                  fontsize=10, color="#555", transform=ax_k.transAxes)
        x0 += .24

    def _line(ax, y_data, col, title, ylabel, ylim=None):
        ax.plot(x, y_data, color=col, linewidth=2.2, marker="o",
                markersize=7, markerfacecolor="white",
                markeredgewidth=2, markeredgecolor=col, zorder=3)
        ax.fill_between(x, y_data, alpha=.10, color=col)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_xlabel("Session"); ax.set_ylabel(ylabel)
        ax.set_xticks(x)
        ax.grid(True, linestyle="--", color=C["grid"])
        ax.set_facecolor(C["bg"])
        if ylim: ax.set_ylim(*ylim)

    ax1 = fig.add_subplot(gs[1, 0])
    _line(ax1, data["scores"], C["score"], "Score per Session",
          "Score", (0, 120))

    ax2 = fig.add_subplot(gs[1, 1])
    _line(ax2, data["accuracies"], C["acc"], "Accuracy per Session",
          "Accuracy (%)", (0, 105))
    ax2.axhspan(0,  50,  alpha=.05, color="red",    label="Beginner")
    ax2.axhspan(50, 75,  alpha=.05, color="orange", label="Intermediate")
    ax2.axhspan(75, 105, alpha=.05, color="green",  label="Advanced")
    ax2.legend(fontsize=7, loc="lower right")

    # Confusion matrix (paper Table I)
    ax3 = fig.add_subplot(gs[1, 2])
    import seaborn as sns
    cm = np.array([[93, 7], [5, 95]])
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=["Open", "Closed"],
                yticklabels=["Open", "Closed"],
                ax=ax3, annot_kws={"size": 18, "weight": "bold"})
    ax3.set_xlabel("Predicted"); ax3.set_ylabel("Actual")
    ax3.set_title("Gesture Confusion Matrix\n(Table I)", fontweight="bold")

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"✅  Dashboard → {save_path}")
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", default="Player1")
    ap.add_argument("--save",   default=None)
    args = ap.parse_args()
    build_dashboard(args.player, args.save)
