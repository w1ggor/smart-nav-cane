# CLAUDE.md — Smart Cane Environmental Awareness System

> **This file is the project's living memory and source of truth.**
> Update it whenever code changes, decisions are made, or lessons are learned.

---

## Project Overview

An IoT + Edge AI environmental awareness assistant running entirely on a Raspberry Pi 4. The device is worn or carried like a smart cane and provides two core functions:

1. **Obstacle detection** — the ToF camera continuously measures forward depth; anything within a configurable threshold triggers an audio alert.
2. **Location recognition** — the webcam matches the current scene against a database of trained locations using ORB feature descriptors; when the user enters a recognized space they are told where they are.

The system runs fully offline. No cloud services, no internet required.

**University:** IoT Term Project  
**Platform:** Raspberry Pi 4 Model B  
**Language:** Python 3.9+  
**Repository:** https://github.com/w1ggor/smart-nav-cane

---

## Hardware

| Component | Model | Interface | Role |
|-----------|-------|-----------|------|
| Compute | Raspberry Pi 4 Model B (4GB+) | — | Central processing unit |
| Depth Camera | Arducam ToF Camera B0410 | CSI | Real-time obstacle depth measurement |
| RGB Camera | USB Webcam (C270 HD WEBCAM) | USB (UVC) | Location/room recognition |
| Audio Output | Bluetooth Headphones | Bluetooth (A2DP) | Spoken alerts and announcements |

### Optional Future Hardware (not dependencies)
- IMU (MPU-6050): Step counting for future navigation features
- Ultrasonic sensors (HC-SR04): Redundant close-range detection
- GPS module: Outdoor extension

---

## Architecture

### Scope Decision — Awareness over Navigation
Full indoor navigation (SLAM, route planning, turn-by-turn guidance) is documented as future work. The first version focuses on **environmental awareness**: telling the user what is around them rather than guiding them to a destination. This is more achievable, more robust, and still genuinely useful for visually impaired users.

### Core Design: Awareness Loop
Two parallel concerns run in a single loop at ~2 Hz:

```
ToF frame  → ObstacleDetector → audio alert if obstacle < threshold
Webcam frame → PlaceRecognizer → audio announce if location changes
```

The loop is intentionally simple — no state machine, no route planning, no graph traversal.

### Location Recognition — ORB Feature Matching
- Webcam frames are matched against stored location descriptors using ORB (OpenCV built-in)
- Each trained location stores an ORB descriptor matrix (.npy) and a ToF depth profile
- FLANN/BFMatcher with Lowe's ratio test selects good matches
- A confidence score (good_matches / n_features) gates announcements
- No deep learning, no GPU, no cloud — runs on RPi CPU at ~5 FPS for recognition

### Obstacle Detection — Depth Thresholding
- The ToF camera produces a 240×180 depth frame at ~10 FPS
- The central zone (configurable fraction of frame) is checked for minimum depth
- If min depth < alert_threshold_m → audio alert with distance
- A cooldown prevents repeated alerts for the same obstacle

### Audio Strategy
- Linux/RPi: `espeak-ng` called via subprocess (most reliable, no driver bugs)
- Fallback: `pyttsx3` (macOS/Windows only)
- Location announcements: non-blocking (background thread)
- Obstacle alerts: blocking (~0.3s) to guarantee immediate delivery

### Why Not SLAM / ROS / Navigation
Full indoor navigation requires:
- Accurate step counting or odometry (no IMU available)
- Map building and localization simultaneously (computationally expensive)
- Safe real-time path planning with obstacle avoidance

These are left as future work. The awareness system provides real value without them.

---

## Module Structure

```
src/nav_assistant/
├── sensors/
│   ├── base.py               # Abstract ISensor interface
│   ├── webcam.py             # USB webcam (OpenCV, V4L2 auto-detect)
│   ├── tof.py                # Arducam ToF B0410 (SDK, V4L2 auto-detect)
│   └── utils.py              # V4L2 device name detection shared utility
├── mapping/
│   ├── waypoint.py           # Location dataclass + serialization
│   ├── environment.py        # SQLite-backed location store
│   └── recorder.py           # Training: capture + store locations
├── localization/
│   └── place_recognizer.py   # ORB matching → current location
├── obstacle/
│   └── detector.py           # ToF depth threshold → ObstacleAlert
├── audio/
│   └── guidance.py           # TTS (espeak-ng) + obstacle beep
└── awareness.py              # AwarenessSystem: main loop coordinator

scripts/
├── train.py                  # CLI: capture and store named locations
├── awareness.py              # Entry point: run the awareness system
└── test_sensors.py           # Hardware validation

Future work (stubs present, not active):
└── navigation/
    ├── route_graph.py        # Dijkstra route planning (future)
    └── navigator.py          # Navigation state machine (future)
```

### Data Flow
```
WebcamSensor → frame → PlaceRecognizer → location label → AudioGuidance
ToFSensor    → depth → ObstacleDetector → alert         → AudioGuidance
```

---

## Location Data Model

```python
@dataclass
class Waypoint:          # represents a named location / room
    id: str              # UUID
    label: str           # Human name: "hallway", "kitchen", "office"
    descriptor_path: str # Path to .npy ORB descriptor matrix
    depth_profile: list[float]  # 9-cell depth grid (3×3) from ToF
    created_at: str
    notes: str
```

Edges between locations are stored in SQLite but are **not used** in the current version. They are preserved for future navigation features.

---

## Development Roadmap

### Phase 1 — Sensor Integration ✅ COMPLETE
- [x] Abstract sensor interface
- [x] WebcamSensor with V4L2 auto-detection by device name
- [x] ToFSensor with Arducam SDK + V4L2 auto-detection
- [x] Sensor validation script

### Phase 2 — Location Training ✅ COMPLETE
- [x] Waypoint/location data model
- [x] SQLite + .npy environment storage
- [x] ORB descriptor extraction
- [x] Training CLI (train.py)
- [x] First environment captured on hardware (lab_test: door, office)

### Phase 3 — Awareness Loop ← CURRENT
- [x] ObstacleDetector (ToF depth threshold)
- [x] PlaceRecognizer (ORB matching)
- [x] AudioGuidance (espeak-ng)
- [ ] AwarenessSystem coordinator (main loop)
- [ ] awareness.py entry point script
- [ ] End-to-end test on hardware

### Phase 4 — Tuning & Polish
- [ ] Confidence threshold tuning (min matches for location announcement)
- [ ] Obstacle alert threshold tuning (distance, cooldown)
- [ ] Location announcement cooldown (suppress repeat announcements)
- [ ] CPU profiling on RPi, frame rate optimization
- [ ] Graceful startup / shutdown (announcements on start/stop)

### Future Work (not in scope for v1)
- Route planning and turn-by-turn navigation
- Waypoint edge recording and graph traversal
- Dead-reckoning with IMU between locations
- SLAM integration for unknown environments
- MobileNetV3 or similar for more robust location recognition
- Multi-environment support with automatic environment selection

---

## Current Status

**Phase:** 3 — Awareness Loop  
**Last Updated:** 2026-06-07  
**Working On:** AwarenessSystem coordinator + awareness.py entry point

---

## Completed Features

- Project structure initialized
- WebcamSensor with V4L2 device name auto-detection (no hardcoded indices)
- ToFSensor with Arducam SDK + V4L2 device name auto-detection
- Waypoint/location data model (SQLite + .npy)
- EnvironmentMap persistent storage
- Training CLI — capture named locations from webcam + ToF
- PlaceRecognizer — ORB feature matching against stored locations
- ObstacleDetector — ToF depth threshold with cooldown
- AudioGuidance — espeak-ng subprocess on Linux, pyttsx3 fallback
- First real environment captured on hardware (lab_test)

---

## Pending Tasks

- Implement AwarenessSystem coordinator class
- Implement awareness.py entry point
- End-to-end hardware test of full awareness loop
- Tune confidence and obstacle thresholds for real environment

---

## Implementation Notes

### Arducam ToF B0410 SDK
- Install from: https://github.com/ArduCAM/Arducam_tof_camera
- Import as: `import ArducamDepthCamera as ac`
- Open: `cam.open(ac.Connection.CSI, index)` — index from V4L2 unicam detection
- Start: `cam.start(ac.FrameType.DEPTH)`
- Frame data: `frame.depth_data` (property, not method), `frame.confidence_data`
- Shutdown: `cam.stop()` then `cam.close()`

### ORB Matching Parameters
- `nfeatures=500` balances richness vs. speed
- BFMatcher with `NORM_HAMMING`, Lowe's ratio test at 0.75
- Minimum 15 good matches for a confident location recognition
- Confidence = min(1.0, good_matches / 250) — tune threshold in config

### RPi Performance Targets
- ToF read + obstacle check: < 50ms
- ORB extraction + matching: < 300ms per frame
- Awareness loop cycle: ~500ms (2 Hz)
- Location recognition runs every 3rd cycle to reduce CPU load

### Bluetooth Audio Setup (RPi)
```bash
bluetoothctl
  power on; scan on; pair <MAC>; connect <MAC>; trust <MAC>
pactl set-default-sink bluez_sink.<MAC>.a2dp_sink
espeak-ng "Hello world"   # test
```

---

## Lessons Learned

### USB Webcam is NOT /dev/video0 on RPi with CSI camera attached — and the index is not stable
When the Arducam ToF is on the CSI port, `/dev/video0` is the CSI unicam device. The USB webcam index is not fixed across reboots. Fix: `WebcamSensor` now auto-detects the correct `/dev/videoX` index at `open()` time by parsing `v4l2-ctl --list-devices` and matching by device name (e.g. "C270 HD WEBCAM"). Falls back to `device_index` from config if detection fails. Set `webcam.device_name` in `config/default.yaml`.

### Arducam SDK: start() takes FrameType, not DeviceType — and FrameType.DEPTH is the correct value
`camera.start()` requires a `FrameType` argument, not `DeviceType`. In the installed SDK, `DeviceType` is actually a frame-resolution enum (`HQVGA`, `VGA`) with no relation to depth mode. The correct call is `camera.start(FrameType.DEPTH)`. The module now imports `ArducamDepthCamera as ac` (matching official examples) and calls `cam.start(ac.FrameType.DEPTH)`.

### Arducam SDK frame data is accessed via properties, not methods
`requestFrame()` returns an `ac.DepthData` object. Data is accessed via **properties**: `frame.depth_data` and `frame.confidence_data` — NOT via `getDepthData()` / `getAmplitudeData()` methods (which do not exist). Always check `isinstance(frame, ac.DepthData)` before accessing. The second channel is `confidence_data` (signal strength 0–255), not "amplitude".

### cv2.CAP_V4L2 hint makes CSI unicam appear to open — use default backend
Explicitly passing `cv2.CAP_V4L2` to `VideoCapture` causes the CSI unicam device (`/dev/video0`) to report `isOpened() == True` while returning no frames. Using `cv2.VideoCapture(index)` with no backend hint lets OpenCV auto-select V4L2, which only opens devices that actually stream. Removed the explicit backend hint from `WebcamSensor.open()`.

### UVC webcam returns empty frames immediately after open
USB webcams on Linux (V4L2) often return black/empty frames for the first few reads while the sensor initializes. Fix: call `cap.grab()` 5 times after opening to flush the initial empty frames before the first real `read()`.

### pyttsx3 broken on Python 3.13 + espeak-ng (RPi OS Bookworm)
`pyttsx3`'s espeak driver hardcodes the voice name `gmw/en` which doesn't exist in `espeak-ng`. This raises `ValueError: SetVoiceByName failed` on init. **Fix:** call `espeak-ng` directly via `subprocess` on Linux — no pyttsx3 needed. pyttsx3 is kept as a fallback for macOS/Windows only. The `AudioGuidance` class auto-detects the backend at import time using `shutil.which("espeak-ng")`.

### ToF cam.open() index maps to V4L2 device — must match unicam, not a hardcoded 0
The Arducam SDK maps `cam.open(Connection.CSI, index)` to the V4L2 device at `/dev/video{index}`. If the unicam isn't at index 0 (e.g. USB webcam boots first), the SDK fails with "I2C bus name doesn't match any bus present!". Fix: same V4L2 auto-detection as the webcam, searching for "unicam" in `v4l2-ctl --list-devices`.

---

## Deployment

See [docs/deployment.md](docs/deployment.md) for full Raspberry Pi setup guide.
