"""
config.py
---------
Single source of truth for the entire webcam-calibration project.

If you change camera resolution, update CAMERA_WIDTH / CAMERA_HEIGHT here,
delete old calibration_images, recapture, and rerun calibrate.py.
Everything else adjusts automatically.
"""

import os
from pathlib import Path

# ── Project root (always the folder this file lives in) ───────────────────────
ROOT = Path(__file__).resolve().parent


# =============================================================================
# CAMERA SETTINGS
# =============================================================================
CAMERA_INDEX  = 0           # 0 = first camera (/dev/video0). Try 1, 2 ... for others
CAMERA_WIDTH  = 1280        # must be a mode your camera supports
                            # (Linux: v4l2-ctl --list-formats-ext -d /dev/video0)
CAMERA_HEIGHT = 960
CAMERA_FPS    = 30
CAMERA_CODEC  = "MJPG"      # 4-char FourCC string


# =============================================================================
# CHARUCO BOARD
# =============================================================================
SQUARES_X        = 8                               # columns
SQUARES_Y        = 6                               # rows
SQUARE_LENGTH    = 0.030                           # metres (30 mm) -> board needs A4 LANDSCAPE
MARKER_LENGTH    = 0.022                           # metres (22 mm)
ARUCO_DICTIONARY = "DICT_5X5_50"                  # must match generate_charuco.py


# =============================================================================
# PATHS  (all relative to project ROOT, resolved to absolute)
# =============================================================================
CALIBRATION_IMAGES  = str(ROOT / "data" / "calibration_images")
CALIBRATION_RESULTS = str(ROOT / "data" / "calibration_results")
CALIBRATION_YAML    = str(ROOT / "data" / "calibration_results" / "calibration.yaml")
BOARDS_DIR          = str(ROOT / "data" / "boards")
CAPTURED_DIR        = str(ROOT / "data" / "captured_undistorted")


# =============================================================================
# CALIBRATION OPTIONS
# =============================================================================
FIX_K3 = False   # True = do not estimate the k3 radial term. Try this if the
                 # calibration shows a huge |k3| (overfitting) or the undistorted
                 # image looks wavy near the edges. See docs/troubleshooting.md
