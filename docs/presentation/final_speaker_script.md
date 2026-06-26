# Speaker Script — Final Presentation
**Smart Cane Environmental Awareness System · Max 10 minutes including Q&A**
**Target: ~7.5 minutes talk, leaving ~2.5 minutes for Q&A**

---

## Slide 1 — Title

Good morning. We are Igor Xavier and Fang Jialuo, and this is our final presentation for the AI Smart Navigation Assistant for Visually Impaired People Using Raspberry Pi — what we call the Smart Cane Environmental Awareness System.

---

## Slide 2 — Outline

Here's what we'll cover: the motivation, our project idea and how the scope evolved, the system architecture, hardware and software, the AI and deep learning components and their accuracy, our results, the challenges we solved, and future work.

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

Our second mode is guided navigation. Since we have no IMU and no wheel odometry, we cannot plan a path to arbitrary coordinates the way SLAM would. Instead we use reactive wall-following: we split the ToF depth frame into left, center, and right zones every cycle. If the center is clear, we say go straight; if it's blocked, we turn toward whichever side has more clearance. We combine this with arrival detection and landmark announcements. This works reliably for a route the system has walked before.

---

## Slide 9 — What If the User Deviates?

This is an important honesty point, and we want to address it directly rather than wait for the question. Because we have no map and no odometry, the system has no concept of being "on" or "off" the trained route — it only reacts to what it currently sees. Obstacle avoidance keeps working perfectly regardless, since that's purely reactive. But arrival detection and landmark recognition depend on visual matching, and can silently fail if the viewpoint differs too much from training. And critically, we have no recovery behavior — no "you seem lost" message. It will just keep giving wall-following instructions. This limitation is exactly why we measured visual robustness directly, which we'll show in a moment.

---

## Slide 10 — Hardware Photo

This is our assembled prototype — the Raspberry Pi, the Arducam ToF camera on the CSI port, and the USB webcam, all mounted on the cane.

---

## Slide 11 — Hardware Components

Four components: the Raspberry Pi 4 for compute, the Arducam ToF camera for depth up to 4 metres, the Logitech C270 webcam for both recognition and YOLO classification, and Bluetooth headphones for audio in and out. Total hardware cost is around 80 euros.

---

## Slide 12 — Software Architecture

Our codebase is organized into eight modules by concern. I want to highlight two in particular: perception, which wraps our YOLO model, and speech, which wraps Vosk — these are our two deep learning components. Everything is backed by 27 automated unit tests.

---

## Slide 13 — AI / Deep Learning Components

This is the core of our technical contribution. We use three different recognition techniques, each chosen deliberately for where it performs best. ORB is classical computer vision — used for place and landmark recognition because it needs only a two-minute capture session and no labeled data. YOLOv8-nano is a real convolutional neural network, pretrained on COCO, used to classify obstacles. And Vosk uses a deep neural network acoustic model for fully offline speech recognition.

Two design decisions are worth explaining clearly: we gate YOLO behind the cheap ToF threshold because a CNN running continuously would be too slow for a Raspberry Pi 4 CPU with no GPU. And we still use ORB for doors instead of YOLO, because "door" is not a class in the COCO dataset YOLO was trained on.

---

## Slide 14 — Dataset Sources & Accuracy

Since the professor specifically asked us to be explicit about this: our three AI components have fundamentally different relationships to data. ORB uses no external dataset at all — every descriptor comes from the user's own two-minute capture session in their own home. YOLOv8-nano is pretrained on COCO, a public dataset of about 330,000 images and 80 object categories, and its published accuracy is a mean average precision of 37.3 on the COCO validation set. Vosk's small English model is trained on public speech corpora, with a published word error rate of 9.85 percent on LibriSpeech.

We want to be upfront about one limitation: the Raspberry Pi we developed on was not available to us during this final submission period, so we could not re-measure end-to-end accuracy on the deployed hardware. For the pretrained models, we report their official published benchmarks rather than inventing new numbers. For our own ORB component, we did something better than guessing — we ran a real, controlled test, which is the next slide.

---

## Slide 15 — ORB Robustness — Real Test Results

We took the exact production matching code — the same 500 ORB features, the same Lowe's ratio test, the same thresholds used in the deployed system — and tested it against synthetic perturbations of a real photo: rotation, blur, and brightness changes. Rotation alone never broke recognition, ORB is naturally rotation-invariant by design. But Gaussian blur, simulating motion while walking, caused recognition to fail once the blur got heavy. And darker lighting caused failure even faster — at minus 40 brightness, good matches dropped from 500 to 133, well below our threshold.

We want to be precise about what this does and doesn't prove: rotating an image in 2D is not the same as a real 3D viewpoint change, which also introduces perspective distortion we didn't model here. So this likely *overestimates* robustness to camera angle. But the blur and lighting results are directly informative, and they explain exactly why path deviation is risky — it's less about the angle you approach from and more about motion blur and lighting changes.

---

## Slide 16 — Code: Gated DL Inference

Here's the actual classify function from our object detector. It returns early in three cases — if the classifier isn't available, if YOLO finds no objects at all, or if the best detection's confidence is below threshold. Only then do we return a real label with its confidence score.

---

## Slide 17 — Code: Wall-Following Decision

And here's the decision logic for navigation. It's a pure function: given left, center, and right depth, it returns go straight, turn left, turn right, or stop. Because it's pure logic, we can unit test it directly without needing the actual sensors.

---

## Slide 18 — Results & Status

In terms of status: sensor integration, location training, and the awareness loop are all complete and validated on real hardware. Guided navigation and YOLO obstacle classification are implemented and unit tested. All 27 of our automated tests pass.

---

## Slide 19 — Contributions

To summarize: a working, fully offline assistive prototype combining depth sensing, classical computer vision, and two deep learning models on a single Raspberry Pi 4; a deliberate architecture that pairs ORB, YOLO, and Vosk rather than defaulting to one technique; explicit dataset sourcing and a real robustness measurement rather than an unverified accuracy claim; and 27 automated tests.

---

## Slide 20 — Challenges & Solutions

Four challenges shaped this project the most. First, full SLAM was infeasible without an IMU or odometry — we treated that as a scope decision, not a failure, and redesigned around reactive navigation while keeping SLAM as documented future work. Second, our training data approach evolved through three iterations — a single frame was unreliable, a five-frame burst barely helped because the frames were too similar, and we landed on a two-minute continuous capture that actually works. Third — and this one is very recent — building a demo this week without the Raspberry Pi, we discovered a real cross-platform threading bug: our Windows text-to-speech fallback hangs when one engine is shared across threads, because of how Windows COM threading works. We fixed it by creating a fresh engine per call. Fourth, running deep learning every cycle was too slow, so we gated YOLO behind the cheap depth check.

---

## Slide 21 — Future Work

Looking ahead: Visual SLAM for real-time 3D mapping and navigation to unseen destinations; graph-based route planning, since our data model already stores the edges needed for this; IMU integration for dead-reckoning; fine-tuning a custom object detector for assistive-specific classes like doors and stairs; and multi-environment support.

---

## Slide 22 — Thank You

That's our project. The full code is open source on GitHub. Thank you — we're ready for your questions.

---

## Anticipated Q&A — Prepare These Answers

**Q: Why didn't you implement full SLAM as originally planned?**
A: SLAM needs accurate odometry — typically from an IMU or wheel encoders — to track motion between frames. We have neither. Attempting SLAM without that would produce an unreliable map, which is worse than not having one. We made an explicit, documented trade-off toward a system we could make reliable in the time available.

**Q: What is the accuracy of your system?**
A: We're precise about what we can and can't claim. The two pretrained deep learning models have official published benchmarks — YOLOv8-nano at 37.3 mAP on COCO, Vosk's small model at 9.85% word error rate on LibriSpeech — which we report rather than re-deriving without the original test data. For our own ORB recognition component, we ran a controlled robustness test using the exact production code on synthetic image perturbations: it tolerates rotation well, but fails under heavy motion blur or darker lighting. We don't have a single end-to-end accuracy percentage for the full deployed system, because the Raspberry Pi wasn't available to us during this final phase — and we'd rather say that clearly than state a number we didn't actually measure.

**Q: What's the source of your training/test data?**
A: Three different sources, by design. ORB uses no external dataset — it's entirely self-collected by the user in their own environment, a two-minute walk-around capture with no labeling needed. YOLOv8-nano uses Microsoft's COCO dataset, a public benchmark with about 330,000 images and 80 object categories — we use the pretrained weights as released, no fine-tuning. Vosk's model is trained by its maintainers on public English speech corpora, also used as released.

**Q: What happens if the user deviates from the trained path, or something in the environment changes?**
A: Obstacle avoidance is unaffected — it's purely reactive to whatever the depth sensor sees right now, so it keeps working regardless of route. But arrival and landmark detection depend on ORB matching the live view against training data, and our robustness test shows that's more sensitive to lighting changes and motion blur than to viewpoint angle. If recognition confidence drops too far, the system doesn't detect that it's "lost" — there's no recovery behavior yet. It will just continue giving wall-following guidance. That's an honest limitation we've documented rather than hidden.

**Q: Why use YOLO if it's slow on a Raspberry Pi?**
A: We don't run it continuously. The cheap depth check runs every cycle; YOLO only runs on the rare cycles where an obstacle is already confirmed close, so the inference cost is paid only when it matters.

**Q: Could you train YOLO to recognize doors directly?**
A: Yes, that's in our future work. It would require collecting and labeling a custom dataset of door images, which wasn't feasible in our timeline. ORB landmarks solve the same problem today with a two-minute capture and zero labeling.

**Q: Is this safe for real-world use today?**
A: Not yet without further field testing on the actual hardware, which we no longer have access to. Our wall-following logic and the ORB robustness numbers were derived from a desktop validation, not a deployed field test. We're transparent about that gap in both the report and here.
