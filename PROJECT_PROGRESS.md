# PostgreSQL Query AI — Project Progress

## Overall Progress

Completion: 43%

## Current Phase

Phase 7 — Agentic Workflow (LangGraph, ~30%, first working graph in `agent.py`)

## Current Task

Phase 7/8 crossover: `agent.py` now has conversational memory — a `history` field (LangGraph reducer, accumulates across turns instead of overwriting), a `record_history_node` that runs only on the success path, a `SqliteSaver` checkpointer keyed by `thread_id` for per-conversation isolation, and `sql_generator.generate_sql()` now accepts `history` to resolve follow-up references ("now show me the same thing but for 2022"). Deliberately scoped to *just* the memory mechanism — no truncation/summarization for long conversations yet (explicit next step once a real conversation gets long enough to need it). `tests/test_agent.py` (the sanity/latency harness built alongside this) was also updated: each test case now gets its own `thread_id` so unrelated questions don't bleed history into each other.

Both `agent.py` and `tests/test_agent.py` were hand-written by the user from pseudocode and needed real bug fixes before they'd run (see Bugs Fixed) — this is now a recurring, expected part of the workflow, not a one-off. One API-level finding worth keeping in mind for later: `SqliteSaver.from_conn_string()` is a context-manager factory (only yields a usable saver inside `with`), which doesn't work for a module-level `app` that other files import — fixed by constructing `SqliteSaver` directly from a raw `sqlite3.connect(...)` connection instead.

Earlier milestone (now superseded by the above): `agent.py` was first stood up as a faithful LangGraph port of `executor.py`'s retry loop, smoke-tested successfully ("how many questions were posted in 2025?" → 0). The full `test_agent.py` 9-question run that followed hit the Gemini free-tier daily quota (20 requests/day) partway through, so only the `easy` tier reflects real agent behavior from that run — the rest is quota exhaustion, not signal. Deeper review of that run is still deferred, not resolved.

## Phase Progress

```
Database Foundation     ██████████ 100%
Python Layer             ██████████ 100%
Schema Intelligence      ██████████ 100%
SQL Generation           ██████████ 100%
Safety                    ██████████ 100%
Execution / Retry         ███████░░░ 70%
Agent                     █████░░░░░ 50%
Memory                    ██░░░░░░░░ 20%
Visualization             ░░░░░░░░░░ 0%
API                       ░░░░░░░░░░ 0%
Frontend                  ░░░░░░░░░░ 0%
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

## In Progress

- Phase 7/8 (Agentic Workflow + Memory): core mechanism is in and smoke-tests import cleanly; not yet run against real questions to confirm follow-ups actually resolve correctly (blocked short-term by Gemini free-tier quota exhaustion from the last full test run).

## Next

1. Run `agent.py`'s smoke test (two questions, same `thread_id`: "...2023?" then "now show me the same thing but for 2022") once Gemini quota resets, to confirm the second question actually resolves "the same thing" via history rather than failing or hallucinating an unrelated query.
2. Re-run `tests/test_agent.py`'s full 9-question suite cleanly (previous run hit the 20-req/day free-tier quota partway through) — review real success/failure/latency per difficulty tier this time.
3. Decide: simple truncation (`history[-N:]`) vs. rolling summarization node for keeping long conversations within a reasonable prompt size — deliberately not built yet, this is the explicit next design increment for memory.
4. Decide how to handle genuinely heavy analytical queries like the python-join test (deferred, not blocking): raising `statement_timeout` for this query class, `CLUSTER posts` on the trigram index (one-time, static dataset) to co-locate same-tag rows, or a normalized tag lookup table (unnest `tags` — the "correct" fix for substring tag search at scale).
5. Consider enforcing a default `LIMIT` in `sql_safety.py` (or a dedicated step) for queries without one, so a broad question against `posts` can't pull an enormous result set into memory.
6. Looking ahead (not started): Phase 10 (FastAPI backend) to expose `run_question()`/`thread_id` over HTTP, then Phase 11 (frontend chat widget) — needs Phase 10 first, since a widget needs something to call.

## Blockers

- (none currently — DB verification and read-only access are both resolved)

## Deferred (revisit at Phase 14 — Deployment)

- GitHub Actions QC for `tests/test_agent.py`: blocked by the fact that CI runners can't reach the local 117GB Postgres DB. Discussed three options (small seeded Postgres service container in CI / self-hosted runner / no-DB lightweight checks only) — leaning toward the seeded-container approach since it would have caught most of today's bugs, but explicitly deferred until closer to deployment rather than decided now.

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
