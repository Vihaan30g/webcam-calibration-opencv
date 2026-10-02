"""
scripts/validate_calibration.py
--------------------------------
Visually verify calibration results using the images from calibration_images/.

Shows:
  - Side-by-side: Original | Undistorted
  - Reprojection overlay: detected corners (green) vs projected corners (red)

No resizing applied to saved images.
For display only, images are scaled to fit your screen.

Controls: [Space] next image | [q] quit

Usage (from project root):
    python3 scripts/validate_calibration.py [--save]
"""

import sys
import os
import glob
import argparse
from pathlib import Path

import cv2
import cv2.aruco as aruco
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config as cfg
from utils.charuco_utils import get_charuco_detector

DISPLAY_MAX_W = 1400   # max width for on-screen display (not saved images)
DISPLAY_MAX_H = 800


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
    rms = data["rms_reprojection_error"]
    return cm, dc, image_size, rms


# ── helpers ───────────────────────────────────────────────────────────────────

def load_image_paths():
    extensions = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tiff")
    paths = []
    for ext in extensions:
        paths.extend(glob.glob(os.path.join(cfg.CALIBRATION_IMAGES, ext)))
    return sorted(paths)


def fit_for_display(img, max_w=DISPLAY_MAX_W, max_h=DISPLAY_MAX_H):
    """
    Scale image down to fit the display window — for DISPLAY ONLY.
    The original image and saved images are never resized.
    """
    h, w = img.shape[:2]
    scale = min(max_w / w, max_h / h, 1.0)
    if scale < 1.0:
        new_w = int(w * scale)
        new_h = int(h * scale)
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return img


def make_side_by_side(original, undistorted):
    """Concatenate two full-res images horizontally with a separator."""
    h, w = original.shape[:2]
    sep  = np.zeros((h, 8, 3), dtype=np.uint8)   # thin black bar
    canvas = np.hstack([original, sep, undistorted])

    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(canvas, "Original",    (10, 35), font, 1.0, (0, 255, 0), 2)
    cv2.putText(canvas, "Undistorted", (w + 18, 35), font, 1.0, (0, 255, 0), 2)
    return canvas


def draw_reprojection(img, charuco_corners, charuco_ids,
                      board, rvec, tvec, camera_matrix, dist_coeffs):
    vis = img.copy()
    aruco.drawDetectedCornersCharuco(vis, charuco_corners, charuco_ids, (0, 255, 0))
    obj_pts, img_pts = board.matchImagePoints(charuco_corners, charuco_ids)
    if obj_pts is not None and len(obj_pts) > 0:
        projected, _ = cv2.projectPoints(obj_pts, rvec, tvec, camera_matrix, dist_coeffs)
        for pt in projected.reshape(-1, 2):
            cv2.circle(vis, (int(pt[0]), int(pt[1])), 5, (0, 0, 255), -1)
    return vis


# ── main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Validate camera calibration visually")
    p.add_argument("--save", action="store_true",
                   help="Save comparison images to calibration_results/validation/")
    return p.parse_args()


def main():
    args = parse_args()

    camera_matrix, dist_coeffs, image_size, rms = load_calibration()

    print(f"\n{'='*60}")
    print(f"  Calibration     : {cfg.CALIBRATION_YAML}")
    print(f"  RMS error       : {rms:.5f} px")
    print(f"  Image size      : {image_size[0]}×{image_size[1]}")
    print(f"{'='*60}\n")
    print("  Controls: [Space] next image | [q] quit\n")

    # Build undistort maps once (full resolution, no resize)
    new_cam, roi = cv2.getOptimalNewCameraMatrix(
        camera_matrix, dist_coeffs, image_size, alpha=0, newImgSize=image_size
    )
    map1, map2 = cv2.initUndistortRectifyMap(
        camera_matrix, dist_coeffs, None, new_cam, image_size, cv2.CV_16SC2
    )

    detector, board, _ = get_charuco_detector()
    image_paths = load_image_paths()

    if not image_paths:
        print(f"[ERROR] No images found in '{cfg.CALIBRATION_IMAGES}'")
        sys.exit(1)

    save_dir = None
    if args.save:
        save_dir = os.path.join(cfg.CALIBRATION_RESULTS, "validation")
        os.makedirs(save_dir, exist_ok=True)

    for idx, path in enumerate(image_paths):
        img = cv2.imread(path)
        if img is None:
            continue

        label = f"[{idx+1}/{len(image_paths)}]  {os.path.basename(path)}"
        print(f"  {label}")

        # ── undistort (full resolution, no resize) ────────────────────────────
        undistorted = cv2.remap(img, map1, map2, cv2.INTER_LINEAR)
        x, y, w, h  = roi
        if w > 0 and h > 0:
            undistorted = undistorted[y:y+h, x:x+w]
            # Pad back to original size (black borders) so side-by-side aligns
            padded = np.zeros_like(img)
            padded[y:y+h, x:x+w] = undistorted
            undistorted = padded

        side_by_side = make_side_by_side(img, undistorted)

        # ── reprojection ──────────────────────────────────────────────────────
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        charuco_corners, charuco_ids, _, _ = detector.detectBoard(gray)
        reproj_vis = None
        if charuco_ids is not None and len(charuco_ids) >= 4:
            obj_pts, img_pts = board.matchImagePoints(charuco_corners, charuco_ids)
            if obj_pts is not None and len(obj_pts) >= 4:
                ok, rvec, tvec = cv2.solvePnP(
                    obj_pts, img_pts, camera_matrix, dist_coeffs
                )
                if ok:
                    reproj_vis = draw_reprojection(
                        img, charuco_corners, charuco_ids,
                        board, rvec, tvec, camera_matrix, dist_coeffs
                    )

        # ── save full-res comparison images (no resize) ───────────────────────
        if args.save and save_dir:
            base = os.path.splitext(os.path.basename(path))[0]
            cv2.imwrite(os.path.join(save_dir, f"{base}_comparison.jpg"), side_by_side)
            if reproj_vis is not None:
                cv2.imwrite(os.path.join(save_dir, f"{base}_reproj.jpg"), reproj_vis)

        # ── display (scaled down to fit screen) ───────────────────────────────
        cv2.namedWindow("Original | Undistorted", cv2.WINDOW_NORMAL)
        display_sbs = fit_for_display(side_by_side,
                                       max_w=DISPLAY_MAX_W * 2,
                                       max_h=DISPLAY_MAX_H)
        cv2.imshow("Original | Undistorted", display_sbs)

        if reproj_vis is not None:
            cv2.namedWindow("Reprojection  green=detected  red=projected", cv2.WINDOW_NORMAL)
            cv2.imshow("Reprojection  green=detected  red=projected",
                       fit_for_display(reproj_vis))

        key = cv2.waitKey(0) & 0xFF
        if key == ord("q"):
            break

    cv2.destroyAllWindows()
    if args.save and save_dir:
        print(f"\n  ✓ Full-resolution validation images → {save_dir}/\n")


if __name__ == "__main__":
    main()
