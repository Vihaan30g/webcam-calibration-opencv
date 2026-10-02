"""
scripts/capture_images.py
-------------------------
Live camera preview with real-time ChArUco corner detection.
Press [s] to save a frame (only accepted if ≥ 15 corners detected).
Press [q] to quit.

Resolution and camera index come from config.py.
Images are saved to config.CALIBRATION_IMAGES as PNG (lossless).

Usage (from project root):
    python3 scripts/capture_images.py
"""

import sys
import os
from pathlib import Path
import cv2
import cv2.aruco as aruco

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config as cfg
from utils.charuco_utils import get_charuco_detector
from utils.camera import open_camera

MIN_CORNERS = 15   # minimum ChArUco corners to accept a frame for saving


def main():
    os.makedirs(cfg.CALIBRATION_IMAGES, exist_ok=True)

    # ── open camera ───────────────────────────────────────────────────────────
    cap = open_camera()

    # ── board / detector ──────────────────────────────────────────────────────
    detector, board, dictionary = get_charuco_detector()
    print(f"  Saving images to : {cfg.CALIBRATION_IMAGES}")
    print(f"  Min corners      : {MIN_CORNERS}")
    print(f"  Controls         : [s] save frame  |  [q] quit\n")

    image_counter = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Failed to grab frame.")
            break

        display = frame.copy()

        # ── detect ────────────────────────────────────────────────────────────
        charuco_corners, charuco_ids, marker_corners, marker_ids = \
            detector.detectBoard(frame)

        num_markers = 0 if marker_ids is None else len(marker_ids)
        num_charuco = 0 if charuco_ids is None else len(charuco_ids)

        # draw detected marker outlines
        if marker_ids is not None:
            aruco.drawDetectedMarkers(display, marker_corners, marker_ids)

        # draw detected ChArUco corners
        if charuco_ids is not None:
            aruco.drawDetectedCornersCharuco(display, charuco_corners, charuco_ids)

        # ── overlay text ──────────────────────────────────────────────────────
        color_ok   = (0, 255,   0)
        color_warn = (0, 165, 255)

        corner_color = color_ok if num_charuco >= MIN_CORNERS else color_warn

        cv2.putText(display, f"Markers : {num_markers}",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color_ok, 2)
        cv2.putText(display, f"Corners : {num_charuco}  (need {MIN_CORNERS}+)",
                    (20, 85), cv2.FONT_HERSHEY_SIMPLEX, 1.0, corner_color, 2)
        cv2.putText(display, f"Saved   : {image_counter}",
                    (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 255), 2)
        cv2.putText(display, "[s] save   [q] quit",
                    (20, display.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        cv2.namedWindow("Capture calibration images", cv2.WINDOW_NORMAL)
        cv2.imshow("Capture calibration images", display)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("s"):
            if num_charuco >= MIN_CORNERS:
                filename = os.path.join(
                    cfg.CALIBRATION_IMAGES,
                    f"image_{image_counter:03d}.png"   # PNG = lossless
                )
                cv2.imwrite(filename, frame)            # save raw frame, no overlay
                image_counter += 1
                print(f"  [{image_counter:>3}] Saved → {filename}  (corners: {num_charuco})")
            else:
                print(f"  [SKIP]  Only {num_charuco} corners — move the board.")

        elif key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"\n  Done. {image_counter} image(s) saved to: {cfg.CALIBRATION_IMAGES}\n")


if __name__ == "__main__":
    main()
