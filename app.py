"""
app.py – CivicAI Flask Application
Phase 2: Citizen submission + admin dashboard.

Run:
    python app.py
    OR
    flask --app app run --debug
"""

import os
import logging
from flask import Flask, redirect, url_for, send_from_directory, abort

import database as db
from config import (
    SECRET_KEY, DEBUG, HOST, PORT,
    UPLOAD_DIR, BASE_DIR,
)
from routes.submit import submit_bp
from routes.admin  import admin_bp

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Application factory ───────────────────────────────────────────────────────

def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
    )
    app.secret_key = SECRET_KEY

    # ── CSRF: lightweight token via session ───────────────────────────
    # Full WTForms CSRF is Phase 3+. We inject a simple session token here
    # to satisfy the template {{ csrf_token() }} call.
    from secrets import token_hex
    from flask import session

    @app.before_request
    def _ensure_csrf():
        if "csrf_token" not in session:
            session["csrf_token"] = token_hex(32)

    @app.template_global()
    def csrf_token():
        from flask import session
        return session.get("csrf_token", "")

    # ── Blueprints ────────────────────────────────────────────────────
    app.register_blueprint(submit_bp)
    app.register_blueprint(admin_bp)

    # ── Home redirect ─────────────────────────────────────────────────
    @app.route("/")
    def index():
        return redirect(url_for("submit.complaint_form"))

    # ── Upload serving (images) ───────────────────────────────────────
    @app.route("/uploads/<path:filename>")
    def serve_upload(filename):
        """Serve uploaded complaint images securely."""
        # Prevent path traversal: only basename is stored in DB
        safe_name = os.path.basename(filename)
        if not os.path.isfile(os.path.join(UPLOAD_DIR, safe_name)):
            abort(404)
        return send_from_directory(UPLOAD_DIR, safe_name)

    # ── 404 / 500 handlers ────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template("errors/500.html"), 500

    # ── Ensure DB is ready ────────────────────────────────────────────
    with app.app_context():
        db.init_db()
        db.seed_departments()

    return app


# ── Entry point ───────────────────────────────────────────────────────────────
app = create_app()

if __name__ == "__main__":
    logger.info("Starting CivicAI on http://%s:%d", HOST, PORT)
    app.run(host=HOST, port=PORT, debug=DEBUG)
