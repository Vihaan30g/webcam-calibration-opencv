"""
scripts/capture_undistorted.py
-------------------------------
Live webcam preview with undistortion applied in real-time.
Press [Space] to capture and save an undistorted frame.
Press [q] to quit.

Saved images are written at the native camera resolution — no resizing.
Output path: config.CAPTURED_DIR (default: data/captured_undistorted/)

Usage (from project root):
    python3 scripts/capture_undistorted.py [--output_dir path/to/folder]
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config as cfg
from utils.camera import open_camera, check_calibration_resolution


# ── calibration loader ────────────────────────────────────────────────────────

def load_calibration():
    yaml_path = cfg.CALIBRATION_YAML
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(
            f"Calibration file not found: {yaml_path}\n"
            "  Run scripts/calibrate.py first."
        )
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
    cm = np.array(data["camera_matrix"]["data"],         dtype=np.float64).reshape(3, 3)
    dc = np.array(data["distortion_coefficients"]["data"], dtype=np.float64).reshape(1, -1)
    image_size = (data["image_width"], data["image_height"])
    return cm, dc, image_size


# ── main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Capture undistorted images from webcam")
    p.add_argument("--output_dir", default=cfg.CAPTURED_DIR,
                   help=f"Where to save captured images (default: {cfg.CAPTURED_DIR})")
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    # ── open camera ───────────────────────────────────────────────────────────
    cap = open_camera()

    # ── check calibration ─────────────────────────────────────────────────────
    print("  Checking calibration resolution …")
    check_calibration_resolution(cap=cap)   # raises RuntimeError on mismatch

    # ── load calibration ──────────────────────────────────────────────────────
    camera_matrix, dist_coeffs, image_size = load_calibration()

    # Build maps once (full resolution)
    new_cam, roi = cv2.getOptimalNewCameraMatrix(
        camera_matrix, dist_coeffs, image_size, alpha=0, newImgSize=image_size
    )
    map1, map2 = cv2.initUndistortRectifyMap(
        camera_matrix, dist_coeffs, None, new_cam, image_size, cv2.CV_16SC2
    )
    x, y, w, h = roi

    print(f"  Output folder : {os.path.abspath(args.output_dir)}")
    print(f"  Controls      : [Space] capture  |  [q] quit\n")

    saved_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Failed to grab frame.")
            break

        # ── undistort (no resize — crop only) ─────────────────────────────────
        undistorted = cv2.remap(frame, map1, map2, cv2.INTER_LINEAR)
        if w > 0 and h > 0:
            undistorted = undistorted[y:y+h, x:x+w]
            # NOTE: we do NOT resize back to original dimensions.
            # The cropped image is slightly smaller but pixel-accurate.

        # ── display overlay (on a copy, not on what we save) ──────────────────
        display = undistorted.copy()
        cv2.putText(display,
                    f"UNDISTORTED  {undistorted.shape[1]}x{undistorted.shape[0]}  "
                    "[Space] capture  [q] quit",
                    (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(display, f"Saved: {saved_count}",
                    (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)

        cv2.namedWindow("Undistorted capture", cv2.WINDOW_NORMAL)
        cv2.imshow("Undistorted capture", display)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

        elif key == ord(" "):
            ts       = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
            filename = f"capture_{ts}.png"           # PNG = lossless
            out_path = os.path.join(args.output_dir, filename)
            cv2.imwrite(out_path, undistorted)        # save clean image, no overlay
            saved_count += 1
            print(f"  [{saved_count:>4}] Saved → {out_path}  "
                  f"({undistorted.shape[1]}×{undistorted.shape[0]})")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\n  Done. {saved_count} image(s) saved to: {os.path.abspath(args.output_dir)}\n")


if __name__ == "__main__":
    main()
