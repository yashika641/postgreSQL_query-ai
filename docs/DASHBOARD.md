# 📊 PostgreSQL Query AI — Project Dashboard

> Auto-narrated from `project_metrics.json` and `PROJECT_PROGRESS.md`. Update both whenever this file is regenerated.

**Last updated:** 2026-08-18 · **Overall completion:** **61%** · **Current phase:** `Observability + first Evaluation done → Open Bugs debugging pass`

---

## 🎯 Where we are right now

```
┌──────────────────────────────────────────────────────────┐
│  OBSERVABILITY LIVE + FIRST EVAL BASELINE IN — DEBUGGING       │
│  PASS STARTS NEXT                                              │
│  observalibilty/evaluation/{metrics,observability}.py wired    │
│  into all 4 agent.py nodes + backend/api.py's /chat. Docker    │
│  Compose runs Prometheus + Grafana; a 7-panel dashboard was    │
│  pushed via API, confirmed rendering real data.                │
│                                                                │
│  Full 9-question eval suite ran: 3/9 succeeded outright, but   │
│  4 of the 6 "failures" were Gemini's 20-req/day free-tier      │
│  quota running out mid-suite (429 RESOURCE_EXHAUSTED), not     │
│  real bugs — excluded from the numbers below. The 2 genuine    │
│  failures both trace to votes.creationdate having no index.    │
│  Also caught: sql_generator.py runs gemini-3.5-flash, not      │
│  gemini-2.5-flash as previously documented (confirmed          │
│  intentional; docs corrected).                                 │
│                                                                │
│  Decision: work around the quota by testing in small batches   │
│  going forward rather than upgrading billing.                  │
│                                                                │
│  Next: Open Bugs debugging pass, starting with #7 (votes       │
│  index) and #8 (COUNT(*) prompt nudge) — both already          │
│  confirmed and cheap.                                          │
└──────────────────────────────────────────────────────────┘
```

## 🧭 Overall Completion

```
[████████████████████████░░░░░░░░░░░░░░]  61%
```

## 🪜 Phase-by-Phase Progress

| # | Phase | Status | Progress |
|---|-------|--------|----------|
| 1 | Database Foundation | 🟢 Complete | `██████████` 100% |
| 2 | Python Database Layer | 🟢 Complete | `██████████` 100% |
| 3 | Schema Intelligence | 🟢 Complete | `██████████` 100% |
| 4 | NL → SQL Generation | 🟢 Complete | `██████████` 100% |
| 5 | SQL Safety & Validation | 🟢 Complete | `██████████` 100% |
| 6 | Execution + Self-Correction | 🟡 In Progress | `███████░░░` 70% |
| 7 | Agentic Workflow (LangGraph) | 🟡 In Progress | `██████░░░░` 60% |
| 8 | Conversational Memory | 🟡 In Progress | `████░░░░░░` 40% |
| 9 | Result Intelligence / Viz | ⬜ Not Started | `░░░░░░░░░░` 0% |
| 10 | FastAPI Backend | 🟡 In Progress | `██████░░░░` 60% |
| 11 | Frontend | 🟡 In Progress | `█████░░░░░` 50% |
| 12 | Evaluation | 🟡 In Progress | `█████░░░░░` 50% |
| 13 | Observability | 🟢 Near-Complete | `█████████░` 90% |
| 14 | Docker + Deployment | ⬜ Not Started | `░░░░░░░░░░` 0% |

## 📈 Phase Completion (visual)

```mermaid
%%{init: {'theme': 'neutral'} }%%
xychart-beta
    title "Phase Completion %"
    x-axis ["DB", "Python", "Schema", "SQL Gen", "Safety", "Exec", "Agent", "Memory", "Viz", "API", "Frontend", "Eval", "Observ.", "Deploy"]
    y-axis "Completion %" 0 --> 100
    bar [100, 100, 100, 100, 100, 70, 60, 40, 0, 60, 50, 50, 90, 0]
```

## 🗺️ Milestone Timeline

```mermaid
timeline
    title PostgreSQL Query AI — Milestone Timeline
    Phase 1 : PostgreSQL 18 installed : DB created : Dataset restore in progress
    Phase 2 : Python project + DB connection (next up)
    Phase 3 : Schema introspection engine
    Phase 4 : Natural language → SQL generation
    Phase 5 : SQL safety + read-only validation
    Phase 6 : Execution + self-correction loop
    Phase 7 : True agentic workflow
    Phase 8 : Conversational memory
    Phase 9 : Result intelligence + auto-viz
    Phase 10 : FastAPI backend
    Phase 11 : Frontend UI
    Phase 12 : Evaluation harness
    Phase 13 : Observability
    Phase 14 : Docker + deployment
```

## 🏗️ Architecture Overview (target end state)

```mermaid
flowchart TD
    U["User question (NL)"] --> AGENT["AI Agent"]
    AGENT --> SCHEMA["Schema Retrieval\n(Phase 3)"]
    SCHEMA --> GEN["SQL Generation\n(Phase 4)"]
    GEN --> VAL["SQL Validator\nread-only guardrails\n(Phase 5)"]
    VAL -->|blocked| AGENT
    VAL -->|passes| EXEC["Executor\n(Phase 6)"]
    EXEC -->|error| CORRECT["LLM Self-Correction\n(max retries)"]
    CORRECT --> VAL
    EXEC -->|results| ANALYZE["Result Analysis +\nOptional Chart\n(Phase 9)"]
    ANALYZE --> ANSWER["Final Answer"]
    ANSWER --> U

    style VAL fill:#f8d7da,stroke:#c0392b
    style EXEC fill:#d4edda,stroke:#27ae60
    style GEN fill:#fff3cd,stroke:#d4a017
```

## 🧪 Evaluation Metrics (first full suite run, 2026-08-18)

| Metric | Value |
|---|---|
| Questions tested (clean signal) | 5 of 9 — the other 4 hit a Gemini free-tier quota limit mid-run, excluded |
| SQL execution success rate | 60% (3/5) |
| Answer accuracy | 100% on completed queries |
| Average retries | 1.7 across successes (2, 2, 1 attempts); both failures hit max (3/3) |
| Average latency | 65.9s across the 5 clean results — dominated by 30s-per-timed-out-attempt cost |
| Token usage / query | not yet measured |

Successes: "questions posted in 2023" (2 attempts, 105.8s — attempt 1's `COUNT(*)` timed out, attempt 2's `COUNT(id)` succeeded), "posts marked as duplicates" (2 attempts, 53.2s), "who are the best users" (1 attempt, 3.3s). Genuine failures: "upvotes cast in 2022" and "rep>1000, never deletion-voted" — both hit 3/3 attempts, both root-caused to `votes.creationdate` having no index.

**Excluded (not real failures):** the hard/stress-tier questions (5, 6, 8, 9) returned `429 RESOURCE_EXHAUSTED` — Gemini's free tier caps at 20 requests/day/project/model, and this run's up-to-27 generate calls burned through it mid-suite. Re-test these once quota resets, in small batches.

*Full results: `eval_results_20260818_190634.csv`. Next: re-run the hard/stress tier once the two confirmed bugs (`votes` index, `COUNT(*)` prompt bias) are fixed, to get a real baseline unaffected by known issues.*

## 🐛 Bugs Fixed (session handoff — real browser testing)

- User tested in a real (non-automated) browser tab and hit "Failed to fetch" despite curl working against the same `/chat` endpoint. Root cause: `localhost` resolves to IPv6 (`::1`) on this machine (confirmed via `ping`), uvicorn only binds IPv4 (`127.0.0.1`, confirmed via its own log) — the frontend's `fetch()` was silently trying the wrong address. Fixed by hardcoding `frontend/src/api.js`'s `API_BASE` to `http://127.0.0.1:8000`. **Not yet committed** — first thing to do next session.

## 🐛 Bugs Fixed (Phase 10/11 — backend + frontend verification)

- `AgentState.result` was a raw `pandas.DataFrame`. `SqliteSaver` persists the *whole* state via msgpack after every node — `DataFrame` has no msgpack representation, so **every successful query crashed** (`TypeError: Type is not msgpack serializable: DataFrame`), not an edge case. Existed since memory was added, only surfaced now under a real end-to-end test. Fixed: `result` is now `{"columns": [...], "rows": [...]}` everywhere (`agent.py`, `backend/api.py`, `tests/test_agent.py`); `run_question()` reconstructs a `DataFrame` before returning to preserve its documented type for CLI/test callers.
- `generate_node` had no error handling for the Gemini call itself — a transient `APIError` (429 and 503 both genuinely hit today) crashed straight out of the graph. Fixed by catching `google.genai.errors.APIError` and adding a new `after_generate` router so generation failures retry through the same loop as validation/execution failures, instead of the fixed `generate → validate` edge assuming generation always succeeds.
- `backend/api.py`'s `ChatResponse.columns` was typed `list[dict]` instead of `list[str]` — would fail Pydantic response validation on every call. Fixed.
- Full detail in `PROJECT_PROGRESS.md`.

## 🐛 Bugs Fixed (Phase 8 — conversational memory)

- `sql_generator.py`'s `generate_sql()` referenced a `history` parameter it never declared (`NameError`), and built `conversation_context` but never inserted it into the prompt. Both fixed.
- `agent.py`: a `:` used instead of `=` for a keyword argument, `state=AgentState` used instead of `state: AgentState`, a duplicate/stale `add_conditional_edges("execute", ...)` call (LangGraph doesn't support redefining a node's edges), and a stray extra `)` — all `SyntaxError`/compile-time failures, all fixed.
- `SqliteSaver.from_conn_string(...)` is a context-manager factory — only yields a usable saver inside `with`, which breaks a module-level `app` that other files import. Fixed by constructing `SqliteSaver` directly from a raw `sqlite3.connect(...)` connection instead.
- `tests/test_agent.py` called `app.invoke()` with no `thread_id` — confirmed this raises `ValueError` on a checkpointed graph. Fixed by giving each test case its own `thread_id`.
- Full detail in `PROJECT_PROGRESS.md`.

## 🐛 Bugs Fixed (Phase 7 — `agent.py`)

- File was named `langgraph.py`, which shadowed the real `langgraph` package on import — confirmed by the actual `ImportError` traceback pointing at itself. Renamed to `agent.py`.
- `langgraph` was never installed in the venv — installed (1.2.11), added to `requirements.txt`.
- Missing `pandas`/`DataFrame` imports despite using both — `NameError`s. Added.
- State schema/node mismatch: schema declared `validate_sql`, but the validate node wrote `validated_sql` and the execute node read `state["validate_sql"]` — guaranteed `KeyError` on any successful validation. Unified to `validated_sql`.
- `execute` node registered as `"Execute"` (capital E) but referenced as lowercase `"execute"` elsewhere — node-not-found at compile time. Also, conditional-edge maps used the string `'END'` instead of the real imported `END` sentinel, so those branches would never actually match. Both fixed.
- Full detail in `PROJECT_PROGRESS.md`'s Bugs Fixed section.

## 🐛 Bugs Fixed

- Connection string built via raw f-string broke on a password containing `@` (parsed as an extra host separator). Fixed with SQLAlchemy's `URL.create()`, which percent-encodes credentials.
- `schema.py` / `executor.py` used relative imports (`from .database import engine`) while being run as standalone scripts — `ImportError`. Fixed to absolute imports.
- `executor.py`'s retry loop had a bare `try:` with no matching `except`/`finally` — a `SyntaxError` that prevented the file from parsing at all. Restructured the try/except nesting and moved the final `raise` outside the loop.
- `executor.py` caught `sqlalchemy.exc.DBAPIError`, but `pd.read_sql()` re-wraps DB errors as `pandas.errors.DatabaseError` — the except clause never matched, so DB errors crashed instead of retrying. Fixed to catch the pandas exception type.
- `sql_safety.py`'s `validate_sql()` was typed `-> None` but returns a string — caused a type-checker false positive downstream. Fixed the annotation.
- First real query hit the read-only role's 30s `statement_timeout`: `posts` had no index on `creationdate`. Added `posts_posttypeid_creationdate_idx` via `CREATE INDEX CONCURRENTLY`.
- `pd.read_sql(validated_sql, conn)` raised `TypeError: immutabledict is not a sequence` on every query — passing a raw SQL string routes through SQLAlchemy's `exec_driver_sql`, which hands psycopg2 an empty `immutabledict` instead of `None`, and psycopg2 then tries to `%`-substitute against literal `%` in `LIKE` patterns. Fixed by wrapping the SQL in `sqlalchemy.text()`.
- A join question ("top 5 users ... about python") then hit the timeout again — `EXPLAIN` showed a full scan of ~18M question rows checking `tags LIKE '%<python>%'` row-by-row, since no existing btree index supports a leading-wildcard pattern. Added and applied a `pg_trgm` GIN index (`posts_tags_trgm_idx`). **Still times out** — the index is used correctly, but fetching the ~380K matching rows costs ~3.15M planner cost units because they're scattered across all 59.5M rows with no physical clustering by tag. Not a missing-index bug; a genuinely expensive query at this scale. Options being weighed: raise `statement_timeout` for heavy analytical queries, `CLUSTER posts` by tag (one-time, static dataset), or build a normalized tag lookup table.

## ✅ What's Done

- PostgreSQL 18 installed, `postgresql_query_ai` database created and restore verified
- Read-only role `query_ai_agent` created and tested (SELECT works, writes blocked, 30s statement timeout)
- Python project scaffold complete: venv, `requirements.txt`, `.env`, `database.py`
- Schema reflection (`schema.py`), hand-encoded FK relationships (`relationships.py`), and lookup-code documentation (`lookups.py`) merged into one structured schema
- `schema_prompt.py` renders that schema as `CREATE TABLE`-style DDL for the LLM prompt
- `sql_generator.py` (Gemini, `gemini-3.5-flash`) generates SQL from a natural-language question + schema context
- `sql_safety.py` validates single-statement SELECT-only, including a token scan that catches writable CTEs
- `executor.py` chains generation → validation → execution with a 3-attempt self-correction retry loop
- Added `posts_posttypeid_creationdate_idx` after discovering the missing index via a real timeout
- First full pipeline success: NL question → 993,601 (correct answer)
- GitHub repo scaffolded (README, LICENSE, `.gitignore`, remote configured)
- Progress tracking system established (`PROJECT_PROGRESS.md`, `project_metrics.json`, this dashboard)
- Phase 7 framework decided: LangGraph
- `agent.py`: first working `StateGraph` port of the retry loop, smoke-tested end-to-end
- `tests/test_agent.py`: difficulty-tiered sanity/latency harness, saves timestamped CSV results
- Conversational memory: `history` reducer, `record_history_node`, `SqliteSaver` checkpointer keyed by `thread_id`, history-aware `generate_sql()`
- GitHub Actions QC discussed, deliberately deferred to Phase 14 (CI can't reach the local 117GB DB)
- `backend/api.py`: FastAPI `/chat` + `/health`, CORS configured for the Vite dev origin, verified working end-to-end via curl (correct answer, HTTP 200)
- `frontend/`: React + Vite chat widget, built by Claude per the user's request (not pseudocode-first, unlike the Python files) — UI verified rendering and accepting input via screenshots
- Three real bugs found and fixed during end-to-end verification: the `DataFrame`/msgpack checkpointer crash (affected every successful query since memory was added), missing error handling in `generate_node` for Gemini API failures, and an IPv4/IPv6 `localhost` mismatch breaking the browser's `fetch()`
- MVP declared functionally ready by the user — session ends here, next session pivots to Observability + Evaluation before further bug fixing
- **Observability implemented and verified live**: `observalibilty/evaluation/metrics.py` (Prometheus `Counter`/`Histogram`s) + `observalibilty/evaluation/observability.py` (`log_node` decorator wrapping all 4 `agent.py` nodes, `log_chat_request` for `/chat` — each writes a structured JSON line to `logs/agent.log` *and* updates Prometheus in one call); `/metrics` mounted in `backend/api.py`; `docker-compose.yml` runs Prometheus + Grafana; a 7-panel Grafana dashboard pushed via API, confirmed rendering real scraped data via a live browser check
- Two real findings surfaced immediately from the new instrumentation: `votes` has no `creationdate` index (unrecovered 3/3-attempt timeout), and Gemini prefers `COUNT(*)` over `COUNT(id)` on huge tables (recoverable on retry, but wastes a 30s+ attempt) — both logged as new Open Bugs items

## 🔜 What's Left (immediate)

- [x] **Observability**: structured logging per graph node + per `/chat` request, Prometheus + Grafana with a live dashboard — done and verified
- [x] **Evaluation (first pass)**: full 9-question suite run — 5/9 clean signal, 4/9 invalidated by Gemini's daily quota. Re-run the invalidated tier once quota resets and the two confirmed bugs below are fixed
- [ ] Commit `frontend/src/api.js`'s IPv4/IPv6 fix, and get the user's confirmation that a real browser question now round-trips successfully (still pending, not currently blocking)
- [ ] **Open Bugs debugging pass** (`PROJECT_PROGRESS.md`, 8 items, priority-ordered) — start with #7 (`votes.creationdate` index) and #8 (Gemini's `COUNT(*)` preference), both already confirmed and cheap; also includes confirming memory follow-ups actually resolve correctly, which still hasn't been proven
- [ ] Decide: simple truncation vs. rolling summarization for long conversations — next memory design increment, deliberately not built yet
- [ ] Decide how to handle genuinely heavy analytical queries (raise `statement_timeout` for this class, `CLUSTER posts` by tag, or a normalized tag lookup table) — deferred, not blocking
- [ ] Consider enforcing a default `LIMIT` for un-bounded queries against huge tables

## 🔭 What's Left (whole project, at a glance)

```mermaid
pie showData
    title Phases remaining vs done (14 total)
    "Done / near-done" : 8
    "Not started" : 6
```

---

*Regenerate this file after each completed milestone — see `PROJECT_PROGRESS.md` for the authoritative log and `project_metrics.json` for machine-readable metrics.*
