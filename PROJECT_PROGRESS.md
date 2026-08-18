# PostgreSQL Query AI — Project Progress

## Overall Progress

Completion: 56%

## Current Phase

Phase 10/11 — FastAPI Backend + React Frontend (user explicitly chose to build these before finishing Phase 7/8 validation/testing — see Deferred)

## Current Task

Backend (`backend/api.py`) and frontend (`frontend/`, React + Vite) now exist and were verified working end-to-end for real — not just smoke-tested in isolation. That verification surfaced a genuinely important bug that had been silently waiting in the memory design since it was added: `AgentState.result` held a raw `pandas.DataFrame`, but `SqliteSaver` (added for Phase 8 memory) persists the **entire state** after every node via msgpack, and `DataFrame` isn't msgpack-serializable — so **every single successful query would have crashed** once memory was wired in, not just edge cases. Confirmed via the actual traceback (`TypeError: Type is not msgpack serializable: DataFrame`, inside `SqliteSaver.put_writes`). Fixed by changing `AgentState.result` to a plain JSON-safe `{"columns": [...], "rows": [...]}` dict instead of a DataFrame — `execute_node`, `record_history_node`, `run_question()` (reconstructs a `DataFrame` before returning, to preserve its documented return type for CLI/test callers), `backend/api.py`, and `tests/test_agent.py` all updated to match.

Also found and fixed during the same verification pass: `generate_node` had no error handling around the Gemini call itself (only `validate_node`/`execute_node` had try/except for their own failure modes) — a transient API error (429 rate limit, 503 overload, both genuinely observed today) crashed straight out of the graph uncaught, past `api.py`'s own missing error handling, surfacing as a bare unhelpful 500. Fixed by catching `google.genai.errors.APIError` in `generate_node` and adding a proper `after_generate` conditional router (mirroring `after_validate`/`after_execute`) so a generation failure retries through the same attempt-counted loop instead of crashing.

End-to-end proof: `curl -X POST http://localhost:8000/chat -d '{"question":"How many questions were posted in 2023?"}'` → HTTP 200, correct answer (993,601), in 43.6s (real Gemini latency, not a hang). The React chat widget renders and accepts input correctly (verified via screenshots), but the actual browser→backend fetch could not be verified end-to-end through browser automation — the automated test tab enforces an ~8.6s fetch timeout, well under Gemini's real ~15-45s response time, and this is confirmed to be a constraint of the automation tooling itself (a plain `fetch()` to `/health` succeeds instantly; only the long-running `/chat` call is affected). A normal (non-automated) browser tab has no such limit. **User needs to verify the full browser flow themselves** — both dev servers are left running (`localhost:5173` frontend, `localhost:8000` backend).

Phase 7/8 (agentic workflow + conversational memory) mechanism is now more solid than before this session (the DataFrame bug fix and the generate-error-handling fix both apply there too — this wasn't backend-specific work, it fixed real defects in `agent.py` itself), but the deliberate validation steps from before (two-question memory smoke test proving follow-ups resolve correctly, full clean `tests/test_agent.py` run) are still not done — see Deferred.

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
Evaluation                ░░░░░░░░░░ 0%
Observability             ░░░░░░░░░░ 0%
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
- `sql_generator.py` built with the Gemini SDK (`google-genai`, model `gemini-2.5-flash`): first end-to-end test — "How many questions were posted in 2023?" — correctly generated `SELECT COUNT(id) FROM posts WHERE posttypeid = 1 AND EXTRACT(YEAR FROM creationdate) = 2023;`, confirming the schema context (including the `posttypeid` lookup) is reaching the model correctly
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

## In Progress

- Phase 10/11 (Backend + Frontend): backend verified working end-to-end for real (curl). Frontend UI verified rendering/accepting input, but the actual browser→backend chat call is unverified — browser-automation tooling's ~8.6s fetch timeout is shorter than Gemini's real response time, so this specific check needs the user to do it themselves in a normal tab. Both dev servers left running (`localhost:5173`, `localhost:8000`).

## Next

1. **User**: open `http://localhost:5173` in a normal browser tab and confirm a real question round-trips correctly through the actual chat widget (this is the one thing automation couldn't verify).
2. Run `agent.py`'s two-question memory smoke test (same `thread_id`: "...2023?" then "now show me the same thing but for 2022") to confirm follow-ups actually resolve via history — still not done, now more likely to actually work given today's two bug fixes, but not yet proven.
3. Re-run `tests/test_agent.py`'s full 9-question suite cleanly — previous runs were invalidated first by Gemini quota exhaustion, then by the DataFrame serialization bug (which would have failed every successful case anyway). This will be the first real signal on success/failure/latency per difficulty tier.
4. Decide: simple truncation (`history[-N:]`) vs. rolling summarization node for keeping long conversations within a reasonable prompt size — still not built.
5. Decide how to handle genuinely heavy analytical queries like the python-join test (deferred, not blocking): raising `statement_timeout` for this query class, `CLUSTER posts` on the trigram index, or a normalized tag lookup table.
6. Consider enforcing a default `LIMIT` in `sql_safety.py` for queries without one.
7. `frontend/App.jsx`'s shell is minimal (just renders `ChatWidget`) — fine as-is, but any visual polish is the user's call since they've opted out of frontend work.

## Blockers

- (none currently — DB verification and read-only access are both resolved)

## Deferred (revisit at Phase 14 — Deployment)

- GitHub Actions QC for `tests/test_agent.py`: blocked by the fact that CI runners can't reach the local 117GB Postgres DB. Discussed three options (small seeded Postgres service container in CI / self-hosted runner / no-DB lightweight checks only) — leaning toward the seeded-container approach since it would have caught most of today's bugs, but explicitly deferred until closer to deployment rather than decided now.

## Bugs Fixed (Phase 10/11 — backend + frontend verification)

- `AgentState.result` was a raw `pandas.DataFrame`. Once `SqliteSaver` (Phase 8) was compiled into the graph, it persists the *entire* state after every node via msgpack serialization — and `DataFrame` has no msgpack representation. This meant **every successful query would crash**, not an edge case — confirmed via the actual traceback (`TypeError: Type is not msgpack serializable: DataFrame`, raised from `SqliteSaver.put_writes` → `ormsgpack.packb`). This bug existed from the moment memory was added but was never triggered until this session's real end-to-end test, because `tests/test_agent.py` calls `app.invoke()` directly and only checks `final_state["result"] is not None` / `len(...)` — it never actually let the checkpointer *finish* persisting a successful state in a way that surfaced the serialization step failing loudly (the earlier full-suite run hit quota exhaustion before any question could reach this code path). Fixed by changing `result` to `{"columns": [...], "rows": [...]}` (plain JSON-safe types) in `execute_node`, updating `record_history_node` (`len(state["result"]["rows"])`), `run_question()` (reconstructs a `DataFrame` from the dict before returning, preserving its documented return type), `backend/api.py`'s `/chat` handler, and `tests/test_agent.py`'s `rows_returned` computation.
- `generate_node` had no error handling around the Gemini call — only `validate_node`/`execute_node` caught their own failure modes. A transient `google.genai.errors.APIError` (both a 429 rate-limit and a 503 "high demand" were genuinely observed today) crashed straight out of `app.invoke()` uncaught. `backend/api.py` didn't catch it either, so it surfaced as a bare unhelpful 500. Fixed by catching `APIError` in `generate_node` (returns it into `state["error"]` like any other node) and adding a new `after_generate` conditional router — mirroring `after_validate`/`after_execute` — so `generate → validate` is no longer a fixed edge; a generation failure now retries through the same attempt-counted loop instead of crashing.
- `backend/api.py`'s `ChatResponse.columns` was typed `list[dict]` instead of `list[str]` — column names are strings, so this would fail Pydantic response validation on every successful call. Fixed.
- Confirmed NOT a bug (checked, not assumed): `backend/api.py` living in a `backend/` subdirectory while `agent.py` stays in the project root works fine for imports, because `uvicorn backend.api:app` run from the project root puts the root on `sys.path` — unlike `tests/test_agent.py`'s situation, which needed an explicit `sys.path.insert`.

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

Questions tested: 2
SQL success rate: 50% (1/2) — "questions posted in 2023?" succeeded (993,601, matches expected logic); "top 5 users by reputation who answered questions about python" generated correct-looking SQL each of 3 retry attempts but timed out at 30s on all three (genuine query cost, not a generation error)
Answer accuracy: 1/1 on completed queries (the timeout case never produced an answer to check)
Average latency: not yet measured
Average retries: 3/3 (max) on the timeout case, 0 on the first success

## Architecture Changes

- (none yet)

## Learning Notes

- (to be filled in as concepts are introduced, starting with Phase 1 verification and Phase 2's driver choice)
