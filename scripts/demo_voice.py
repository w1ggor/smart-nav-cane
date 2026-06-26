#!/usr/bin/env python3
"""
Demo voice simulator — no Raspberry Pi or sensors required.

Speaks the exact phrases the real system produces, using the same
AudioGuidance backend (espeak-ng / pyttsx3) as awareness.py and
navigate_voice.py. Intended for recording a demo video by triggering
phrases on cue while acting out the cane's movement on camera.

This does NOT run any sensors, recognition, or navigation logic — it
only reproduces the wording so the audio in a demo recording is
authentic to what the real system would say.

Usage:
    python scripts/demo_voice.py                  # interactive menu
    python scripts/demo_voice.py --sequence        # full scripted demo, auto-paced
    python scripts/demo_voice.py --say arrived --destination kitchen
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml

from nav_assistant.audio.guidance import AudioGuidance

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "default.yaml"


def load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _norm(label: str) -> str:
    return label.replace("_", " ")


# ----------------------------------------------------------------------
# Exact phrase builders — mirrors the wording used in the real codebase:
#   src/nav_assistant/awareness.py
#   src/nav_assistant/obstacle/detector.py        (alert_message)
#   src/nav_assistant/navigation/guided_navigator.py
#   scripts/navigate_voice.py
# ----------------------------------------------------------------------

class Phrases:
    # --- System lifecycle (awareness.py) ---
    @staticmethod
    def awareness_started() -> str:
        return "Awareness system started."

    @staticmethod
    def awareness_stopped() -> str:
        return "Awareness system stopped."

    # --- Location announcements (awareness.py) ---
    @staticmethod
    def location_new(label: str) -> str:
        return f"You are in the {_norm(label)}."

    @staticmethod
    def location_still(label: str) -> str:
        return f"You are still in the {_norm(label)}."

    # --- Obstacle alerts (obstacle/detector.py: alert_message) ---
    @staticmethod
    def obstacle_very_close() -> str:
        return "Warning! Obstacle very close."

    @staticmethod
    def obstacle_distance(distance_m: float) -> str:
        return f"Obstacle ahead, {distance_m:.1f} metres."

    @staticmethod
    def obstacle_generic() -> str:
        return "Obstacle detected ahead."

    # --- YOLO-classified obstacle (awareness.py / navigate_voice.py) ---
    @staticmethod
    def obstacle_classified(label: str, distance_m: float) -> str:
        return f"{label.capitalize()} ahead, {distance_m:.1f} metres."

    # --- Voice destination flow (navigate_voice.py) ---
    @staticmethod
    def ask_destination() -> str:
        return "Where do you want to go?"

    @staticmethod
    def destination_not_understood() -> str:
        return "Sorry, I did not understand. Please try again."

    @staticmethod
    def destination_unknown(label: str) -> str:
        return f"{label} is not a known location."

    @staticmethod
    def navigating_to(label: str) -> str:
        return f"Navigating to the {_norm(label)}."

    # --- Wall-following guidance (navigation/guided_navigator.py) ---
    @staticmethod
    def go_straight() -> str:
        return "Go straight."

    @staticmethod
    def turn_left() -> str:
        return "Turn left."

    @staticmethod
    def turn_right() -> str:
        return "Turn right."

    @staticmethod
    def path_blocked() -> str:
        return "Path blocked. Please stop."

    @staticmethod
    def landmark_ahead(label: str) -> str:
        return f"{_norm(label).title()} ahead."

    @staticmethod
    def landmark_ahead_with_guidance(label: str, guidance: str) -> str:
        return f"{Phrases.landmark_ahead(label)} {guidance}"

    @staticmethod
    def arrived(label: str) -> str:
        return f"You have arrived at the {_norm(label)}."


# ----------------------------------------------------------------------
# Unified speak/alert helpers — every code path (menu, --say, --sequence)
# goes through these so console output and TTS stay consistent.
# ----------------------------------------------------------------------

def _say(audio: AudioGuidance, text: str) -> None:
    print(f'  -> "{text}"')
    audio.speak(text)


def _say_alert(audio: AudioGuidance, text: str) -> None:
    print(f'  !! "{text}"')
    audio.alert(text)


# ----------------------------------------------------------------------
# Phrase catalogue: key -> (is_alert, text_builder(state))
# Single source of truth, reused by the interactive menu, --say, and
# --sequence so every entry point can say exactly the same set of things.
# ----------------------------------------------------------------------

def _catalogue(state: dict) -> dict:
    return {
        "started": (False, Phrases.awareness_started()),
        "stopped": (False, Phrases.awareness_stopped()),
        "location": (False, Phrases.location_new(state["label"])),
        "location-still": (False, Phrases.location_still(state["label"])),
        "obstacle-close": (True, Phrases.obstacle_very_close()),
        "obstacle-distance": (True, Phrases.obstacle_distance(state["distance"])),
        "obstacle-generic": (True, Phrases.obstacle_generic()),
        "obstacle-classified": (True, Phrases.obstacle_classified(state["object"], state["distance"])),
        "ask": (False, Phrases.ask_destination()),
        "not-understood": (False, Phrases.destination_not_understood()),
        "unknown": (False, Phrases.destination_unknown(state["label"])),
        "navigating": (False, Phrases.navigating_to(state["label"])),
        "straight": (False, Phrases.go_straight()),
        "left": (False, Phrases.turn_left()),
        "right": (False, Phrases.turn_right()),
        "blocked": (False, Phrases.path_blocked()),
        "landmark": (False, Phrases.landmark_ahead(state["landmark"])),
        "landmark-guidance": (False, Phrases.landmark_ahead_with_guidance(state["landmark"], Phrases.go_straight())),
        "arrived": (False, Phrases.arrived(state["label"])),
    }


_MENU_LABELS = {
    "started": "Awareness started",
    "stopped": "Awareness stopped",
    "location": "Location: you are in '{label}'",
    "location-still": "Location: still in '{label}'",
    "obstacle-close": "Obstacle: very close (<0.5m)",
    "obstacle-distance": "Obstacle: distance ({distance:.1f}m)",
    "obstacle-generic": "Obstacle: generic",
    "obstacle-classified": "Obstacle classified: '{object}' at {distance:.1f}m",
    "ask": "Ask destination",
    "not-understood": "Destination not understood",
    "unknown": "Destination unknown ('{label}')",
    "navigating": "Navigating to '{label}'",
    "straight": "Go straight",
    "left": "Turn left",
    "right": "Turn right",
    "blocked": "Path blocked",
    "landmark": "Landmark ahead: '{landmark}'",
    "landmark-guidance": "Landmark + guidance: '{landmark}' + go straight",
    "arrived": "Arrived at '{label}'",
}

# Stable display order for the interactive menu (dict preserves insertion order)
_MENU_ORDER = list(_MENU_LABELS.keys())


def speak_entry(audio: AudioGuidance, state: dict, key: str) -> None:
    """Speak/alert one catalogue entry by key, printing what was said."""
    is_alert, text = _catalogue(state)[key]
    if is_alert:
        _say_alert(audio, text)
    else:
        _say(audio, text)


def print_menu() -> None:
    print("\n=== Smart Cane Demo Voice Simulator ===")
    print("(no sensors, no Raspberry Pi required — real TTS backend)\n")
    for i, key in enumerate(_MENU_ORDER, 1):
        print(f"  [{i:>2d}] {key}")
    print(f"  [{'c':>2s}] Change destination / object / landmark / distance values")
    print(f"  [{'s':>2s}] Run full scripted demo sequence")
    print(f"  [{'q':>2s}] Quit")


def run_interactive(audio: AudioGuidance) -> None:
    state = {"label": "kitchen", "object": "chair", "landmark": "door", "distance": 0.8}

    while True:
        print_menu()
        choice = input("\n> ").strip().lower()

        if choice == "q":
            break
        elif choice == "c":
            state["label"] = input(f"  Destination/location label [{state['label']}]: ").strip() or state["label"]
            state["object"] = input(f"  Classified object label [{state['object']}]: ").strip() or state["object"]
            state["landmark"] = input(f"  Landmark label [{state['landmark']}]: ").strip() or state["landmark"]
            dist_raw = input(f"  Obstacle distance in metres [{state['distance']}]: ").strip()
            if dist_raw:
                try:
                    state["distance"] = float(dist_raw)
                except ValueError:
                    print("  Invalid number, keeping previous value.")
        elif choice == "s":
            run_scripted_sequence(audio, state)
        elif choice.isdigit() and 1 <= int(choice) <= len(_MENU_ORDER):
            key = _MENU_ORDER[int(choice) - 1]
            speak_entry(audio, state, key)
            audio.wait_until_done(timeout=10.0)
        else:
            print("  Unknown option.")


def run_scripted_sequence(audio: AudioGuidance, state: dict, pause_s: float = 2.5) -> None:
    """
    Plays a full guided-navigation demo end to end, automatically paced.
    Mirrors the real navigate_voice.py flow: ask -> navigate -> guidance ->
    obstacle -> landmark -> arrival.
    """
    sequence_keys = [
        "started",
        "ask",
        "navigating",
        "straight",
        "obstacle-classified",
        "left",
        "landmark-guidance",
        "right",
        "straight",
        "arrived",
    ]

    print(f"\n--- Running scripted demo sequence ({len(sequence_keys)} steps, ~{pause_s}s gap) ---")
    print("Press Ctrl+C to stop early.\n")
    try:
        for i, key in enumerate(sequence_keys, 1):
            print(f"[{i}/{len(sequence_keys)}] {key}")
            speak_entry(audio, state, key)
            audio.wait_until_done(timeout=10.0)  # avoid overlapping/cut-off speech
            time.sleep(pause_s)
    except KeyboardInterrupt:
        print("\nSequence stopped early.")
    print("\n--- Sequence complete ---\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo voice simulator (no hardware required)")
    parser.add_argument("--say", choices=_MENU_ORDER, default=None,
                        help="Speak one phrase immediately and exit")
    parser.add_argument("--sequence", action="store_true",
                        help="Run the full scripted demo sequence and exit")
    parser.add_argument("--destination", default="kitchen", help="Destination/location label to use")
    parser.add_argument("--object", default="chair", help="Classified object label to use")
    parser.add_argument("--landmark", default="door", help="Landmark label to use")
    parser.add_argument("--distance", type=float, default=0.8, help="Obstacle distance in metres")
    parser.add_argument("--pause", type=float, default=2.5, help="Seconds between steps in --sequence mode")
    args = parser.parse_args()

    cfg = load_config()
    audio = AudioGuidance(rate=cfg["audio"]["rate"], volume=cfg["audio"]["volume"])
    audio.initialize()

    state = {
        "label": args.destination,
        "object": args.object,
        "landmark": args.landmark,
        "distance": args.distance,
    }

    try:
        if args.say:
            speak_entry(audio, state, args.say)
            audio.wait_until_done(timeout=10.0)
        elif args.sequence:
            run_scripted_sequence(audio, state, pause_s=args.pause)
        else:
            run_interactive(audio)
    finally:
        audio.shutdown()


if __name__ == "__main__":
    main()
