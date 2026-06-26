# Speaker Script — Final Presentation
**Smart Cane Environmental Awareness System · Max 10 minutes including Q&A**
**Target: ~7 minutes talk, leaving ~3 minutes for Q&A**

This script is written to be read almost word-for-word. Practice it out loud at least twice — it'll sound much more natural the second time.

## Pronunciation guide (the tricky words)
- **ORB** — say it like the word "orb"
- **YOLO** — like the slang word "yolo"
- **Vosk** — rhymes with "cost" → "VOSK"
- **COCO** — like "coco" in cocoa
- **SLAM** — like the word "slam"
- **mAP** — easiest to just say "mean average precision"
- **CNN** — say the letters: "C-N-N"
- **IMU** — say the letters: "I-M-U"
- Whenever you see "ToF camera," it's fine to just say "depth camera" instead

---

## Slide 1 — Title

Hello everyone. We are Igor Xavier and Fang Jialuo, presenting the AI Smart Navigation Assistant for Visually Impaired People Using Raspberry Pi — the Smart Cane Environmental Awareness System.

---

## Slide 2 — Outline

Five things: the problem, our solution, the AI technologies behind it, our results, and what's next.

---

## Slide 3 — Motivation & Problem

Visually impaired people face real challenges getting around indoor spaces independently. Existing solutions typically fall into two categories. Full mapping systems are accurate but need expensive sensors and heavy computing power. Simple ultrasonic canes are cheap, but only beep when something is close — no information about what it is or where you are. We built something in between: useful awareness of your surroundings, fully offline, on one low-cost Raspberry Pi.

---

## Slide 4 — Project Idea

Our cane answers three questions: what's in front of me, where am I, and how do I reach my destination. In practice: you say "kitchen," the cane warns you "chair ahead, 0.8 metres," tells you when to turn, and confirms when you've arrived.

---

## Slide 5 — Scope Decision

Our original plan was a full 3D map built in real time, with automatic route planning — similar to a robot vacuum. We deliberately reduced that scope. It needs a motion sensor we don't have, and far more compute than the time we had allowed for. So we built two things that work reliably today — awareness mode and guided navigation — and kept the full mapping vision as future work.

---

## Slide 6 — System Architecture

The depth camera feeds an obstacle checker every cycle. Only when it finds something close do we run our object-recognition AI to identify it. The regular camera recognizes rooms and landmarks. At the start of navigation, we plan a route over previously connected locations, then follow it step by step. The microphone listens for your destination using an offline speech recognizer. Everything comes together as spoken audio over Bluetooth.

---

## Slide 7 — Awareness Mode

Our simplest mode — watches and reports, no destination needed. When something's close, it has a generic warning ready, but if our AI classifier can identify the object, it says something specific instead — "chair ahead, 0.8 metres" rather than just "obstacle ahead."

---

## Slide 8 — Guided Navigation Mode

This is the more advanced mode. At the start, we figure out where the user currently is, and plan a route using connections between locations we trained earlier — similar to looking up directions between two rooms. Then, every cycle, the system follows that plan one step at a time: if the next step says "go forward," it only actually says "go straight" once the depth camera confirms the way is clear right now. If the plan says turn, it tells you to turn. And if there's no trained route at all, it falls back to scanning left, center, and right and choosing whichever side has the most open space — so navigation never simply fails, even without a trained connection. Throughout, it also checks if you've arrived and announces landmarks like doors along the way.

---

## Slide 9 — Limitations

A few honest limitations. Routes only exist between locations we've explicitly connected during training — there's no continuous map of the whole space. Without a trained connection, navigation falls back to the reactive obstacle-avoidance I just described. Obstacle detection itself always works, no matter where you are. And recognizing a room or landmark can fail if the lighting or your exact position is very different from when it was trained.

---

## Slide 10 — Hardware Photo

Our assembled prototype — Raspberry Pi, depth camera, and webcam, mounted on the cane.

---

## Slide 11 — Hardware Components

Four parts: the Raspberry Pi 4 for computing, the depth camera for distance up to 4 metres, the webcam for recognition and object identification, and Bluetooth headphones for audio both ways. Total hardware cost: about 80 euros.

---

## Slide 12 — Software Architecture

Our code is split into eight clear modules. Two are worth calling out: one wraps our object-recognition AI, another wraps our speech-recognition AI. We back this with 33 automated tests.

---

## Slide 13 — AI / Deep Learning Components

The core of our technical work: three recognition techniques, each chosen for a specific reason. ORB is a classic, non-AI computer vision technique, used for recognizing rooms and landmarks from reference images captured during setup — no labeled training data needed. YOLO is a real trained AI model, used to identify obstacles. Vosk is a speech-recognition AI, used for fully offline voice commands.

Two notes on why we built it this way: we only run YOLO when something's already close — running it constantly would be too slow for this hardware. And we still use ORB for doors instead of YOLO, because YOLO's training data doesn't include "door" as a category.

---

## Slide 14 — Dataset Sources & Accuracy

It's worth being clear about where our AI actually comes from — the three pieces are quite different. ORB uses no outside data at all; everything comes from reference images captured in the user's own space. YOLO is pretrained on a public dataset called COCO — about 330,000 images across 80 categories — with a published accuracy score of 37.3. Vosk's speech model is trained on public speech recordings, with a published error rate of about 9.85 percent.

Beyond those published numbers, we validated our own recognition pipeline directly: automated tests for every decision-making module, plus a hands-on robustness experiment on the exact code that runs in production — which is the next slide.

---

## Slide 15 — ORB Robustness — Real Test Results

We took our actual recognition code and tested it against a photo we deliberately rotated, blurred, and changed the brightness of — simulating different angles, motion while walking, and different lighting. Rotation had almost no effect. Blur hurt recognition once it got strong enough. And poor lighting hurt it even more. The takeaway: lighting and motion matter more than camera angle for reliable recognition.

---

## Slide 16 — Code: Gated DL Inference

Here's the actual function behind object recognition. It checks three things before answering: is the model available, did it find anything, and is it confident enough. Only then does it return what it sees.

---

## Slide 17 — Code: Planned Route With a Safety Check

And here's the navigation logic. Given the current route step's direction — forward, turn left, or turn right — it acts on it, but a "forward" step is only confirmed if the depth sensor agrees the way is actually clear. If there's no route loaded, it falls back to the same reactive logic from the previous mode. This function drives every movement decision in real time.

---

## Slide 18 — Results & Status

Where we stand: sensors, location training, and awareness mode are complete and tested on real hardware. Guided navigation — including route planning and the object-recognition feature — is implemented and tested: 33 out of 33 automated tests passing.

---

## Slide 19 — Contributions

Three things we're proud of: a fully offline assistive device running two AI models and a classical computer vision technique together on one small computer; a deliberate hybrid architecture — ORB, YOLO, Vosk, and Dijkstra route planning — each used where it performs best, with the depth sensor as a constant safety check; and all of it validated through 33 automated tests plus a real robustness experiment on the production code.

---

## Slide 20 — Challenges & Solutions

Three things shaped this project most. First, the original full-mapping idea wasn't realistic with our hardware and time, so we treated that as a planning decision and built something achievable, keeping the bigger idea as future work. Second, how we collected reference images mattered a lot — we had to learn the right way to capture enough visual diversity for reliable recognition. Third, running a full AI model every single moment was too slow, so we only run it when it's actually needed.

---

## Slide 21 — Future Work

Looking ahead: a continuous 3D map instead of discrete trained connections, a motion sensor for direct movement tracking, a custom AI model trained specifically on doors and stairs, and support for more than one environment at a time.

---

## Slide 22 — Thank You

That's our project. All the code is publicly available on GitHub. Thank you — happy to answer questions.

---

## Anticipated Q&A — Prepare These Answers

**Q: Why didn't you build the full mapping system you originally planned?**
A: That needs a motion sensor to track movement between frames, which we don't have. Building it anyway would have given us an unreliable map — worse than not having one. We made a clear decision to build something smaller that works well, instead of something bigger that barely works.

**Q: How accurate is your system?**
A: We don't report a single accuracy number for the whole system, because that would have to come from extended real-world testing we haven't completed yet. What we can say confidently: the two AI models we use have official published accuracy figures from their creators, which we report directly. For our own recognition pipeline, we ran a real robustness test using the actual production code, and every decision-making module is covered by automated tests — 33 out of 33 passing. That's real validation of every piece; the next step is testing the complete system in more real-world conditions.

**Q: Where does your training data come from?**
A: Three different places, by design. Our room-recognition piece uses no outside data — it's built entirely from reference images the user captures in their own space during setup. Our object-recognition AI is pretrained on COCO, a public dataset, used exactly as released. Our speech-recognition AI is pretrained on public speech recordings, also used exactly as released.

**Q: How does navigation actually decide where to go?**
A: At the start, we recognize the user's current location and look up a planned route — a sequence of trained connections between locations, found using a shortest-path algorithm. Each step in that plan says "go forward," "turn left," or "turn right." We only follow a "forward" step if the depth camera confirms it's actually clear right now — so the plan never overrides what the sensor sees. If no trained connection exists, we fall back to scanning left, center, and right and choosing the clearer side.

**Q: What happens if the user goes somewhere without a trained connection?**
A: Obstacle avoidance keeps working regardless, since it reacts to whatever's in front of you. Without a planned route, navigation falls back to that same reactive logic — picking the clearer direction — so it still moves you safely, just without a specific plan toward the destination.

**Q: Why not just run the AI model all the time instead of only when needed?**
A: It would be too slow — our Raspberry Pi has no graphics card. By only running it when the depth camera already noticed something close, we get the benefit of the AI model without paying that cost every moment.

**Q: Could you train your AI model to recognize doors directly?**
A: Yes, that's on our future work list. It would mean collecting and labeling our own door photos, which we didn't have time for. For now, our ORB-based technique handles that instead, with no labeling needed.

**Q: Is this ready for someone to actually use today?**
A: Not yet. We've validated every component thoroughly — automated tests and real robustness experiments — but the natural next step is testing with actual visually impaired users in real environments, to validate practical day-to-day usability beyond what controlled tests can show.
