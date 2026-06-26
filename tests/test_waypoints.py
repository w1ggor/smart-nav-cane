"""Tests for Waypoint, WaypointEdge, and EnvironmentMap."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import numpy as np
import pytest

from nav_assistant.mapping.waypoint import Waypoint, WaypointEdge
from nav_assistant.mapping.environment import EnvironmentMap


# ---- Waypoint serialization ----

def test_waypoint_roundtrip():
    wp = Waypoint(
        label="test_door",
        descriptor_path="/tmp/test.npy",
        depth_profile=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
        notes="unit test waypoint",
    )
    d = wp.to_dict()
    wp2 = Waypoint.from_dict(d)
    assert wp2.id == wp.id
    assert wp2.label == wp.label
    assert wp2.depth_profile == pytest.approx(wp.depth_profile)
    assert wp2.notes == wp.notes


def test_waypoint_edge_valid_hints():
    for hint in ("forward", "turn_left", "turn_right", "turn_around"):
        edge = WaypointEdge(
            from_id=str(uuid.uuid4()),
            to_id=str(uuid.uuid4()),
            steps=10,
            direction_hint=hint,
            audio_instruction="Test instruction.",
        )
        assert edge.direction_hint == hint


def test_waypoint_edge_invalid_hint():
    with pytest.raises(ValueError, match="direction_hint"):
        WaypointEdge(
            from_id=str(uuid.uuid4()),
            to_id=str(uuid.uuid4()),
            steps=5,
            direction_hint="diagonal",
            audio_instruction="Invalid.",
        )


def test_waypoint_edge_negative_steps():
    with pytest.raises(ValueError, match="steps"):
        WaypointEdge(
            from_id=str(uuid.uuid4()),
            to_id=str(uuid.uuid4()),
            steps=-1,
            direction_hint="forward",
            audio_instruction="Bad.",
        )


# ---- EnvironmentMap persistence ----

@pytest.fixture
def tmp_env(tmp_path):
    env = EnvironmentMap("test_env", environments_dir=str(tmp_path))
    env.open()
    yield env
    env.close()


def test_add_and_retrieve_waypoint(tmp_env):
    wp = Waypoint(
        label="entrance",
        descriptor_path="/tmp/fake.npy",
        depth_profile=[1.0] * 9,
    )
    tmp_env.add_waypoint(wp)

    retrieved = tmp_env.get_waypoint(wp.id)
    assert retrieved is not None
    assert retrieved.label == "entrance"


def test_list_waypoints_empty(tmp_env):
    assert tmp_env.list_waypoints() == []


def test_add_and_list_multiple_waypoints(tmp_env):
    for label in ("a", "b", "c"):
        tmp_env.add_waypoint(
            Waypoint(label=label, descriptor_path="/tmp/x.npy", depth_profile=[0.0] * 9)
        )
    waypoints = tmp_env.list_waypoints()
    assert len(waypoints) == 3
    assert {w.label for w in waypoints} == {"a", "b", "c"}


def test_add_edge_and_retrieve(tmp_env):
    wp_a = Waypoint(label="a", descriptor_path="/tmp/a.npy", depth_profile=[0.0] * 9)
    wp_b = Waypoint(label="b", descriptor_path="/tmp/b.npy", depth_profile=[0.0] * 9)
    tmp_env.add_waypoint(wp_a)
    tmp_env.add_waypoint(wp_b)

    edge = WaypointEdge(
        from_id=wp_a.id,
        to_id=wp_b.id,
        steps=15,
        direction_hint="forward",
        audio_instruction="Walk forward 15 steps.",
    )
    tmp_env.add_edge(edge)

    edges = tmp_env.get_edges_from(wp_a.id)
    assert len(edges) == 1
    assert edges[0].steps == 15


def test_delete_waypoint_removes_edges(tmp_env):
    wp_a = Waypoint(label="a", descriptor_path="/tmp/a.npy", depth_profile=[0.0] * 9)
    wp_b = Waypoint(label="b", descriptor_path="/tmp/b.npy", depth_profile=[0.0] * 9)
    tmp_env.add_waypoint(wp_a)
    tmp_env.add_waypoint(wp_b)
    tmp_env.add_edge(WaypointEdge(
        from_id=wp_a.id, to_id=wp_b.id, steps=5,
        direction_hint="forward", audio_instruction="Go."
    ))

    tmp_env.delete_waypoint(wp_a.id)

    assert tmp_env.get_waypoint(wp_a.id) is None
    assert tmp_env.get_edges_from(wp_a.id) == []


# ---- ToF depth grid ----

def test_tof_depth_grid():
    from nav_assistant.sensors.tof import ToFFrame
    import time
    depth = np.ones((180, 240), dtype=np.float32) * 2.5
    frame = ToFFrame(depth=depth, confidence=np.zeros_like(depth), timestamp=time.monotonic())
    grid = frame.depth_grid(rows=3, cols=3)
    assert grid.shape == (9,)
    assert np.allclose(grid, 2.5)


def test_tof_forward_min_depth():
    from nav_assistant.sensors.tof import ToFFrame
    import time
    depth = np.ones((180, 240), dtype=np.float32) * 3.0
    depth[70:110, 80:160] = 0.8  # obstacle in central zone
    frame = ToFFrame(depth=depth, confidence=np.zeros_like(depth), timestamp=time.monotonic())
    min_d = frame.forward_min_depth(zone_fraction=0.33)
    assert min_d == pytest.approx(0.8, abs=0.01)


def test_tof_zone_depths_uniform():
    from nav_assistant.sensors.tof import ToFFrame
    import time
    depth = np.ones((180, 240), dtype=np.float32) * 2.0
    frame = ToFFrame(depth=depth, confidence=np.zeros_like(depth), timestamp=time.monotonic())
    left, center, right = frame.zone_depths()
    assert left == pytest.approx(2.0)
    assert center == pytest.approx(2.0)
    assert right == pytest.approx(2.0)


def test_tof_zone_depths_blocked_center():
    from nav_assistant.sensors.tof import ToFFrame
    import time
    depth = np.ones((180, 240), dtype=np.float32) * 3.0
    third = 240 // 3
    depth[:, third:2 * third] = 0.5  # block the center column only
    frame = ToFFrame(depth=depth, confidence=np.zeros_like(depth), timestamp=time.monotonic())
    left, center, right = frame.zone_depths()
    assert left == pytest.approx(3.0)
    assert center == pytest.approx(0.5)
    assert right == pytest.approx(3.0)


# ---- Waypoint kind ----

def test_waypoint_default_kind_is_location():
    wp = Waypoint(label="kitchen", descriptor_path="/tmp/k.npy", depth_profile=[0.0] * 9)
    assert wp.kind == "location"


def test_waypoint_landmark_kind():
    wp = Waypoint(label="door", descriptor_path="/tmp/d.npy", depth_profile=[0.0] * 9, kind="landmark")
    assert wp.kind == "landmark"


def test_waypoint_invalid_kind_raises():
    with pytest.raises(ValueError, match="kind"):
        Waypoint(label="bad", descriptor_path="/tmp/b.npy", depth_profile=[0.0] * 9, kind="portal")


def test_waypoint_kind_roundtrip_through_dict():
    wp = Waypoint(label="door", descriptor_path="/tmp/d.npy", depth_profile=[0.0] * 9, kind="landmark")
    restored = Waypoint.from_dict(wp.to_dict())
    assert restored.kind == "landmark"


def test_environment_list_waypoints_filtered_by_kind(tmp_env):
    tmp_env.add_waypoint(Waypoint(label="kitchen", descriptor_path="/tmp/k.npy", depth_profile=[0.0] * 9, kind="location"))
    tmp_env.add_waypoint(Waypoint(label="door", descriptor_path="/tmp/d.npy", depth_profile=[0.0] * 9, kind="landmark"))

    locations = tmp_env.list_waypoints(kind="location")
    landmarks = tmp_env.list_waypoints(kind="landmark")

    assert [w.label for w in locations] == ["kitchen"]
    assert [w.label for w in landmarks] == ["door"]
    assert len(tmp_env.list_waypoints()) == 2


# ---- GuidedNavigator wall-following logic ----

def test_wall_following_clear_center_goes_straight():
    from nav_assistant.navigation.guided_navigator import GuidedNavigator, NavCommand
    nav = GuidedNavigator(location_recognizer=None, landmark_recognizer=None, clear_distance_m=1.0)
    result = nav._wall_following(left=2.0, center=2.0, right=2.0)
    assert result.command == NavCommand.STRAIGHT


def test_wall_following_blocked_center_turns_toward_clearer_side():
    from nav_assistant.navigation.guided_navigator import GuidedNavigator, NavCommand
    nav = GuidedNavigator(location_recognizer=None, landmark_recognizer=None, clear_distance_m=1.0)
    result = nav._wall_following(left=2.0, center=0.5, right=0.3)
    assert result.command == NavCommand.TURN_LEFT

    result = nav._wall_following(left=0.3, center=0.5, right=2.0)
    assert result.command == NavCommand.TURN_RIGHT


def test_wall_following_fully_blocked_stops():
    from nav_assistant.navigation.guided_navigator import GuidedNavigator, NavCommand
    nav = GuidedNavigator(location_recognizer=None, landmark_recognizer=None, clear_distance_m=1.0)
    result = nav._wall_following(left=0.0, center=0.4, right=0.0)
    assert result.command == NavCommand.STOP


# ---- GuidedNavigator planned-route following ----

def _make_edge(to_id="wp_b", direction_hint="forward", instruction="Go straight."):
    return WaypointEdge(
        from_id="wp_a", to_id=to_id, steps=10,
        direction_hint=direction_hint, audio_instruction=instruction,
    )


def test_no_route_set_has_no_route():
    from nav_assistant.navigation.guided_navigator import GuidedNavigator
    nav = GuidedNavigator(location_recognizer=None, landmark_recognizer=None)
    assert nav.has_route is False


def test_set_route_enables_has_route():
    from nav_assistant.navigation.guided_navigator import GuidedNavigator
    nav = GuidedNavigator(location_recognizer=None, landmark_recognizer=None)
    nav.set_route([_make_edge()])
    assert nav.has_route is True


def test_follow_planned_route_forward_when_clear():
    from nav_assistant.navigation.guided_navigator import GuidedNavigator, NavCommand
    nav = GuidedNavigator(location_recognizer=None, landmark_recognizer=None, clear_distance_m=1.0)
    nav.set_route([_make_edge(direction_hint="forward", instruction="Walk forward 10 steps.")])
    result = nav._follow_planned_route(left=2.0, center=2.0, right=2.0)
    assert result.command == NavCommand.STRAIGHT
    assert result.message == "Walk forward 10 steps."


def test_follow_planned_route_forward_overridden_when_blocked():
    """Safety check: the plan says forward, but the ToF frame disagrees — must not blindly follow the plan."""
    from nav_assistant.navigation.guided_navigator import GuidedNavigator, NavCommand
    nav = GuidedNavigator(location_recognizer=None, landmark_recognizer=None, clear_distance_m=1.0)
    nav.set_route([_make_edge(direction_hint="forward", instruction="Walk forward 10 steps.")])
    result = nav._follow_planned_route(left=2.0, center=0.3, right=2.0)
    assert result.command == NavCommand.STOP


def test_follow_planned_route_turn_left():
    from nav_assistant.navigation.guided_navigator import GuidedNavigator, NavCommand
    nav = GuidedNavigator(location_recognizer=None, landmark_recognizer=None)
    nav.set_route([_make_edge(direction_hint="turn_left", instruction="Turn left at the wall.")])
    result = nav._follow_planned_route(left=2.0, center=0.3, right=0.3)
    assert result.command == NavCommand.TURN_LEFT
    assert result.message == "Turn left at the wall."


def test_advance_route_if_at_target_waypoint():
    from nav_assistant.navigation.guided_navigator import GuidedNavigator
    nav = GuidedNavigator(location_recognizer=None, landmark_recognizer=None)
    nav.set_route([_make_edge(to_id="wp_b"), _make_edge(to_id="wp_c")])
    assert nav._route_index == 0

    nav._advance_route_if_at("wp_b")
    assert nav._route_index == 1

    # Recognizing an unrelated waypoint should not advance further
    nav._advance_route_if_at("not_in_route")
    assert nav._route_index == 1

    nav._advance_route_if_at("wp_c")
    assert nav._route_index == 2
    assert nav.has_route is False  # route exhausted
