# Smart Cane Environmental Awareness System

An IoT + Edge AI assistive device running entirely on a Raspberry Pi 4. Designed for visually impaired users, it provides real-time environmental awareness through two complementary sensors and spoken audio feedback.

## What It Does

**Obstacle Detection** — The Arducam ToF depth camera continuously monitors the forward zone. When an object enters the alert threshold, the user hears:
> *"Obstacle detected 0.8 metres ahead."*

**Location Recognition** — The USB webcam matches the current scene against a database of trained locations. When the user enters a recognized space:
> *"You are in the kitchen."*

Everything runs offline on the Raspberry Pi. No cloud, no internet required.

## Hardware

| Component | Role |
|-----------|------|
| Raspberry Pi 4 Model B | Central compute |
| Arducam ToF Camera B0410 (CSI) | Depth sensing / obstacle detection |
| USB Webcam (C270) | Location recognition |
| Bluetooth Headphones | Spoken audio feedback |

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/w1ggor/smart-nav-cane.git
cd smart-nav-cane
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# 2. Validate hardware
python scripts/test_sensors.py

# 3. Train locations (walk to each room, run capture)
python scripts/train.py --env my_home
# > capture kitchen
# > capture hallway
# > capture office
# > quit

# 4. Run awareness mode
python scripts/awareness.py --env my_home
```

Press `Ctrl+C` to stop.

## Project Structure

```
src/nav_assistant/
├── sensors/          Webcam + ToF abstractions (auto-detect device index)
├── mapping/          Location storage (SQLite + .npy ORB descriptors)
├── localization/     ORB-based place recognition
├── obstacle/         ToF depth threshold detector
├── audio/            espeak-ng TTS + audio alerts
└── awareness.py      Main loop coordinator

scripts/
├── train.py          Interactive location training CLI
├── awareness.py      Awareness mode entry point
└── test_sensors.py   Hardware validation
```

## Configuration

Edit `config/default.yaml` to tune:
- `obstacle.alert_threshold_m` — distance at which obstacles are flagged
- `localization.confidence_threshold` — minimum confidence for location announcements
- `localization.min_good_matches` — minimum ORB matches required
- `webcam.device_name` — V4L2 name of your webcam
- `tof.device_name` — V4L2 name of the CSI device (default: "unicam")

## Future Work

- Route planning and turn-by-turn navigation
- Waypoint graph and path finding
- IMU dead-reckoning between locations
- SLAM for unknown environments

See [CLAUDE.md](CLAUDE.md) for architecture decisions and development history.

## Deployment

See [docs/deployment.md](docs/deployment.md) for Raspberry Pi OS setup, Arducam SDK installation, and Bluetooth audio configuration.

## License

MIT
