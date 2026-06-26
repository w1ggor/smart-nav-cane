# Speaker Script — Final Presentation
**Smart Cane Environmental Awareness System · Max 10 minutes including Q&A**
**Target: ~7.5 minutes talk, leaving ~2.5 minutes for Q&A**

This script is written to be read almost word-for-word. Practice it out loud at least twice before presenting — it'll sound much more natural the second time.

## Pronunciation guide (the tricky words)
- **ORB** — say it like the word "orb" (a glowing orb)
- **YOLO** — like the slang word "yolo"
- **Vosk** — rhymes with "cost" → "VOSK"
- **COCO** — like "coco" in cocoa
- **SLAM** — like the word "slam"
- **mAP** — easiest to just say "mean average precision" instead of spelling it out
- **CNN** — say the letters: "C-N-N"
- **IMU** — say the letters: "I-M-U"
- Whenever you see "ToF camera," it's fine to just say "depth camera" instead — same thing, easier to say

---

## Slide 1 — Title

Good morning. We are Igor Xavier and Fang Jialuo, and this is our final presentation for the AI Smart Navigation Assistant for Visually Impaired People Using Raspberry Pi. We call it the Smart Cane Environmental Awareness System.

---

## Slide 2 — Outline

Here's what we'll cover: the problem we're solving, how our project idea evolved, the system architecture, the hardware and software, the AI components and how accurate they are, our results, the challenges we ran into, and what's next.

---

## Slide 3 — Motivation & Problem

Visually impaired people face real challenges getting around indoor spaces on their own. Most existing solutions are at one of two extremes. Full mapping systems are accurate but need expensive sensors and a lot of computing power. Simple ultrasonic canes are cheap, but they only beep when something is close — they can't tell you what it is or where you are. We wanted something in between: useful awareness of your surroundings, fully offline, on one low-cost Raspberry Pi.

---

## Slide 4 — Project Idea

Our cane answers three simple questions. What's in front of me? Where am I? And how do I get to where I'm going? In practice, here's what that looks like: you say "kitchen," the cane warns you "chair ahead, 0.8 metres," tells you when to turn, and finally says "you have arrived."

---

## Slide 5 — Scope Decision

Our original plan was much bigger — building a full 3D map of the space in real time and planning routes automatically, similar to how a robot vacuum works. We stepped back from that on purpose. It needs a motion sensor we don't have, a lot more computing power, and careful setup we couldn't guarantee in the time we had. So instead we built two simpler things that actually work: a passive awareness mode, and a guided navigation mode. The full mapping idea is still in our plan — just listed as future work instead of something we forced to work badly now.

---

## Slide 6 — System Architecture

Here's the big picture. The depth camera feeds an obstacle checker that runs constantly — that part is cheap and fast. Only when it actually finds something close do we run our AI model to figure out what that something is. At the same time, the regular camera looks for rooms and landmarks it recognizes. And when navigation starts, the microphone listens for your destination using an offline speech recognizer. Everything comes back together as spoken audio through the Bluetooth headphones.

---

## Slide 7 — Awareness Mode

This is our simplest mode — it just watches and reports, no destination needed. When it spots something close, it first has a generic warning ready. But if our AI classifier can identify the object, it says something more specific instead — like "chair ahead, 0.8 metres" instead of just "obstacle ahead."

---

## Slide 8 — Guided Navigation Mode

This is the more advanced mode. Since we don't have a motion sensor, we can't plan a path to an exact location the way a robot with GPS would. Instead, we look at the depth camera split into three zones — left, center, and right — every cycle. If the middle is clear, we say "go straight." If it's blocked, we turn toward whichever side has more open space. On top of that, we check if you've arrived at your destination, and we announce landmarks like doors when we recognize them. This works well as long as you're walking a route the system has seen before.

---

## Slide 9 — What If the User Deviates?

It's worth being upfront about a limitation here. Because we have no map and no motion tracking, the system doesn't know if you're "on" or "off" the route — it only reacts to what it sees right now. The good news: obstacle warnings keep working no matter what, since that part doesn't depend on the route at all. The part that can struggle is recognizing your destination or a landmark — if you're looking at it from a different angle or in different lighting than when it was trained, it might not recognize it. And right now, there's no "you seem lost, let me help" feature — it'll just keep giving directions based on what's in front of you. We actually tested how much this matters, which is coming up in a couple of slides.

---

## Slide 10 — Hardware Photo

This is our assembled prototype — the Raspberry Pi, the depth camera, and the regular webcam, all mounted on the cane.

---

## Slide 11 — Hardware Components

Four parts: the Raspberry Pi 4 does all the computing, the depth camera measures distance up to 4 metres, the webcam handles recognition and object identification, and Bluetooth headphones handle audio both ways — listening and speaking. Total cost for all the hardware is about 80 euros.

---

## Slide 12 — Software Architecture

Our code is split into eight clear pieces. Two of them are worth calling out specifically: one wraps our object-recognition AI model, and another wraps our speech-recognition AI model. We also wrote 27 automated tests to make sure things keep working as we changed the code.

---

## Slide 13 — AI / Deep Learning Components

This is the core of our technical work. We use three different recognition techniques, and we picked each one for a specific reason, not just by default. The first, called ORB, is a classic, non-AI computer vision technique — we use it to recognize rooms and landmarks because it only needs a two-minute setup and no labeled training data. The second is YOLO, a real trained AI model, which we use to identify obstacles. The third is Vosk, a speech-recognition AI, which we use for fully offline voice commands.

Two quick notes on why we built it this way. We only run the YOLO model when there's already something close by — running it constantly would be too slow for this hardware. And we still use the simpler ORB method for doors instead of YOLO, because YOLO's training data doesn't actually include "door" as a category.

---

## Slide 14 — Dataset Sources & Accuracy

It's important to be clear about where our AI actually comes from, because the three pieces are quite different. ORB doesn't use any outside data at all — everything comes from a quick two-minute walk-around capture in your own home. YOLO is pretrained on a public dataset called COCO, with about 330,000 images across 80 object categories, and its official published accuracy score is 37.3. Vosk's speech model is trained on public speech recordings, with an official published error rate of about 9.85 percent.

One honest note: the Raspberry Pi we built this on isn't available to us anymore, so we couldn't re-measure accuracy on the actual device. For the two AI models, we're reporting their official published numbers rather than guessing. For our own piece — the room recognition — we did something better than guessing: we ran a real test, which is the next slide.

---

## Slide 15 — ORB Robustness — Real Test Results

We took our actual recognition code, exactly as it runs in the real system, and tested it against a photo that we deliberately rotated, blurred, and brightened or darkened — to simulate things like looking from a different angle, moving while walking, or different lighting. Rotating the photo never broke recognition at all. But blurring it — like motion blur while walking — caused it to fail once the blur got strong enough. And making the photo darker caused it to fail even sooner.

One honest caveat: rotating a flat photo isn't quite the same as actually walking around and viewing something from a new angle in 3D, so real-world angle changes are probably harder on the system than this test shows. But the blur and lighting results are realistic, and they tell us motion and lighting are bigger risks than camera angle.

---

## Slide 16 — Code: Gated DL Inference

Here's the actual function that runs our object recognition. It checks three things before giving an answer: is the AI model even available, did it find anything at all, and is it confident enough. Only if all three pass does it tell us what it sees.

---

## Slide 17 — Code: Wall-Following Decision

And here's the navigation logic. It's a simple function: given how much open space is on the left, center, and right, it decides one of four things — go straight, turn left, turn right, or stop because it's blocked. Because it's simple logic, we could test it thoroughly without needing the actual hardware running.

---

## Slide 18 — Results & Status

Where we stand: the sensors, the room-training tool, and the basic awareness mode are all complete and were tested on the real hardware. Guided navigation and the object-recognition feature are built and pass all our automated tests — 27 out of 27.

---

## Slide 19 — Contributions

To sum up what we built: a fully offline assistive device that runs two AI models and a classic computer vision technique together on one small computer; a deliberate design where each technique is used where it's strongest, instead of picking one and forcing it everywhere; clear documentation of exactly where our data and accuracy numbers come from; and 27 automated tests.

---

## Slide 20 — Challenges & Solutions

Four things shaped this project the most. First, the original full-mapping idea simply wasn't realistic with the hardware and time we had, so we treated that as a planning decision and built something achievable instead, keeping the bigger idea as future work. Second, how we collected training data mattered a lot — a single photo per room didn't work well, a quick burst of five photos barely helped, and we landed on a full two-minute walk-around capture that actually works reliably. Third — and this happened just this week — building a demo without the Raspberry Pi, we found a real bug: our backup voice software would freeze on Windows computers under certain conditions, caused by how Windows handles background tasks. We fixed it. Fourth, we learned the hard way that running a full AI model every single moment was too slow, so we only run it when it's actually needed.

---

## Slide 21 — Future Work

Looking ahead: building the full 3D map we originally wanted, automatic route planning between rooms, adding a motion sensor to track movement directly, training our own custom AI model on things like doors and stairs specifically, and supporting more than one trained environment at a time.

---

## Slide 22 — Thank You

That's our project. All the code is publicly available on GitHub. Thank you — happy to answer any questions.

---

## Anticipated Q&A — Prepare These Answers

**Q: Why didn't you build the full mapping system you originally planned?**
A: That kind of system needs a motion sensor to track movement between frames, which we don't have. Trying to build it anyway would have given us an unreliable map — worse than not having one at all. We made a clear decision to build something smaller that actually works well, instead of something bigger that barely works.

**Q: How accurate is your system?**
A: We're careful to only state what we actually know. The two AI models we use have official published accuracy numbers from their creators, which we report directly rather than making up our own. For our own room-recognition piece, we ran a real test using the actual code, and it holds up well to camera angle changes, but is more sensitive to blur and lighting. We don't have one single accuracy number for the whole system end-to-end, because we no longer have the Raspberry Pi to test it on — and we'd rather say that honestly than invent a number.

**Q: Where does your training data come from?**
A: Three different places, on purpose. Our room-recognition piece uses no outside data at all — it's entirely built from a two-minute walk-around video the user records themselves. Our object-recognition AI is pretrained on a public dataset called COCO, used exactly as released, no changes. Our speech-recognition AI is pretrained on public speech recordings, also used exactly as released.

**Q: What happens if the user goes off the trained route, or something changes?**
A: Obstacle warnings keep working no matter what, since they just react to whatever's right in front of you. But recognizing a room or a landmark can fail if the lighting or your exact position is different enough from when it was trained — our testing showed lighting and motion blur matter more than camera angle. If that happens, the system doesn't know it's confused — it doesn't say "I'm lost." It just keeps giving directions based on what it currently sees. That's a real limitation, and we've written it down rather than hidden it.

**Q: Why not just run the AI model all the time instead of only when needed?**
A: It would be too slow. Our Raspberry Pi has no graphics card, so running a full AI model constantly would slow everything down. By only running it when the depth camera already noticed something close, we get the benefit of the AI model without paying that cost every single moment.

**Q: Could you train your AI model to recognize doors directly?**
A: Yes, and that's on our future work list. It would mean collecting and labeling our own photos of doors, which we didn't have time for. For now, our simpler room-recognition technique handles that instead, with just a two-minute capture and no labeling needed.

**Q: Is this ready for someone to actually use today?**
A: Not yet — it needs more real-world testing, and we no longer have the hardware to do that testing ourselves. Our navigation logic and our accuracy numbers come from controlled tests, not from a finished, deployed device. We're upfront about that gap in our report.
