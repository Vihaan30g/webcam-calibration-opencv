# Troubleshooting

| Problem | Likely cause and fix |
|---|---|
| `AttributeError: module 'cv2.aruco' has no attribute 'CharucoBoard'` or `CharucoDetector` | You have an old OpenCV, or only `opencv-python`. Run `pip uninstall opencv-python opencv-contrib-python`, then `pip install -r requirements.txt`. Needs OpenCV 4.7 or newer |
| `Cannot open camera index N` | Wrong `CAMERA_INDEX`, camera busy (close other apps), or no permission. Linux: `ls /dev/video*`, and add your user to the `video` group |
| `Resolution mismatch` warning | The camera does not support your `CAMERA_WIDTH x HEIGHT`. Linux: `v4l2-ctl --device=/dev/video0 --list-formats-ext`. Pick a listed mode and update `config.py` |
| Low frame rate or laggy preview | Use `CAMERA_CODEC = "MJPG"`. Some cameras only offer high resolutions in MJPG, not YUYV |
| Corners are never detected | Board not flat or too small in frame; glare on the print (use matte paper, avoid direct lights); `ARUCO_DICTIONARY` / board settings in `config.py` differ from the board you printed |
| Image skipped: `size ... != ...` during calibration | Images were captured at another resolution. Delete them and recapture at the configured resolution |
| High RMS error (> 1 px) | Blurry or motion-smeared images, bent board, autofocus changed focus, too few or too similar views. Delete the worst images in `calibration_summary.txt` and recapture a more varied set |
| Huge `k3` or wavy image edges after undistortion | Overfitting. Set `FIX_K3 = True` in `config.py`, recapture with more views near the image corners, and recalibrate |
| Undistorted image has big black borders | Normal for strong distortion. The scripts crop to the valid area (`alpha=0`). Use `alpha=1` in your own code to keep all pixels |
| `cx`, `cy` far from the image centre | Too few or poorly distributed views. Capture more images with strong tilts |
| Autofocus camera gives different results each time | Disable autofocus (Linux: `v4l2-ctl -d /dev/video0 -c focus_auto=0 -c focus_absolute=<value>`) and calibrate at that fixed focus |
| Distances in metres look scaled wrong | Measure the printed square with a ruler and set `SQUARE_LENGTH` and `MARKER_LENGTH` to the measured values |
| Black preview window on macOS or Windows | Try another `CAMERA_INDEX`, or change `CAMERA_CODEC` to a value your camera supports (for example `"YUYV"` or leave MJPG) |
