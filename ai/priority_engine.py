"""
ai/priority_engine.py – CivicAI Priority Scoring Module
STUB – full implementation in Phase 4.

Phase 4 plan:
  - Rule-based baseline: category + keyword signals → base score
  - ML/LLM enhancement: GPT prompt returns 0–10 score + one-line reason
  - Map score → priority_level: 0–3 Low, 3–6 Medium, 6–8 High, 8–10 Critical
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

SCORE_BANDS = [
    (8.0, "Critical"),
    (6.0, "High"),
    (3.0, "Medium"),
    (0.0, "Low"),
]


class PriorityEngine:
    """
    Assigns a numeric priority score (0.0–10.0) and a human-readable level
    to each complaint.
    """

    def __init__(self) -> None:
        logger.info("PriorityEngine initialised (stub).")

    def score(self, category: str, title: str, description: str) -> dict:
        """
        Compute priority for a complaint.

        Returns:
            {
                "priority_score":  float,
                "priority_level":  str,
                "priority_reason": str,
            }
        """
        # TODO Phase 4: implement rule-based + LLM scoring
        return {
            "priority_score":  0.0,
            "priority_level":  "Low",
            "priority_reason": "Priority scoring not yet active",
        }

    @staticmethod
    def score_to_level(score: float) -> str:
        """Convert a numeric score to a priority level string."""
        for threshold, level in SCORE_BANDS:
            if score >= threshold:
                return level
        return "Low"
