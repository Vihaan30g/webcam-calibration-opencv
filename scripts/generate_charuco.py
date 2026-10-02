"""
scripts/generate_charuco.py
---------------------------
Generate a ChArUco board whose squares print at EXACTLY config.SQUARE_LENGTH.

Output (in data/boards/):
  charuco_board.png  - 300 DPI image with DPI metadata embedded
  charuco_board.pdf  - same board as a PDF (easiest way to print at 100% scale)

The board is placed on an A4 landscape or portrait sheet (whichever fits).
All board parameters come from config.py.

Usage (from project root):
    python3 scripts/generate_charuco.py
"""

import sys
import os
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config as cfg
from utils.charuco_utils import get_charuco_board

DPI = 300
MM_PER_INCH = 25.4
A4_MM = (210.0, 297.0)          # width, height (portrait)
MIN_MARGIN_MM = 10.0            # keep the white border; printers need margins


def mm_to_px(mm: float) -> int:
    return int(round(mm / MM_PER_INCH * DPI))


def main():
    os.makedirs(cfg.BOARDS_DIR, exist_ok=True)
    board, _ = get_charuco_board()

    board_w_mm = cfg.SQUARES_X * cfg.SQUARE_LENGTH * 1000
    board_h_mm = cfg.SQUARES_Y * cfg.SQUARE_LENGTH * 1000

    # choose A4 orientation that fits the board with margins
    sheet = None
    for name, (w, h) in (("portrait", A4_MM), ("landscape", A4_MM[::-1])):
        if board_w_mm + 2 * MIN_MARGIN_MM <= w and board_h_mm + 2 * MIN_MARGIN_MM <= h:
            sheet = (name, w, h)
            break
    if sheet is None:
        print(f"\n[ERROR] A {board_w_mm:.0f} x {board_h_mm:.0f} mm board does not fit on A4.\n"
              f"  Reduce SQUARES_X/SQUARES_Y or SQUARE_LENGTH in config.py.\n")
        sys.exit(1)
    name, sheet_w_mm, sheet_h_mm = sheet

    # board image: every square is exactly SQUARE_LENGTH wide at DPI
    sq_px = mm_to_px(cfg.SQUARE_LENGTH * 1000)
    bw, bh = sq_px * cfg.SQUARES_X, sq_px * cfg.SQUARES_Y
    board_img = board.generateImage((bw, bh), marginSize=0, borderBits=1)

    # centre it on a white A4 sheet
    W, H = mm_to_px(sheet_w_mm), mm_to_px(sheet_h_mm)
    canvas = np.full((H, W), 255, dtype=np.uint8)
    x0, y0 = (W - bw) // 2, (H - bh) // 2
    canvas[y0:y0 + bh, x0:x0 + bw] = board_img

    png_path = os.path.join(cfg.BOARDS_DIR, "charuco_board.png")
    pdf_path = os.path.join(cfg.BOARDS_DIR, "charuco_board.pdf")
    cv2.imwrite(png_path, canvas)

    try:  # Pillow embeds DPI so the PNG/PDF print at true size
        from PIL import Image
        img = Image.fromarray(canvas)
        img.save(png_path, dpi=(DPI, DPI))
        img.convert("RGB").save(pdf_path, resolution=DPI)
        pdf_note = f"  PDF -> {pdf_path}   (print this one)"
    except ImportError:
        pdf_note = "  (Install Pillow for a ready-to-print PDF:  pip install Pillow)"

    print(f"\n  Board parameters (from config.py):")
    print(f"    Dictionary  : {cfg.ARUCO_DICTIONARY}")
    print(f"    Squares     : {cfg.SQUARES_X} x {cfg.SQUARES_Y}")
    print(f"    Square size : {cfg.SQUARE_LENGTH*1000:.1f} mm")
    print(f"    Marker size : {cfg.MARKER_LENGTH*1000:.1f} mm")
    print(f"    Board area  : {board_w_mm:.0f} x {board_h_mm:.0f} mm on A4 {name}")
    print(f"\n  PNG -> {png_path}")
    print(pdf_note)
    print("  Print at 100% / 'Actual size' (NOT 'fit to page'), then measure one square with a ruler.\n")


if __name__ == "__main__":
    main()
