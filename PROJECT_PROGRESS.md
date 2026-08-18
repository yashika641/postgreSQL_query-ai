# PostgreSQL Query AI — Project Progress

## Overall Progress

Completion: 60%

## Current Phase

Observability (Phase 13) and a first Evaluation run (Phase 12) are both done. Next: the Open Bugs debugging pass below, starting with the two cheapest confirmed fixes (#7, #8).

## Current Task (session handoff — read this first)

**Evaluation ran — real baseline, but partially contaminated by a Gemini free-tier quota limit, not code bugs:**

`tests/test_agent.py`'s full 9-question suite ran clean end-to-end (no crashes). 3/9 succeeded. Results for questions 1-4 and 7 are clean signal:
- Q1 "questions posted in 2023" — OK, 2 attempts, 105.8s (attempt 1 timed out on `COUNT(*)`, attempt 2 succeeded with `COUNT(id)` — Open Bugs #8)
- Q2 "upvotes cast in 2022" — **FAILED**, 3 attempts, 172.8s (`votes.creationdate` has no index — Open Bugs #7, all 3 attempts genuinely timed out)
- Q3 "posts marked as duplicates" — OK, 2 attempts, 53.2s
- Q4 "rep>1000, never deletion-voted" — **FAILED**, 3 attempts, 212.5s (same missing-index class of failure)
- Q7 "who are the best users" (ambiguous) — OK, 1 attempt, 3.3s

Questions 5, 6, 8, 9 all failed too, but their logs show `429 RESOURCE_EXHAUSTED` from Gemini (`generativelanguage.googleapis.com/generate_content_free_tier_requests`, **limit: 20/day/project/model**) — a single 9-question run can burn up to 27 generate calls (3 attempts × 9 questions), so the free tier ran out mid-suite. **Those 4 results are noise, not evidence those questions are broken** — don't treat them as confirmed bugs. Results saved to `eval_results_20260818_190634.csv`.

Also found while investigating: `sql_generator.py` actually calls **`gemini-3.5-flash`**, not `gemini-2.5-flash` as previously documented here — confirmed intentional by the user, docs corrected throughout this file and `docs/DASHBOARD.md`.

**Decision on the quota limit**: work around it rather than upgrading billing — test in small batches (1-2 questions) instead of full 9-question sweeps going forward, and treat any `RESOURCE_EXHAUSTED` result as noise to re-test later, not a real failure.

**Observability is done and verified working, not just written:**
- `observalibilty/evaluation/metrics.py` — Prometheus `Counter`/`Histogram` definitions (per-node duration/outcomes, per-request duration/count/attempts)
- `observalibilty/evaluation/observability.py` — `log_node` decorator (wraps all four `agent.py` graph nodes: `generate`, `validate`, `execute`, `record_history`) and `log_chat_request` (called from `backend/api.py`'s `/chat`), each writing a structured JSON line to `logs/agent.log` **and** updating the matching Prometheus metric in the same call
- `backend/api.py` mounts `/metrics` (via `prometheus_client.make_asgi_app()`) for Prometheus to scrape
- `docker-compose.yml` + `docker/prometheus.yml` run Prometheus (`localhost:9090`, scraping `host.docker.internal:8000` since uvicorn runs on the host, not in a container) and Grafana (`localhost:3000`)
- A starter Grafana dashboard (`Query AI - Observability`, uid `query-ai-observability`) was pushed via the Grafana API with 7 panels: success/failure counts, overall success rate, avg attempts, chat latency p50/p95, node duration p95 by node, node outcomes by node, requests over time. **Confirmed rendering real data via a live browser check** — the count/stat panels (success vs failure, node outcomes) show real numbers; the two `rate()`-based latency panels were still empty at verification time because too few requests had been sent for `rate()` over a 5m window to resolve — expected to populate once the Phase 12 eval suite generates real traffic, not a bug.
- Grafana's admin password had been changed via its first-login UI flow at some point (broke API access with `admin`/`admin`) — reset via `docker exec ... grafana cli admin reset-admin-password admin`, then the "update your password" prompt was explicitly **skipped** on the next login so `admin`/`admin` keeps working for future API/dashboard-provisioning calls. Worth remembering if Grafana API calls start 401ing again.

**Two real findings surfaced immediately from live instrumentation** (see Open Bugs below, added as items 7-8):
- Gemini generates `COUNT(*)` more often than `COUNT(id)` for simple count questions, which is slow enough on `posts`/`votes` to hit the 30s `statement_timeout` on attempt 1 — the retry loop recovers by regenerating (attempt 2 tends to succeed), but it's a wasted 30s+ round-trip every time. A prompt-engineering fix (nudge the schema prompt to prefer `COUNT(id)`/`COUNT(1)` on huge tables) would avoid the wasted attempt entirely.
- `votes` has no index covering `creationdate` (same class of gap `posts` had before `posts_posttypeid_creationdate_idx` was added) — a `creationdate`-filtered `votes` query ("how many upvotes were cast in 2022?") timed out on **all 3 retry attempts**, a genuine unrecovered failure, not just a slow-but-fine case.

Still outstanding from before: `frontend/src/api.js`'s IPv4/IPv6 fix is **still uncommitted** — hasn't blocked anything since the backend's been run directly, but pick it up before frontend work resumes.

**Next**: the Open Bugs debugging pass, starting with #7 (`votes` index) and #8 (`COUNT(*)` prompt nudge) since both are already confirmed and cheap, then working down the priority-ordered list. Test fixes in small batches (1-2 questions) to stay under the Gemini quota rather than re-running the full suite each time.

## Phase Progress

```
Database Foundation     ██████████ 100%
Python Layer             ██████████ 100%
Schema Intelligence      ██████████ 100%
SQL Generation           ██████████ 100%
Safety                    ██████████ 100%
Execution / Retry         ███████░░░ 70%
Agent                     ██████░░░░ 60%
Memory                    ████░░░░░░ 40%
Visualization             ░░░░░░░░░░ 0%
API                       ██████░░░░ 60%
Frontend                  █████░░░░░ 50%
Evaluation                █████░░░░░ 50%
Observability             █████████░ 90%
Deployment                ░░░░░░░░░░ 0%
```

## Completed

- PostgreSQL 18 installed (`C:\Program Files\PostgreSQL\18`)
- Database `postgresql_query_ai` created and restore formally verified by the user (tables, row counts checked)
- Read-only role `query_ai_agent` created (`sql/create_readonly_role.sql`): `SELECT`-only grants + default privileges for future tables, `default_transaction_read_only = on` as a defense-in-depth guard, `statement_timeout = 30s`. Verified: `SELECT` works, `DELETE` correctly rejected with a read-only-transaction error.
- Python project scaffold stood up: venv (`query/`), `requirements.txt` installed, `.env` + `database.py` created inside `postgreSQL_query-ai/` (both were briefly created one level up in `query_ai/` and moved in so `.gitignore`'s `.env` rule actually covers them)
- First working Python → PostgreSQL connection test passed, using `pg_class.reltuples` instead of `COUNT(*)` (the latter exceeds the role's 30s timeout on the 59.5M-row `posts` table) — closes Phase 2's entry milestone
- Schema reflection module (`schema.py`) built with SQLAlchemy `inspect()`: confirms 7 tables (no `posthistory` in this restore), pulls columns/types/PKs/indexes for each
- Implicit FK relationships hand-encoded in `relationships.py` (13 relationships across the 7 tables, since the dump has no real FK constraints) and merged into `schema.py`'s output as a `foreign_keys` list per table
- Lookup-code tables hand-documented in `lookups.py` (`posttypeid`, `votetypeid`, `linktypeid` — Stack Overflow encodes these as bare integers with no in-database lookup table)
- `schema_prompt.py` renders the reflected schema as `CREATE TABLE`-style DDL text with FK relationships and lookup-code meanings as comments — this is the exact string injected into the LLM prompt. Chose DDL over raw JSON for token efficiency and because it matches the format LLMs are most reliably trained on for SQL tasks; FKs are rendered as comments rather than real `FOREIGN KEY` clauses since the dump doesn't enforce them (orphaned references exist)
- `sql_generator.py` built with the Gemini SDK (`google-genai`, model `gemini-3.5-flash`): first end-to-end test — "How many questions were posted in 2023?" — correctly generated `SELECT COUNT(id) FROM posts WHERE posttypeid = 1 AND EXTRACT(YEAR FROM creationdate) = 2023;`, confirming the schema context (including the `posttypeid` lookup) is reaching the model correctly
- `executor.py` built: chains `generate_sql()` → `validate_sql()` → `pandas.read_sql()` against `engine`, with a self-correction retry loop (max 3 attempts) that feeds the previous error back into the next `generate_sql()` call
- Added `posts_posttypeid_creationdate_idx` (`sql/add_indexes.sql`, built `CONCURRENTLY`) after the first real end-to-end run hit the read-only role's 30s `statement_timeout` on a date-filtered query — `posts` had no index covering `creationdate` despite that being one of the most common query shapes. Added `sql/check_index_progress.sql` (queries `pg_stat_progress_create_index`) for monitoring long index builds.
- First full pipeline success: "How many questions were posted in 2023?" → 993,601 (NL question → Gemini → safety validation → Postgres → DataFrame, end to end)
- GitHub repo scaffold in place (`postgreSQL_query-ai`): README, LICENSE, `.gitignore`, remote `origin` set to `github.com/yashika641/postgreSQL_query-ai`
- Project mentoring framework agreed (this file + `project_metrics.json` + `docs/DASHBOARD.md`)
- Phase 7 framework decision: LangGraph, over Google ADK / plain custom loop / CrewAI
- `agent.py`: first working LangGraph `StateGraph` port of `executor.py`'s retry loop (`generate` → `validate` → `execute` nodes, conditional edges back to `generate` on error), smoke-tested successfully end-to-end
- `tests/test_agent.py`: sanity/latency test harness — runs a difficulty-tiered question set through `app.invoke()` directly (not `run_question()`, to get full state incl. `attempts`), times each with `time.perf_counter()`, saves results to a timestamped CSV
- `agent.py` + `sql_generator.py`: conversational memory — `history` reducer field, `record_history_node`, `SqliteSaver` checkpointer keyed by `thread_id`, `generate_sql()` now prompt-injects prior turns
- GitHub Actions QC discussed and deliberately deferred to Phase 14 (see Deferred section) — CI runners can't reach the local 117GB DB
- `backend/api.py`: FastAPI app, `/chat` (wraps `agent.app.invoke()` directly to expose the generated SQL alongside results, not just via `run_question()`) and `/health`, CORS configured for the Vite dev origin
- `frontend/`: React + Vite chat widget (`ChatWidget.jsx`, `ResultTable.jsx`, `api.js`, styling) — built end-to-end by Claude per the user's explicit request ("not interested in frontend"), not pseudocode-first like the Python files
- Found + fixed a real bug present since memory was added: `AgentState.result` (a raw `DataFrame`) isn't msgpack-serializable, so `SqliteSaver` crashed on every successful query once persistence was in the picture — changed `result` to a JSON-safe `{"columns", "rows"}` dict across `agent.py`, `backend/api.py`, `tests/test_agent.py`
- Found + fixed a second real bug: `generate_node` had no error handling for the Gemini call itself — added `after_generate` conditional routing so API errors retry like any other node failure instead of crashing the graph
- End-to-end verified via curl: NL question → Gemini → safety → Postgres → checkpointed state → HTTP JSON response, correct answer, no crash
- Found + fixed a third real bug, this one by the user testing in a real browser (not automation): `localhost` resolves to IPv6 (`::1`) on this machine, uvicorn only binds IPv4 (`127.0.0.1`) — `frontend/src/api.js` hardcoded to target `127.0.0.1:8000` explicitly. **Uncommitted** — first thing to do next session.
- MVP declared functionally ready by the user; session ends here, next session pivots to Observability + Evaluation before further bug fixing (explicit user decision)
- **Observability implemented and verified end-to-end**: `observalibilty/evaluation/{metrics,observability}.py` (Prometheus metrics + structured JSON logging via one shared `log_node` decorator + `log_chat_request`), wired into all four `agent.py` graph nodes and `backend/api.py`'s `/chat`; `/metrics` endpoint mounted; `docker-compose.yml` running Prometheus + Grafana; a 7-panel Grafana dashboard pushed via API and confirmed rendering real scraped data in a live browser check. Surfaced two real findings immediately (missing `votes.creationdate` index; Gemini's `COUNT(*)` vs `COUNT(id)` preference) — added as Open Bugs items 7-8.

## In Progress

- Session handoff: MVP works end-to-end (backend confirmed via curl; frontend fixed for the IPv4/IPv6 issue but not yet re-confirmed by the user in-browser, and that fix isn't committed yet). Next session starts with Observability, not bug fixes — see Current Task above and Next below.

## Next

1. **First thing next session**: commit the uncommitted `frontend/src/api.js` IPv4/IPv6 fix, and confirm with the user that a real browser question now round-trips successfully (this confirmation was still pending when this session ended).
2. **Observability** (user's explicit priority — before bug fixing): structured logging per graph node (timing + outcome: which node ran, how long, success/failure) and per `/chat` request in `backend/api.py` (question, `thread_id`, total latency, attempts used). Persist somewhere reviewable — likely Python's `logging` module + `rich` (already in `requirements.txt`), not raw uvicorn stdout.
3. **Evaluation**: re-run `tests/test_agent.py`'s full 9-question suite cleanly now that the DataFrame and generate_node bugs are both fixed — previous runs were invalidated first by Gemini quota exhaustion, then by the DataFrame serialization bug (would have failed every successful case regardless). This will be the first real signal on success/failure/latency per difficulty tier. Feed real numbers into the AI Evaluation section below.
4. **Then the debugging pass** — see Open Bugs below, already roughly priority-ordered.

## Open Bugs (compiled for the next debugging pass — not yet fixed)

1. **`generate_node` only catches `google.genai.errors.APIError`** — a different Gemini SDK failure mode (e.g. a client-side timeout) may not subclass `APIError` and would still crash the graph uncaught. `backend/api.py`'s `/chat` also has no catch-all around `agent_app.invoke()` beyond the `RuntimeError`→422 path — any other uncaught exception surfaces as a bare, undiagnosable 500. **Highest priority**: most likely to produce another confusing unhandled-error bug, and observability work will make it easy to actually pin down once instrumented.
2. **`sql_generator.generate_sql()` doesn't validate Gemini's output before returning it** — an empty string or a refusal instead of SQL would pass straight to `validate_sql()` with no earlier, clearer error.
3. **Conversational memory has never been proven to actually work** — the two-question follow-up test ("now show me the same thing but for 2022") has never successfully run. The crash blocking it is fixed, but nobody has seen a follow-up resolve correctly yet.
4. **No default `LIMIT` enforcement** in `sql_safety.py` — an unbounded broad question against `posts` can pull an enormous result set into memory with nothing stopping it. Small, contained, no dependencies on anything else.
5. **No truncation/summarization for long conversation history** — `generate_sql()` dumps the *entire* `history` into every prompt with no cap. Fine now, will grow prompt size/cost unboundedly on a long conversation. Bigger design decision (truncation vs. rolling summarization), tackle once everything else is solid.
6. **Heavy analytical queries still time out** — the python-join question and the "average reputation per tag" stress question both hit the 30s `statement_timeout` on every attempt. Root-caused (not a missing-index problem, genuinely expensive at 59.5M-row scale). Three options already scoped: raise `statement_timeout` for this query class, `CLUSTER posts` by tag, or normalize `tags` into its own lookup table. Biggest design decision of the list, tackle last.
7. **`votes` has no index covering `creationdate`** — found via the new observability logs: "how many upvotes were cast in 2022?" timed out on all 3 attempts (every attempt generated a `creationdate`-range-filtered `COUNT`). Same class of fix as `posts_posttypeid_creationdate_idx` — small, contained, high-confidence fix.
8. **Gemini prefers `COUNT(*)` over `COUNT(id)`/`COUNT(1)` for simple counts**, which is slow enough on `posts`/`votes` to hit the 30s timeout on attempt 1 even when the retry recovers — a wasted 30s+ round-trip on otherwise-simple questions. Fix is prompt engineering (nudge `schema_prompt.py` to prefer `COUNT(id)` on large tables), not a code bug. Worth doing alongside item 7 since both showed up in the same observability session.

## Blockers

- (none currently — DB verification and read-only access are both resolved)

## Deferred (revisit at Phase 14 — Deployment)

- GitHub Actions QC for `tests/test_agent.py`: blocked by the fact that CI runners can't reach the local 117GB Postgres DB. Discussed three options (small seeded Postgres service container in CI / self-hosted runner / no-DB lightweight checks only) — leaning toward the seeded-container approach since it would have caught most of today's bugs, but explicitly deferred until closer to deployment rather than decided now.

## Bugs Fixed (Phase 10/11 — backend + frontend verification)

- `AgentState.result` was a raw `pandas.DataFrame`. Once `SqliteSaver` (Phase 8) was compiled into the graph, it persists the *entire* state after every node via msgpack serialization — and `DataFrame` has no msgpack representation. This meant **every successful query would crash**, not an edge case — confirmed via the actual traceback (`TypeError: Type is not msgpack serializable: DataFrame`, raised from `SqliteSaver.put_writes` → `ormsgpack.packb`). This bug existed from the moment memory was added but was never triggered until this session's real end-to-end test, because `tests/test_agent.py` calls `app.invoke()` directly and only checks `final_state["result"] is not None` / `len(...)` — it never actually let the checkpointer *finish* persisting a successful state in a way that surfaced the serialization step failing loudly (the earlier full-suite run hit quota exhaustion before any question could reach this code path). Fixed by changing `result` to `{"columns": [...], "rows": [...]}` (plain JSON-safe types) in `execute_node`, updating `record_history_node` (`len(state["result"]["rows"])`), `run_question()` (reconstructs a `DataFrame` from the dict before returning, preserving its documented return type), `backend/api.py`'s `/chat` handler, and `tests/test_agent.py`'s `rows_returned` computation.
- `generate_node` had no error handling around the Gemini call — only `validate_node`/`execute_node` caught their own failure modes. A transient `google.genai.errors.APIError` (both a 429 rate-limit and a 503 "high demand" were genuinely observed today) crashed straight out of `app.invoke()` uncaught. `backend/api.py` didn't catch it either, so it surfaced as a bare unhelpful 500. Fixed by catching `APIError` in `generate_node` (returns it into `state["error"]` like any other node) and adding a new `after_generate` conditional router — mirroring `after_validate`/`after_execute` — so `generate → validate` is no longer a fixed edge; a generation failure now retries through the same attempt-counted loop instead of crashing.
- `backend/api.py`'s `ChatResponse.columns` was typed `list[dict]` instead of `list[str]` — column names are strings, so this would fail Pydantic response validation on every successful call. Fixed.
- Confirmed NOT a bug (checked, not assumed): `backend/api.py` living in a `backend/` subdirectory while `agent.py` stays in the project root works fine for imports, because `uvicorn backend.api:app` run from the project root puts the root on `sys.path` — unlike `tests/test_agent.py`'s situation, which needed an explicit `sys.path.insert`.
- User tested in a real (non-automated) browser and hit "Failed to fetch" on `/chat` despite curl working fine against the same endpoint. Root cause: `localhost` resolves to the IPv6 loopback (`::1`) on this machine (confirmed via `ping localhost`), but uvicorn only binds the IPv4 loopback (`127.0.0.1`, confirmed via its own startup log) — the frontend's `fetch("http://localhost:8000/...")` was silently trying the wrong address family. Fixed by hardcoding `frontend/src/api.js`'s `API_BASE` to `http://127.0.0.1:8000`. Not yet committed.

## Bugs Fixed (Phase 8 — conversational memory)

- `sql_generator.py`: `generate_sql()`'s signature wasn't updated to accept `history` even though the function body referenced it (`if history:`) — guaranteed `NameError` on every call. Also `conversation_context` was built but never actually inserted into `user_message`, so even once fixed it wouldn't have reached the model. Both fixed.
- `agent.py` line `history:state.get("history",[])` used `:` instead of `=` for a keyword argument — `SyntaxError`.
- `agent.py`'s `record_history_node(state=AgentState)` used `=` (making the `AgentState` class itself a default value) instead of `:` (type annotation) — should be `state: AgentState`.
- `agent.py` had `builder.add_conditional_edges("execute", ...)` called twice — once with the old two-way mapping (pre-memory), once with the new three-way mapping including `record_history`. LangGraph doesn't support redefining a node's conditional edges; removed the stale first call.
- `agent.py`: stray extra `)` on `app = builder.compile(checkpointer=checkpointer))` — `SyntaxError`.
- `agent.py`: `SqliteSaver.from_conn_string("agent_memory.sqlite")` returns a context-manager generator, only yielding a usable `SqliteSaver` inside a `with` block — assigning it directly gave `builder.compile()` a context manager instead of a checkpointer. Since `app` needs to stay alive at module scope for other files (`tests/test_agent.py`) to import, switched to constructing `SqliteSaver` directly from a raw connection: `SqliteSaver(sqlite3.connect("agent_memory.sqlite", check_same_thread=False))`.
- `agent.py`'s smoke test called `run_question(test_question)` with `thread_id` now a required parameter — missing-argument `TypeError`. Fixed, and upgraded to two sequential calls on the same `thread_id` so the smoke test actually demonstrates memory working, not just that the function runs.
- `tests/test_agent.py`: `app.invoke()` was called with no `config`/`thread_id` at all — confirmed via direct test that a checkpointed graph raises `ValueError: Checkpointer requires one or more of the following 'configurable' keys: thread_id, ...` without one. Fixed by giving each test case its own `thread_id` (`eval-{i}-{difficulty}`) so unrelated test questions don't bleed history into each other.

## Bugs Fixed (Phase 7 — `agent.py`)

- File was originally named `langgraph.py`, which shadowed the real installed `langgraph` package on `from langgraph import ...` (same directory wins over site-packages) — caused `ImportError: cannot import name 'State' from 'langgraph'` pointing at itself, confirmed by the actual traceback the user hit. Fixed by renaming to `agent.py`.
- `langgraph` was never in `requirements.txt` / installed in the venv — would have been the next failure even after the rename. Installed `langgraph` (1.2.11) into `query/`.
- `from langgraph import State` and `from click import group` were unused/incorrect imports (no `State` export exists on `langgraph`; `click.group` unrelated, likely autocomplete noise) — removed.
- `Stategraph` (wrong capitalization/casing of `StateGraph`) — fixed.
- `pandas` was never imported (only `from pandas.errors import DatabaseError`) despite calling `pd.read_sql()` — `NameError`. Added `import pandas as pd`.
- `DataFrame` used as a type hint in two places but never imported — `NameError` at file-load time (return-type annotations evaluate eagerly without `from __future__ import annotations`). Added `from pandas import DataFrame`.
- State schema declared the field `validate_sql` (shadowing the imported `validate_sql` function name) while `validate_node` actually wrote `validated_sql` and `initial_state` also used `validated_sql` — `execute_node` read the never-set key `state["validate_sql"]`, guaranteed `KeyError` on any successful validation. Unified everything to `validated_sql`.
- `execute` node was registered as `"Execute"` (capital E) but `add_conditional_edges("execute", ...)` and the edge-mapping dicts referenced lowercase `"execute"` — node-not-found error at compile/invoke. Unified to lowercase `"execute"` throughout, matching `"generate"`/`"validate"`.
- Conditional-edge mapping dicts used the string `'END'` as both key and value, but the router functions return the actual `END` sentinel object imported from `langgraph.graph` — a string never matches the sentinel by `==`. Fixed to use the real `END` object as the dict key/value.
- `run_question`'s final error message used single-quoted f-string with a single-quoted key access nested inside (`f'...{final_state['error']}'`) — a `SyntaxError` pre-3.12. Fixed by switching the outer quotes to double.

## Bugs Fixed

- `database.py` built its connection string with a raw f-string; the DB password contains `@`, which collided with the `user:pass@host` separator and caused `psycopg2.OperationalError: could not translate host name "pal01@localhost"`. Fixed by building the URL with SQLAlchemy's `URL.create()`, which percent-encodes special characters.
- `schema.py` and `executor.py` both initially used relative imports (`from .database import engine`) despite being run as standalone scripts, not package modules — fails with `ImportError: attempted relative import with no known parent package`. Fixed to plain `from database import engine`.
- `executor.py`'s retry loop had a bare `try:` with two nested try/except pairs inside it but no matching `except`/`finally` of its own — a `SyntaxError`, so the file wouldn't even parse. Restructured so each DB/validation step has its own try/except directly, and the final `raise RuntimeError(...)` moved outside the `for` loop (it was incorrectly indented to run after every single iteration).
- `executor.py` caught `sqlalchemy.exc.DBAPIError` around `pd.read_sql()`, but pandas wraps SQLAlchemy exceptions into `pandas.errors.DatabaseError` before they propagate — `DBAPIError` never matched, so DB errors crashed the script instead of triggering a retry. Fixed to catch `pandas.errors.DatabaseError`.
- `sql_safety.py`'s `validate_sql()` was annotated `-> None` but actually returns the validated SQL string — caused a downstream type-checker false positive in `executor.py` (`pd.read_sql` flagged as possibly receiving `None`). Fixed the annotation to `-> str`.
- First real end-to-end query hit the read-only role's 30s `statement_timeout` — not a code bug, but exposed that `posts` had no index on `creationdate`. Fixed with `sql/add_indexes.sql` (see Completed).
- `executor.py`'s `pd.read_sql(validated_sql, conn)` raised `TypeError: sqlalchemy.cyextension.immutabledict.immutabledict is not a sequence` on every query. Root cause: passing a raw SQL string (not a `text()` object) into `pd.read_sql` with a SQLAlchemy `Connection` routes through `exec_driver_sql`, which hands psycopg2 an empty `immutabledict` as query params instead of `None` — psycopg2 then tries to `%`-substitute against the SQL text and chokes on the literal `%` characters in `LIKE` patterns. Fixed by wrapping the SQL in `sqlalchemy.text()` before passing it to `pd.read_sql`, which routes through `connection.execute()` instead.
- Testing a join question ("top 5 users by reputation who answered questions about python") hit the 30s `statement_timeout` again after the above fix — `EXPLAIN` showed the planner doing a parallel scan of all ~18M `posttypeid=1` rows and checking `tags LIKE '%<python>%'` row-by-row, since none of the existing btree indexes on `tags` support a leading-wildcard pattern. Added a `pg_trgm` GIN index (`posts_tags_trgm_idx`) to `sql/add_indexes.sql` and applied it (confirmed `indisvalid = t`). **Did not fix the timeout** — re-running the join test still times out. `EXPLAIN` (with `enable_hashjoin`/`enable_seqscan` toggled off to compare plans) shows the trigram index is being used correctly, but fetching the ~380K matching rows itself costs ~3.15M planner cost units via bitmap heap scan because tag matches are scattered across all 59.5M rows with no physical clustering — not a missing-index problem, a genuinely expensive query at this scale. See Current Task / Next for options under consideration.

## Technical Decisions

- **Dataset**: Stack Overflow PostgreSQL public dump (~117 GB) — realistic scale for demonstrating schema-aware retrieval, indexing awareness, and query safety on a non-trivial database, rather than a toy dataset.
- **DB engine**: PostgreSQL (already decided/installed) — richer type system, `EXPLAIN ANALYZE`, mature Python drivers, and it's the most common production RDBMS to be asked about in interviews.
- **LLM provider**: Gemini (`google-genai` SDK), not Anthropic — `requirements.txt` and `.env` updated accordingly (`GEMINI_API_KEY`). `sql_generator.py`'s prompt-construction logic (schema DDL + question → SQL) is provider-agnostic; only the client/call syntax differs.

## Tests

- (none yet — Phase 2 will introduce the first test: DB connection test)

## AI Evaluation

**First full 9-question suite run (2026-08-18, `eval_results_20260818_190634.csv`).** Only questions 1-4 and 7 are clean signal — 5, 6, 8, 9 hit Gemini's 20-req/day free-tier quota mid-run and are excluded, not counted as failures.

Questions tested (clean signal): 5
SQL success rate: 60% (3/5) — successes: "questions posted in 2023" (2 attempts, 105.8s), "posts marked as duplicates" (2 attempts, 53.2s), "who are the best users" (1 attempt, 3.3s). Failures: "upvotes cast in 2022" and "rep>1000, never deletion-voted" — both genuine unrecovered timeouts (missing `votes.creationdate` index, Open Bugs #7), not generation errors.
Answer accuracy: 100% on completed queries
Average latency: 65.9s across the 5 clean results (105.8, 53.2, 3.3s for successes; 172.8, 212.5s for the two timeout failures) — dominated by the 30s-per-timed-out-attempt cost, not generation time
Average retries: 2/2 on the two failures (hit MAX_ATTEMPTS=3 but counted from 0), 1.7 average attempts across successes (2, 2, 1)

*Not yet measured cleanly: questions 5, 6, 8, 9 (hard/stress tier) — re-run once daily quota resets, in small batches.*

## Architecture Changes

- (none yet)

## Learning Notes

- (to be filled in as concepts are introduced, starting with Phase 1 verification and Phase 2's driver choice)
