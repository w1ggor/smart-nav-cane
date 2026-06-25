# CLAUDE.md — Smart Cane Environmental Awareness System

> **This file is the project's living memory and source of truth.**
> Update it whenever code changes, decisions are made, or lessons are learned.

---

## Project Overview

An IoT + Edge AI environmental awareness assistant running entirely on a Raspberry Pi 4. The device is worn or carried like a smart cane and provides two modes:

1. **Awareness mode** (`scripts/awareness.py`) — obstacle detection via ToF depth threshold + passive location announcements via ORB recognition. No destination, no guidance.
2. **Guided navigation mode** (`scripts/navigate_voice.py`) — the user speaks a destination ("kitchen"), and the cane gives turn-by-turn audio guidance using reactive wall-following on the ToF depth frame, announces trained landmarks (e.g. doors) along the way, and confirms arrival.

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
| Audio Input | Bluetooth headset mic or USB mic | Bluetooth (HSP/HFP) or USB | Voice destination input for guided navigation |

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

### Guided Navigation — Reactive Wall-Following (no IMU/odometry)
There is no IMU and no wheel encoder on this hardware, so the guided navigation mode does **not** plan a path to arbitrary coordinates the way SLAM-based navigation would. Instead it reacts to the live ToF depth frame every cycle:

```
ToF frame → split into left / center / right zones (zone_depths())
  center clear  → "Go straight"
  center blocked, left clearer  → "Turn left"
  center blocked, right clearer → "Turn right"
  both sides blocked            → "Path blocked. Please stop."
```

This is combined with two ORB recognizers:
- **Location recognizer** (`kind="location"`) — checked every cycle; if the current view matches the destination label with sufficient confidence, guidance ends with "You have arrived."
- **Landmark recognizer** (`kind="landmark"`) — trained the same way as locations (e.g. capture a door), but announced ("Door ahead.") rather than treated as a destination, only when recognized AND within `landmark_distance_m` on the ToF center zone.

**Important limitation:** this approach works for a known, previously walked route in a fixed environment — it reacts correctly to walls and openings it can currently see, but it has no memory of the overall layout and cannot route around an obstacle to reach a destination it can't directly perceive. True path planning would need IMU/odometry or SLAM (see Future Work).

### Voice Destination Input — Vosk (offline STT)
`navigate_voice.py` asks "Where do you want to go?" and listens via the default microphone (Bluetooth headset mic or USB). Speech is transcribed locally using [Vosk](https://alphacephei.com/vosk/models) (`vosk-model-small-en-us-0.15`, ~40MB) — no internet, no cloud STT. The transcribed text is matched against the trained `location` labels by substring match; the first match wins. If no Vosk model is installed, `--destination <label>` bypasses voice entirely.

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

### Obstacle Classification — YOLOv8-nano (the project's deep learning component)
ORB and Vosk's acoustic model are the other two recognition techniques in this project; YOLOv8-nano is the explicit, visible **deep learning** component requested by the project guidelines.

- A pretrained YOLOv8n model (COCO, 80 classes, ~6MB) classifies WHAT triggered a ToF obstacle alert — e.g. "Chair ahead, 0.8 metres" instead of a generic "Obstacle ahead"
- **Why gated, not continuous:** running a CNN every cycle would be too slow for real-time use on RPi4 CPU. Instead the cheap ToF depth threshold (`ObstacleDetector`) runs every cycle as normal, and YOLO only runs on the webcam frame *after* an obstacle is already flagged — classifying what's already known to be close. This keeps the system real-time while still using a genuine DL model.
- **Why not used for doors:** "door" is not a COCO class. Trained ORB landmarks (see Location Recognition) handle custom small-data classes that have no pretrained equivalent. YOLO and ORB are deliberately used where each is strongest.
- Implemented in `src/nav_assistant/perception/object_detector.py`, wired into both `AwarenessSystem` and `navigate_voice.py`'s emergency obstacle check. Degrades gracefully (falls back to the generic alert message) if `ultralytics` isn't installed.

### Audio Strategy
- Linux/RPi: `espeak-ng` called via subprocess (most reliable, no driver bugs)
- Fallback: `pyttsx3` (macOS/Windows only)
- Location announcements: non-blocking (background thread)
- Obstacle alerts: blocking (~0.3s) to guarantee immediate delivery

### Why Not Full SLAM / ROS
Full indoor mapping (building a 3D map and localizing within it simultaneously) is computationally expensive and was the original project vision. It's preserved as future work — see below. Guided navigation today uses lightweight reactive wall-following instead, which is achievable on this hardware and still demonstrates real turn-by-turn guidance for a known route.

---

## Module Structure

```
src/nav_assistant/
├── sensors/
│   ├── base.py               # Abstract ISensor interface
│   ├── webcam.py             # USB webcam (OpenCV, V4L2 auto-detect)
│   ├── tof.py                # Arducam ToF B0410 (SDK, V4L2 auto-detect)
│   │                         #   .zone_depths() → (left, center, right) for wall-following
│   └── utils.py              # V4L2 device name detection shared utility
├── mapping/
│   ├── waypoint.py           # Waypoint dataclass (kind: "location" | "landmark")
│   ├── environment.py        # SQLite-backed store, filterable by kind
│   └── recorder.py           # Training: capture + store locations/landmarks
├── localization/
│   └── place_recognizer.py   # ORB matching → current location/landmark, filterable by kind
├── navigation/
│   ├── guided_navigator.py   # GuidedNavigator: wall-following + landmark + arrival
│   ├── route_graph.py        # Dijkstra route planning (future — not used today)
│   └── navigator.py          # Graph-based nav state machine (future — not used today)
├── speech/
│   └── recognizer.py         # VoiceRecognizer: offline Vosk STT for destination input
├── obstacle/
│   └── detector.py           # ToF depth threshold → ObstacleAlert
├── perception/
│   └── object_detector.py    # ObjectClassifier: YOLOv8-nano, classifies flagged obstacles (the DL component)
├── audio/
│   └── guidance.py           # TTS (espeak-ng) + obstacle beep
└── awareness.py              # AwarenessSystem: simple awareness-mode loop coordinator

scripts/
├── train.py                  # CLI: capture/append locations and landmarks
├── awareness.py               # Entry point: passive awareness mode
├── navigate_voice.py          # Entry point: guided navigation (voice + turn-by-turn)
└── test_sensors.py            # Hardware validation
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
class Waypoint:          # represents a named location, room, or landmark
    id: str              # UUID
    label: str           # Human name: "hallway", "kitchen", "door_kitchen_entrance"
    descriptor_path: str # Path to .npy ORB descriptor matrix
    depth_profile: list[float]  # 9-cell depth grid (3×3) from ToF
    created_at: str
    notes: str
    kind: str             # "location" (destination/announcement) | "landmark" (announced along the way)
```

`kind` is stored as a SQLite column with a migration step (`ALTER TABLE ... ADD COLUMN`) so older environment databases upgrade automatically on next open. `EnvironmentMap.list_waypoints(kind=...)` and `PlaceRecognizer.load(kind=...)` filter by it — guided navigation keeps two separate recognizer instances, one per kind.

Edges between locations are stored in SQLite but are **not used** by the current guided navigation (which is reactive, not graph-based). They are preserved for the future graph-based `RouteGraph`/`Navigator` modules.

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

### Phase 3 — Awareness Loop ✅ COMPLETE
- [x] ObstacleDetector (ToF depth threshold)
- [x] PlaceRecognizer (ORB matching)
- [x] AudioGuidance (espeak-ng)
- [x] AwarenessSystem coordinator (main loop)
- [x] awareness.py entry point script
- [x] End-to-end test on hardware

### Phase 4 — Guided Navigation ← CURRENT
- [x] Waypoint `kind` field (location vs landmark) + EnvironmentMap migration
- [x] `ToFFrame.zone_depths()` for wall-following (left/center/right)
- [x] `GuidedNavigator`: arrival detection, landmark announcement, turn/straight logic
- [x] `VoiceRecognizer`: offline Vosk STT for destination input
- [x] `navigate_voice.py` entry point
- [x] `train.py` support for capturing landmarks (`landmark <label>`)
- [ ] End-to-end hardware test of the full guided navigation flow
- [ ] Tune `clear_distance_m`, `landmark_distance_m`, `emergency_threshold_m` for the real test route

### Phase 5 — Tuning & Polish
- [ ] Confidence threshold tuning (min matches for location/landmark announcement)
- [ ] CPU profiling on RPi, frame rate optimization
- [ ] Graceful startup / shutdown (announcements on start/stop)

### Future Work (not in scope for this submission)
- Visual SLAM / indoor map building (the original project vision)
- Graph-based route planning (Dijkstra on the existing `WaypointEdge` model) for routes spanning more than one reactive leg
- Dead-reckoning with IMU between locations
- MobileNetV3 or similar for more robust location recognition
- Multi-environment support with automatic environment selection

---

## Current Status

**Phase:** 4 — Guided Navigation  
**Last Updated:** 2026-06-08  
**Working On:** End-to-end hardware test of voice destination + turn-by-turn + landmark guidance

---

## Completed Features

- Project structure initialized
- WebcamSensor with V4L2 device name auto-detection (no hardcoded indices)
- ToFSensor with Arducam SDK + V4L2 device name auto-detection
- Waypoint data model (SQLite + .npy) with `kind` field (location/landmark)
- EnvironmentMap persistent storage with kind-filtered queries and auto-migration
- Training CLI — capture named locations and landmarks from webcam + ToF
- PlaceRecognizer — ORB feature matching, filterable by waypoint kind
- ObstacleDetector — ToF depth threshold with cooldown
- AudioGuidance — espeak-ng subprocess on Linux, pyttsx3 fallback
- AwarenessSystem — passive obstacle + location announcement loop
- `ToFFrame.zone_depths()` — left/center/right depth split for wall-following
- GuidedNavigator — reactive turn-by-turn guidance, landmark announcements, arrival detection
- VoiceRecognizer — offline Vosk speech-to-text for destination input
- navigate_voice.py — full guided navigation entry point
- First real environment captured on hardware (lab_test)

---

## Pending Tasks

- End-to-end hardware test of navigate_voice.py (voice input → guidance → arrival)
- Train at least one landmark (door) and confirm announcement during navigation
- Tune `clear_distance_m`, `landmark_distance_m`, `emergency_threshold_m` for the real test route
- Download and verify the Vosk model on the Raspberry Pi (not yet tested on ARM)
- Confirm Bluetooth headset microphone is usable as the default audio input device
- Benchmark YOLOv8n inference time on RPi4 CPU (ultralytics not yet installed/tested on ARM)
- Confirm `ultralytics` + `torch` install successfully on RPi OS Bookworm (known to be a heavy dependency)

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
