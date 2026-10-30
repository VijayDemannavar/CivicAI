"""
ai/hotspot_detector.py – CivicAI Geographic Hotspot Detection Module
STUB – full implementation in Phase 5.

Phase 5 plan:
  - Use Haversine distance to cluster complaints within config.AI_HOTSPOT_RADIUS_KM
  - Flag clusters with >= 3 complaints as hotspots
  - Return cluster summary for the department dashboard heatmap
"""

from __future__ import annotations
import math
import logging

logger = logging.getLogger(__name__)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance in kilometres between two coordinates.
    Implemented here so it is available immediately without heavy dependencies.
    """
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


class HotspotDetector:
    """
    Identifies geographic clusters of complaints (hotspots).
    Uses a simple radius-based approach; Phase 5 may upgrade to DBSCAN.
    """

    def __init__(self, radius_km: float = 0.5) -> None:
        self.radius_km = radius_km
        logger.info("HotspotDetector initialised (stub, radius=%.2f km).", radius_km)

    def detect(self, complaints: list[dict]) -> list[dict]:
        """
        Given a list of complaint dicts (each with latitude, longitude, complaint_id),
        return hotspot cluster summaries.

        Returns:
            List of dicts: [
                {
                    "centre_lat": float,
                    "centre_lon": float,
                    "complaint_ids": [str, ...],
                    "count": int,
                }
            ]
        """
        # TODO Phase 5: implement clustering
        return []
