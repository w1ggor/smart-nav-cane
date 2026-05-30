"""Navigation state machine: tracks current position and issues instructions.

Phase 3 implementation.
"""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import Optional

from nav_assistant.mapping.waypoint import WaypointEdge
from .route_graph import RouteGraph

logger = logging.getLogger(__name__)


class NavigationState(Enum):
    IDLE = auto()
    NAVIGATING = auto()
    ARRIVED = auto()
    LOST = auto()


class Navigator:
    """
    Maintains navigation state and advances through a planned route.

    Usage:
        nav = Navigator(route_graph)
        nav.start_navigation(from_label="entrance", to_label="kitchen")
        while not nav.is_done:
            result = nav.advance(current_waypoint_label)
            if result.instruction:
                audio.speak(result.instruction)
    """

    def __init__(self, route_graph: RouteGraph) -> None:
        self._graph = route_graph
        self._route: list[WaypointEdge] = []
        self._step_index: int = 0
        self._state: NavigationState = NavigationState.IDLE
        self._destination: str = ""

    @property
    def state(self) -> NavigationState:
        return self._state

    @property
    def is_done(self) -> bool:
        return self._state in (NavigationState.ARRIVED, NavigationState.IDLE)

    def start_navigation(self, from_label: str, to_label: str) -> Optional[str]:
        """
        Plan and start a new navigation session.

        Returns the first audio instruction, or None if no path exists.
        """
        self._route = self._graph.plan(from_label, to_label)
        if not self._route:
            self._state = NavigationState.IDLE
            logger.warning("No route found from '%s' to '%s'", from_label, to_label)
            return None

        self._step_index = 0
        self._destination = to_label
        self._state = NavigationState.NAVIGATING
        first_instruction = self._route[0].audio_instruction
        logger.info("Navigation started: %s → %s (%d steps in route)",
                    from_label, to_label, len(self._route))
        return first_instruction

    def advance(self, current_waypoint_id: str) -> Optional[str]:
        """
        Called when the user reaches a new waypoint. Returns the next
        audio instruction, or None if arrived or lost.
        """
        if self._state != NavigationState.NAVIGATING:
            return None

        current_edge = self._route[self._step_index]
        if current_waypoint_id == current_edge.to_id:
            self._step_index += 1
            if self._step_index >= len(self._route):
                self._state = NavigationState.ARRIVED
                return f"You have arrived at {self._destination}."
            next_edge = self._route[self._step_index]
            return next_edge.audio_instruction

        # The recognized waypoint doesn't match the expected next waypoint
        logger.warning(
            "Position mismatch: expected '%s', got '%s'",
            current_edge.to_id,
            current_waypoint_id,
        )
        self._state = NavigationState.LOST
        return "Position lost. Please stand still while I re-localize."

    def abort(self) -> None:
        self._route = []
        self._step_index = 0
        self._state = NavigationState.IDLE
