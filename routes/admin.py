"""
routes/admin.py – CivicAI Admin Dashboard Blueprint

Routes:
  GET /admin                               → dashboard with stats + complaint table
  GET /admin/complaint/<complaint_id>      → complaint detail page
"""

import logging
import sqlite3

from flask import Blueprint, render_template, request, abort

import database as db
from config import COMPLAINT_CATEGORIES, COMPLAINT_STATUSES, PRIORITY_LEVELS

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_stats(complaints: list) -> dict:
    """Compute summary statistics from a list of complaint rows."""
    def count(status):
        return sum(1 for c in complaints if c["status"] == status)

    return {
        "total":        len(complaints),
        "submitted":    count("Submitted"),
        "under_review": count("Under Review"),
        "assigned":     count("Assigned"),
        "in_progress":  count("In Progress"),
        "resolved":     count("Resolved"),
        "closed":       count("Closed"),
        "rejected":     count("Rejected"),
        "critical":     sum(1 for c in complaints if c["priority_level"] == "Critical"),
    }


def _get_all_complaints() -> list:
    """
    Return all complaints ordered by created_at desc.
    Returns a list of sqlite3.Row objects.
    """
    with db.db_cursor() as (conn, cur):
        cur.execute(
            """SELECT complaint_id, title, category, address,
                      status, priority_level, priority_score,
                      ai_category, ai_confidence, ai_needs_review,
                      created_at, department_id, assigned_officer
               FROM complaints
               ORDER BY created_at DESC;"""
        )
        return cur.fetchall()


def _get_department(department_id: int | None) -> sqlite3.Row | None:
    if not department_id:
        return None
    with db.db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM departments WHERE id = ?;", (department_id,))
        return cur.fetchone()


def _get_officer(officer_id: int | None) -> sqlite3.Row | None:
    if not officer_id:
        return None
    with db.db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM officers WHERE id = ?;", (officer_id,))
        return cur.fetchone()


def _get_status_history(complaint_id: str) -> list:
    with db.db_cursor() as (conn, cur):
        cur.execute(
            """SELECT * FROM status_history
               WHERE complaint_id = ?
               ORDER BY changed_at ASC;""",
            (complaint_id,),
        )
        return cur.fetchall()


def _get_action_notes(complaint_id: str) -> list:
    with db.db_cursor() as (conn, cur):
        cur.execute(
            """SELECT * FROM action_notes
               WHERE complaint_id = ?
               ORDER BY created_at ASC;""",
            (complaint_id,),
        )
        return cur.fetchall()


def _get_duplicate_links(complaint_id: str) -> list:
    with db.db_cursor() as (conn, cur):
        cur.execute(
            """SELECT * FROM duplicate_links
               WHERE complaint_id = ?
               ORDER BY similarity_score DESC;""",
            (complaint_id,),
        )
        return cur.fetchall()


# ── Routes ────────────────────────────────────────────────────────────────────

@admin_bp.route("/")
def dashboard():
    """
    Admin dashboard.
    Loads all complaints; client-side JS handles search/filter.
    """
    complaints = _get_all_complaints()
    stats      = _get_stats(complaints)

    return render_template(
        "admin/dashboard.html",
        complaints=complaints,
        stats=stats,
        categories=COMPLAINT_CATEGORIES,
        statuses=COMPLAINT_STATUSES,
        priority_levels=PRIORITY_LEVELS,
    )


@admin_bp.route("/complaint/<complaint_id>")
def complaint_detail(complaint_id: str):
    """Show full details for a single complaint."""
    complaint = db.get_complaint_by_id(complaint_id)
    if complaint is None:
        abort(404)

    department     = _get_department(complaint["department_id"])
    officer        = _get_officer(complaint["assigned_officer"])
    status_history = _get_status_history(complaint_id)
    action_notes   = _get_action_notes(complaint_id)
    duplicate_links = _get_duplicate_links(complaint_id)

    return render_template(
        "admin/detail.html",
        complaint=complaint,
        department=department,
        officer=officer,
        status_history=status_history,
        action_notes=action_notes,
        duplicate_links=duplicate_links,
    )
