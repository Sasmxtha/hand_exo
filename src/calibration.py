"""
calibration.py
Author: S. Sasmitha

Interactive 4-point perspective calibration.
Click the four corners of the game display in camera view to generate
the 3×3 perspective matrix (paper eq. 2) and save it to disk.

Usage
-----
    python src/calibration.py
"""

import cv2
import numpy as np
import os
from src.config import CAM, GAME

_pts: list = []


def _on_click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN and len(_pts) < 4:
        _pts.append((x, y))
        print(f"  Point {len(_pts)}: ({x}, {y})")


def run():
    cap = cv2.VideoCapture(CAM.CAM_TRACKER)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM.WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM.HEIGHT)

    cv2.namedWindow("Calibration", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Calibration", _on_click)

    print("\n=== Perspective Calibration ===")
    print("Click the 4 corners of the game display area:")
    print("  1. Top-left  2. Top-right  3. Bottom-right  4. Bottom-left")
    print("Press Q to cancel.\n")

    screen_corners = np.float32([
        [0,           0],
        [GAME.SCREEN_W, 0],
        [GAME.SCREEN_W, GAME.SCREEN_H],
        [0,           GAME.SCREEN_H],
    ])

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        for i, pt in enumerate(_pts):
            cv2.circle(frame, pt, 8, (0, 255, 0), -1)
            cv2.putText(frame, str(i + 1), (pt[0] + 10, pt[1] - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        if len(_pts) >= 2:
            for i in range(len(_pts) - 1):
                cv2.line(frame, _pts[i], _pts[i + 1], (0, 200, 255), 2)

        cv2.putText(frame, f"Corners: {len(_pts)}/4 | Q=quit",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 255, 0), 2)
        cv2.imshow("Calibration", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if len(_pts) == 4:
            M = cv2.getPerspectiveTransform(
                np.float32(_pts), screen_corners
            )
            np.save(CAM.CALIB_PATH, M)
            print(f"\n✅  Matrix saved → {CAM.CALIB_PATH}")
            cv2.waitKey(1500)
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run()
