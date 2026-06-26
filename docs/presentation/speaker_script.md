# Speaker Script — Smart Cane Environmental Awareness System
**5-minute presentation · First Draft**

---

## Slide 1 — Title

Good morning everyone. My name is Igor Xavier, and together with my teammate Fang Jialuo, we are building an AI-powered smart cane for visually impaired people using a Raspberry Pi.

The full project title is *"AI Smart Navigation Assistant for Visually Impaired People Using Raspberry Pi"* — but in practice we call it the Smart Cane Environmental Awareness System.

---

## Slide 2 — Main Idea & Objective

The problem we are addressing is simple: visually impaired people face real daily challenges navigating indoor spaces safely and independently.

Our original vision was to build a full indoor navigation system using Visual SLAM — basically building a 3D map of the environment in real time, similar to what robots do. However, after analyzing the available hardware and development time, we realized that was too ambitious for this first version.

So we redesigned the scope around two focused, achievable functions: **real-time obstacle detection** using the depth camera, and **location recognition** using the webcam. The system tells the user what is around them through spoken audio on Bluetooth headphones — for example, *"Obstacle detected 0.8 metres ahead"* or *"You are in the office."*

---

## Slide 3 — System Design

The core of the system is an awareness loop running at about 2 times per second, entirely on the Raspberry Pi with no internet connection.

On every cycle, the ToF depth camera checks if anything is closer than a threshold distance in the user's forward path. If it is, it immediately speaks an alert.

Every three cycles — about every one and a half seconds — the webcam captures a frame and runs it through an ORB feature matching algorithm against a database of previously trained locations. If it finds a confident match, it tells the user where they are.

Everything runs offline. No cloud, no internet, no latency from a remote server.

---

## Slide 4 — Assembled Hardware Photo

This is our current prototype. You can see the Raspberry Pi connected to the Arducam ToF camera through the CSI ribbon cable, the USB webcam, and the system is powered by a powerbank which makes it portable.

---

## Slide 5 — Hardware Components

These are the four main components. The Raspberry Pi 4 does all the processing. The Arducam ToF camera measures depth up to 4 metres at 10 frames per second. The Logitech C270 webcam captures video for location recognition. And the Bluetooth headphones deliver the audio feedback to the user.

The total hardware cost is around 80 euros, which makes it accessible compared to commercial assistive technology.

---

## Slide 6 — Code: Obstacle Detection

This is the core of our obstacle detection. Every cycle we read a depth frame from the ToF camera and check the minimum depth in the central third of the frame — that represents what is directly in front of the user.

If that minimum depth is below our threshold — currently set at 1.2 metres — and the cooldown period has passed, we trigger an audio alert. The cooldown prevents the system from repeating the same alert every half second for a stationary obstacle.

The messages are distance-aware: something at 0.3 metres says *"Warning, obstacle very close"*, while something at a metre says *"Obstacle ahead, one metre."*

---

## Slide 7 — Code: Location Recognition

For location recognition we use ORB — Oriented FAST and Rotated BRIEF — which is a classical computer vision algorithm built into OpenCV. It runs efficiently on the Raspberry Pi CPU with no GPU needed.

During training, the user walks around each room for two minutes while the system captures a frame every three seconds — that gives us about 40 frames, and 500 visual features per frame, stored as 5000 descriptors per location.

During recognition, we extract features from the live webcam frame and compare them against every stored location using a nearest-neighbour matcher. We apply Lowe's ratio test to keep only strong, unambiguous matches. The location with the most good matches above a confidence threshold is announced to the user.

---

## Slide 8 — Current Progress

In terms of progress: we have completed Phases 1 and 2. Both sensors are validated and working on the Raspberry Pi hardware, and we have successfully trained 2 locations with 5000 descriptors each.

We are currently in Phase 3 — the awareness loop is built and running, and we are testing it end to end on hardware.

Phase 4, which is threshold tuning and performance optimization, is coming next.

---

## Slide 9 — Challenges & Solutions

We faced several real hardware and software challenges during development. I want to highlight the most interesting ones.

The camera device index problem: on Linux, the USB webcam does not always get the same device number across reboots. We solved this by automatically detecting the correct device by name using the V4L2 system at startup.

The Arducam SDK was also different from the documentation — the function to start the camera required a `FrameType` argument, not a `DeviceType` as the older docs suggested. We found the correct API by reading the official Python examples.

And for text to speech, the standard Python library crashed on our system. We bypassed it entirely by calling the espeak-ng command directly from Python, which works perfectly.

---

## Slide 10 — Expected Output & Benefits

The end user experience is purely through audio. The system speaks on startup, announces the current location when it changes, and gives immediate warnings for obstacles.

The main benefits are: it runs completely offline, the hardware cost is low, it responds in under 500 milliseconds, and the architecture is designed to be extended — future versions can add navigation features without rewriting the core.

---

## Slide 11 — Next Steps

In the next few days we will complete the end-to-end hardware test, tune the recognition and obstacle thresholds for reliability, and train more locations in our real test environment.

Before the final submission we will add proper startup and shutdown announcements, and optimize CPU usage on the Raspberry Pi.

Looking further ahead — the things we deprioritized from the original vision are documented as future work: Visual SLAM for unknown environments, route planning using a waypoint graph, turn-by-turn navigation, and IMU integration for step counting. The architecture already has placeholder modules for all of these.

---

## Slide 12 — Thank You

That covers our first draft progress. The full code is open source at github.com/w1ggor/smart-nav-cane.

Thank you — we are happy to take any questions.

---

## Timing Guide

| Slide | Target time | Cumulative |
|---|---|---|
| 1 — Title | 20s | 0:20 |
| 2 — Objective | 45s | 1:05 |
| 3 — System Design | 35s | 1:40 |
| 4 — Hardware Photo | 20s | 2:00 |
| 5 — Components | 25s | 2:25 |
| 6 — Code: Obstacle | 30s | 2:55 |
| 7 — Code: Location | 35s | 3:30 |
| 8 — Progress | 20s | 3:50 |
| 9 — Challenges | 30s | 4:20 |
| 10 — Output | 20s | 4:40 |
| 11 — Next Steps | 25s | 5:05 |
| 12 — Thank You | 10s | 5:15 |
