# Speaker Script — Final Presentation
**Smart Cane Environmental Awareness System · Max 10 minutes including Q&A**
**Target: ~7 minutes talk, leaving 3 minutes for Q&A**

---

## Slide 1 — Title

Good morning. We are Igor Xavier and Fang Jialuo, and this is our final presentation for the AI Smart Navigation Assistant for Visually Impaired People Using Raspberry Pi — what we call the Smart Cane Environmental Awareness System.

---

## Slide 2 — Outline

Here's what we'll cover: the motivation, our project idea and how the scope evolved, the system architecture, hardware and software, the AI and deep learning components, our results, the challenges we solved, and future work. Then we're happy to take questions.

---

## Slide 3 — Motivation & Problem

Visually impaired users face real daily challenges navigating indoor spaces independently. Existing solutions sit at two extremes: full SLAM systems are accurate but need expensive sensors like LiDAR and IMUs, putting them out of reach for a student project. Simple ultrasonic canes are cheap but "dumb" — they beep when something is close, but tell you nothing about what it is or where you are. Our goal was to find a middle ground: meaningful semantic awareness, fully offline, on a single Raspberry Pi, at low cost.

---

## Slide 4 — Project Idea

Our cane answers three questions in real time. What is in front of me — solved with depth detection plus deep learning classification. Where am I — solved with visual place recognition. And how do I get to my destination — solved with voice input and turn-by-turn audio guidance. In practice, the experience looks like this: you say "kitchen," the cane warns you "chair ahead, 0.8 metres," tells you to turn, and finally says "you have arrived."

---

## Slide 5 — Scope Decision

Our original vision was full Visual SLAM — building a 3D map in real time using something like ORB-SLAM3 and planning routes autonomously. We deliberately stepped back from that. It needs an IMU, heavy compute, and careful calibration, none of which we could deliver reliably in the time we had. Instead we shipped two achievable modes — awareness and guided navigation — and we kept SLAM as clearly documented future work rather than abandoning the idea.

---

## Slide 6 — System Architecture

This is the core data flow. The ToF camera feeds an obstacle detector every cycle — that's cheap and runs constantly. Only when it actually flags something close do we run YOLOv8-nano on the webcam frame to classify what it is. In parallel, the webcam feeds our ORB-based place and landmark recognizer, which talks to the guided navigator. And at the start of navigation, the microphone feeds Vosk, our offline speech recognizer, to get the destination. Everything converges on Bluetooth audio.

---

## Slide 7 — Awareness Mode

Our first operating mode is passive awareness — no destination, just continuous feedback. The code here shows the core logic: when an obstacle is detected, we first get a generic alert message, and if our YOLO classifier is available, we try to identify what the object actually is and speak something more specific, like "chair ahead, 0.8 metres," instead of just "obstacle ahead."

---

## Slide 8 — Guided Navigation Mode

Our second mode is guided navigation. Since we have no IMU and no wheel odometry, we cannot plan a path to arbitrary coordinates the way SLAM would. Instead we use reactive wall-following: we split the ToF depth frame into left, center, and right zones every cycle. If the center is clear, we say go straight; if it's blocked, we turn toward whichever side has more clearance. We combine this with arrival detection — matching the live view against the destination — and landmark announcements for things like trained doors. This works reliably for a route the system has walked before.

---

## Slide 9 — Hardware Photo

This is our assembled prototype — the Raspberry Pi, the Arducam ToF camera on the CSI port, and the USB webcam, all mounted on the cane.

---

## Slide 10 — Hardware Components

Four components: the Raspberry Pi 4 for compute, the Arducam ToF camera for depth up to 4 metres, the Logitech C270 webcam for both recognition and YOLO classification, and Bluetooth headphones for audio in and out. Total hardware cost is around 80 euros — no GPU, no cloud, no internet connection required anywhere in the pipeline.

---

## Slide 11 — Software Architecture

Our codebase is organized into eight modules by concern. I want to highlight two in particular: perception, which wraps our YOLO model, and speech, which wraps Vosk — these are our two deep learning components. Everything is backed by 27 automated unit tests.

---

## Slide 12 — AI / Deep Learning Components

This is the core of our technical contribution. We use three different recognition techniques, each chosen deliberately for where it performs best. ORB is classical computer vision — no neural network — used for place and landmark recognition because it needs only a two-minute capture session and no labeled data. YOLOv8-nano is a real convolutional neural network, pretrained on COCO, used to classify obstacles. And Vosk uses a deep neural network acoustic model for fully offline speech recognition.

Two design decisions are worth explaining clearly, because we expect questions on this: first, we gate YOLO behind the cheap ToF threshold rather than running it every cycle, because a CNN running continuously would be too slow for a Raspberry Pi 4 CPU with no GPU. Second, we still use ORB for doors instead of YOLO, simply because "door" is not a class in the COCO dataset YOLO was trained on.

---

## Slide 13 — Code: Gated DL Inference

Here's the actual classify function from our object detector. Notice it returns early in three cases — if the classifier isn't available, if YOLO finds no objects at all, or if the best detection's confidence is below our threshold. Only if none of those apply do we return a real label like "chair" with its confidence score.

---

## Slide 14 — Code: Wall-Following Decision

And here's the decision logic for navigation. It's a pure function: given three numbers — left, center, and right depth — it returns one of four outcomes: go straight, turn left, turn right, or stop because the path is blocked. Because it's pure logic with no hardware dependency, we can unit test it directly without needing the actual sensors.

---

## Slide 15 — Results & Status

In terms of status: sensor integration, location training, and the awareness loop are all complete and validated on real hardware. Guided navigation and YOLO obstacle classification are implemented and unit tested. All 27 of our automated tests pass.

---

## Slide 16 — Contributions

To summarize our contributions: a working, fully offline assistive prototype combining depth sensing, classical computer vision, and two deep learning models on a single Raspberry Pi 4; a deliberate architecture that pairs ORB, YOLO, and Vosk rather than defaulting to one technique; a hardware layer that automatically detects camera devices by name, solving a real instability we hit during development; and 27 automated tests.

---

## Slide 17 — Challenges & Solutions

We want to be transparent about the real engineering problems we solved. Our USB webcam's device index wasn't stable across reboots, so we built automatic detection by device name. The Arducam SDK's actual API didn't match its documentation, so we had to read the official examples directly to find the right function calls. Python's text-to-speech library crashed on our system, so we now call espeak-ng directly. A single training frame per location was too fragile for reliable recognition, so we built a two-minute continuous capture session. And running deep learning every cycle was too slow, so we gated it behind the cheap depth check.

---

## Slide 18 — Future Work

Looking ahead, the features we deliberately deferred from our original vision: Visual SLAM for real-time 3D mapping and navigation to unseen destinations; graph-based route planning — our data model already stores the edges needed for this; IMU integration for dead-reckoning; fine-tuning a custom object detector for assistive-specific classes like doors and stairs; and multi-environment support.

---

## Slide 19 — Thank You

That's our project. The full code, including everything we just showed, is open source on GitHub. Thank you — we're ready for your questions.

---

## Anticipated Q&A — Prepare These Answers

**Q: Why didn't you implement full SLAM as originally planned?**
A: SLAM needs accurate odometry — typically from an IMU or wheel encoders — to track motion between frames. We have neither. Attempting SLAM without that would produce an unreliable map, which is worse than not having one. We made an explicit, documented trade-off toward a system we could make reliable in the time available.

**Q: Why use YOLO if it's slow on a Raspberry Pi?**
A: We don't run it continuously — that's the whole point of gating it behind the ToF threshold. The cheap depth check (no neural network, near-instant) runs every cycle. YOLO only runs on the rare cycles where an obstacle is already confirmed close, so the inference cost is paid only when it matters.

**Q: Could you train YOLO to recognize doors directly?**
A: Yes, that's listed explicitly in our future work. It would require collecting and labeling a custom dataset of door images, which wasn't feasible in our timeline. ORB landmarks solve the same problem today with a two-minute capture session and zero labeling.

**Q: How accurate is the ORB place recognition?**
A: It depends on descriptor count and lighting consistency. We aim for 1000–5000 descriptors per location from a 2-minute walk-around capture. It's not as robust as a learned embedding model would be, but it requires zero training data, which matters for a system end-users would train themselves in their own home.

**Q: What happens if the voice recognition fails?**
A: The system falls back gracefully — if Vosk isn't available or doesn't understand, the script supports a `--destination` flag to bypass voice entirely, and at runtime it asks the user to try again rather than crashing.

**Q: Is this safe for real-world use today?**
A: Not yet without further field testing — our wall-following logic was tuned and tested on a specific known route, not validated across many environments. We're transparent about that limitation in the report.
