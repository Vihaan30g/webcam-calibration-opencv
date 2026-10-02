"""
utils/camera.py
---------------
Reusable camera-open module.  Every script in this project uses open_camera().

Responsibilities:
  - Request the resolution and codec defined in config.py via V4L2.
  - Print the active camera configuration after opening.
  - Warn loudly if the camera did not accept the requested resolution.
  - Raise RuntimeError if the camera cannot be opened at all.

Optional: check_calibration_resolution(yaml_path) verifies that the saved
calibration matches the current camera resolution — call this before undistorting.
"""

import sys
from pathlib import Path
import cv2
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config as cfg


# ── FourCC helper ─────────────────────────────────────────────────────────────

def _fourcc_int(code: str) -> int:
    assert len(code) == 4, "Codec must be a 4-character string (e.g. 'MJPG')"
    return cv2.VideoWriter_fourcc(*code)


def _fourcc_str(val: int) -> str:
    return "".join(chr((val >> 8 * i) & 0xFF) for i in range(4))


def _backend() -> int:
    """V4L2 on Linux; let OpenCV choose (DirectShow/MSMF/AVFoundation) elsewhere."""
    return cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY


# ── Main public function ───────────────────────────────────────────────────────

def open_camera(
    camera_index: int  = None,
    width: int         = None,
    height: int        = None,
    fps: int           = None,
    codec: str         = None,
) -> cv2.VideoCapture:
    """
    Open a camera (V4L2 on Linux), request the desired settings, and return the cap.

    All arguments default to values in config.py so callers can simply write:
        cap = open_camera()

    Parameters
    ----------
    camera_index : int   override config.CAMERA_INDEX
    width        : int   override config.CAMERA_WIDTH
    height       : int   override config.CAMERA_HEIGHT
    fps          : int   override config.CAMERA_FPS
    codec        : str   override config.CAMERA_CODEC  (4-char FourCC, e.g. "MJPG")

    Returns
    -------
    cv2.VideoCapture  (already opened and configured)

    Raises
    ------
    RuntimeError if the camera cannot be opened.
    """
    idx    = camera_index if camera_index is not None else cfg.CAMERA_INDEX
    w      = width        if width        is not None else cfg.CAMERA_WIDTH
    h      = height       if height       is not None else cfg.CAMERA_HEIGHT
    f      = fps          if fps          is not None else cfg.CAMERA_FPS
    codec_ = codec        if codec        is not None else cfg.CAMERA_CODEC

    print(f"\n{'─'*55}")
    print(f"  Opening camera index {idx}")
    print(f"  Requesting  : {w}×{h}  {codec_}  {f} fps")
    print(f"{'─'*55}")

    cap = cv2.VideoCapture(idx, _backend())

    if not cap.isOpened():
        raise RuntimeError(
            f"Cannot open camera index {idx}.\n"
            f"  Check that /dev/video{idx} exists and is not in use."
        )

    # ── apply settings ────────────────────────────────────────────────────────
    cap.set(cv2.CAP_PROP_FOURCC,      _fourcc_int(codec_))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    cap.set(cv2.CAP_PROP_FPS,          f)

    # ── read back what the driver actually accepted ───────────────────────────
    actual_w     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps   = cap.get(cv2.CAP_PROP_FPS)
    actual_codec = _fourcc_str(int(cap.get(cv2.CAP_PROP_FOURCC)))

    print(f"  Got         : {actual_w}×{actual_h}  {actual_codec}  {actual_fps:.1f} fps")

    # ── warn on mismatch ──────────────────────────────────────────────────────
    ok = True
    if actual_w != w or actual_h != h:
        print(
            f"\n  [WARNING] Resolution mismatch!\n"
            f"            Requested {w}×{h}, got {actual_w}×{actual_h}.\n"
            f"            Your camera may not support this mode.\n"
            f"            Run:  v4l2-ctl --device=/dev/video{idx} --list-formats-ext\n"
            f"            to see supported resolutions."
        )
        ok = False

    if actual_codec.strip("\x00") != codec_.strip():
        print(
            f"\n  [WARNING] Codec mismatch!\n"
            f"            Requested '{codec_}', got '{actual_codec}'.\n"
            f"            Frames may be decoded at lower quality."
        )
        ok = False

    if ok:
        print(f"  ✓ Camera ready.\n")
    else:
        print(f"  Camera opened with above warnings.\n")

    return cap


# ── Calibration-resolution guard ──────────────────────────────────────────────

def check_calibration_resolution(yaml_path: str = None, cap: cv2.VideoCapture = None):
    """
    Verify that the calibration YAML resolution matches the live camera resolution.

    Call this in undistort / capture_undistorted BEFORE processing frames,
    so you don't silently apply wrong calibration.

    Parameters
    ----------
    yaml_path : str              path to calibration.yaml (default: config.CALIBRATION_YAML)
    cap       : cv2.VideoCapture already-opened camera (used to read actual resolution)

    Raises
    ------
    RuntimeError if there is a resolution mismatch.
    """
    yaml_path = yaml_path or cfg.CALIBRATION_YAML

    if not Path(yaml_path).exists():
        raise FileNotFoundError(
            f"Calibration file not found: {yaml_path}\n"
            f"  Run scripts/calibrate.py first."
        )

    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    cal_w = data["image_width"]
    cal_h = data["image_height"]

    if cap is not None:
        cam_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        cam_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    else:
        cam_w = cfg.CAMERA_WIDTH
        cam_h = cfg.CAMERA_HEIGHT

    print(f"  Calibration : {cal_w}×{cal_h}")
    print(f"  Camera      : {cam_w}×{cam_h}")

    if cal_w != cam_w or cal_h != cam_h:
        raise RuntimeError(
            f"\n[ERROR] Resolution mismatch!\n"
            f"  Calibration was done at {cal_w}×{cal_h}.\n"
            f"  Camera is running at    {cam_w}×{cam_h}.\n"
            f"  You must recalibrate at the current camera resolution,\n"
            f"  or change CAMERA_WIDTH / CAMERA_HEIGHT in config.py to match\n"
            f"  the resolution used during calibration ({cal_w}×{cal_h})."
        )

    print(f"  ✓ Resolution match: {cam_w}×{cam_h}\n")
