"""
ai/action_brief.py – CivicAI Action Brief Generator
STUB – full implementation in Phase 6.

Phase 6 plan:
  - LLM prompt (GPT-4 / Gemini) given: category, cluster summary, priority
  - Generate a concise action brief for the department officer
  - Include suggested SLA, required resources, and escalation path
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class ActionBriefGenerator:
    """
    Generates a natural-language action brief for department officers.
    Input: structured complaint / cluster data.
    Output: a short paragraph the officer can act on immediately.
    """

    def __init__(self) -> None:
        logger.info("ActionBriefGenerator initialised (stub).")

    def generate(self, complaint_data: dict) -> str:
        """
        Generate an action brief for a single complaint.

        Args:
            complaint_data: dict with keys title, description, category,
                            priority_level, address, etc.

        Returns:
            Action brief string (empty in stub mode).
        """
        # TODO Phase 6: call LLM API
        return ""

    def generate_cluster_brief(self, cluster: dict) -> str:
        """
        Generate a consolidated action brief for a hotspot cluster.

        Args:
            cluster: dict with keys centre_lat, centre_lon, complaint_ids, count.

        Returns:
            Cluster action brief string (empty in stub mode).
        """
        # TODO Phase 6
        return ""
