# Master Contract Gap Analysis & Phase 0 Implementation Plan

## 1. Gap Analysis Against Master Contract

| Area | Contract Requirement | Existing State | Gap / Action |
|------|----------------------|----------------|--------------|
| **Python Packaging** | Proper Python package, `pyproject.toml`, clean imports | No `pyproject.toml`, script-based layout | Create `pyproject.toml`, configure package roots and pytest |
| **Import Hygiene** | No `sys.path.append` anywhere | `skills.py` still had `sys.path.append` | Remove all remaining `sys.path` hacks; use centralized dependencies |
| **Hardcoded Paths** | No hardcoded local machine paths | `skills.py` has `C:\Users\taguo\...` in `/plugins/scan` | Replace with configurable/relative path resolution with env var fallback |
| **Source of Truth** | SQLite is sole source of truth; JSON is seed-only | Dual writes to JSON & DB; JSON overriding DB on read | Make SQLite authoritative; use JSON only to seed empty DB; do not mutate JSON on API CRUD |
| **Mock Fallback** | Absolutely NO silent mock fallback on process startup failure | Lines 409-434 in `runtime_adapter.py` had mock fallback | **Removed**; confirmed errors log and mark execution FAILED |
| **SSE Framing** | Proper SSE framing (`event: ...\ndata: ...\n\n`), `media_type="text/event-stream"`, no raw dicts | Yielded raw dicts with `media_type="text/plain"` | Fix `tasks.py` SSE generator to yield formatted strings with `text/event-stream` |
| **Timestamps** | API responses must return real DB timestamps | `agents.py` returns `""` for `created_at` and `updated_at` | Populate `created_at`/`updated_at` from SQLite row data in `persistence.py` & `agents.py` |
| **SQLite Concurrency** | SQLite WAL mode enabled, busy timeout set | Standard DELETE mode, no timeout | WAL mode added; add `busy_timeout` (5000ms) to connection helper |
| **Logging** | Proper Python logging, no bare prints | Scattered `print()` statements | Standardize on `logging.getLogger(__name__)` across backend |
| **Testing** | Automated tests using pytest | Manual one-off scripts, no pytest test suite | Create `poc/tests/` with unit tests for config, persistence, API, and mock-free runtime |

---

## 2. Phase 0 Implementation Plan

### Step 1: Python Packaging & Project Config
- Create `pyproject.toml` at workspace root defining package metadata, dependencies, and `[tool.pytest.ini_options]`.
- Verify `.gitignore` covers build artifacts, virtual environments, sqlite databases, cache, and logs.

### Step 2: Clean Imports & Remove Hardcoded Paths in `skills.py`
- In `poc/backend/api/skills.py`:
  - Remove `sys.path.append(...)`.
  - Import from `..dependencies import get_config_manager, get_db_manager, Skill`.
  - In `/plugins/scan`, remove hardcoded `C:\Users\taguo\...` paths. Use `os.environ.get("SKILLS_SCAN_PATHS")` and relative project directory paths.

### Step 3: SQLite as Single Source of Truth
- In `persistence.py`:
  - Add `busy_timeout = 5000` to `_get_connection()`.
  - Ensure `AgentConfig` in `config.py` and `persistence.py` preserves `created_at` and `updated_at`.
- In `poc/backend/api/agents.py`:
  - Read from `db_manager` directly as primary source of truth.
  - On create/update/delete, write to `db_manager` (and optionally notify config_manager in-memory cache without requiring JSON disk mutation).
  - Return actual `created_at` and `updated_at` in responses.
- In `poc/backend/api/projects.py`:
  - Ensure `db_manager` is primary source of truth.

### Step 4: Fix SSE Content-Type & Framing
- In `poc/backend/api/tasks.py`:
  - Ensure `event_generator()` yields strings: `f"event: {event_type}\ndata: {json_str}\n\n"`.
  - Set `media_type="text/event-stream"`.

### Step 5: Automated Test Suite (Pytest)
- Create `poc/tests/`:
  - `poc/tests/test_phase0_hygiene.py`: Test imports, database WAL mode, SQLite source of truth, real timestamps, and mock removal.
  - `poc/tests/test_api_endpoints.py`: Test all CRUD operations and SSE format.
- Run `python -m pytest poc/tests` to verify 100% pass rate.

### Step 6: Full Verification
- Run `npm run build` in `poc/dashboard` to verify frontend build integrity.
- Run `python poc/start_api.py --help` / startup check.
