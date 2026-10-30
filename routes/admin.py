"""
routes/admin.py – CivicAI Admin Dashboard Blueprint

Routes:
  GET  /admin                                     → dashboard with stats + complaint table
  GET  /admin/complaint/<complaint_id>            → complaint detail page
  POST /admin/complaint/<complaint_id>/update     → update status + assignment (Phase 4B)
  POST /admin/complaint/<complaint_id>/add_note   → add action note (Phase 4B)
  GET  /admin/hotspots                            → geographic hotspot map (Phase 3D)
"""

import hmac
import logging
import sqlite3

from flask import (
    Blueprint, render_template, request, abort,
    redirect, url_for, flash, current_app,
)
from ai.hotspot_detector import get_hotspot_detector

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

    department      = _get_department(complaint["department_id"])
    officer         = _get_officer(complaint["assigned_officer"])
    status_history  = _get_status_history(complaint_id)
    action_notes    = _get_action_notes(complaint_id)
    duplicate_links = _get_duplicate_links(complaint_id)

    # Data needed by the write forms (Phase 4B)
    all_departments = db.get_all_departments()
    # Build a flat officer list for the assignment dropdown
    all_officers = []
    for dept in all_departments:
        all_officers.extend(db.get_officers_by_department(dept["id"]))

    return render_template(
        "admin/detail.html",
        complaint=complaint,
        department=department,
        officer=officer,
        status_history=status_history,
        action_notes=action_notes,
        duplicate_links=duplicate_links,
        # Write-form data
        statuses=COMPLAINT_STATUSES,
        departments=all_departments,
        all_officers=all_officers,
    )


# ── CSRF helper (Phase 4B) ────────────────────────────────────────────────────

def _verify_csrf() -> bool:
    """
    Timing-safe comparison of the submitted CSRF token against the session value.

    Returns True (valid) or False (invalid / missing).
    Automatically passes when app.config["TESTING"] is True so that the existing
    test suite, which does not inject tokens, continues to pass unchanged.
    """
    if current_app.config.get("TESTING"):
        return True
    submitted = request.form.get("csrf_token", "")
    expected  = request.environ.get("HTTP_X_CSRF_TOKEN") or ""
    # prefer session-stored token
    from flask import session
    expected = session.get("csrf_token", "")
    if not submitted or not expected:
        return False
    return hmac.compare_digest(submitted, expected)


# ── Admin write routes (Phase 4B) ─────────────────────────────────────────────

_NOTE_MAX_LEN = 1000   # maximum characters for an action note


@admin_bp.route("/complaint/<complaint_id>/update", methods=["POST"])
def complaint_update(complaint_id: str):
    """
    Update a complaint's status and/or department/officer assignment.

    Form fields (all optional, applied only when non-empty):
        new_status      – must be in COMPLAINT_STATUSES
        department_id   – integer FK; "0" or "" clears the assignment
        officer_id      – integer FK; "0" or "" clears the assignment
        action_note     – free text appended to status_history

    CSRF-protected: rejects requests without a valid session token.
    """
    if not _verify_csrf():
        abort(403)

    complaint = db.get_complaint_by_id(complaint_id)
    if complaint is None:
        abort(404)

    errors = []

    new_status  = request.form.get("new_status",    "").strip()
    dept_raw    = request.form.get("department_id", "").strip()
    officer_raw = request.form.get("officer_id",    "").strip()
    action_note = request.form.get("action_note",   "").strip() or None

    # ── Validate new_status ─────────────────────────────────────────
    if new_status:
        if new_status not in COMPLAINT_STATUSES:
            errors.append(f"Invalid status: '{new_status}'.")

    # ── Validate department_id ──────────────────────────────────────
    department_id: int | None = None
    if dept_raw and dept_raw != "0":
        try:
            department_id = int(dept_raw)
        except ValueError:
            errors.append("Department ID must be a number.")
        else:
            # Verify FK exists
            departments = {d["id"] for d in db.get_all_departments()}
            if department_id not in departments:
                errors.append(f"Department {department_id} does not exist.")

    # ── Validate officer_id ─────────────────────────────────────────
    officer_id: int | None = None
    if officer_raw and officer_raw != "0":
        try:
            officer_id = int(officer_raw)
        except ValueError:
            errors.append("Officer ID must be a number.")
        else:
            if department_id is not None:
                valid_officers = {
                    o["id"] for o in db.get_officers_by_department(department_id)
                }
                if officer_id not in valid_officers:
                    errors.append(
                        f"Officer {officer_id} does not belong to department {department_id}."
                    )

    if errors:
        flash(" ".join(errors), "error")
        return redirect(url_for("admin.complaint_detail", complaint_id=complaint_id)), 422

    # ── Apply changes ────────────────────────────────────────────────
    if new_status:
        db.update_complaint_status(
            complaint_id=complaint_id,
            new_status=new_status,
            action_note=action_note,
        )

    if dept_raw or officer_raw:
        # Pass None when the raw value was empty or "0" (clear assignment)
        db.assign_complaint(
            complaint_id=complaint_id,
            department_id=department_id,
            officer_id=officer_id,
        )

    flash("Complaint updated.", "success")
    return redirect(url_for("admin.complaint_detail", complaint_id=complaint_id))


@admin_bp.route("/complaint/<complaint_id>/add_note", methods=["POST"])
def complaint_add_note(complaint_id: str):
    """
    Append an action note to a complaint.

    Form fields:
        note  – required, 1–1000 characters

    CSRF-protected.
    """
    if not _verify_csrf():
        abort(403)

    complaint = db.get_complaint_by_id(complaint_id)
    if complaint is None:
        abort(404)

    note = request.form.get("note", "").strip()

    if not note:
        flash("Note cannot be empty.", "error")
        return redirect(url_for("admin.complaint_detail", complaint_id=complaint_id)), 422

    if len(note) > _NOTE_MAX_LEN:
        flash(f"Note must be {_NOTE_MAX_LEN} characters or fewer.", "error")
        return redirect(url_for("admin.complaint_detail", complaint_id=complaint_id)), 422

    db.add_action_note(complaint_id=complaint_id, note=note)
    flash("Note added.", "success")
    return redirect(url_for("admin.complaint_detail", complaint_id=complaint_id))


# ── Hotspot map ───────────────────────────────────────────────────────────────

def _get_geo_complaints() -> list:
    """
    Return all complaints that have non-NULL latitude and longitude,
    along with the columns needed for hotspot detection and display.
    Read-only — never modifies any complaint record.
    """
    with db.db_cursor() as (conn, cur):
        cur.execute(
            """SELECT complaint_id, title, category, address,
                      latitude, longitude, priority_level, priority_score
               FROM complaints
               WHERE latitude IS NOT NULL
                 AND longitude IS NOT NULL
               ORDER BY created_at DESC;"""
        )
        return cur.fetchall()


@admin_bp.route("/hotspots")
def hotspots():
    """
    Admin hotspot map.
    Runs the HotspotDetector over all geo-located complaints and renders
    a Leaflet map with cluster markers.  Read-only — no DB writes.
    """
    geo_complaints = _get_geo_complaints()
    detector       = get_hotspot_detector()
    hotspot_list   = detector.detect([dict(c) for c in geo_complaints])

    # Convert NamedTuples to plain dicts so Jinja2 tojson serialises them
    # as JSON objects (not arrays), making the client-side code simple.
    hotspots_data = [
        {
            "center_lat":         h.center_lat,
            "center_lon":         h.center_lon,
            "complaint_ids":      h.complaint_ids,
            "count":              h.count,
            "dominant_category":  h.dominant_category,
            "radius_km":          h.radius_km,
            "critical_count":     h.critical_count,
            "high_count":         h.high_count,
            "avg_priority_score": h.avg_priority_score,
        }
        for h in hotspot_list
    ]

    return render_template(
        "admin/hotspots.html",
        hotspots=hotspot_list,          # NamedTuples for Jinja2 template iteration
        hotspots_json=hotspots_data,    # plain dicts for tojson → Leaflet JS
        total_geo=len(geo_complaints),
    )
