# Camera calibration: theory and methods

This page explains what calibration is, what the numbers mean, and why this repo uses a ChArUco board.

## Contents
1. [Why calibrate?](#why-calibrate)
2. [The camera model](#the-camera-model)
3. [Lens distortion](#lens-distortion)
4. [How calibration works](#how-calibration-works)
5. [Calibration targets compared](#calibration-targets-compared)
6. [Why ChArUco](#why-charuco)
7. [Reading the results](#reading-the-results)
8. [Using the result](#using-the-result)
9. [Limits and other camera types](#limits-and-other-camera-types)

---

## Why calibrate?

A camera turns 3D rays into 2D pixels. Two things stand between "what is in front of the lens" and "what the pixels say":

1. **Intrinsics:** the focal length and optical centre, which define how 3D points map to pixel positions.
2. **Distortion:** real lenses bend straight lines, especially near the image edges.

Without calibration, measurements from images (distances, angles, object pose, depth, SLAM, visual odometry,
AprilTag/ArUco pose) are biased. Calibration estimates these parameters once per camera, resolution and focus setting.

## The camera model

OpenCV uses the **pinhole model**. A 3D point `(X, Y, Z)` in the camera frame projects to pixel `(u, v)`:

```
u = fx * (X / Z) + cx
v = fy * (Y / Z) + cy
```

These are packed into the **camera matrix** (intrinsics):

```
    | fx  0  cx |
K = |  0 fy  cy |
    |  0  0   1 |
```

| Parameter | Meaning |
|---|---|
| `fx`, `fy` | Focal length in **pixels** (focal length in mm divided by pixel size). Usually nearly equal |
| `cx`, `cy` | Principal point, where the optical axis hits the image. Close to the image centre |

A world point `P_w` first moves into the camera frame by the **extrinsics** (rotation `R`, translation `t`):
`P_c = R * P_w + t`. Every captured board image has its own extrinsics; they are estimated during calibration
but are not needed afterwards. Only `K` and the distortion coefficients are kept.

## Lens distortion

Real lenses add two effects, applied to normalised coordinates `(x, y) = (X/Z, Y/Z)` with `r^2 = x^2 + y^2`
before multiplying by `K`:

**Radial distortion** (straight lines bow outward "barrel" or inward "pincushion"):

```
x_d = x * (1 + k1*r^2 + k2*r^4 + k3*r^6)
y_d = y * (1 + k1*r^2 + k2*r^4 + k3*r^6)
```

**Tangential distortion** (lens not perfectly parallel to the sensor):

```
x_d = x + 2*p1*x*y + p2*(r^2 + 2*x^2)
y_d = y + p1*(r^2 + 2*y^2) + 2*p2*x*y
```

OpenCV returns the five numbers `[k1, k2, p1, p2, k3]`. Typical webcams have `k1` around -0.3 to +0.1, and `p1`, `p2`
close to zero. `k1 < 0` means barrel distortion.

## How calibration works

OpenCV implements **Zhang's method** (2000):

1. Show the camera a **flat target with known geometry** from many viewpoints.
2. In each image, detect the target's feature points (corners). Their 3D positions on the board are known
   (`Z = 0` on the board plane, spacing = your printed square size).
3. For each view, the mapping from the board plane to the image is a homography. Each homography gives constraints
   on `K`. With 3 or more views at different orientations, `K` can be solved in closed form.
4. That gives an initial guess for `K`, the distortion, and each view's pose.
5. Everything is refined together by **non-linear least squares (Levenberg-Marquardt)** that minimises the
   **reprojection error**: the pixel distance between the *detected* corners and the corners obtained by projecting
   the known 3D points through the current model.

Why many views from different angles? If all views are frontal, focal length and distance are ambiguous. Tilted views
break that ambiguity. Views that cover the image edges are what constrain distortion.

## Calibration targets compared

| Target | Idea | Pros | Cons |
|---|---|---|---|
| **Checkerboard** | Black/white squares, detect inner corners | Simple, accurate sub-pixel corners, built into OpenCV (`findChessboardCorners`) | The **entire board must be visible** in every image, so you cannot calibrate the edges well. No ID, so no partial views. Fails with occlusion or glare |
| **Circle grid** (symmetric / asymmetric) | Grid of dots, detect centres | Accurate centres, robust to blur | Perspective bias on circle centres; large target needed; entire grid must be visible |
| **ArUco board** | Grid of ArUco markers with unique IDs | Works with partial visibility and occlusion; also gives pose | Corner accuracy of marker corners is lower than checkerboard corners |
| **ChArUco** (this repo) | Checkerboard with ArUco markers in the white squares | **Partial views allowed**, each corner has an ID, **sub-pixel accurate** checkerboard corners, robust to occlusion | Needs OpenCV contrib / aruco module, slightly more setup |
| **AprilGrid** | Grid of AprilTags (used by Kalibr) | Great for multi-camera and camera-IMU calibration | Needs separate tooling (Kalibr) |

**Rule of thumb:** use a plain checkerboard for a quick one-off if you can get the whole board everywhere in the frame;
use **ChArUco** when you want the best coverage and reliability, especially near the edges of wide-angle lenses.

## Why ChArUco

- A single ChArUco corner has a unique ID, so the board does not need to be entirely in view. You can push it into
  the frame corners, which is where distortion information lives.
- Detection is tolerant of partial occlusion (a hand holding the board) and uneven lighting.
- Corners are refined to sub-pixel accuracy as with a checkerboard.
- The ID-to-position mapping removes the orientation ambiguity of symmetric checkerboards.

## Reading the results

- **RMS reprojection error** (pixels): the typical distance between detected and re-projected corners.
  Under 0.5 px is excellent, under 1 px good. It is *not* proof of accuracy on its own: a model that overfits a poor set
  of views can show a low error and still be wrong elsewhere.
- **Per-image error:** outliers usually mean blur, a bent board, or a bad detection. Remove them and recalibrate.
- **Sanity checks:**
  - `fx` and `fy` should be close to each other.
  - `cx`, `cy` should be near the image centre (`width/2`, `height/2`), within about 5 to 10 percent.
  - `k3` very large (for example above 5 in magnitude) usually means overfitting. Set `FIX_K3 = True` in `config.py`.
  - The validation window should show straight lines made straight, and overlapping green and red points.
- **Focal length check:** `fx = f_mm * width_px / sensor_width_mm`. Compare with the datasheet if you have one.

## Using the result

- **Undistort images:** `cv2.remap` with maps from `initUndistortRectifyMap`, as in `scripts/undistort.py`.
  `alpha=0` crops to valid pixels (no black borders), `alpha=1` keeps every pixel (with black borders).
  The new camera matrix returned by `getOptimalNewCameraMatrix` is the correct `K` **for the undistorted image**.
- **Pose estimation** (ArUco, AprilTag, `solvePnP`): pass `K` and `dist` from the YAML for the raw image,
  or pass `new_K` and zero distortion for an already-undistorted image. Never apply distortion twice.
- **ROS 2 `sensor_msgs/CameraInfo`:** `k` = the 9 values of `K`, `d` = `[k1, k2, p1, p2, k3]`,
  `distortion_model` = `"plumb_bob"`, `r` = identity, `p` = `K` with an extra zero column
  (for the raw image, `[fx 0 cx 0; 0 fy cy 0; 0 0 1 0]`).
- **Resolution:** if you later use a different resolution of the same sensor *without cropping*, scale `fx, cx` by
  `new_width / old_width` and `fy, cy` by `new_height / old_height`. Cropped or binned modes need their own calibration.

## Limits and other camera types

- Calibrate again if you change **focus** (especially autofocus cameras: lock focus or disable autofocus),
  **zoom**, **resolution mode**, or if the lens is knocked.
- Calibration accuracy depends on **print flatness and the measured square size**. Intrinsics (`fx`, `fy`, `cx`, `cy`,
  distortion) do not depend on the true square size, but any metric distance (the `tvec` values) does.
- For wide-angle and fisheye lenses (about 120 degrees or more), the standard model is a poor fit.
  Use OpenCV's `cv2.fisheye` module (equidistant model with four coefficients) instead.
- Rolling-shutter cameras give extra error if the board moves while capturing. Hold the board still.
- This repo covers a **single camera (intrinsics)**. Stereo calibration (`cv2.stereoCalibrate`), hand-eye calibration
  and camera-IMU calibration (Kalibr) are the next steps if you need them.

## References

- Z. Zhang, *A Flexible New Technique for Camera Calibration*, IEEE TPAMI, 2000.
- OpenCV docs: *Camera Calibration and 3D Reconstruction* and *ArUco / ChArUco detection*.
- S. Garrido-Jurado et al., *Automatic generation and detection of highly reliable fiducial markers under occlusion*, 2014 (ArUco).
