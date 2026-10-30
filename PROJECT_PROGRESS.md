# CivicAI – Project Progress

**Project:** CivicAI – From Complaints to Action  
**Hackathon:** PromptWars × ASTRA  
**Last saved:** 2026-10-30  
**Current test result:** ✅ 117 / 117 passed, 6 subtests passed  
**Database records:** 51 complaints · 6 departments · 12 officers · 5 duplicate links · 52 status history rows · 8 action notes

---

## Overall Progress: 3 of 7 Phases Complete (Phase 3C also done)

```
Phase 1  ✅  Architecture, Database, Synthetic Data
Phase 2  ✅  Flask Backend, Routes, Frontend Templates
Phase 3  🔄  AI Engine (3A ✅ 3B ✅ 3C ✅ | 3D ❌ 3E ❌)
Phase 4  ❌  Not started
Phase 5  ❌  Not started
Phase 6  ❌  Not started
Phase 7  ❌  Not started
```

---

## Completed Features

### Phase 1 – Architecture, Database, Synthetic Data ✅

| Item | Status | Details |
|------|--------|---------|
| Project folder structure | ✅ Done | All dirs and stub files created |
| `config.py` | ✅ Done | All app + AI settings, no hardcoded secrets |
| `database.py` | ✅ Done | 6 tables, FK enforcement, indexes, migrations, helpers |
| `seed_data.py` | ✅ Done | 44 synthetic complaints, deliberate duplicates, geographic cluster |
| `requirements.txt` | ✅ Done | Flask 3.0.3, numpy, pytest, Werkzeug |
| `README.md` | ✅ Done | Full docs with PowerShell commands |
| `tests/test_database.py` | ✅ Done | 13 tests — connection, tables, FK, insert, unique IDs |

**Database schema (6 tables):**
- `complaints` — 21 columns including AI fields + priority fields
- `departments` — 6 seeded civic departments
- `officers` — 12 seeded demo officers
- `status_history` — tracks every status transition
- `duplicate_links` — links similar complaints with similarity score
- `action_notes` — admin notes per complaint

---

### Phase 2 – Flask Backend, Routes, Frontend ✅

| Item | Status | Details |
|------|--------|---------|
| `app.py` | ✅ Done | App factory, blueprints, CSRF, upload serving |
| `routes/submit.py` | ✅ Done | GET/POST /submit, image validation, DB save, AI pipeline hook |
| `routes/admin.py` | ✅ Done | Dashboard with 4-way filter, complaint detail page |
| `templates/submit/form.html` | ✅ Done | Citizen form with GPS capture |
| `templates/submit/success.html` | ✅ Done | Confirmation page |
| `templates/admin/dashboard.html` | ✅ Done | Table with Category + Status + Priority + Search filters |
| `templates/admin/detail.html` | ✅ Done | Full detail view with AI Analysis sidebar |
| `templates/base.html` | ✅ Done | Shared layout |
| `templates/errors/404.html` | ✅ Done | Error pages |
| `templates/errors/500.html` | ✅ Done | Error pages |
| `static/css/main.css` | ✅ Done | Citizen-facing styles |
| `static/css/admin.css` | ✅ Done | Admin-facing styles |
| `static/js/main.js` | ✅ Done | 4-way live filter (category/status/priority/search) |
| `tests/test_routes.py` | ✅ Done | 41 tests — form, validation, dashboard, filters, data integrity |

**Routes implemented:**
- `GET /submit/` — complaint form
- `POST /submit/` — submit complaint (validates, saves, runs AI pipeline)
- `GET /submit/success/<id>` — confirmation page
- `GET /admin/` — dashboard with filter controls
- `GET /admin/complaint/<id>` — full complaint detail with AI sidebar

---

### Phase 3A – AI Category Classifier ✅

| Item | Status | Details |
|------|--------|---------|
| `ai/category_classifier.py` | ✅ Done | Keyword + TF-IDF hybrid, 11 categories |
| `ai/__init__.py` | ✅ Done | Exposes `AIEngine` |
| DB migration | ✅ Done | `ai_confidence`, `ai_explanation`, `ai_needs_review` columns added |
| Admin detail template | ✅ Done | AI Analysis sidebar: citizen category, AI prediction, confidence bar, review badge |
| Tests in `TestCategoryClassifier` | ✅ Done | 11 tests |

**Classifier behaviour:**
- 11 categories: Road Damage, Waterlogging, Garbage Overflow, Streetlight, Drainage, Public Safety, Water Supply, Sewage, Tree/Vegetation, Noise Pollution, Other
- Returns `CategoryResult(category, confidence, explanation, needs_review)`
- Sets `needs_review=True` when `confidence < AI_CATEGORY_CONFIDENCE_THRESHOLD` (0.55)
- Admin dashboard shows 🤖 Review badge on low-confidence rows
- AI category stored in `ai_category` column; citizen's `category` column is **never overwritten**

---

### Phase 3B – Duplicate Detector ✅

| Item | Status | Details |
|------|--------|---------|
| `ai/duplicate_detector.py` | ✅ Done | 4-signal blend: title (50%), desc (30%), category (10%), geo (10%) |
| `database.py` → `save_duplicate_link()` | ✅ Done | Idempotent insert with FK references |
| `routes/submit.py` AI pipeline | ✅ Done | Calls duplicate detector post-save, persists all links |
| Admin detail template | ✅ Done | Duplicate panel always visible; lists matched complaint IDs + scores |
| Tests in `TestDuplicateDetector` | ✅ Done | 13 tests |
| Regression fixes | ✅ Done | 3 previously failing tests fixed (was 85/89, now 117/117) |

**Algorithm details:**
- `_text_pair_similarity()` = `max(TF-IDF cosine, overlap coefficient)` — prevents 2-doc IDF discounting of shared tokens
- `_blend()` only includes signals with available data; redistributes weights so identical text → score=1.0
- `DuplicateMatch` NamedTuple: `complaint_id, similarity_score, title_sim, desc_sim, geo_sim, category_match, explanation`
- Threshold: `AI_SIMILARITY_THRESHOLD = 0.60` (configurable)

---

### Phase 3C – Priority Engine ✅

| Item | Status | Details |
|------|--------|---------|
| `ai/priority_engine.py` | ✅ Done | Rule-based, 0–100 score, 4 levels, 6 additive factors |
| `ai/ai_engine.py` | ✅ Done | Step 3 added: priority scoring after duplicate detection |
| `database.py` → `save_ai_results()` | ✅ Done | Now persists `priority_score`, `priority_level`, `priority_reason` |
| `routes/submit.py` | ✅ Done | Passes priority fields to `save_ai_results()` |
| Tests in `TestPriorityEngine` | ✅ Done | 28 tests |

**Scoring model (additive, clamped to [0, 100]):**

| Factor | Points | Condition |
|--------|--------|-----------|
| Category base | 10–50 | Public Safety=50, Road Damage=30, Waterlogging=25, … |
| Urgency keywords | +25 (once) | accident, collapse, fire, electrocution, assault, flood, … |
| Infrastructure risk | +15 (once) | road closed, no water supply, power outage, open manhole, gas leak, … |
| Scope keywords | +10 (once) | entire area, whole colony, hundreds of, all residents, … |
| Duration keywords | +10 (once) | for months, since last year, not fixed, no response, … |
| Duplicate count | +5 each, max +15 | 1 duplicate = +5, 2 = +10, 3+ = +15 |

**Level thresholds (from config):**
- Critical: score ≥ 75
- High: score ≥ 50
- Medium: score ≥ 25
- Low: score < 25

---

## Partially Completed Features

### Phase 3D – Hotspot Detector 🔄 (stub only)

| Item | Status |
|------|--------|
| `ai/hotspot_detector.py` | ⚠️ Stub — logs "not implemented", returns empty list |
| Hotspot clustering algorithm | ❌ Not started |
| Hotspot map view (Leaflet) | ❌ Not started |
| DB columns for hotspot data | ❌ Not started |
| Tests | ❌ Not started |

**Planned approach:** DBSCAN-lite spatial clustering using Haversine distance (no scikit-learn). Cluster radius: `AI_HOTSPOT_RADIUS_KM = 0.5 km`. Minimum complaints per hotspot: `AI_HOTSPOT_MIN_COMPLAINTS = 3`. Admin map page using Leaflet.js with cluster markers.

---

### Phase 3E – Action Brief Generator 🔄 (stub only)

| Item | Status |
|------|--------|
| `ai/action_brief.py` | ⚠️ Stub — returns empty string |
| Template-based brief generation | ❌ Not started |
| DB table `action_briefs` | ❌ Not started |
| Admin detail page integration | ❌ Not started |
| Tests | ❌ Not started |

**Planned approach:** Template-based (no LLM). Per-category response templates with `{complaint_id}`, `{title}`, `{address}`, `{priority_level}` substitution. `AI_BRIEF_MAX_STEPS = 5` recommended steps per brief.

---

## Remaining Tasks

### Immediate Next Steps (Phase 3D – Hotspot Detector)

1. **Implement `ai/hotspot_detector.py`:**
   - DBSCAN-lite spatial clustering using Haversine distance
   - Input: list of complaints with `latitude`, `longitude`, `complaint_id`, `category`
   - Output: list of `Hotspot(center_lat, center_lon, complaint_ids, radius_km, dominant_category)`
   - Only complaints with coordinates are clustered
   - Configurable via `AI_HOTSPOT_RADIUS_KM` and `AI_HOTSPOT_MIN_COMPLAINTS`

2. **Add hotspot admin page/map:**
   - New route `GET /admin/hotspots` 
   - Template `templates/admin/hotspots.html` with Leaflet.js map
   - Cluster markers with complaint count and dominant category
   - Link from admin dashboard navigation

3. **Integrate into `ai_engine.py`** (optional batch step, not per-complaint)

4. **Write tests** in `tests/test_ai.py` — `TestHotspotDetector` class

### Following Steps (Phase 3E – Action Briefs)

5. **Implement `ai/action_brief.py`:**
   - `generate_brief(complaint)` → structured dict with steps list
   - Per-category templates (11 categories)
   - Placeholder substitution for ID, title, address, level

6. **Add `action_briefs` table** (migration in `database.py`)

7. **Show brief on admin detail page** (`templates/admin/detail.html`)

8. **Write tests** — `TestActionBrief` class

### Future Phases (4–7)

| Phase | Description |
|-------|-------------|
| Phase 4 | Admin management — status updates, department assignment, officer assignment |
| Phase 5 | Public-facing dashboard — complaint tracking by ID, map view |
| Phase 6 | Analytics & reporting — charts, trends, resolution time stats |
| Phase 7 | Final polish — mobile responsiveness, accessibility, demo data refresh |

---

## Modified Files (Phase 3B → 3C changes)

Files modified during the current session (most recent to oldest):

| File | Changes |
|------|---------|
| `tests/test_ai.py` | Added `TestPriorityEngine` class (28 new tests); now 117 tests total |
| `ai/priority_engine.py` | **Full implementation** — replaced stub with rule-based scoring engine |
| `database.py` | `save_ai_results()` updated to also persist `priority_score`, `priority_level`, `priority_reason` |
| `routes/submit.py` | `_run_ai_pipeline()` passes priority fields to `save_ai_results()` |
| `ai/ai_engine.py` | Added Step 3 (priority scoring); `_load_models()` loads `PriorityEngine`; result dict includes 3 new keys |
| `ai/duplicate_detector.py` | Fixed `_blend()` (skip zero-weight signals); added `_overlap_coefficient()`; `_text_pair_similarity()` now returns `max(tfidf, overlap)` |

---

## All Project Files

```
civicai/
├── app.py                          Flask app factory, blueprints registration
├── config.py                       All configuration constants (no secrets)
├── database.py                     DB layer: connection, schema, migrations, helpers
├── seed_data.py                    44 synthetic complaints, 6 departments, 12 officers
├── requirements.txt                Flask 3.0.3, numpy>=1.24, pytest, Werkzeug
├── README.md                       Full project documentation + PowerShell setup
├── PROJECT_PROGRESS.md             ← THIS FILE
├── _smoke.py                       Temporary debug script (safe to delete)
├── .env.example                    Environment variable template
├── .gitignore                      Git ignore rules
│
├── database/
│   ├── civicai.db                  Production SQLite database (51 complaints)
│   └── .gitkeep
│
├── uploads/
│   └── .gitkeep                    User-uploaded images stored here
│
├── ai/
│   ├── __init__.py                 Exports AIEngine
│   ├── ai_engine.py                ✅ Orchestrator: categorise → duplicate detect → prioritise
│   ├── category_classifier.py      ✅ Keyword + TF-IDF hybrid, 11 categories
│   ├── duplicate_detector.py       ✅ 4-signal blend, overlap coefficient, geo proximity
│   ├── priority_engine.py          ✅ Rule-based 0–100 scoring, 6 factors, 4 levels
│   ├── hotspot_detector.py         ⚠️ STUB — Phase 3D not started
│   └── action_brief.py             ⚠️ STUB — Phase 3E not started
│
├── routes/
│   ├── __init__.py                 Empty init
│   ├── submit.py                   Citizen submission flow + AI pipeline
│   └── admin.py                    Admin dashboard + complaint detail
│
├── templates/
│   ├── base.html                   Shared layout (nav, footer)
│   ├── submit/
│   │   ├── form.html               Complaint submission form
│   │   └── success.html            Submission confirmation
│   ├── admin/
│   │   ├── dashboard.html          Admin dashboard: table + 4-way filter
│   │   └── detail.html             Complaint detail: info + AI sidebar + duplicates
│   └── errors/
│       ├── 404.html
│       └── 500.html
│
├── static/
│   ├── css/
│   │   ├── main.css                Citizen-facing styles
│   │   └── admin.css               Admin-facing styles
│   ├── js/
│   │   └── main.js                 Live 4-way filter (category/status/priority/search)
│   └── images/                     (empty, reserved)
│
└── tests/
    ├── __init__.py
    ├── test_database.py            13 tests — DB connection, tables, FK, insert
    ├── test_routes.py              41 tests — routes, forms, dashboard, filters
    └── test_ai.py                  63 tests — categoriser, duplicates, priority engine
```

---

## Test Suite Summary

```
tests/test_database.py    13 tests   ✅ all passing
tests/test_routes.py      41 tests   ✅ all passing  (incl. 9 priority filter tests)
tests/test_ai.py          63 tests   ✅ all passing
                        ─────────
TOTAL                    117 tests   ✅ 117 / 117 passed
                                     6 subtests passed
```

**Test breakdown by class:**

| Class | Tests | Description |
|-------|-------|-------------|
| `TestDatabaseConnection` | 4 | Connection, FK enforcement, row factory |
| `TestTableCreation` | 3 | All 6 tables exist, columns, indexes |
| `TestForeignKeyEnforcement` | 1 | Invalid FK raises IntegrityError |
| `TestComplaintInsertion` | 2 | Insert and fetch, defaults |
| `TestUniqueComplaintID` | 1 | Duplicate complaint_id raises |
| `TestStatusHistoryInsertion` | 2 | Insert history, FK validation |
| `TestComplaintSubmission` | 6 | Form GET, POST, redirects, DB save |
| `TestMissingRequiredFields` | 4 | Validation errors for missing fields |
| `TestInvalidComplaintData` | 8 | Bad category, coords, image type/size |
| `TestComplaintRetrieval` | 4 | Detail page, 404, content |
| `TestDashboard` | 6 | Dashboard renders, stats, filters shown |
| `TestPriorityFilter` | 9 | 4-way filter attributes, dropdowns |
| `TestExistingDataIntegrity` | 4 | Production DB records are undisturbed |
| `TestCategoryClassifier` | 11 | All 11 categories, confidence, fallbacks |
| `TestDuplicateDetector` | 13 | Exact/similar/unrelated, DB links, edge cases |
| `TestAIEngine` | 5 | Orchestrator keys, category, duplicates, failure |
| `TestAIIntegration` | 7 | End-to-end via HTTP: AI results in DB |
| `TestPriorityEngine` | 28 | Score, level, factors, clamping, AI engine integration |

---

## Configuration Reference

```python
# config.py — AI settings
AI_SIMILARITY_THRESHOLD          = 0.60   # duplicate detection threshold
AI_CATEGORY_CONFIDENCE_THRESHOLD = 0.55   # below this → needs_review = True
AI_HOTSPOT_RADIUS_KM             = 0.5    # hotspot cluster radius
AI_HOTSPOT_MIN_COMPLAINTS        = 3      # min complaints per hotspot
AI_PRIORITY_CRITICAL_MIN         = 75     # score ≥ 75 → Critical
AI_PRIORITY_HIGH_MIN             = 50     # score ≥ 50 → High
AI_PRIORITY_MEDIUM_MIN           = 25     # score ≥ 25 → Medium
AI_BRIEF_MAX_STEPS               = 5      # max steps in action brief
```

---

## How to Run

```powershell
# From civicai\ directory — activate venv first:
.\venv\Scripts\Activate.ps1

# Run all tests
python -m pytest tests/ -v

# Start the dev server
python app.py

# Reinitialise DB (non-destructive, IF NOT EXISTS)
python database.py

# Re-seed synthetic data (idempotent)
python seed_data.py
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.14 |
| Web framework | Flask 3.0.3 |
| Database | SQLite 3 (via `sqlite3` stdlib) |
| Templates | Jinja2 (bundled with Flask) |
| Frontend | HTML5 · CSS3 · vanilla JavaScript |
| Map (planned) | Leaflet.js (CDN, Phase 3D) |
| AI / NLP | Pure Python + numpy (no downloads) |
| Testing | pytest 9.2.0 + unittest |
| Environment | Python venv · Windows PowerShell |
