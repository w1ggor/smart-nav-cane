# Raspberry Pi Deployment Guide

## Requirements

- Raspberry Pi 4 Model B (2GB+ RAM, 4GB recommended)
- Raspberry Pi OS (Bookworm 64-bit recommended)
- Python 3.9+
- Arducam ToF Camera B0410 connected via CSI
- USB Webcam connected via USB
- Bluetooth Headphones paired at OS level

---

## 1. Initial OS Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
# NOTE: install espeak-ng (not espeak). pyttsx3's espeak driver is broken
# on Python 3.13+ — the project calls espeak-ng directly via subprocess.
sudo apt install -y \
    python3-pip python3-venv \
    libopencv-dev python3-opencv \
    espeak-ng \
    libportaudio2 portaudio19-dev \
    pulseaudio pulseaudio-module-bluetooth \
    bluez bluez-tools \
    sqlite3 \
    git
```

---

## 2. Enable Camera Interface

```bash
# For CSI cameras (Arducam ToF uses CSI)
sudo raspi-config
# → Interface Options → Camera → Enable
# OR for newer RPi OS:
# → Interface Options → Legacy Camera → Enable (if needed by Arducam SDK)

# Verify CSI camera is detected
vcgencmd get_camera
```

---

## 3. Install Arducam ToF SDK

```bash
# Clone the official Arducam ToF SDK
cd ~
git clone https://github.com/ArduCAM/Arducam_tof_camera.git
cd Arducam_tof_camera

# Install Python bindings
cd python
pip install .

# Verify installation
python3 -c "from ArducamDepthCamera import ArducamCamera; print('SDK OK')"
```

> **Note:** If the SDK install fails, check the [Arducam GitHub](https://github.com/ArduCAM/Arducam_tof_camera) for the latest installation instructions. The B0410 may require specific kernel modules.

---

## 4. Clone and Install the Project

```bash
cd ~
git clone https://github.com/w1ggor/smart-nav-cane.git
cd smart-nav-cane

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install project in editable mode
pip install -e .
```

---

## 5. Bluetooth Headphones Setup

```bash
# Start Bluetooth service
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

# Pair headphones (interactive)
bluetoothctl
  power on
  agent on
  scan on
  # Wait for headphone MAC to appear, e.g. AA:BB:CC:DD:EE:FF
  pair AA:BB:CC:DD:EE:FF
  connect AA:BB:CC:DD:EE:FF
  trust AA:BB:CC:DD:EE:FF
  quit

# Set Bluetooth as default PulseAudio sink
pactl list sinks short
pactl set-default-sink bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink

# Test TTS over Bluetooth (using espeak-ng directly — pyttsx3 not needed on RPi)
espeak-ng "Hello world"
```

---

## 6. Find Camera Device Indices

Before running any scripts, confirm which `/dev/videoX` device is your USB webcam:

```bash
v4l2-ctl --list-devices
```

On a Raspberry Pi 4 with the Arducam ToF on CSI and a USB webcam, you will typically see:

```
unicam (platform:fe801000.csi):     → /dev/video0  (CSI — ToF camera)
C270 HD WEBCAM (usb-...):           → /dev/video1  (USB webcam)  ← use this
                                       /dev/video2
```

Update `config/default.yaml` if the index differs:

```yaml
webcam:
  device_index: 1   # set to whichever index matches your USB webcam
```

## 7. Validate Sensors

```bash
# Run from project root with venv active
source .venv/bin/activate

# Test both sensors (hardware)
python scripts/test_sensors.py

# Test webcam only with live view (requires display or VNC)
python scripts/test_sensors.py --show

# Test with ToF in mock mode (if hardware not attached yet)
python scripts/test_sensors.py --tof-mock
```

Expected output:
```
=== Summary ===
  webcam    : PASS
  tof       : PASS
```

---

## 8. Running Training Mode

```bash
source .venv/bin/activate
python scripts/train.py --env my_home

# Commands in training session:
#   capture front_door
#   capture hallway_middle
#   edge front_door hallway_middle 15 forward "Walk forward 15 steps."
#   list
#   quit
```

---

## 9. Running Navigation Mode

```bash
source .venv/bin/activate
python scripts/navigate.py --env my_home --destination kitchen_door
```

Press `Ctrl+C` to stop navigation.

---

## 10. Performance Tuning

```bash
# Check CPU temperature during operation
vcgencmd measure_temp

# Monitor CPU usage
top -d 1

# If overheating: ensure heatsink + fan is fitted
# If memory low: close unnecessary services
sudo systemctl disable bluetooth-mesh
```

### Recommended RPi Config (`/boot/config.txt`)
```ini
# Disable unnecessary GPU memory
gpu_mem=16

# Enable hardware video decoding (helps OpenCV)
dtoverlay=vc4-kms-v3d
```

---

## 11. Auto-Start on Boot (Optional)

```bash
# Create systemd service
sudo nano /etc/systemd/system/nav-assistant.service
```

```ini
[Unit]
Description=Smart Navigation Assistant
After=bluetooth.service pulseaudio.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/smart-nav-cane
ExecStart=/home/pi/smart-nav-cane/.venv/bin/python scripts/navigate.py --env my_home --destination kitchen
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable nav-assistant
sudo systemctl start nav-assistant
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Webcam not found | Check `ls /dev/video*`, try `--webcam-index 1` |
| ToF camera fails to open | Verify CSI ribbon connected, run `dmesg | grep arducam` |
| No audio output | Check `pactl list sinks`, verify BT device is connected |
| espeak-ng not found | Run `sudo apt install espeak-ng` |
| pyttsx3 voice error | Do not use pyttsx3 on RPi — the project uses `espeak-ng` directly |
| Low FPS / high CPU | Reduce `orb_n_features` in `config/default.yaml` |
