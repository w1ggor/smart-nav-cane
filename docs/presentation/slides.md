---
marp: true
theme: gaia
class: lead
paginate: true
backgroundColor: #1a1a2e
color: #eaeaea
style: |
  section {
    font-family: 'Segoe UI', sans-serif;
    padding: 50px 60px;
  }
  section.lead h1 {
    color: #e94560;
    font-size: 2.2em;
  }
  section.lead h3 {
    color: #a0a0c0;
    font-weight: 400;
  }
  h2 {
    color: #e94560;
    border-bottom: 2px solid #e94560;
    padding-bottom: 8px;
    margin-bottom: 24px;
  }
  code {
    background: #16213e;
    color: #00d2ff;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 0.85em;
  }
  pre {
    background: #16213e !important;
    border-left: 4px solid #e94560;
    border-radius: 6px;
    padding: 20px !important;
  }
  pre code {
    background: transparent;
    color: #e2e8f0;
    font-size: 0.78em;
    padding: 0;
  }
  .columns {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 30px;
    align-items: start;
  }
  ul li {
    margin-bottom: 10px;
    line-height: 1.5;
  }
  .tag {
    background: #e94560;
    color: white;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.75em;
    font-weight: bold;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85em;
  }
  th {
    background: #e94560;
    color: white;
    padding: 8px 12px;
    text-align: left;
  }
  td {
    padding: 8px 12px;
    border-bottom: 1px solid #2a2a4a;
  }
  tr:nth-child(even) td {
    background: #16213e;
  }
  footer {
    color: #606080;
    font-size: 0.7em;
  }
---

<!-- Slide 1: Title -->
# Smart Cane Environmental Awareness System

### IoT Term Project — First Draft Presentation

<br>

**Igor Xavier**
Raspberry Pi 4 · Arducam ToF · OpenCV · Python

---
<!-- class: default -->

<!-- Slide 2: Objective -->
## A. Main Idea & Objective

**Problem:** Visually impaired users struggle to navigate indoor environments safely and independently.

**Our solution:** A smart cane device that provides real-time environmental awareness through two mechanisms:

<br>

<div class="columns">

**🔴 Obstacle Detection**
The ToF depth camera continuously monitors the forward path and warns the user about nearby obstacles through their headphones.

**🔵 Location Recognition**
The webcam recognizes previously trained rooms or locations and tells the user where they currently are.

</div>

<br>

> *"Obstacle detected 0.8 metres ahead."*  &nbsp;&nbsp; *"You are in the office."*

---

<!-- Slide 3: System Design -->
## B. System Design & Methodology

**Core loop running at 2 Hz — no cloud, fully offline:**

```
┌─────────────┐    depth frame    ┌──────────────────┐
│ Arducam ToF │ ────────────────► │ Obstacle Detector│──► Audio Alert
└─────────────┘                   └──────────────────┘
                                                         ┌───────────────┐
┌─────────────┐    video frame    ┌──────────────────┐   │ Bluetooth     │
│ USB Webcam  │ ────────────────► │ Place Recognizer │──► Headphones    │
└─────────────┘                   └──────────────────┘   └───────────────┘
```

<br>

| Concern | Approach | Frequency |
|---|---|---|
| Obstacle detection | Depth threshold on ToF frame | Every cycle |
| Location recognition | ORB feature matching | Every 3 cycles (~1.5s) |
| Audio output | espeak-ng via subprocess | On event |

---

<!-- Slide 4: Hardware -->
## D. Hardware Components

<div class="columns">

**Processing & Sensing**

| Component | Role |
|---|---|
| Raspberry Pi 4 (4GB) | Central compute |
| Arducam ToF B0410 | Depth camera (CSI) |
| USB Webcam C270 | Room recognition |
| Bluetooth Headphones | Audio output |

**Why this hardware?**

- Runs **fully offline** — no GPU needed
- ToF gives **precise depth** up to 4m
- ORB matching runs on **CPU only**
- Bluetooth audio = **wearable cane** form factor

</div>

---

<!-- Slide 5: Code — Obstacle Detection -->
## C. Key Code — Obstacle Detection

**`src/nav_assistant/obstacle/detector.py`**

```python
def check(self, tof_frame: ToFFrame) -> Optional[ObstacleAlert]:
    # Get minimum depth in the central forward zone
    min_depth = tof_frame.forward_min_depth(zone_fraction=0.33)

    if min_depth > 0 and min_depth < self._threshold:
        now = time.monotonic()
        if now - self._last_alert_time >= self._cooldown:
            self._last_alert_time = now
            return ObstacleAlert(min_depth=min_depth, ...)

    return None  # no alert
```

- Only the **central third** of the depth frame is checked (forward path)
- A **cooldown** (2s) prevents repeated alerts for the same obstacle
- Output: *"Obstacle detected 0.8 metres ahead."*

---

<!-- Slide 6: Code — Location Recognition -->
## C. Key Code — Location Recognition

**`src/nav_assistant/localization/place_recognizer.py`**

```python
def recognize(self, gray_frame: np.ndarray) -> RecognitionResult:
    _, query_descs = self._orb.detectAndCompute(gray_frame, None)

    for waypoint, stored_descs in self._index:
        matches = self._matcher.knnMatch(query_descs, stored_descs, k=2)
        # Lowe's ratio test — keep only strong matches
        good = [m for m, n in matches
                if m.distance < 0.75 * n.distance]

        if len(good) > best_good:
            best_good = len(good)
            best_wp = waypoint

    confidence = min(1.0, best_good / 250)
    return RecognitionResult(waypoint=best_wp, confidence=confidence, ...)
```

**Training:** 40 frames × 500 features = 5000 descriptors per location

---

<!-- Slide 7: Current Progress -->
## Current Progress

<br>

| Phase | Status | Description |
|---|---|---|
| Phase 1 — Sensors | ✅ Complete | Webcam + ToF working on RPi hardware |
| Phase 2 — Training | ✅ Complete | 2 locations trained (5000 descriptors each) |
| Phase 3 — Awareness | 🔄 In Progress | Awareness loop built, testing underway |
| Phase 4 — Tuning | ⏳ Pending | Threshold and confidence tuning |

<br>

**What runs today:**
- `test_sensors.py` — validates both cameras
- `train.py` — 2-minute capture sessions per location
- `awareness.py` — real-time obstacle + location detection loop

---

<!-- Slide 8: Challenges & Solutions -->
## E. Challenges & Solutions

| Challenge | Root Cause | Solution |
|---|---|---|
| Wrong camera device index | USB webcam index not stable across reboots | Auto-detect by V4L2 device name at startup |
| ToF SDK `DeviceType.TOF` missing | API changed between SDK versions | Use `FrameType.DEPTH`, parse official examples |
| pyttsx3 voice error | Broken espeak-ng driver on Python 3.13 | Call `espeak-ng` directly via subprocess |
| Webcam returns blank frames | UVC sensor warmup time | Discard first 5 frames after `open()` |
| Single frame per location insufficient | ORB needs visual diversity | 2-minute continuous capture session (40 frames) |

---

<!-- Slide 9: Expected Output & Benefits -->
## F. Expected Output & Benefits

**What the system says to the user:**

```
"Awareness system started."

"You are in the office."

"Obstacle detected 0.8 metres ahead."

"You are still in the office."

"You are in the hallway."
```

<br>

**Benefits:**
- **No internet required** — works in any indoor space
- **Low cost** — standard Raspberry Pi hardware (~€80 total)
- **Extensible** — architecture supports future route navigation
- **Practical** — real-time feedback at 2 Hz, < 500ms latency

---

<!-- Slide 10: Next Steps -->
## G. Next Steps & Project Plan

<br>

**Immediate (this week)**
- End-to-end test of `awareness.py` on hardware
- Tune `confidence_threshold` and `min_good_matches` for reliable recognition
- Tune `alert_threshold_m` for comfortable obstacle warning distance

**Short term (next 2 weeks)**
- Train more locations in the real test environment
- Add startup / shutdown audio announcements
- CPU profiling and frame rate optimization on RPi

**Future work (post-submission)**
- Route planning and turn-by-turn navigation
- IMU integration for step counting
- SLAM for unknown environments

---
<!-- class: lead -->

<!-- Slide 11: Thank You -->
# Thank You

<br>

**Smart Cane Environmental Awareness System**

<br>

🔗 `github.com/w1ggor/smart-nav-cane`

<br>

*Built with Raspberry Pi 4 · Arducam ToF · OpenCV · Python*

<br>

### Questions?
