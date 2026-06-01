# CLAUDE.md — Smart Navigation Assistant for Visually Impaired Users

> **This file is the project's living memory and source of truth.**
> Update it whenever code changes, decisions are made, or lessons are learned.

---

## Project Overview

An IoT + Edge AI system running on a Raspberry Pi 4 that acts as a smart navigation assistant for visually impaired users. The device resembles a smart cane: it learns an indoor environment during a training phase, then guides the user through previously learned routes using audio cues and real-time obstacle detection.

**University:** IoT Term Project  
**Platform:** Raspberry Pi 4 Model B  
**Language:** Python 3.9+  
**Repository:** https://github.com/w1ggor/smart-nav-cane

---

## Hardware

| Component | Model | Interface | Role |
|-----------|-------|-----------|------|
| Compute | Raspberry Pi 4 Model B (4GB+) | — | Central processing unit |
| Depth Camera | Arducam ToF Camera B0410 | CSI / USB | Real-time depth measurement, obstacle detection |
| RGB Camera | USB Webcam (generic) | USB (UVC) | Visual place recognition |
| Audio Output | Bluetooth Headphones | Bluetooth (A2DP) | Voice guidance, obstacle alerts |

### Optional Future Hardware (not dependencies)
- IMU (MPU-6050): Step counting and orientation for dead-reckoning between waypoints
- Ultrasonic sensors (HC-SR04): Redundant close-range obstacle detection
- GPS module: Outdoor extension

---

## Architecture Decisions

### Why No SLAM / ROS
Full SLAM (ORB-SLAM3, OpenVSLAM) and ROS add significant complexity, require careful calibration, and are overkill for a constrained indoor environment with a fixed set of learned routes. The chosen approach favors a **working prototype over academic complexity**.

### Core Design: Waypoint Graph + Visual Place Recognition
- **Map Representation**: A directed graph where nodes are *waypoints* (named, visually identifiable locations) and edges are traversable paths with estimated step counts/distances.
- **Localization**: ORB feature descriptors extracted from the webcam frame are matched against stored waypoint descriptors. The waypoint with the best match score above a confidence threshold is the current location.
- **Navigation**: Dijkstra's algorithm on the waypoint graph produces a sequence of waypoints. Audio instructions are issued at each transition.
- **Obstacle Detection**: The ToF camera produces a depth frame (up to 4m). A configurable depth threshold in the forward zone triggers an immediate audio alert.

### Why ORB (not deep learning)
- Runs efficiently on RPi CPU (no GPU)
- No training data required
- Deterministic and debuggable
- OpenCV built-in — no extra dependencies
- Sufficient for indoor place recognition with controlled lighting

### Why SQLite + .npy files
- Zero-dependency database that survives reboots
- `.npy` files store ORB descriptor matrices efficiently (numpy native format)
- No cloud required, fully offline

### Audio Strategy
- Primary: `pyttsx3` (offline TTS engine) for spoken navigation instructions
- Alert: `pygame.mixer` for immediate non-blocking obstacle warning tones
- Bluetooth: Paired at OS level; Python sees it as default audio device

---

## Module Structure

```
src/nav_assistant/
├── sensors/
│   ├── base.py           # Abstract sensor interface (ISensor)
│   ├── webcam.py         # USB webcam wrapper (OpenCV)
│   └── tof.py            # Arducam ToF B0410 wrapper
├── mapping/
│   ├── waypoint.py       # Waypoint dataclass + serialization
│   ├── environment.py    # Environment map: SQLite graph store
│   └── recorder.py       # Training phase: capture + store waypoints
├── localization/
│   └── place_recognizer.py  # ORB matching against waypoint database
├── navigation/
│   ├── route_graph.py    # networkx graph, Dijkstra routing
│   └── navigator.py      # Navigation state machine
├── audio/
│   └── guidance.py       # TTS + audio alert interface
└── obstacle/
    └── detector.py       # Depth-frame threshold obstacle detection
```

### Data Flow (Navigation Mode)
```
WebcamSensor → frame → PlaceRecognizer → current_waypoint
ToFSensor    → depth → ObstacleDetector → alert if needed
current_waypoint + destination → Navigator → next_instruction
next_instruction → AudioGuidance → spoken output
```

### Data Flow (Training Mode)
```
WebcamSensor → frame → ORB descriptors  ┐
ToFSensor    → depth → depth profile    ├→ Waypoint → EnvironmentMap (SQLite)
user input   → label + connections      ┘
```

---

## Waypoint Data Model

```python
@dataclass
class Waypoint:
    id: str                    # UUID
    label: str                 # Human name, e.g. "kitchen_door"
    descriptor_path: str       # Path to .npy file with ORB descriptors
    depth_profile: list[float] # 9-sector depth grid (3x3) from ToF
    created_at: str            # ISO timestamp
    notes: str                 # Optional human notes

@dataclass
class WaypointEdge:
    from_id: str
    to_id: str
    steps: int                 # Estimated steps between waypoints
    direction_hint: str        # "forward", "turn_left", "turn_right"
    audio_instruction: str     # e.g. "Walk forward 10 steps, then turn left"
```

---

## Development Roadmap

### Phase 1 — Sensor Integration & Data Acquisition ✅ IN PROGRESS
- [x] Repository structure
- [x] CLAUDE.md initialized
- [x] Abstract sensor interface (`ISensor`)
- [x] Webcam module (`WebcamSensor`)
- [x] ToF camera module (`ToFSensor`)
- [x] Waypoint data model
- [x] Environment storage (SQLite)
- [ ] Sensor test scripts running on RPi
- [ ] Confirm ToF SDK installation on RPi

### Phase 2 — Environment Learning
- [ ] Training mode recorder
- [ ] ORB descriptor extraction
- [ ] Waypoint capture UI (keyboard-driven CLI)
- [ ] Environment persistence to SQLite + .npy
- [ ] Edge/connection recording between waypoints

### Phase 3 — Localization & Navigation
- [ ] ORB-based place recognizer (match frame → waypoint)
- [ ] Route graph construction from stored environment
- [ ] Dijkstra navigation path planning
- [ ] Navigation state machine (idle → navigating → arrived)

### Phase 4 — Audio Guidance & Obstacle Avoidance
- [ ] pyttsx3 TTS integration
- [ ] Bluetooth audio device selection
- [ ] Real-time obstacle detection (ToF depth threshold)
- [ ] Audio alert system (non-blocking)
- [ ] Navigation instruction speech synthesis

### Phase 5 — Optimization & Polish
- [ ] RPi CPU profiling and bottleneck resolution
- [ ] Frame rate tuning for real-time performance
- [ ] Confidence threshold tuning for place recognition
- [ ] Optional: MobileNetV3 feature extractor as ORB upgrade
- [ ] Optional: Dead-reckoning with IMU between waypoints

---

## Current Status

**Phase:** 1 — Sensor Integration  
**Last Updated:** 2026-05-30  
**Working On:** Initial project scaffolding and sensor abstractions

---

## Completed Features

- Project structure initialized
- Abstract sensor interface defined
- WebcamSensor implementation (OpenCV)
- ToFSensor implementation (Arducam SDK)
- Waypoint and WaypointEdge data models
- EnvironmentMap SQLite storage
- Configuration system (YAML)
- Sensor validation scripts

---

## Pending Tasks

- Deploy and test sensors on physical Raspberry Pi
- Confirm Arducam ToF SDK Python bindings work on RPi OS
- Verify Bluetooth audio device pairing and pyttsx3 output

---

## Implementation Notes

### Arducam ToF B0410 SDK
- Install from: https://github.com/ArduCAM/Arducam_tof_camera
- Python package: `ArducamDepthCamera`
- Connection type: CSI (preferred) or USB
- Output: 240×180 depth frame (float32, meters) + amplitude frame
- Max range: ~4m indoors
- Frame rate: ~10 FPS at full resolution

### ORB Matching Parameters
- `nfeatures=500` balances descriptor richness vs. speed
- FLANN with LSH index for binary descriptors
- Match ratio test: 0.75 (Lowe's ratio)
- Minimum good matches for confident localization: 15

### RPi Performance Targets
- ToF read + obstacle check: < 50ms
- ORB extraction + matching: < 200ms per frame
- Total navigation loop: < 500ms (2 Hz is acceptable)

### Bluetooth Audio Setup (RPi)
```bash
bluetoothctl
  power on
  scan on
  pair <MAC>
  connect <MAC>
  trust <MAC>
# Set as default in /etc/pulse/default.pa or via pactl
pactl set-default-sink bluez_sink.<MAC>
```

---

## Lessons Learned

### USB Webcam is NOT /dev/video0 on RPi with CSI camera attached
When the Arducam ToF is on the CSI port, `/dev/video0` is the CSI unicam device, not the USB webcam. The C270 USB webcam lands at `/dev/video1`. Always run `v4l2-ctl --list-devices` first and set `webcam.device_index` in `config/default.yaml` accordingly. Default is now `1` for this hardware setup.

### Arducam SDK DeviceType.TOF attribute name varies by SDK version
The `DeviceType` enum has been renamed across Arducam SDK releases (`TOF`, `Tof`, `ARDUCAM_TOF`). The tof.py module now uses `_resolve_device_type()` which tries all known names in order and falls back to integer `0` (the underlying C++ enum value, stable across all releases).

### UVC webcam returns empty frames immediately after open
USB webcams on Linux (V4L2) often return black/empty frames for the first few reads while the sensor initializes. Fix: call `cap.grab()` 5 times after opening to flush the initial empty frames before the first real `read()`.

### pyttsx3 broken on Python 3.13 + espeak-ng (RPi OS Bookworm)
`pyttsx3`'s espeak driver hardcodes the voice name `gmw/en` which doesn't exist in `espeak-ng`. This raises `ValueError: SetVoiceByName failed` on init. **Fix:** call `espeak-ng` directly via `subprocess` on Linux — no pyttsx3 needed. pyttsx3 is kept as a fallback for macOS/Windows only. The `AudioGuidance` class auto-detects the backend at import time using `shutil.which("espeak-ng")`.

---

## Deployment Instructions

See [docs/deployment.md](docs/deployment.md) for full Raspberry Pi setup guide.
