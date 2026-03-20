"""
gesture_recognition.py
Author: S. Sasmitha

MediaPipe Hands pipeline — 21 3-D landmarks → OPEN / CLOSED classification.

Paper equation (Section III-A):
    HandState = OPEN   if (1/5)·Σ d(tip_i, wrist) > τ_open
              = CLOSED otherwise

where d(·,·) is the 3-D Euclidean distance and τ_open = 0.25 (normalised).

Hardware: Microsoft LifeCam Studio @ 1280×720 / 30 FPS (Camera index 1).
"""

import cv2
import mediapipe as mp
import numpy as np
from typing import Tuple

from src.config import CAM


class GestureRecognizer:
    """
    Real-time hand-gesture recognizer using MediaPipe Hands.

    Returns (screen_x, screen_y, 'OPEN'|'CLOSED') from each call to
    get_hand_state().  Falls back to the last valid reading on dropped frames.
    """

    TIP_IDS = [4, 8, 12, 16, 20]   # thumb, index, middle, ring, pinky tips

    def __init__(self, camera_index: int = CAM.CAM_GESTURE):
        self._mp_hands = mp.solutions.hands
        self._mp_draw  = mp.solutions.drawing_utils
        self._hands    = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=CAM.DETECT_CONF,
            min_tracking_confidence=CAM.TRACK_CONF,
        )

        self._cap = cv2.VideoCapture(camera_index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM.WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM.HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS,          CAM.FPS)

        # Cache last known good values
        self._last_x     = CAM.WIDTH  // 2
        self._last_y     = CAM.HEIGHT // 2
        self._last_state = "OPEN"

    # ── Public ────────────────────────────────────────────────────────────────

    def get_hand_state(self) -> Tuple[int, int, str]:
        """
        Capture one frame, run MediaPipe, classify hand state.

        Returns
        -------
        (x, y, state) : int, int, str
            x, y  — index-finger tip position mapped to screen pixels
            state — 'OPEN' or 'CLOSED'
        """
        ret, frame = self._cap.read()
        if not ret:
            return self._last_x, self._last_y, self._last_state

        rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._hands.process(rgb)

        if not results.multi_hand_landmarks:
            return self._last_x, self._last_y, self._last_state

        lm    = results.multi_hand_landmarks[0].landmark
        wrist = lm[0]

        # Paper eq. (1): mean Euclidean distance from each tip to wrist
        dists = [
            np.sqrt(
                (lm[t].x - wrist.x) ** 2 +
                (lm[t].y - wrist.y) ** 2 +
                (lm[t].z - wrist.z) ** 2
            )
            for t in self.TIP_IDS
        ]
        state = "OPEN" if np.mean(dists) > CAM.TAU_OPEN else "CLOSED"

        # Index-finger tip (landmark 8) as pointer
        x = int(lm[8].x * CAM.WIDTH)
        y = int(lm[8].y * CAM.HEIGHT)

        self._last_x, self._last_y, self._last_state = x, y, state
        return x, y, state

    def get_annotated_frame(self):
        """Return a BGR frame with landmarks drawn (for debug window)."""
        ret, frame = self._cap.read()
        if not ret:
            return None
        rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._hands.process(rgb)
        if results.multi_hand_landmarks:
            for hand_lm in results.multi_hand_landmarks:
                self._mp_draw.draw_landmarks(
                    frame, hand_lm, self._mp_hands.HAND_CONNECTIONS
                )
        return frame

    def release(self):
        self._cap.release()
        self._hands.close()
