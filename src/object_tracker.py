"""
object_tracker.py
Author: S. Sasmitha

OpenCV CSRT object tracker with perspective-transform calibration.

Paper (Section III-A / III-B):
  - Logitech C920 Camera 0 @ 1280×720 / 30 FPS
  - CSRT (Discriminative Correlation Filter with Channel and Spatial
    Reliability) for robust tracking during occlusion and scale change
  - Perspective transform maps camera coords → game screen coords (eq. 2)
  - Auto-reinitialises after 1.2 s of tracking failure
  - 95.8 % frame coverage sustained across all sessions
"""

import cv2
import numpy as np
import time
from typing import Optional, Tuple

from src.config import CAM


class ObjectTracker:
    """
    Tracks a physical game object using CSRT.
    Converts camera-space bounding boxes to game-screen coordinates via
    the homogeneous perspective transform stored in calibration_matrix.npy.
    """

    def __init__(self, camera_index: int = CAM.CAM_TRACKER):
        self._cap = cv2.VideoCapture(camera_index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM.WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM.HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS,          CAM.FPS)

        self._tracker:  Optional[cv2.TrackerCSRT] = None
        self._bbox:     Optional[Tuple[int,int,int,int]] = None
        self._tracking  = False
        self._fail_time: Optional[float] = None
        self._M: Optional[np.ndarray] = None   # 3×3 perspective matrix

        self._load_calibration()

    # ── Calibration ────────────────────────────────────────────────────────────

    def _load_calibration(self):
        """Load perspective matrix saved by calibration.py."""
        try:
            self._M = np.load(CAM.CALIB_PATH)
        except FileNotFoundError:
            pass   # will use identity until calibration is run

    def calibrate(self,
                  camera_pts: np.ndarray,
                  screen_pts: np.ndarray):
        """
        Compute and save the perspective transform.

        Paper eq. (2):
            [x', y', w']^T = M · [x, y, 1]^T
            screen_x = x'/w',  screen_y = y'/w'

        Parameters
        ----------
        camera_pts : (4, 2) float32 — reference points in camera pixels
        screen_pts : (4, 2) float32 — corresponding game-screen pixels
        """
        self._M = cv2.getPerspectiveTransform(
            np.float32(camera_pts),
            np.float32(screen_pts),
        )
        np.save(CAM.CALIB_PATH, self._M)

    def camera_to_screen(self, cx: int, cy: int) -> Tuple[int, int]:
        """Apply perspective transform to a single camera-space point."""
        if self._M is None:
            return cx, cy
        pt  = np.float32([[[cx, cy]]])
        dst = cv2.perspectiveTransform(pt, self._M)
        return int(dst[0][0][0]), int(dst[0][0][1])

    # ── Tracking ───────────────────────────────────────────────────────────────

    def init_tracking(self, bbox: Tuple[int, int, int, int]):
        """
        Initialise CSRT tracker with an (x, y, w, h) bounding box.
        Should be called once when the game object is first detected.
        """
        ret, frame = self._cap.read()
        if not ret:
            return
        self._tracker = cv2.TrackerCSRT_create()
        self._tracker.init(frame, bbox)
        self._bbox     = bbox
        self._tracking = True
        self._fail_time = None

    def update(self) -> Tuple[bool, Optional[Tuple[int,int,int,int]]]:
        """
        Read one frame and run the tracker.

        Returns (success, bbox_in_camera_space).
        Auto-reinitialises after CAM.CSRT_RECOVER seconds of failure.
        """
        if not self._tracking or self._tracker is None:
            return False, None

        ret, frame = self._cap.read()
        if not ret:
            return False, None

        ok, bbox = self._tracker.update(frame)

        if ok:
            self._bbox      = tuple(map(int, bbox))
            self._fail_time = None
            return True, self._bbox

        # Tracking lost
        if self._fail_time is None:
            self._fail_time = time.time()
        elif time.time() - self._fail_time >= CAM.CSRT_RECOVER:
            # Auto-reinitialise with last known bbox
            if self._bbox is not None:
                self.init_tracking(self._bbox)
        return False, None

    def get_screen_position(self) -> Tuple[Optional[int], Optional[int]]:
        """Return the object's current centre in game-screen coordinates."""
        ok, bbox = self.update()
        if not ok or bbox is None:
            return None, None
        cx = bbox[0] + bbox[2] // 2
        cy = bbox[1] + bbox[3] // 2
        return self.camera_to_screen(cx, cy)

    def release(self):
        self._cap.release()
