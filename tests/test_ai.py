"""
tests/test_ai.py – CivicAI Phase 3 AI Tests

Covers:
  Categorisation (TestCategoryClassifier):
    - Road damage prediction
    - Garbage complaint prediction
    - Water supply prediction
    - Public safety prediction
    - Low-confidence handling (ambiguous text)
    - Citizen-selected category preservation
    - Model failure fallback (mocked exception)
    - Returns CategoryResult NamedTuple with correct fields

  Duplicate detection (TestDuplicateDetector):
    - Identical complaint → similarity ≈ 1.0
    - Very similar complaint → above 0.40
    - Unrelated complaint → below threshold (no match)
    - score_pair() returns float 0–1
    - Multiple duplicate matches returned
    - Self-matching prevention
    - Duplicate relationship DB insertion
    - Exception during find_duplicates returns []

  AI Engine orchestrator (TestAIEngine):
    - process_complaint returns expected keys
    - ai_category field is populated
    - citizen category is preserved in DB (never overwritten)
    - duplicate_matches list present in result
    - Engine failure → safe defaults returned

  Integration (TestAIIntegration):
    - New complaint via POST /submit/ receives AI categorisation in DB
    - New complaint via POST /submit/ receives duplicate analysis (DB check)
    - Existing Phase 1 / Phase 2 complaints remain intact
    - Dashboard filters (category, status, priority, search) still work

All tests are offline — no internet access required.
Mocked models use unittest.mock.patch.
"""

import os
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config as _config
import database as db

# ── Temp DB setup ──────────────────────────────────────────────────────────────

_TEST_DIR   = None
_UPLOAD_DIR = None


def setUpModule():
    global _TEST_DIR, _UPLOAD_DIR
    _TEST_DIR   = tempfile.mkdtemp(prefix="civicai_ai_test_")
    _UPLOAD_DIR = os.path.join(_TEST_DIR, "uploads")
    os.makedirs(_UPLOAD_DIR, exist_ok=True)

    test_db = os.path.join(_TEST_DIR, "test_civicai.db")
    _config.DATABASE_DIR  = _TEST_DIR
    _config.DATABASE_PATH = test_db
    db.DATABASE_DIR  = _TEST_DIR
    db.DATABASE_PATH = test_db

    db.init_db()
    db.seed_departments()

    import routes.submit as rs
    rs.UPLOAD_DIR = _UPLOAD_DIR


def tearDownModule():
    if _TEST_DIR and os.path.exists(_TEST_DIR):
        shutil.rmtree(_TEST_DIR)


# ── Flask test client ──────────────────────────────────────────────────────────

def _make_client():
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client(), app


# ── Helper: insert a complaint row directly ────────────────────────────────────

def _insert_complaint(cid, title, desc, cat="Road Damage"):
    with db.db_cursor() as (conn, cur):
        cur.execute(
            """INSERT OR IGNORE INTO complaints
               (complaint_id, title, description, category)
               VALUES (?, ?, ?, ?);""",
            (cid, title, desc, cat),
        )


# ──────────────────────────────────────────────────────────────────────────────
# 1. CATEGORISATION TESTS
# ──────────────────────────────────────────────────────────────────────────────

class TestCategoryClassifier(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from ai.category_classifier import CategoryClassifier
        cls.clf = CategoryClassifier()

    def test_road_damage_prediction(self):
        r = self.clf.classify(
            "Deep pothole on MG Road causing accidents",
            "There is a very deep pothole near the MG Road junction. "
            "Two bikes have already skidded off the damaged road surface.",
        )
        self.assertEqual(r.category, "Road Damage",
                         f"Expected Road Damage, got {r.category}")
        self.assertGreater(r.confidence, 0.5)

    def test_garbage_prediction(self):
        r = self.clf.classify(
            "Garbage bins not collected for three days",
            "The public garbage bin at Central Park has not been collected "
            "for three days. Waste is spilling onto the footpath.",
        )
        self.assertEqual(r.category, "Garbage Overflow",
                         f"Expected Garbage Overflow, got {r.category}")
        self.assertGreater(r.confidence, 0.5)

    def test_water_supply_prediction(self):
        r = self.clf.classify(
            "No water supply in Sector 7 for 48 hours",
            "Residents of Sector 7 have had no piped water supply for 48 hours. "
            "Families are buying water at very high cost.",
        )
        self.assertEqual(r.category, "Water Supply",
                         f"Expected Water Supply, got {r.category}")
        self.assertGreater(r.confidence, 0.5)

    def test_public_safety_prediction(self):
        r = self.clf.classify(
            "Exposed live electrical wire on Oak Avenue footpath",
            "A live electrical wire is dangling from a broken pole near the bus stand. "
            "The wire touched a metal railing and caused sparks. Children walk here daily.",
        )
        self.assertEqual(r.category, "Public Safety",
                         f"Expected Public Safety, got {r.category}")
        self.assertGreater(r.confidence, 0.5)

    def test_streetlight_prediction(self):
        r = self.clf.classify(
            "Broken streetlight near children park entrance",
            "The streetlight directly in front of the children play area has been "
            "broken for two weeks. The area is pitch dark at night and feels unsafe.",
        )
        self.assertEqual(r.category, "Streetlight",
                         f"Expected Streetlight, got {r.category}")

    def test_waterlogging_prediction(self):
        r = self.clf.classify(
            "Severe waterlogging in Nehru Street residential area",
            "Nehru Street has standing water more than one foot deep. "
            "Residents cannot leave their homes. Water is entering ground-floor houses.",
        )
        self.assertEqual(r.category, "Waterlogging",
                         f"Expected Waterlogging, got {r.category}")

    def test_low_confidence_sets_needs_review(self):
        """Genuinely ambiguous text should set needs_review=True."""
        clf_low = __import__("ai.category_classifier", fromlist=["CategoryClassifier"])
        from ai.category_classifier import CategoryClassifier
        clf = CategoryClassifier(confidence_threshold=0.99)   # extremely strict
        r = clf.classify("Some issue", "There is a problem here somewhere.")
        self.assertTrue(r.needs_review,
                        "Low-confidence prediction must set needs_review=True")

    def test_result_has_all_fields(self):
        """CategoryResult NamedTuple must have all four required fields."""
        r = self.clf.classify("Pothole on road", "Large pothole on main road causing damage.")
        self.assertIsNotNone(r.category)
        self.assertIsInstance(r.confidence, float)
        self.assertIsInstance(r.explanation, str)
        self.assertIsInstance(r.needs_review, bool)

    def test_confidence_between_0_and_1(self):
        r = self.clf.classify(
            "Waterlogging after rain in Brigade Road underpass",
            "The underpass floods to knee level within 30 minutes of rainfall.",
        )
        self.assertGreaterEqual(r.confidence, 0.0)
        self.assertLessEqual(r.confidence, 1.0)

    def test_model_failure_fallback(self):
        """If _classify_inner raises, classify() must return a safe fallback."""
        from ai.category_classifier import CategoryClassifier
        clf = CategoryClassifier()
        with patch.object(clf, "_classify_inner", side_effect=RuntimeError("model crashed")):
            r = clf.classify("test title", "test description")
        self.assertEqual(r.category, "Other")
        self.assertEqual(r.confidence, 0.0)
        self.assertTrue(r.needs_review)
        self.assertIn("error", r.explanation.lower())

    def test_citizen_category_not_overwritten(self):
        """Classifier returns AI prediction but never touches citizen category col."""
        cid = "CAT-PRESERVE-001"
        _insert_complaint(cid, "Broken road near school", "Large cracks in the road surface.", "Road Damage")
        r = self.clf.classify("Broken road near school", "Large cracks in the road surface.")
        # Save AI result
        db.save_ai_results(cid, r.category, r.confidence, r.explanation, r.needs_review)
        # Fetch back
        row = db.get_complaint_by_id(cid)
        self.assertEqual(row["category"], "Road Damage",  # original preserved
                         "Citizen category must never be overwritten")
        self.assertEqual(row["ai_category"], r.category,   # AI stored separately
                         "AI category must be stored in ai_category")


# ──────────────────────────────────────────────────────────────────────────────
# 2. DUPLICATE DETECTION TESTS
# ──────────────────────────────────────────────────────────────────────────────

class TestDuplicateDetector(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from ai.duplicate_detector import DuplicateDetector
        # Use a low threshold so similar (not just identical) complaints match
        cls.det = DuplicateDetector(threshold=0.30)

        cls.existing = [
            {
                "complaint_id": "DUP-ORIG-001",
                "title": "Deep pothole on MG Road causing accidents",
                "description": "There is a very deep pothole near the MG Road junction "
                               "with 1st Cross. Two bikes have already skidded.",
            },
            {
                "complaint_id": "DUP-ORIG-002",
                "title": "Garbage overflow at City Market bins",
                "description": "All four garbage bins at City Market have been "
                               "overflowing since Monday. The stench is affecting shops.",
            },
            {
                "complaint_id": "DUP-ORIG-003",
                "title": "Waterlogging after heavy rain on Brigade Road",
                "description": "The underpass at Brigade Road floods to knee level "
                               "within 30 minutes of moderate rainfall.",
            },
        ]

    def test_identical_complaint_detected(self):
        """Exact duplicate should return similarity_score == 1.0."""
        matches = self.det.find_duplicates(
            "DUP-NEW-001",
            "Deep pothole on MG Road causing accidents",
            "There is a very deep pothole near the MG Road junction "
            "with 1st Cross. Two bikes have already skidded.",
            self.existing,
        )
        self.assertTrue(any(m.complaint_id == "DUP-ORIG-001" for m in matches),
                        "Identical complaint not detected")
        match = next(m for m in matches if m.complaint_id == "DUP-ORIG-001")
        self.assertAlmostEqual(match.similarity_score, 1.0, places=2)

    def test_similar_complaint_detected(self):
        """Clearly similar complaint should score above 0.30 threshold."""
        score = self.det.score_pair(
            "Deep pothole on MG Road causing accidents",
            "Very deep dangerous pothole at MG Road junction causing vehicle skids",
            "Deep pothole on MG Road causing accidents",
            "There is a very deep pothole near the MG Road junction "
            "with 1st Cross. Two bikes have already skidded.",
        )
        self.assertGreater(score, 0.30, f"Expected similar score > 0.30, got {score}")

    def test_unrelated_complaint_no_match(self):
        """Unrelated complaint should not match."""
        matches = self.det.find_duplicates(
            "DUP-NEW-002",
            "Noise pollution from construction near temple",
            "Construction equipment is operating past midnight violating noise norms.",
            self.existing,
        )
        self.assertEqual(matches, [],
                         "Unrelated complaint should produce no duplicate matches")

    def test_score_pair_returns_float(self):
        score = self.det.score_pair("Road damage", "Big pothole",
                                    "Road damage", "Big pothole")
        self.assertIsInstance(score, float)
        self.assertAlmostEqual(score, 1.0, places=2)

    def test_score_pair_range(self):
        s1 = self.det.score_pair("Pothole", "Road crack", "Waterlogging", "Flooded street")
        self.assertGreaterEqual(s1, 0.0)
        self.assertLessEqual(s1, 1.0)

    def test_multiple_matches_returned(self):
        """Two similar complaints should both be returned, sorted desc."""
        existing_multi = [
            {"complaint_id": "M-001", "title": "Pothole on MG Road",
             "description": "Large pothole on MG Road near junction causing accidents."},
            {"complaint_id": "M-002", "title": "Deep pothole MG Road junction",
             "description": "Very deep pothole on MG Road at 1st Cross. Vehicles damaged."},
            {"complaint_id": "M-003", "title": "Unrelated noise issue at park",
             "description": "Loud music being played in the park every evening."},
        ]
        det = __import__("ai.duplicate_detector", fromlist=["DuplicateDetector"]).DuplicateDetector(threshold=0.30)
        matches = det.find_duplicates(
            "M-NEW",
            "Pothole on MG Road near 1st Cross",
            "Deep pothole at MG Road junction causing vehicles to skid.",
            existing_multi,
        )
        # At least the two pothole complaints should match
        matched_ids = [m.complaint_id for m in matches]
        self.assertIn("M-001", matched_ids, "First pothole not detected")
        self.assertIn("M-002", matched_ids, "Second pothole not detected")
        # Sorted descending
        if len(matches) >= 2:
            self.assertGreaterEqual(matches[0].similarity_score,
                                    matches[1].similarity_score,
                                    "Matches must be sorted by similarity descending")

    def test_self_matching_prevented(self):
        """The complaint must never match itself."""
        existing_with_self = self.existing + [
            {
                "complaint_id": "SELF-001",
                "title": "Deep pothole on MG Road causing accidents",
                "description": "There is a very deep pothole near the MG Road junction.",
            }
        ]
        matches = self.det.find_duplicates(
            "SELF-001",
            "Deep pothole on MG Road causing accidents",
            "There is a very deep pothole near the MG Road junction.",
            existing_with_self,
        )
        self.assertFalse(any(m.complaint_id == "SELF-001" for m in matches),
                         "Complaint must not match itself")

    def test_duplicate_link_db_insertion(self):
        """save_duplicate_link must persist and be retrievable."""
        _insert_complaint("DB-DUP-A", "Pothole on road", "Large pothole on main road.", "Road Damage")
        _insert_complaint("DB-DUP-B", "Pothole on main road", "Large pothole causing damage.", "Road Damage")

        db.save_duplicate_link("DB-DUP-A", "DB-DUP-B", 0.87)

        with db.db_cursor() as (conn, cur):
            cur.execute(
                "SELECT * FROM duplicate_links WHERE complaint_id = 'DB-DUP-A';",
            )
            row = cur.fetchone()

        self.assertIsNotNone(row, "Duplicate link not found in DB")
        self.assertEqual(row["matched_complaint_id"], "DB-DUP-B")
        self.assertAlmostEqual(row["similarity_score"], 0.87, places=2)

    def test_duplicate_link_idempotent(self):
        """Saving the same duplicate link twice must not create two rows."""
        _insert_complaint("IDEM-A", "Waterlogging on street", "Standing water on road.", "Waterlogging")
        _insert_complaint("IDEM-B", "Water on road", "Waterlogging on main road.", "Waterlogging")

        db.save_duplicate_link("IDEM-A", "IDEM-B", 0.80)
        db.save_duplicate_link("IDEM-A", "IDEM-B", 0.80)

        with db.db_cursor() as (conn, cur):
            cur.execute(
                "SELECT COUNT(*) FROM duplicate_links "
                "WHERE complaint_id = 'IDEM-A' AND matched_complaint_id = 'IDEM-B';"
            )
            count = cur.fetchone()[0]

        self.assertEqual(count, 1, "Duplicate link must be idempotent (only 1 row)")

    def test_exception_returns_empty_list(self):
        """If find_duplicates raises internally, it must return []."""
        from ai.duplicate_detector import DuplicateDetector
        det = DuplicateDetector(threshold=0.30)
        with patch.object(det, "_find_inner", side_effect=RuntimeError("crash")):
            result = det.find_duplicates("X-001", "title", "desc", [])
        self.assertEqual(result, [], "Exception must produce empty list, not raise")

    def test_empty_existing_complaints(self):
        """When no existing complaints exist, find_duplicates returns []."""
        matches = self.det.find_duplicates("NEW-001", "Road damage", "Pothole.", [])
        self.assertEqual(matches, [])

    def test_duplicate_match_has_explanation(self):
        """Each DuplicateMatch must include a non-empty explanation string."""
        matches = self.det.find_duplicates(
            "EXP-NEW",
            "Deep pothole on MG Road causing accidents",
            "There is a very deep pothole near the MG Road junction "
            "with 1st Cross. Two bikes have already skidded.",
            self.existing,
        )
        self.assertTrue(len(matches) > 0, "Expected at least one match")
        for m in matches:
            self.assertIsInstance(m.explanation, str)
            self.assertGreater(len(m.explanation), 0)


# ──────────────────────────────────────────────────────────────────────────────
# 3. AI ENGINE ORCHESTRATOR TESTS
# ──────────────────────────────────────────────────────────────────────────────

class TestAIEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from ai.ai_engine import AIEngine
        cls.engine = AIEngine()

    def test_process_complaint_returns_expected_keys(self):
        result = self.engine.process_complaint(
            complaint_id="ENG-001",
            title="Pothole on road",
            description="Large pothole on main road damaging vehicles.",
            category="Road Damage",
            existing_complaints=[],
        )
        for key in ("ai_category", "ai_confidence", "ai_explanation",
                    "ai_needs_review", "duplicate_matches"):
            self.assertIn(key, result, f"Missing key: {key}")

    def test_ai_category_populated(self):
        result = self.engine.process_complaint(
            complaint_id="ENG-002",
            title="Garbage bins overflowing at the market",
            description="The garbage bins at City Market have not been collected for days.",
            category="Garbage Overflow",
            existing_complaints=[],
        )
        self.assertIn(result["ai_category"],
                      _config.COMPLAINT_CATEGORIES,
                      f"ai_category '{result['ai_category']}' not a valid category")

    def test_ai_confidence_in_range(self):
        result = self.engine.process_complaint(
            complaint_id="ENG-003",
            title="Streetlight broken on Lake Road",
            description="Four streetlights on Lake Road are non-functional. "
                        "The area is dark and unsafe at night.",
            category="Streetlight",
            existing_complaints=[],
        )
        self.assertGreaterEqual(result["ai_confidence"], 0.0)
        self.assertLessEqual(result["ai_confidence"], 1.0)

    def test_duplicate_matches_is_list(self):
        result = self.engine.process_complaint(
            complaint_id="ENG-004",
            title="Water supply disrupted in colony",
            description="No water supply for two days in residential colony.",
            category="Water Supply",
            existing_complaints=[],
        )
        self.assertIsInstance(result["duplicate_matches"], list)

    def test_classifier_failure_gives_safe_defaults(self):
        """If classifier raises, engine returns citizen category as fallback."""
        from ai.ai_engine import AIEngine
        engine = AIEngine()
        engine._classifier = None   # simulate load failure
        result = engine.process_complaint(
            complaint_id="ENG-005",
            title="Tree fallen on road",
            description="A large tree has fallen across the road blocking traffic.",
            category="Tree / Vegetation",
            existing_complaints=[],
        )
        # When classifier is None, ai_category defaults to citizen category
        self.assertEqual(result["ai_category"], "Tree / Vegetation")
        self.assertEqual(result["ai_confidence"], 0.0)
        self.assertFalse(result["ai_needs_review"])


# ──────────────────────────────────────────────────────────────────────────────
# 4. INTEGRATION TESTS
# ──────────────────────────────────────────────────────────────────────────────

class TestAIIntegration(unittest.TestCase):
    """End-to-end: POST /submit/ → AI pipeline → DB results."""

    @classmethod
    def setUpClass(cls):
        cls.client, cls.app = _make_client()

    def _post_complaint(self, title, description, category="Road Damage",
                        address="Test Street, Novapolis"):
        return self.client.post(
            "/submit/",
            data={
                "title":       title,
                "description": description,
                "category":    category,
                "address":     address,
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )

    def test_submission_receives_ai_category(self):
        """After submission, complaints.ai_category must be populated."""
        resp = self._post_complaint(
            "Garbage bins not collected near the bus stop area",
            "The garbage bins at the central bus stop area have not been collected "
            "for three days. Waste is overflowing and attracting stray animals.",
            category="Garbage Overflow",
        )
        self.assertEqual(resp.status_code, 302)
        cid = resp.headers["Location"].split("/submit/success/")[-1].rstrip("/")

        row = db.get_complaint_by_id(cid)
        self.assertIsNotNone(row)
        self.assertIsNotNone(row["ai_category"],
                             "ai_category must be populated after submission")
        self.assertIn(row["ai_category"], _config.COMPLAINT_CATEGORIES)

    def test_submission_receives_ai_confidence(self):
        """After submission, complaints.ai_confidence must be a float 0–1."""
        resp = self._post_complaint(
            "Streetlight broken near school entrance on main avenue road",
            "The streetlight near the school entrance on Main Avenue has been broken "
            "for two weeks. The area is completely dark at night.",
            category="Streetlight",
        )
        self.assertEqual(resp.status_code, 302)
        cid = resp.headers["Location"].split("/submit/success/")[-1].rstrip("/")

        row = db.get_complaint_by_id(cid)
        self.assertIsNotNone(row["ai_confidence"])
        self.assertGreaterEqual(row["ai_confidence"], 0.0)
        self.assertLessEqual(row["ai_confidence"], 1.0)

    def test_citizen_category_preserved_after_submission(self):
        """
        citizen category column must equal what was submitted,
        even if AI predicts something different.
        """
        resp = self._post_complaint(
            "Road surface broken near old town junction area",
            "The road surface near Old Town has developed large cracks and potholes. "
            "Vehicles are getting damaged every day.",
            category="Road Damage",
        )
        self.assertEqual(resp.status_code, 302)
        cid = resp.headers["Location"].split("/submit/success/")[-1].rstrip("/")

        row = db.get_complaint_by_id(cid)
        self.assertEqual(row["category"], "Road Damage",
                         "Citizen category must never be overwritten by AI")

    def test_duplicate_analysis_runs_after_submission(self):
        """
        After submitting a complaint that is clearly similar to an existing one,
        a duplicate_links row should be created.
        """
        # Insert a 'seed' complaint for the duplicate to match against
        _insert_complaint(
            "DUP-SEED-INT",
            "Waterlogging near Nehru Street residential area house",
            "Nehru Street near House 45 has standing water more than one foot deep. "
            "Residents cannot leave their homes. Water is entering ground-floor houses.",
            "Waterlogging",
        )

        # Submit an almost-identical complaint via the web form
        resp = self._post_complaint(
            "Waterlogging near Nehru Street residential area house",
            "Nehru Street near House 45 has standing water more than one foot deep. "
            "Residents cannot leave their homes. Water entering ground-floor houses.",
            category="Waterlogging",
        )
        self.assertEqual(resp.status_code, 302)
        cid = resp.headers["Location"].split("/submit/success/")[-1].rstrip("/")

        with db.db_cursor() as (conn, cur):
            cur.execute(
                "SELECT * FROM duplicate_links WHERE complaint_id = ?;", (cid,)
            )
            rows = cur.fetchall()

        self.assertGreater(len(rows), 0,
                           f"No duplicate link created for {cid} vs DUP-SEED-INT")
        self.assertIn("DUP-SEED-INT",
                      [r["matched_complaint_id"] for r in rows])

    def test_existing_complaints_intact_after_ai(self):
        """Phase 1 seeded departments and AI do not corrupt existing records."""
        with db.db_cursor() as (conn, cur):
            cur.execute("SELECT COUNT(*) FROM departments;")
            dept_count = cur.fetchone()[0]
        self.assertGreaterEqual(dept_count, 6)

    def test_dashboard_still_works_after_ai(self):
        """Admin dashboard must return 200 and render filter elements."""
        resp = self.client.get("/admin/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"filter-priority",  resp.data)
        self.assertIn(b"filter-status",    resp.data)
        self.assertIn(b"filter-category",  resp.data)
        self.assertIn(b"search-input",     resp.data)
        self.assertIn(b"clear-filters",    resp.data)

    def test_detail_page_shows_ai_analysis_section(self):
        """Detail page must contain the AI Analysis sidebar section."""
        # Submit a complaint and check its detail page
        resp = self._post_complaint(
            "Sewage overflow near sunshine colony gate entrance",
            "Manhole near the main gate of Sunshine Colony is overflowing with sewage. "
            "The smell is unbearable and children are getting sick from the fumes.",
            category="Sewage",
        )
        cid = resp.headers["Location"].split("/submit/success/")[-1].rstrip("/")
        detail = self.client.get(f"/admin/complaint/{cid}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"AI Analysis", detail.data)
        self.assertIn(b"Citizen category", detail.data)
        self.assertIn(b"AI prediction",    detail.data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
