"""Route graph built from EnvironmentMap data. Provides Dijkstra path planning.

Phase 3 implementation.
"""

from __future__ import annotations

import logging
from typing import Optional

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False

from nav_assistant.mapping.environment import EnvironmentMap
from nav_assistant.mapping.waypoint import Waypoint, WaypointEdge

logger = logging.getLogger(__name__)


class RouteGraph:
    """
    Directed weighted graph of waypoints.

    Edge weight = steps (walking steps between waypoints). Dijkstra finds
    the minimum-step path.

    Usage:
        graph = RouteGraph(env)
        graph.build()
        path = graph.plan("entrance", "kitchen")
        # path = [WaypointEdge, WaypointEdge, ...]
    """

    def __init__(self, env: EnvironmentMap) -> None:
        if not _NX_AVAILABLE:
            raise ImportError("networkx is required. Run: pip install networkx")
        self._env = env
        self._graph: Optional[nx.DiGraph] = None
        self._waypoints: dict[str, Waypoint] = {}

    def build(self) -> None:
        """Load waypoints and edges from the database and build the graph."""
        self._graph = nx.DiGraph()
        self._waypoints = {wp.id: wp for wp in self._env.list_waypoints()}

        for wp in self._waypoints.values():
            self._graph.add_node(wp.id, label=wp.label)

        for edge in self._env.list_edges():
            self._graph.add_edge(
                edge.from_id,
                edge.to_id,
                weight=edge.steps,
                edge_obj=edge,
            )

        logger.info(
            "RouteGraph built: %d waypoints, %d edges",
            self._graph.number_of_nodes(),
            self._graph.number_of_edges(),
        )

    def plan(self, from_label: str, to_label: str) -> list[WaypointEdge]:
        """
        Return the list of WaypointEdges forming the shortest path (by steps)
        from from_label to to_label.

        Returns an empty list if no path exists.
        Raises ValueError if either label is not in the graph.
        """
        self._require_built()

        from_wp = self._env.get_waypoint_by_label(from_label)
        to_wp = self._env.get_waypoint_by_label(to_label)

        if from_wp is None:
            raise ValueError(f"Start waypoint '{from_label}' not found")
        if to_wp is None:
            raise ValueError(f"Destination waypoint '{to_label}' not found")

        try:
            node_path = nx.shortest_path(
                self._graph, from_wp.id, to_wp.id, weight="weight"
            )
        except nx.NetworkXNoPath:
            logger.warning("No path from '%s' to '%s'", from_label, to_label)
            return []

        edges: list[WaypointEdge] = []
        for u, v in zip(node_path, node_path[1:]):
            edge_data = self._graph[u][v]
            edges.append(edge_data["edge_obj"])

        return edges

    def waypoint_by_id(self, waypoint_id: str) -> Optional[Waypoint]:
        return self._waypoints.get(waypoint_id)

    def _require_built(self) -> None:
        if self._graph is None:
            raise RuntimeError("RouteGraph not built. Call build() first.")
