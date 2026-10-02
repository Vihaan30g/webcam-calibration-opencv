"""
scripts/undistort.py
--------------------
Apply saved calibration to undistort images or video files.

Modes:
  Single image  →  python3 scripts/undistort.py --image photo.png
  Folder        →  python3 scripts/undistort.py --images_dir my_photos/
  Video file    →  python3 scripts/undistort.py --video input.mp4

Output goes to --output_dir (default: data/captured_undistorted/).
Saved images are at native resolution — no resizing, crop only.
For video, press [q] to quit, [s] to save the current frame.

Usage (from project root):
    python3 scripts/undistort.py --image path/to/image.png
"""

import sys
import os
import glob
import argparse
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config as cfg


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


def build_maps(camera_matrix, dist_coeffs, image_size):
    new_cam, roi = cv2.getOptimalNewCameraMatrix(
        camera_matrix, dist_coeffs, image_size, alpha=0, newImgSize=image_size
    )
    map1, map2 = cv2.initUndistortRectifyMap(
        camera_matrix, dist_coeffs, None, new_cam, image_size, cv2.CV_16SC2
    )
    return map1, map2, roi


# ── apply undistort ───────────────────────────────────────────────────────────

def undistort_frame(frame, map1, map2, roi):
    """
    Undistort a frame.  Crop to valid pixels only — no resize, no interpolation
    beyond the remap itself.
    """
    result = cv2.remap(frame, map1, map2, cv2.INTER_LINEAR)
    x, y, w, h = roi
    if w > 0 and h > 0:
        result = result[y:y+h, x:x+w]
    return result


def save_image(output_dir, filename, img):
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, filename)
    cv2.imwrite(out_path, img)
    print(f"  Saved → {out_path}  ({img.shape[1]}×{img.shape[0]})")


# ── modes ─────────────────────────────────────────────────────────────────────

def process_single(path, map1, map2, roi, output_dir):
    img = cv2.imread(path)
    if img is None:
        print(f"[ERROR] Cannot read: {path}")
        return
    result   = undistort_frame(img, map1, map2, roi)
    out_name = "undistorted_" + os.path.splitext(os.path.basename(path))[0] + ".png"
    save_image(output_dir, out_name, result)


def process_folder(images_dir, map1, map2, roi, output_dir):
    extensions = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tiff")
    paths = []
    for ext in extensions:
        paths.extend(glob.glob(os.path.join(images_dir, ext)))
    paths.sort()

    if not paths:
        print(f"[ERROR] No images found in '{images_dir}'")
        return

    print(f"\n  Processing {len(paths)} image(s) …\n")
    for path in paths:
        img = cv2.imread(path)
        if img is None:
            print(f"  [SKIP] {path}")
            continue
        result   = undistort_frame(img, map1, map2, roi)
        out_name = "undistorted_" + os.path.splitext(os.path.basename(path))[0] + ".png"
        save_image(output_dir, out_name, result)


def process_video(video_path, map1, map2, roi, output_dir):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video: {video_path}")
        sys.exit(1)

    print(f"\n  Video opened. Controls: [s] save frame  [q] quit\n")
    saved = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("  End of video.")
            break

        result = undistort_frame(frame, map1, map2, roi)

        # side-by-side display only (not saved)
        fh, fw = frame.shape[:2]
        rh, rw = result.shape[:2]
        # pad result height to match original for display
        if rh < fh:
            pad    = np.zeros((fh - rh, rw, 3), dtype=np.uint8)
            result_disp = np.vstack([result, pad])
        else:
            result_disp = result[:fh]
        # pad result width
        if rw < fw:
            pad    = np.zeros((fh, fw - rw, 3), dtype=np.uint8)
            result_disp = np.hstack([result_disp, pad])

        preview = np.hstack([frame, result_disp])
        cv2.putText(preview, "Original",    (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        cv2.putText(preview, "Undistorted", (fw + 10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        cv2.namedWindow("Video undistort", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Video undistort", 1400, 600)
        cv2.imshow("Video undistort", preview)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("s"):
            saved += 1
            save_image(output_dir, f"frame_{saved:04d}.png", result)

    cap.release()
    cv2.destroyAllWindows()


# ── main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Undistort images or video")
    p.add_argument("--image",      default=None, help="Single image path")
    p.add_argument("--images_dir", default=None, help="Folder of images")
    p.add_argument("--video",      default=None, help="Video file path")
    p.add_argument("--output_dir", default=cfg.CAPTURED_DIR,
                   help=f"Output folder (default: {cfg.CAPTURED_DIR})")
    return p.parse_args()


def main():
    args = parse_args()

    camera_matrix, dist_coeffs, image_size = load_calibration()
    map1, map2, roi = build_maps(camera_matrix, dist_coeffs, image_size)

    print(f"\n  Calibration loaded : {cfg.CALIBRATION_YAML}")
    print(f"  Calibrated size    : {image_size[0]}×{image_size[1]}")
    print(f"  Output folder      : {os.path.abspath(args.output_dir)}\n")

    if args.image:
        process_single(args.image, map1, map2, roi, args.output_dir)
    elif args.images_dir:
        process_folder(args.images_dir, map1, map2, roi, args.output_dir)
    elif args.video:
        process_video(args.video, map1, map2, roi, args.output_dir)
    else:
        print("  Specify an input:")
        print("    --image      <path>")
        print("    --images_dir <folder>")
        print("    --video      <path>")


if __name__ == "__main__":
    main()
