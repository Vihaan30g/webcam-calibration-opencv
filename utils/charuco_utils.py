"""
utils/charuco_utils.py
----------------------
ChArUco board and detector setup.
All parameters come from config.py — never hardcoded here.
"""

import sys
from pathlib import Path
import cv2
import cv2.aruco as aruco

# ── resolve project root so this module works from any cwd ───────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config as cfg


def _get_aruco_dict():
    """Resolve the ARUCO_DICTIONARY string from config to a cv2.aruco constant."""
    mapping = {
        "DICT_4X4_50":    aruco.DICT_4X4_50,
        "DICT_4X4_100":   aruco.DICT_4X4_100,
        "DICT_5X5_50":    aruco.DICT_5X5_50,
        "DICT_5X5_100":   aruco.DICT_5X5_100,
        "DICT_6X6_50":    aruco.DICT_6X6_50,
        "DICT_6X6_100":   aruco.DICT_6X6_100,
    }
    key = cfg.ARUCO_DICTIONARY
    if key not in mapping:
        raise ValueError(
            f"Unknown ARUCO_DICTIONARY '{key}' in config.py.\n"
            f"  Valid options: {list(mapping.keys())}"
        )
    return mapping[key]


def get_charuco_board():
    """Return (CharucoBoard, aruco.Dictionary) using config.py parameters."""
    dictionary = aruco.getPredefinedDictionary(_get_aruco_dict())
    board = aruco.CharucoBoard(
        (cfg.SQUARES_X, cfg.SQUARES_Y),
        cfg.SQUARE_LENGTH,
        cfg.MARKER_LENGTH,
        dictionary,
    )
    return board, dictionary


def get_charuco_detector():
    """
    Return (CharucoDetector, CharucoBoard, aruco.Dictionary).
    Uses the OpenCV ≥ 4.7 CharucoDetector API.
    """
    board, dictionary = get_charuco_board()
    detector_params   = aruco.DetectorParameters()
    charuco_params    = aruco.CharucoParameters()
    detector          = aruco.CharucoDetector(board, charuco_params, detector_params)
    return detector, board, dictionary
