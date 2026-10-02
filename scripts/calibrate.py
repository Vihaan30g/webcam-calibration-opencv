"""
scripts/calibrate.py
--------------------
Reads captured ChArUco images from config.CALIBRATION_IMAGES,
runs camera calibration, and saves results to config.CALIBRATION_YAML.

No resizing is performed — images must all be at the resolution in config.py.

Usage (from project root):
    python3 scripts/calibrate.py [--visualize]
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


# ── image loading ─────────────────────────────────────────────────────────────

def load_image_paths(images_dir: str):
    extensions = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tiff")
    paths = []
    for ext in extensions:
        paths.extend(glob.glob(os.path.join(images_dir, ext)))
    return sorted(paths)


# ── corner detection ──────────────────────────────────────────────────────────

def detect_corners(image_paths, detector, board, visualize=False, vis_dir=None):
    """
    Detect ChArUco corners in every image.
    Images that don't match config resolution or have too few corners are skipped.
    No resizing is ever applied.
    """
    all_corners  = []
    all_ids      = []
    image_size   = None
    valid_images = []
    expected_w   = cfg.CAMERA_WIDTH
    expected_h   = cfg.CAMERA_HEIGHT

    total = len(image_paths)
    print(f"\n{'─'*60}")
    print(f"  Detecting corners in {total} image(s) …")
    print(f"  Expected size : {expected_w}×{expected_h}")
    print(f"{'─'*60}")

    for idx, path in enumerate(image_paths):
        img = cv2.imread(path)
        if img is None:
            print(f"  [SKIP]  Cannot read : {path}")
            continue

        h, w = img.shape[:2]
        label = os.path.basename(path)

        # ── resolution guard ──────────────────────────────────────────────────
        if w != expected_w or h != expected_h:
            print(
                f"  [{idx+1:>3}/{total}]  {label:40s}  "
                f"[SKIP – size {w}×{h} ≠ {expected_w}×{expected_h}]"
            )
            continue

        if image_size is None:
            image_size = (w, h)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        charuco_corners, charuco_ids, marker_corners, marker_ids = \
            detector.detectBoard(gray)

        n = 0 if charuco_ids is None else len(charuco_ids)

        if charuco_ids is None or n < 6:
            print(f"  [{idx+1:>3}/{total}]  {label:40s}  corners: {n:>3}  [SKIP – too few]")
            continue

        print(f"  [{idx+1:>3}/{total}]  {label:40s}  corners: {n:>3}  ✓")
        all_corners.append(charuco_corners)
        all_ids.append(charuco_ids)
        valid_images.append(path)

        if visualize and vis_dir:
            vis = img.copy()
            aruco.drawDetectedCornersCharuco(vis, charuco_corners, charuco_ids)
            cv2.imwrite(os.path.join(vis_dir, f"detected_{label}"), vis)

    return all_corners, all_ids, image_size, valid_images


# ── calibration ───────────────────────────────────────────────────────────────

def run_calibration(all_corners, all_ids, image_size, board):
    print(f"\n{'─'*60}")
    print(f"  Running calibration on {len(all_corners)} image(s) …")
    print(f"{'─'*60}")

    all_obj_pts = []
    all_img_pts = []

    for corners, ids in zip(all_corners, all_ids):
        obj_pts, img_pts = board.matchImagePoints(corners, ids)
        if obj_pts is not None and len(obj_pts) > 3:
            all_obj_pts.append(obj_pts)
            all_img_pts.append(img_pts)

    if len(all_obj_pts) < 3:
        raise RuntimeError(
            f"Only {len(all_obj_pts)} usable images after corner matching. "
            "Need at least 3."
        )

    flags = cv2.CALIB_FIX_K3 if getattr(cfg, "FIX_K3", False) else 0
    rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        all_obj_pts, all_img_pts, image_size, None, None, flags=flags
    )
    return rms, camera_matrix, dist_coeffs, rvecs, tvecs


# ── per-image reprojection error ──────────────────────────────────────────────

def per_image_error(all_corners, all_ids, board, rvecs, tvecs,
                    camera_matrix, dist_coeffs):
    errors = []
    for corners, ids, rvec, tvec in zip(all_corners, all_ids, rvecs, tvecs):
        obj_pts, img_pts = board.matchImagePoints(corners, ids)
        if obj_pts is None or len(obj_pts) == 0:
            errors.append(float("nan"))
            continue
        projected, _ = cv2.projectPoints(obj_pts, rvec, tvec,
                                          camera_matrix, dist_coeffs)
        err = cv2.norm(img_pts, projected.reshape(-1, 1, 2), cv2.NORM_L2)
        errors.append(err / np.sqrt(len(projected)))
    return errors


# ── save results ──────────────────────────────────────────────────────────────

def save_results(rms, camera_matrix, dist_coeffs,
                 image_size, valid_images, errors):
    os.makedirs(cfg.CALIBRATION_RESULTS, exist_ok=True)
    yaml_path    = cfg.CALIBRATION_YAML
    summary_path = os.path.join(cfg.CALIBRATION_RESULTS, "calibration_summary.txt")

    data = {
        "image_width":  image_size[0],
        "image_height": image_size[1],
        "rms_reprojection_error": float(rms),
        "camera_matrix": {
            "rows": 3, "cols": 3,
            "data": camera_matrix.flatten().tolist(),
        },
        "distortion_coefficients": {
            "rows": 1,
            "cols": int(dist_coeffs.shape[1]),
            "data": dist_coeffs.flatten().tolist(),
        },
        "valid_images_used": [os.path.basename(p) for p in valid_images],
        "per_image_rms": {
            os.path.basename(valid_images[i]): round(float(e), 5)
            for i, e in enumerate(errors)
            if not (isinstance(e, float) and e != e)
        },
    }

    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    fx, fy = camera_matrix[0, 0], camera_matrix[1, 1]
    cx, cy = camera_matrix[0, 2], camera_matrix[1, 2]
    k1, k2, p1, p2 = dist_coeffs.flatten()[:4]
    k3 = dist_coeffs.flatten()[4] if dist_coeffs.size > 4 else 0.0

    lines = [
        "=" * 60,
        "  CAMERA CALIBRATION RESULTS",
        "=" * 60,
        f"  Images used       : {len(valid_images)}",
        f"  Image size        : {image_size[0]} × {image_size[1]} px",
        f"  RMS reprojection  : {rms:.5f} px",
        "",
        "  Camera Matrix (intrinsics):",
        f"    fx = {fx:.4f}   fy = {fy:.4f}",
        f"    cx = {cx:.4f}   cy = {cy:.4f}",
        "",
        "  Distortion Coefficients:",
        f"    k1={k1:.6f}  k2={k2:.6f}",
        f"    p1={p1:.6f}  p2={p2:.6f}  k3={k3:.6f}",
        "",
        "  Per-image RMS (px):",
    ]
    for i, (path, e) in enumerate(zip(valid_images, errors)):
        lines.append(f"    [{i+1:>3}] {os.path.basename(path):42s} {e:.5f}")
    lines += ["", f"  Saved to : {yaml_path}", "=" * 60]

    summary = "\n".join(lines)
    print("\n" + summary)
    with open(summary_path, "w") as f:
        f.write(summary + "\n")

    return yaml_path


# ── main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="ChArUco camera calibration")
    p.add_argument("--visualize", action="store_true",
                   help="Save corner-detection overlay images")
    return p.parse_args()


def main():
    args  = parse_args()
    paths = load_image_paths(cfg.CALIBRATION_IMAGES)

    if not paths:
        print(f"\n[ERROR] No images found in '{cfg.CALIBRATION_IMAGES}'")
        sys.exit(1)

    vis_dir = None
    if args.visualize:
        vis_dir = os.path.join(cfg.CALIBRATION_RESULTS, "detections")
        os.makedirs(vis_dir, exist_ok=True)

    detector, board, _ = get_charuco_detector()

    all_corners, all_ids, image_size, valid_images = detect_corners(
        paths, detector, board, visualize=args.visualize, vis_dir=vis_dir
    )

    if image_size is None:
        print("\n[ERROR] No valid images found at the expected resolution "
              f"({cfg.CAMERA_WIDTH}×{cfg.CAMERA_HEIGHT}).")
        sys.exit(1)

    if len(valid_images) < 3:
        print(f"\n[ERROR] Need ≥ 3 valid images, got {len(valid_images)}.")
        sys.exit(1)

    rms, camera_matrix, dist_coeffs, rvecs, tvecs = run_calibration(
        all_corners, all_ids, image_size, board
    )

    errors = per_image_error(
        all_corners, all_ids, board, rvecs, tvecs, camera_matrix, dist_coeffs
    )

    yaml_path = save_results(
        rms, camera_matrix, dist_coeffs, image_size, valid_images, errors
    )

    print(f"\n  ✓ Calibration complete.  Results → {yaml_path}\n")


if __name__ == "__main__":
    main()
