# PostgreSQL Query AI — Project Progress

## Overall Progress

Completion: 41%

## Current Phase

Phase 6 — Execution / Retry (~70%, end-to-end pipeline working) → Phase 7 (Agentic Workflow) next

## Current Task

Phase 6 (Execution / Retry) first end-to-end success: "How many questions were posted in 2023?" → generated, validated, executed, returned 993,601. Full pipeline (NL question → Gemini → safety check → Postgres → DataFrame) is working. Next: broaden test coverage (joins, lookup-code questions) and start thinking about Phase 7 (agent loop / conversation handling).

## Phase Progress

```
Database Foundation     ██████████ 100%
Python Layer             ██████████ 100%
Schema Intelligence      ██████████ 100%
SQL Generation           ██████████ 100%
Safety                    ██████████ 100%
Execution / Retry         ███████░░░ 70%
Agent                     ░░░░░░░░░░ 0%
Memory                    ░░░░░░░░░░ 0%
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

## In Progress

- Phase 6 (Execution / Retry): core pipeline works; broadening test coverage before calling the phase done.

## Next

1. Test `run_question()` against harder questions: multi-table joins (e.g. "top 5 users by reputation who answered questions about python"), `votetypeid`/`linktypeid` lookup questions, and intentionally ambiguous ones — check both correctness and that the retry loop behaves sensibly on genuine failures.
2. Consider enforcing a default `LIMIT` in `sql_safety.py` (or a dedicated step) for queries without one, so a broad question against `posts` can't pull an enormous result set into memory.
3. Start Phase 7 (Agentic Workflow) once Phase 6 feels solid: wrap `run_question()` in a loop that can hold a conversation (follow-up questions referring to prior results) rather than always starting fresh.

## Blockers

- (none currently — DB verification and read-only access are both resolved)

## Bugs Fixed

- `database.py` built its connection string with a raw f-string; the DB password contains `@`, which collided with the `user:pass@host` separator and caused `psycopg2.OperationalError: could not translate host name "pal01@localhost"`. Fixed by building the URL with SQLAlchemy's `URL.create()`, which percent-encodes special characters.
- `schema.py` and `executor.py` both initially used relative imports (`from .database import engine`) despite being run as standalone scripts, not package modules — fails with `ImportError: attempted relative import with no known parent package`. Fixed to plain `from database import engine`.
- `executor.py`'s retry loop had a bare `try:` with two nested try/except pairs inside it but no matching `except`/`finally` of its own — a `SyntaxError`, so the file wouldn't even parse. Restructured so each DB/validation step has its own try/except directly, and the final `raise RuntimeError(...)` moved outside the `for` loop (it was incorrectly indented to run after every single iteration).
- `executor.py` caught `sqlalchemy.exc.DBAPIError` around `pd.read_sql()`, but pandas wraps SQLAlchemy exceptions into `pandas.errors.DatabaseError` before they propagate — `DBAPIError` never matched, so DB errors crashed the script instead of triggering a retry. Fixed to catch `pandas.errors.DatabaseError`.
- `sql_safety.py`'s `validate_sql()` was annotated `-> None` but actually returns the validated SQL string — caused a downstream type-checker false positive in `executor.py` (`pd.read_sql` flagged as possibly receiving `None`). Fixed the annotation to `-> str`.
- First real end-to-end query hit the read-only role's 30s `statement_timeout` — not a code bug, but exposed that `posts` had no index on `creationdate`. Fixed with `sql/add_indexes.sql` (see Completed).

## Technical Decisions

- **Dataset**: Stack Overflow PostgreSQL public dump (~117 GB) — realistic scale for demonstrating schema-aware retrieval, indexing awareness, and query safety on a non-trivial database, rather than a toy dataset.
- **DB engine**: PostgreSQL (already decided/installed) — richer type system, `EXPLAIN ANALYZE`, mature Python drivers, and it's the most common production RDBMS to be asked about in interviews.
- **LLM provider**: Gemini (`google-genai` SDK), not Anthropic — `requirements.txt` and `.env` updated accordingly (`GEMINI_API_KEY`). `sql_generator.py`'s prompt-construction logic (schema DDL + question → SQL) is provider-agnostic; only the client/call syntax differs.

## Tests

- (none yet — Phase 2 will introduce the first test: DB connection test)

## AI Evaluation

Questions tested: 1
SQL success rate: 100% (1/1, after the index fix — first attempt failed on timeout, second attempt after the fix succeeded)
Answer accuracy: 1/1 correct (993,601 questions in 2023 — matches expected posttypeid/date logic)
Average latency: not yet measured
Average retries: not yet meaningful at n=1

## Architecture Changes

- (none yet)

## Learning Notes

- (to be filled in as concepts are introduced, starting with Phase 1 verification and Phase 2's driver choice)
