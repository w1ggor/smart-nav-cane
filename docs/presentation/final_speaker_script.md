Speaker Script — Final Presentation

Smart Cane Environmental Awareness System
Target: ~7–8 minutes presentation, leaving time for Q&A

⸻

Pronunciation Guide

* ORB — say it like orb
* YOLO — like the slang word
* Vosk — rhymes with cost
* COCO — like cocoa
* SLAM — like the word slam
* mAP — say mean Average Precision
* CNN — “C-N-N”
* IMU — “I-M-U”
* ToF camera — you can simply say depth camera

⸻

Slide 1 — Title

Hello everyone. We are Igor Xavier and Fang Jialuo, and today we’ll present our project, the Smart Cane Environmental Awareness System, an AI-powered navigation assistant for visually impaired people using a Raspberry Pi.

⸻

Slide 2 — Outline

We’ll briefly introduce the problem, explain our solution, present the AI technologies we used, show our results, and finish with future work.

⸻

Slide 3 — Motivation & Problem

Indoor navigation remains a significant challenge for visually impaired people.

Existing solutions typically fall into one of two categories. High-end systems provide accurate navigation but require expensive sensors and considerable computing power. Simpler electronic canes are affordable but can only detect nearby obstacles without identifying them or providing navigation guidance.

Our goal was to build a fully offline system that provides environmental awareness and navigation using affordable hardware.

⸻

Slide 4 — Project Idea

Our system answers three simple questions:

* What’s in front of me?
* Where am I?
* How do I reach my destination?

The user simply speaks a destination, receives obstacle warnings during navigation, and is informed when the destination has been reached.

⸻

Slide 5 — Scope Decision

Our original objective included full 3D mapping and automatic path planning.

After evaluating the hardware requirements, we deliberately reduced the scope and focused on two reliable features: environmental awareness and guided navigation.

The complete mapping system remains future work.

⸻

Slide 6 — System Architecture

The depth camera continuously detects nearby obstacles.

Only when an obstacle is detected do we execute the YOLO object detection model.

At the same time, the RGB camera performs room recognition using ORB, while Vosk processes offline voice commands.

All feedback is delivered to the user through Bluetooth headphones.

⸻

Slide 7 — Awareness Mode

Awareness mode continuously monitors the environment.

Whenever an obstacle is detected, the system immediately prepares a warning.

If YOLO successfully identifies the object, the warning becomes more informative—for example, “Chair ahead, 0.8 meters.”

⸻

Slide 8 — Guided Navigation

During navigation, the center region is continuously monitored for obstacles.

The left and right directions are determined by the planned route toward the selected destination.

Before giving navigation instructions, the depth camera verifies that the intended direction is safe.

Room recognition is also used to determine when the destination has been reached.

⸻

Slide 9 — Limitations

Because the system does not maintain a complete map, navigation decisions combine the planned route with real-time obstacle avoidance.

Obstacle detection continues working even if room recognition fails because of different lighting conditions or viewpoints.

To better understand these limitations, we evaluated the robustness of our recognition algorithm.

⸻

Slide 10 — Hardware

This is our assembled prototype.

It consists of a Raspberry Pi, a depth camera, an RGB webcam, and Bluetooth headphones.

⸻

Slide 11 — Hardware Components

The Raspberry Pi performs all computation.

The depth camera measures obstacle distance.

The RGB webcam performs room and object recognition.

Bluetooth headphones provide both voice input and spoken navigation feedback.

The complete hardware costs approximately 80 euros.

⸻

Slide 12 — Software Architecture

Our software is organized into eight independent modules.

Separate modules manage object recognition and speech recognition, making the system easier to maintain and extend.

We also implemented 33 automated software tests covering the core system logic.

⸻

Slide 13 — AI Components

Our system combines three complementary recognition techniques.

ORB performs room recognition without requiring labeled datasets.

YOLO identifies obstacles using deep learning.

Vosk provides fully offline speech recognition.

To improve performance, YOLO only runs after the depth camera detects a nearby obstacle.

⸻

Slide 14 — Dataset Sources & Validation

Each recognition component uses a different source of data.

ORB uses reference images captured during the environment setup process.

YOLO is pretrained on the COCO dataset.

Vosk is pretrained on public speech datasets.

Beyond the published model metrics, we validated our own recognition pipeline through automated testing and a real robustness experiment on the production code.

⸻

Slide 15 — ORB Robustness Test

We evaluated our room-recognition algorithm by testing rotated, blurred, and darker images.

Rotation had very little impact on recognition.

Motion blur and poor lighting reduced performance because fewer visual features remained detectable.

These experiments helped us understand the strengths and limitations of the system under realistic conditions.

⸻

Slide 16 — Gated Object Detection

This function executes object recognition only after three checks.

The model must be available, an object must be detected, and the confidence score must exceed our threshold.

Only then is the detected object announced to the user.

⸻

Slide 17 — Navigation Logic

This function decides whether to continue straight, turn left, turn right, or stop based on obstacle information and the planned route toward the destination.

Its simplicity makes the navigation logic reliable and easy to validate.

⸻

Slide 18 — Results

All major system components were successfully implemented and validated.

Environmental awareness, guided navigation, room recognition, obstacle detection, and offline voice commands all worked successfully during testing.

In addition, all 33 automated software tests passed successfully.

⸻

Slide 19 — Contributions

Our main contributions are:

* A fully offline navigation assistant running entirely on a Raspberry Pi.
* A hybrid architecture combining classical computer vision with deep learning.
* A complete validation process supported by automated software testing.

⸻

Slide 20 — Challenges

We faced three major challenges during development.

First, full 3D mapping exceeded the capabilities of our hardware, so we reduced the project scope.

Second, collecting representative reference images proved essential for reliable room recognition.

Finally, continuously running YOLO created unnecessary computational overhead, so we activated it only after obstacle detection.

⸻

Slide 21 — Future Work

Future improvements include:

* Full 3D indoor mapping.
* Automatic path planning.
* Motion tracking for localization.
* A custom object detection model for accessibility-specific objects such as doors and stairs.
* Support for multiple trained environments.

⸻

Slide 22 — Thank You

Thank you for your attention.

We’d be happy to answer any questions.

⸻

Anticipated Q&A

Q: Why didn’t you build the full mapping system?

A: Full mapping requires continuous localization using additional sensors such as an IMU. Without those sensors, the resulting map would not be reliable. We chose to reduce the scope and deliver a solution that performs reliably with the available hardware.

⸻

Q: How accurate is your system?

A: The system combines three different recognition components, so there isn’t a single overall accuracy number.

For YOLO and Vosk, we report the official metrics published for those pretrained models.

For our room-recognition algorithm, we performed robustness testing under different rotations, lighting conditions, and motion blur, showing strong tolerance to viewpoint changes while identifying lighting and image quality as the primary factors affecting performance.

Finally, every core decision-making module is covered by automated tests, and our recognition pipeline was validated through a real robustness experiment.

⸻

Q: Where does your training data come from?

A: Room recognition uses reference images captured during the initial environment setup.

YOLO is used as a pretrained model trained on the COCO dataset.

Vosk is also used as a pretrained model trained on public speech datasets.

⸻

Q: What happens if the user leaves the trained route?

A: Obstacle detection continues working because it depends only on the current camera image.

Room recognition may become less reliable if lighting or viewpoints differ significantly from the reference images.

Even in those situations, the user continues receiving obstacle warnings while navigation decisions are based on the current surroundings.

⸻

Q: Why not run YOLO continuously?

A: Running deep learning continuously on a Raspberry Pi would reduce responsiveness and consume unnecessary computational resources.

Instead, the depth camera acts as a lightweight filter, activating YOLO only when a nearby obstacle is detected.

⸻

Q: Could you train your own object detection model?

A: Yes. That’s part of our future work. A custom model would allow us to recognize accessibility-specific objects such as doors, stairs, elevators, and other indoor landmarks that are not included in standard pretrained datasets.

⸻

Q: Is this ready for real-world use?

A: The prototype demonstrates that the proposed approach is technically feasible and that all core components work together successfully.

Before deployment as an assistive device, it would require larger-scale testing with visually impaired users, additional safety validation, and more robust localization.
