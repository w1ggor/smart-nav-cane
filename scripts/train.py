#!/usr/bin/env python3
"""
Training mode — capture named locations for the awareness system.

Go to each location you want recognised, run 'capture <label>', then walk
slowly around the space for the capture duration. The system samples the
webcam every few seconds and builds up a rich visual descriptor set.

Usage:
    python scripts/train.py --env my_home
    python scripts/train.py --env my_home --duration 120 --interval 3

Commands:
    capture <label>            Capture a location (default: 120s session)
    capture <label> <seconds>  Custom duration, e.g. capture kitchen 60
    landmark <label>           Capture a landmark (e.g. a door) — announced
                               during guided navigation, never a destination
    landmark <label> <seconds> Custom duration for a landmark capture
    list                       List all waypoints, their kind and descriptor counts
    delete <label>             Delete a waypoint and its descriptors
    quit                       Save and exit

Tips:
  - Walk slowly around the room during capture to maximise diversity.
  - Run 'capture <label>' again from a different angle to add more data.
  - More descriptors = more robust recognition. Aim for 1000+ per location.
  - Use 'landmark' for features along a path (doors, stairs) that should
    be announced while navigating but never selected as a destination.
  - 'edge' connections between locations are stored for future navigation
    but are not required for the awareness or guided navigation systems.
"""

from __future__ import annotations

import argparse
import logging
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import yaml

from nav_assistant.mapping.environment import EnvironmentMap
from nav_assistant.mapping.recorder import WaypointRecorder
from nav_assistant.sensors.webcam import WebcamSensor
from nav_assistant.sensors.tof import ToFSensor

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train")

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "default.yaml"


def load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def run_training_session(
    recorder: WaypointRecorder,
    env: EnvironmentMap,
    default_duration: float,
    default_interval: float,
) -> None:
    print("\nTraining session started. Type 'help' for commands.\n")

    while True:
        try:
            raw = input("train> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not raw:
            continue

        try:
            parts = shlex.split(raw)
        except ValueError as e:
            print(f"Parse error: {e}")
            continue

        cmd = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            print("Training complete. Environment saved.")
            break

        elif cmd == "help":
            print(__doc__)

        elif cmd in ("capture", "landmark"):
            kind = "location" if cmd == "capture" else "landmark"

            if len(parts) < 2:
                print(f"Usage: {cmd} <label> [seconds]")
                continue

            label = parts[1]
            try:
                duration = float(parts[2]) if len(parts) > 2 else default_duration
            except ValueError:
                print(f"  Invalid duration: {parts[2]!r}")
                continue

            is_new = env.get_waypoint_by_label(label) is None
            action = f"Creating new {kind}" if is_new else "Appending to existing"
            print(f"  {action} '{label}'.")

            try:
                wp, total = recorder.capture_location(
                    label,
                    duration_s=duration,
                    interval_s=default_interval,
                    kind=kind,
                )
                print(f"  Saved '{wp.label}' ({wp.kind}) — {total} total descriptors stored.")
                if total < 500:
                    print("  Tip: run capture again to add more data (aim for 1000+).")
            except RuntimeError as e:
                print(f"  Error: {e}")

        elif cmd == "list":
            waypoints = env.list_waypoints()
            if not waypoints:
                print("  No waypoints captured yet.")
            else:
                print(f"\n  {'Label':20s}  {'Kind':10s}  {'Descriptors':12s}  {'ID':8s}")
                print(f"  {'-'*20}  {'-'*10}  {'-'*12}  {'-'*8}")
                for wp in waypoints:
                    n = recorder.descriptor_count(wp.label)
                    quality = "good" if n >= 1000 else ("ok" if n >= 500 else "low")
                    print(f"  {wp.label:20s}  {wp.kind:10s}  {n:<8d} [{quality:4s}]  {wp.id[:8]}")
                print()

        elif cmd == "delete":
            if len(parts) < 2:
                print("Usage: delete <label>")
                continue
            wp = env.get_waypoint_by_label(parts[1])
            if wp is None:
                print(f"  Location '{parts[1]}' not found")
            else:
                confirm = input(f"  Delete '{parts[1]}'? [y/N] ").strip().lower()
                if confirm == "y":
                    env.delete_waypoint(wp.id)
                    print(f"  Deleted '{parts[1]}'.")

        elif cmd == "edge":
            if len(parts) < 6:
                print('Usage: edge <from> <to> <steps> <hint> "<instruction>"')
                continue
            try:
                edge = recorder.add_edge(
                    from_label=parts[1],
                    to_label=parts[2],
                    steps=int(parts[3]),
                    direction_hint=parts[4],
                    audio_instruction=parts[5],
                )
                print(f"  Edge added: {parts[1]} -> {parts[2]} ({parts[3]} steps)")
            except (ValueError, KeyError) as e:
                print(f"  Error: {e}")

        else:
            print(f"  Unknown command: {cmd!r}. Type 'help' for commands.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Training mode — capture named locations")
    parser.add_argument("--env", required=True, help="Environment name (e.g. 'my_home')")
    parser.add_argument("--duration", type=float, default=120.0,
                        help="Default capture duration in seconds (default: 120)")
    parser.add_argument("--interval", type=float, default=3.0,
                        help="Seconds between frame samples during capture (default: 3)")
    parser.add_argument("--tof-mock", action="store_true", help="Use ToF mock mode")
    args = parser.parse_args()

    cfg = load_config()

    webcam = WebcamSensor(
        device_name=cfg["webcam"].get("device_name"),
        device_index=cfg["webcam"]["device_index"],
        width=cfg["webcam"]["width"],
        height=cfg["webcam"]["height"],
        fps=cfg["webcam"]["fps"],
    )
    tof = ToFSensor(
        connection=cfg["tof"]["connection"],
        device_name=cfg["tof"].get("device_name", "unicam"),
        device_index=cfg["tof"]["device_index"],
        frame_timeout_ms=cfg["tof"]["frame_timeout_ms"],
        mock_mode=args.tof_mock,
    )

    with EnvironmentMap(args.env, environments_dir=cfg["data"]["environments_dir"]) as env:
        with webcam, tof:
            recorder = WaypointRecorder(env, webcam, tof)
            run_training_session(recorder, env, args.duration, args.interval)


if __name__ == "__main__":
    main()
