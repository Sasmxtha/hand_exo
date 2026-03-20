"""
Session Report Generator — exports a PDF progress report per player
Author: S. Sasmitha

Pulls session history from MySQL (or uses demo data offline) and
writes a polished single-page PDF report.

Usage
-----
    python src/session_report.py --player Player1 --out reports/Player1.pdf
    python src/session_report.py --demo --out reports/demo_report.pdf
"""

from __future__ import annotations
import argparse
import os
import sys
import io
import datetime

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_pdf import PdfPages

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from src.database import DatabaseManager
    from src.analytics_dashboard import _demo_data
except ImportError:
    from database import DatabaseManager
    from analytics_dashboard import _demo_data


# ── Colour palette ─────────────────────────────────────────────────────────
C1 = "#1565C0"   # deep blue
C2 = "#2E7D32"   # deep green
C3 = "#E65100"   # deep orange
C4 = "#6A1B9A"   # deep purple
LIGHT_GREY = "#F0F4F8"
MID_GREY   = "#B0BEC5"
DARK       = "#263238"


def _fetch(player_name: str, demo: bool) -> dict:
    if demo:
        return _demo_data(player_name)
    db = DatabaseManager()
    if db._cursor is None:
        db.close()
        return _demo_data(player_name)
    try:
        db._cursor.execute(
            "SELECT session_id, score, accuracy, duration_sec, started_at "
            "FROM game_sessions WHERE player_name=%s ORDER BY session_id ASC",
            (player_name,),
        )
        rows = db._cursor.fetchall()
        stats = db.get_player_stats(player_name) or {}
    finally:
        db.close()
    if not rows:
        return _demo_data(player_name)
    return {
        "player":      player_name,
        "sessions":    [r[0] for r in rows],
        "scores":      [r[1] for r in rows],
        "accuracies":  [r[2] * 100 for r in rows],
        "durations":   [r[3] for r in rows],
        "dates":       [str(r[4])[:10] if r[4] else "" for r in rows],
        "avg_score":   stats.get("avg_score", 0),
        "games_played":stats.get("games_played", len(rows)),
    }


def build_report(player_name: str, out_path: str, demo: bool = False):
    data = _fetch(player_name, demo)
    x    = list(range(1, len(data["sessions"]) + 1))
    now  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)

    with PdfPages(out_path) as pdf:
        fig = plt.figure(figsize=(11.69, 8.27), facecolor="white")   # A4 landscape
        gs  = gridspec.GridSpec(
            3, 3, figure=fig,
            hspace=0.55, wspace=0.38,
            left=0.07, right=0.97,
            top=0.85, bottom=0.09,
        )

        # ── Title banner ────────────────────────────────────────────────────
        ax_title = fig.add_axes([0, 0.88, 1, 0.12])
        ax_title.set_facecolor(C1)
        ax_title.axis("off")
        ax_title.text(0.03, 0.62,
                      "Hand Rehabilitation System — Session Progress Report",
                      color="white", fontsize=16, fontweight="bold",
                      transform=ax_title.transAxes, va="top")
        ax_title.text(0.03, 0.22,
                      f"Player: {data['player']}   |   "
                      f"Total Sessions: {data['games_played']}   |   "
                      f"Avg Score: {data['avg_score']:.1f}   |   "
                      f"Generated: {now}",
                      color="#B3E5FC", fontsize=9,
                      transform=ax_title.transAxes, va="top")
        ax_title.text(0.97, 0.50,
                      "S. Sasmitha · Amrita School of AI",
                      color="#B3E5FC", fontsize=8,
                      transform=ax_title.transAxes, ha="right", va="center")

        # ── KPI boxes (row 0 across all 3 columns) ───────────────────────────
        kpis = [
            ("Games Played",   str(data["games_played"]),          C1),
            ("Avg Score",      f"{data['avg_score']:.1f}",         C2),
            ("Latest Accuracy",f"{data['accuracies'][-1]:.1f} %",  C3),
            ("Overall Accuracy",f"{np.mean(data['accuracies']):.1f} %", C4),
            ("Best Score",     str(max(data['scores'])),           C1),
            ("Total Duration", f"{sum(data['durations'])} s",      C2),
        ]
        kpi_axes_positions = [
            [0.07 + i * 0.156, 0.87, 0.14, 0.065] for i in range(6)
        ]
        for (label, value, color), pos in zip(kpis, kpi_axes_positions):
            ax_k = fig.add_axes(pos)
            ax_k.set_facecolor(LIGHT_GREY)
            ax_k.axis("off")
            ax_k.text(0.5, 0.70, value, ha="center", va="center",
                      fontsize=14, fontweight="bold", color=color,
                      transform=ax_k.transAxes)
            ax_k.text(0.5, 0.22, label, ha="center", va="center",
                      fontsize=7.5, color="#546E7A",
                      transform=ax_k.transAxes)
            for spine_side in ["top","bottom","left","right"]:
                ax_k.spines[spine_side].set_visible(False)
            ax_k.add_patch(
                plt.Rectangle((0,0), 1, 0.04,
                               transform=ax_k.transAxes, color=color,
                               clip_on=False)
            )

        # ── Score over sessions ───────────────────────────────────────────────
        ax1 = fig.add_subplot(gs[0:2, 0])
        ax1.plot(x, data["scores"], color=C1, linewidth=2,
                 marker="o", markersize=6,
                 markerfacecolor="white", markeredgewidth=1.8,
                 markeredgecolor=C1, zorder=3)
        ax1.fill_between(x, data["scores"], alpha=0.10, color=C1)
        ax1.set_title("Score per Session", fontsize=11, fontweight="bold",
                      color=DARK, pad=6)
        ax1.set_xlabel("Session #", fontsize=9)
        ax1.set_ylabel("Score",     fontsize=9)
        ax1.set_xticks(x)
        ax1.grid(True, linestyle="--", alpha=0.4)
        ax1.set_facecolor(LIGHT_GREY)
        ax1.set_ylim(0, max(data["scores"]) * 1.2 + 10)

        # ── Accuracy over sessions ────────────────────────────────────────────
        ax2 = fig.add_subplot(gs[0:2, 1])
        ax2.plot(x, data["accuracies"], color=C2, linewidth=2,
                 marker="o", markersize=6,
                 markerfacecolor="white", markeredgewidth=1.8,
                 markeredgecolor=C2, zorder=3)
        ax2.fill_between(x, data["accuracies"], alpha=0.10, color=C2)
        ax2.axhspan(0,  50,  alpha=0.05, color="red")
        ax2.axhspan(50, 75,  alpha=0.05, color="orange")
        ax2.axhspan(75, 105, alpha=0.05, color="green")
        ax2.set_title("Accuracy per Session (%)", fontsize=11,
                      fontweight="bold", color=DARK, pad=6)
        ax2.set_xlabel("Session #", fontsize=9)
        ax2.set_ylabel("Accuracy (%)", fontsize=9)
        ax2.set_xticks(x)
        ax2.set_ylim(0, 105)
        ax2.grid(True, linestyle="--", alpha=0.4)
        ax2.set_facecolor(LIGHT_GREY)

        # ── Session duration ──────────────────────────────────────────────────
        ax3 = fig.add_subplot(gs[0:2, 2])
        bars = ax3.bar(x, data["durations"],
                       color=[C3] * len(x), alpha=0.75,
                       edgecolor="white", linewidth=0.8)
        ax3.set_title("Session Duration (s)", fontsize=11,
                      fontweight="bold", color=DARK, pad=6)
        ax3.set_xlabel("Session #", fontsize=9)
        ax3.set_ylabel("Duration (s)", fontsize=9)
        ax3.set_xticks(x)
        ax3.grid(True, linestyle="--", alpha=0.3, axis="y")
        ax3.set_facecolor(LIGHT_GREY)

        # ── Session data table ────────────────────────────────────────────────
        ax_table = fig.add_subplot(gs[2, :])
        ax_table.axis("off")
        col_labels = ["Session", "Score", "Accuracy (%)", "Duration (s)", "Tier"]
        tiers = []
        for acc in data["accuracies"]:
            if acc < 50:
                tiers.append("Beginner")
            elif acc < 75:
                tiers.append("Intermediate")
            else:
                tiers.append("Advanced")

        rows_data = [
            [str(s), str(sc), f"{ac:.1f}", str(dur), tier]
            for s, sc, ac, dur, tier in zip(
                x, data["scores"], data["accuracies"],
                data["durations"], tiers
            )
        ]

        tbl = ax_table.table(
            cellText=rows_data,
            colLabels=col_labels,
            cellLoc="center",
            loc="center",
            bbox=[0, 0, 1, 1],
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)

        for (row, col), cell in tbl.get_celld().items():
            cell.set_edgecolor(MID_GREY)
            if row == 0:
                cell.set_facecolor(C1)
                cell.set_text_props(color="white", fontweight="bold")
            elif row % 2 == 0:
                cell.set_facecolor(LIGHT_GREY)
            else:
                cell.set_facecolor("white")
            # Colour tier column
            if row > 0 and col == 4:
                tier = rows_data[row - 1][4]
                cell.set_facecolor(
                    "#E8F5E9" if tier == "Advanced" else
                    "#FFF3E0" if tier == "Intermediate" else
                    "#FFEBEE"
                )

        ax_table.set_title("Session Log", fontsize=11,
                            fontweight="bold", color=DARK, pad=8)

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    print(f"✅  PDF report saved → {out_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a PDF session report for a player."
    )
    parser.add_argument("--player", type=str, default="Player1")
    parser.add_argument("--out",    type=str, default="reports/session_report.pdf")
    parser.add_argument("--demo",   action="store_true",
                        help="Use synthetic demo data (no MySQL needed)")
    args = parser.parse_args()
    build_report(args.player, args.out, demo=args.demo)
