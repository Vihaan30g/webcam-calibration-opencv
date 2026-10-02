# webcam-calibration-opencv

Calibrate **any webcam** with OpenCV and a **ChArUco board** in about 15 minutes.
Clone, edit one config file, print a board, capture images, calibrate, done.

- One config file (`config.py`) drives every script
- Generates a print-ready board at the exact physical size
- Live capture with real-time corner detection and quality gating
- Reprojection-error report, per-image outliers, and visual validation
- Ready-made tools to undistort live camera, images, folders and videos
- Works on Linux, Windows and macOS (Linux tested most)

> New to calibration? Read **[docs/theory.md](docs/theory.md)** for the explanation (camera model, distortion,
> how calibration works, checkerboard vs ChArUco vs other targets). Problems? See **[docs/troubleshooting.md](docs/troubleshooting.md)**.

---

## Quick start

```bash
git clone https://github.com/Vihaan30g/webcam-calibration-opencv.git
cd webcam-calibration-opencv

python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> Install **`opencv-contrib-python`** (already in `requirements.txt`), not plain `opencv-python`. The ChArUco code needs the contrib build.
> If you already have `opencv-python` installed, run `pip uninstall opencv-python` first so the two do not clash.

### 1. Edit `config.py`

| Setting | Meaning |
|---|---|
| `CAMERA_INDEX` | `0` = first camera. Try `1`, `2` for others |
| `CAMERA_WIDTH/HEIGHT` | Resolution to calibrate **and later use**. Must be supported by your camera |
| `CAMERA_CODEC` | `MJPG` gives high resolution at 30 fps on most USB webcams |
| `SQUARES_X/Y`, `SQUARE_LENGTH`, `MARKER_LENGTH` | Board geometry (metres). Defaults: 8x6 squares, 30 mm / 22 mm |

On Linux, list supported modes with `v4l2-ctl --list-formats-ext -d /dev/video0`.

### 2. Generate and print the board

```bash
python3 scripts/generate_charuco.py
```

Print `data/boards/charuco_board.pdf` at **100% / "Actual size"** (never "fit to page"). Mount it on something
**rigid and flat** (foam board, glass, clipboard). Measure one square with a ruler. If it is not 30 mm, update
`SQUARE_LENGTH` and `MARKER_LENGTH` in `config.py` to the measured values.

### 3. Capture calibration images

```bash
python3 scripts/capture_images.py
```

Press **`s`** to save (accepted only when 15 or more corners are detected), **`q`** to quit.
Aim for **25 to 40 images**:

- Fill every region of the frame, **including the corners and edges** (distortion is strongest there)
- Tilt the board up to about 45 degrees in different directions
- Vary the distance (near, medium, far)
- Hold still to avoid motion blur, and keep the lighting even
- Do not change zoom or focus during the session

### 4. Calibrate

```bash
python3 scripts/calibrate.py --visualize
```

Writes `data/calibration_results/calibration.yaml` and `calibration_summary.txt`.

| RMS reprojection error | Quality |
|---|---|
| < 0.5 px | Excellent |
| 0.5 to 1.0 px | Good |
| 1.0 to 2.0 px | Acceptable |
| > 2.0 px | Recapture |

If a few images have a clearly higher per-image error in the summary, delete them from `data/calibration_images/` and run again.

### 5. Validate

```bash
python3 scripts/validate_calibration.py --save
```

`Space` = next image, `q` = quit. Left: original. Right: undistorted (straight lines should now be straight).
Second window: **green** = detected corners, **red** = reprojected corners. They should overlap.

### 6. Use the calibration

```bash
# live camera, undistorted, press Space to save frames
python3 scripts/capture_undistorted.py --output_dir path/to/output/

# one image / a folder / a video file
python3 scripts/undistort.py --image photo.png      --output_dir out/
python3 scripts/undistort.py --images_dir raw/      --output_dir out/
python3 scripts/undistort.py --video recording.mp4  --output_dir out/
```

---

## Using the result in your own code

```python
import cv2, numpy as np, yaml

with open("data/calibration_results/calibration.yaml") as f:
    cal = yaml.safe_load(f)

K    = np.array(cal["camera_matrix"]["data"]).reshape(3, 3)
dist = np.array(cal["distortion_coefficients"]["data"]).reshape(1, -1)
size = (cal["image_width"], cal["image_height"])

new_K, roi = cv2.getOptimalNewCameraMatrix(K, dist, size, alpha=0)
map1, map2 = cv2.initUndistortRectifyMap(K, dist, None, new_K, size, cv2.CV_16SC2)

frame = cv2.imread("my_image.png")
und   = cv2.remap(frame, map1, map2, cv2.INTER_LINEAR)
x, y, w, h = roi
und = und[y:y+h, x:x+w]          # crop black borders
```

`K` is the 3x3 intrinsic matrix and `dist` is `[k1, k2, p1, p2, k3]` (OpenCV "plumb bob" model),
the same layout ROS 2 uses in `camera_info` (`k` and `d`). See [docs/theory.md](docs/theory.md#using-the-result).

> **The calibration is only valid for the resolution it was captured at.** Calibrating at 1280x960 and then
> running the camera at 640x480 gives wrong results. The scripts check this and stop with a clear error.

---

## Project structure

```
webcam-calibration-opencv/
├── config.py                 single source of truth for all settings
├── requirements.txt
├── scripts/
│   ├── generate_charuco.py       step 1  print-ready board (PNG + PDF)
│   ├── capture_images.py         step 2  live capture with corner detection
│   ├── calibrate.py              step 3  run calibration, write YAML
│   ├── validate_calibration.py   step 4  visual checks
│   ├── capture_undistorted.py    step 5a live undistorted capture
│   └── undistort.py              step 5b image / folder / video undistortion
├── utils/
│   ├── camera.py                 camera opening and resolution guards
│   └── charuco_utils.py          board and detector setup
├── docs/
│   ├── theory.md                 how and why calibration works
│   └── troubleshooting.md
└── data/                         your images and results (git-ignored)
```

## Reusing for another camera

Edit `config.py`, empty `data/calibration_images/`, and repeat steps 3 to 5.

## Requirements

Python 3.8+, `opencv-contrib-python >= 4.7`, `numpy`, `PyYAML`, `Pillow`.

## License

MIT, see [LICENSE](LICENSE). Author: Vihaan Gupta ([@Vihaan30g](https://github.com/Vihaan30g)).
