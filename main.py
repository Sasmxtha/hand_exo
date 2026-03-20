"""
main.py — hand_exo entry point
Author: S. Sasmitha

Single command to launch any part of the system.

    python main.py game   --player Player1 --mode VISION
    python main.py game   --player Player1 --mode GLOVE
    python main.py demo                               # no hardware needed
    python main.py calibrate                          # camera calibration
    python main.py dashboard --player Player1
    python main.py report    --player Player1
    python main.py emg                                # EMG analysis demo
    python main.py evaluate                           # gesture eval (Table I)
"""

import argparse
import sys


def main():
    ap = argparse.ArgumentParser(
        prog="hand_exo",
        description="Hand Exoskeleton Sorting Game — S. Sasmitha",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = ap.add_subparsers(dest="cmd")

    # game
    g = sub.add_parser("game", help="Run the sorting game")
    g.add_argument("--player", default="Player1")
    g.add_argument("--mode",   default="VISION", choices=["VISION", "GLOVE"])

    # demo
    d = sub.add_parser("demo", help="Hardware-free simulated demo")
    d.add_argument("--player",   default="DemoPlayer")
    d.add_argument("--duration", type=float, default=45.0)
    d.add_argument("--headless", action="store_true")

    # calibrate
    sub.add_parser("calibrate", help="Interactive camera calibration")

    # dashboard
    db = sub.add_parser("dashboard", help="Generate analytics dashboard")
    db.add_argument("--player", default="Player1")
    db.add_argument("--save",   default=None)

    # report
    r = sub.add_parser("report", help="Generate PDF session report")
    r.add_argument("--player", default="Player1")
    r.add_argument("--out",    default="reports/session_report.pdf")
    r.add_argument("--demo",   action="store_true")

    # emg
    sub.add_parser("emg", help="Run EMG analysis demo")

    # evaluate
    ev = sub.add_parser("evaluate", help="Reproduce Table I gesture metrics")
    ev.add_argument("--save_cm", default=None)

    args = ap.parse_args()

    if args.cmd == "game":
        from src.game import SortingGame
        SortingGame(args.player, args.mode).run()

    elif args.cmd == "demo":
        from demo import HeadlessDemo, WindowedDemo
        try:
            import pygame
            _pg = True
        except ImportError:
            _pg = False
        if args.headless or not _pg:
            HeadlessDemo(args.player, args.duration).run()
        else:
            WindowedDemo(args.player, args.duration).run()

    elif args.cmd == "calibrate":
        from src.calibration import run
        run()

    elif args.cmd == "dashboard":
        from src.analytics_dashboard import build_dashboard
        build_dashboard(args.player, args.save)

    elif args.cmd == "report":
        from src.session_report import build_report
        build_report(args.player, args.out, demo=args.demo)

    elif args.cmd == "emg":
        import numpy as np
        from src.emg_analysis import EMGProcessor, plot_emg_comparison
        from src.config import EMG
        np.random.seed(42)
        vol = np.random.randn(17 * EMG.FS, 4) * 0.12
        vol[:, 2] *= 2.0
        act = np.random.randn(20 * EMG.FS, 4) * 0.04
        p = EMGProcessor()
        stats = p.compare(vol, act)
        print(f"Mean RMS ratio: {stats['mean_rms_ratio']:.2f}×")
        plot_emg_comparison(vol, act, save_path="emg_output.png")
        print("Saved emg_output.png")

    elif args.cmd == "evaluate":
        from src.evaluate_gestures import demo_evaluation, compute_metrics, \
            print_report, confusion_matrix_values, plot_confusion_matrix
        y_true, y_pred = demo_evaluation()
        metrics = compute_metrics(y_true, y_pred)
        print_report(metrics)
        cm = confusion_matrix_values(y_true, y_pred)
        plot_confusion_matrix(cm, save_path=args.save_cm)

    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
