# Smart Navigation Assistant for Visually Impaired Users

An IoT + Edge AI navigation assistant running entirely on a Raspberry Pi 4. The device learns indoor environments during a training phase and later guides visually impaired users through stored routes using voice instructions and real-time obstacle detection.

## Hardware

- Raspberry Pi 4 Model B
- Arducam ToF Camera B0410 (depth sensing)
- USB Webcam (visual place recognition)
- Bluetooth Headphones (audio guidance)

## How It Works

1. **Training Phase**: Walk through the environment, marking waypoints (named locations). The system captures visual descriptors and depth profiles at each point.
2. **Navigation Phase**: The system recognizes the current location, plans a route to the destination, and issues spoken turn-by-turn instructions. Obstacles detected by the ToF camera trigger immediate audio alerts.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Test sensors
python scripts/test_sensors.py

# Training mode
python scripts/train.py --env my_home

# Navigation mode
python scripts/navigate.py --env my_home --destination kitchen_door
```

## Project Structure

```
src/nav_assistant/   Core modules
scripts/             CLI entry points
config/              YAML configuration
data/environments/   Stored environment maps
docs/                Deployment and API documentation
tests/               Unit tests
```

## Deployment

See [docs/deployment.md](docs/deployment.md) for full Raspberry Pi OS setup, dependency installation, and Bluetooth audio configuration.

## Architecture

See [CLAUDE.md](CLAUDE.md) for architecture decisions, data models, and development roadmap.

## License

MIT
