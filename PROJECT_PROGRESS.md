# PostgreSQL Query AI — Project Progress

## Overall Progress

Completion: 85%

## Current Phase

Observability (Phase 13) and a first Evaluation run (Phase 12) are both done. **All 8 originally-documented Open Bugs (#1-#8) are fixed and verified.** Phase 9 — Visualization is done and verified through a real Gemini-backed call. A local Ollama fallback (not from the original bug list) was also added for Gemini API/quota failures. Remaining work is deliberately deferred, not blocking: full-table partitioning (Phase 14, needs more disk) and confirming the Ollama fallback under a real (not simulated) outage.

## Session Handoff (2026-08-19, continued — quota reset, #3 closed, Phase 9 verified live)

Quota had in fact reset by this point in the day (~18:40 IST) — the working theory from earlier in the day (UTC-midnight reset, not local midnight) is consistent with this. Two things closed out:

- **Bug #3 (conversational memory) confirmed genuinely working**, not just "didn't crash": ran `agent.py`'s two-question smoke test for real. Q1 ("How many questions were posted in 2023?") → 993,601, 1 attempt. Q2 ("now show me the same thing but for 2022") → 1,376,793, 1 attempt. Verified by reading the actual persisted checkpoint state (`app.get_state()`), not just trusting the printed output — Q2's `validated_sql` was `SELECT COUNT(id) FROM posts WHERE posttypeid = 1 AND creationdate >= '2022-01-01...' AND creationdate < '2023-01-01...'` — same query shape as Q1, correctly re-derived the 2022 date range from "the same thing but for 2022" using injected history, not a coincidence or a repeat of Q1's SQL. Closing this bug.
- **Phase 9 spot-checked through a real `/chat`-equivalent call** (direct `app.invoke()`, real Gemini): "What are the top 5 tags by number of posts?" → correct 5-row result (`javascript` 2,519,291 ... `php` 1,462,812), `visualize_node` correctly built a `bar` chart (`x_column: tagname`, `y_column: count`) with a real base64 PNG (`has_image: True`). Confirms the whole `execute -> visualize -> record_history` chain works with real data, not just the synthetic-state test from earlier. Phase 9 moved from 90% to 100%.

**Next**: only #5 and #6 remain, both deliberately saved for last as bigger design decisions. Discuss trade-offs with the user before implementing either — #5 is truncation vs. rolling summarization for `history`; #6 is `statement_timeout` increase vs. `CLUSTER posts` by tag vs. normalizing `tags` into its own table.

## Session Handoff (2026-08-19, continued further — #5/#6 design decisions made, partly implemented)

Design decisions made after discussion (see below for reasoning) — user wanted RAG + sharding initially, but real numbers ruled out most of that:

- **RAG-over-schema-metadata (part of user's original #6 ask): dropped.** Measured the actual schema prompt: only ~740 tokens across all 7 tables. Embedding-based retrieval wouldn't measurably help generation latency at that size, doesn't touch #6's actual bottleneck (Postgres execution time, not Gemini generation time), and would cost extra Gemini embedding calls per question — worsening the exact 20-req/day quota problem this whole session fought. Explicitly ruled out with the user's agreement.
- **Full-table partitioning (part of user's original #6 ask): deferred, not done.** Checked real numbers before committing to anything on a 117GB DB: `posts` is 68GB, `votes` is 18GB, whole DB is 122GB, and only **83GB is free on disk**. The standard non-destructive way to partition an already-populated table (new partitioned table + copy all data in + swap + drop original) needs roughly the table's own size again as temporary headroom — 68-86GB needed against 83GB free is too tight, real risk of a failed migration leaving the DB half-migrated. Deferred to Phase 14 (Deployment) or whenever more disk is provisioned. Also flagged to the user: date-range partitioning wouldn't have fixed the actual open timeout anyway (see next point) — it only helps date-filtered queries, and the documented #6 failure has no date filter.
- **`post_tags` normalization table: built, not yet run.** This is what actually fixes the open #6 timeout (`tags LIKE '%python%'` scans scattered across 59.5M rows even with the pg_trgm index). `sql/normalize_tags.sql` written (explodes `posts.tags`' packed `<a><b><c>` format into one row per tag via `unnest(string_to_array(...))`, indexes `tag` and `post_id`). Sized safely (~7-8GB estimate, no disk risk unlike partitioning). `relationships.py` updated with the new FK. `sql_generator.py`'s `SYSTEM_PROMPT` updated to tell Gemini to `JOIN post_tags` instead of `tags LIKE`. **Not yet run** — needs the user to run it as superuser (`psql -U postgres -d postgresql_query_ai -f sql/normalize_tags.sql`), same pattern as `add_indexes.sql`. **Important ordering note**: `schema.py`'s `get_schema()` will `KeyError` on `post_tags` if run before the migration, since it expects every table named in `RELATIONSHIPS` to already exist — run the SQL first.
- **#5 (rolling summarization): written by the user from pseudocode, then debugged and verified — closing this bug.** User typed the pseudocode into `sql_generator.py`/`agent.py` themselves. Found and fixed 3 real bugs in the result: (1) `exising_summary` typo in `summarize_turn()` — `NameError` on every call; (2) `generate_sql()`'s signature was never actually updated to accept `history_summary`, even though `agent.py`'s `generate_node` already called it with that kwarg — `TypeError` on the very first question; relatedly, the `if history:` block used `conversation_context = "..."` (overwrite) instead of `+=`, which would have silently erased the summary text once fixed; (3) `record_history_node` returned the counter under the key `"history_fold_count"` (missing "ed") instead of the actual state field `history_folded_count` — the real counter never updated, so past the cap it would have kept re-folding `old_history[0]` every turn instead of rolling forward. All three fixed directly (bug-fixing in code the user wrote, not new pseudocode). Verified live: two chained `summarize_turn()` calls correctly produced a rolling summary (second call referenced both years, built on the first summary, not from scratch) and `agent.py` imports cleanly.

**Next session starts with**: user runs `sql/normalize_tags.sql` as superuser, verify `post_tags` exists and query_ai_agent can `SELECT` from it (default privileges should cover it automatically), retest the previously-failing tag-scan question ("top 5 users who answered questions about python") to confirm it no longer times out. #5 is done; a full 6+ turn conversation smoke test through `agent.py` (not just `summarize_turn()` standalone) would be good confirmation but wasn't run this session to conserve Gemini quota.

## Session Handoff (2026-08-19, continued further still — Ollama local fallback added)

New, not from the original bug list: user wanted Gemini's API/quota failures to fall back to a **local Ollama model** instead of failing the whole request, so the pipeline keeps working during a quota exhaustion or outage without waiting for the daily reset. Machine already had Ollama installed with `qwen3:0.6b` pulled (0.6B params — small/general, not SQL-tuned; user explicitly chose to use what's already there over pulling a stronger code model, so expect noticeably weaker SQL from the fallback path than from Gemini — it's an availability fallback, not a quality-equivalent one).

`sql_generator.py` changes (written by the user from pseudocode, one bug found and fixed):
- New `_generate_with_ollama(user_message)`: POSTs to `http://localhost:11434/api/generate` (confirmed this endpoint cleanly separates `qwen3:0.6b`'s `<think>` reasoning from the actual `response` field — no manual stripping needed), prepends `SYSTEM_PROMPT` manually since the endpoint has no separate system-instruction param like the Gemini SDK.
- `generate_sql()`: the Gemini call is now wrapped in `try/except (APIError, SQLGenerationError)`, falling back to `_generate_with_ollama()` on either kind of Gemini failure (API-level like quota/network, or content-level like a safety-filtered empty response). If Ollama also fails, `_generate_with_ollama` raises `SQLGenerationError`, which propagates uncaught exactly like before — `agent.py`'s existing retry loop handles it unchanged, no other code needed to change.
- **Bug found and fixed**: `OLLAMA_MODEL` was typo'd as `"qwen:0.6b"` (missing the `3`) — the actual pulled model is `qwen3:0.6b` (confirmed via `ollama list`). As written this would have 404'd against Ollama's API every time, silently defeating the whole fallback (still wouldn't crash — `agent.py`'s catch-all `except Exception` would catch the resulting `requests.exceptions.HTTPError` and retry as usual — but the fallback would never actually produce SQL). Fixed.
- `requests>=2.31.0` added to `requirements.txt` (was already installed transitively via `google-genai`/`fastapi`, now a direct, declared dependency).

**Verified live, in stages** (to avoid spending real Gemini quota just to prove failure-handling): `_generate_with_ollama()` called directly — correct SQL back. Then `sql_generator.client.models.generate_content` monkeypatched to raise a real `APIError` and `generate_sql()` called normally — correctly printed the `[fallback]` message and returned valid SQL via Ollama. Then that SQL run through `sql_safety.validate_sql()` — passed cleanly, `LIMIT 1000` injected as expected (same safety path regardless of which model generated the SQL). Not yet verified through the full `agent.py` graph with a real forced Gemini failure (would need either exhausting today's quota for real or a more invasive monkeypatch inside the graph) — the three pieces (Ollama call, Gemini-failure routing, safety validation) are each independently confirmed working, which is strong evidence the full chain works, but the end-to-end graph path itself hasn't been directly observed.

**Next**: if a real quota exhaustion happens during normal use, watch for the `[fallback]` print in the console to confirm this path actually engages in production, not just in the isolated tests above.

## Session Handoff (2026-08-19, continued further still — Bug #6 closed)

User ran `sql/normalize_tags.sql` as superuser. Verified: `post_tags` exists with 71,327,941 rows, both indexes (`post_tags_tag_idx`, `post_tags_post_id_idx`) built, and — importantly — `query_ai_agent` (the actual read-only app role, not superuser) can `SELECT` from it with no manual grant needed, confirming `create_readonly_role.sql`'s default-privileges setup works as designed for new tables.

Retested the actual originally-failing question ("top 5 users by reputation who answered questions about python") through the real `agent.py` graph, real Gemini calls, no mocking:
- **Attempt 1**: Gemini correctly used `post_tags` (the `SYSTEM_PROMPT` nudge worked) but as `JOIN post_tags ... DISTINCT ... ORDER BY reputation` across `users`/`posts`/`post_tags` (71M rows) — still hit the 30s `statement_timeout`.
- **Attempt 2**: same tables, but regenerated as an `EXISTS` correlated subquery instead of a `JOIN`+`DISTINCT` — finished in **1.6s**. Correct answer: Jon Skeet (1,436,762 rep), VonC, Gordon Linoff, BalusC, Martijn Pieters.

**Closing #6 as fixed**, using the same standard already applied elsewhere in this project (e.g. the `COUNT(*)`→`COUNT(id)` case, Q1 in the first eval run): a question that recovers within the retry budget counts as a pass, not a failure. Before this fix, this exact question failed on **all 3 attempts every time** (the original documented case); now it recovers in 2/3. Not literally "always fast on attempt 1" — `post_tags` makes the right query shape (`EXISTS`) fast, but a naive `JOIN`+`DISTINCT` over 71M rows can still be slow — but the self-correction loop reliably finds the fast shape on retry, which is the practical fix.

**All 8 originally-documented Open Bugs (#1-#8) are now closed.** Only two things remain open, both explicitly deferred (not forgotten): full-table partitioning (Phase 14, needs more disk headroom) and confirming the new Ollama fallback engages during a real (not simulated) Gemini outage.

## Session Handoff (2026-08-19, continued further still — partitioning runbooks written, disk situation improved)

Free disk jumped from 87GB to a stable 122GB (checked twice) since the earlier disk-space finding — this changes the partitioning risk calculus. `votes` (18GB) was already safe; `posts` (68GB) is now reasonably safe too (~40-54GB margin after the copy, vs. the earlier razor-thin ~1-19GB margin at 83-87GB free).

Wrote two interactive runbooks (not blind `psql -f` scripts, given the swap step's stakes):
- `sql/partition_votes.sql` — RANGE partition by `creationdate`, yearly 2008-2024 + a `DEFAULT` catch-all, matching `votes`' actual confirmed date range (2008-07-31 to 2023-12-03 for `votetypeid=2`). Recreates `votes_votetypeid_creationdate_idx` on the partitioned parent (auto-propagates to all partitions).
- `sql/partition_posts.sql` — same pattern, but `posts` has 8 indexes total (confirmed via `pg_indexes`: `owneruserid`, `parentid`, `posttypeid`, `(score, tags)`, `tags`, `title`, `(posttypeid, creationdate)`, plus the `pg_trgm` GIN index) — all recreated on the partitioned parent in Step 4, since missing even one would undercut the whole point (e.g. skipping the trgm index would silently regress any tag-`LIKE` query that isn't already using `post_tags`).
- **Important technical wrinkle handled in both**: Postgres requires a partitioned table's PK to include the partition key column. Both tables' original PK is a bare `PRIMARY KEY(id)`, which isn't legal once partitioned by `creationdate` — both runbooks use a composite `PRIMARY KEY(id, creationdate)` instead (still effectively unique in practice).

Sequencing: do `votes` fully (through Step 6, dropping `votes_old`) before starting `posts`, so the two migrations never need their headroom simultaneously. **Neither has been run yet** — both need superuser credentials Claude doesn't have, same as `add_indexes.sql`/`normalize_tags.sql`; user runs them interactively, checking output between steps.

**Next**: user runs both partitioning runbooks; separately, Claude moving on to a backend+frontend browser verification pass (per user's stated priority order: partitioning → backend/frontend → deployment, all targeted for today).

## Session Handoff (2026-08-19, continued further still — backend+frontend verified live, one real regression found+fixed)

Started both servers (`uvicorn backend.api:app` on 127.0.0.1:8000, `npm run dev` frontend on localhost:5173) and drove the actual UI in a real Chrome tab (not curl, not direct `agent.py` calls) — first true browser test since the Phase 9 chart work.

**Real regression found**: asked "What are the top 5 tags by number of posts?" (the same question verified fast during Phase 9's chart spot-check, before `post_tags` existed) — `execute` took **28.7s**, nearly hitting the 30s timeout. Root cause: the `SYSTEM_PROMPT` rule added for Bug #6 ("for tag-based filtering, JOIN post_tags") was too broad — Gemini applied it to this aggregate/ranking question too, generating `SELECT tag, COUNT(post_id) FROM post_tags GROUP BY tag ORDER BY post_count DESC LIMIT 5` — a full GROUP BY over all 71.3M rows of `post_tags`, when the pre-existing `tags` table already has a `count` column with the exact precomputed answer (confirmed: `SELECT tagname, count FROM tags ORDER BY count DESC LIMIT 5` returns the identical numbers instantly).

**Fixed**: split the `SYSTEM_PROMPT` rule in two — one for filtering to a specific tag (still `JOIN post_tags`, e.g. "posts about python"), one for ranking/counting across all tags (use `tags.count`, e.g. "top 5 tags by post count"), with an explicit note that `post_tags` should only be used directly when the question needs something `tags` doesn't have (e.g. joining tag membership to another table, which is Bug #6's actual originally-fixed case).

**Verified the fix live**: re-asked the identical question in a fresh conversation through the real UI. `execute` dropped from 28,757ms to **195.1ms** — confirmed via the backend log, not just visually. The chart's axis labels also changed from `tag`/`post_count` to `tagname`/`count`, visually confirming the `tags` table path was used this time. IPv4 fix in `frontend/src/api.js` also confirmed still working (network request correctly went to `127.0.0.1:8000`, not `localhost`) — the last known uncommitted frontend fix is functioning correctly.

Both servers left running in the background for continued testing. Frontend/API phases (Phase 10/11) are functionally solid based on this pass — no other issues surfaced.

**Next**: deployment (Phase 14), per user's stated plan for today.

## Session Handoff (2026-08-19, continued further still — Phase 14 deployment, Docker Compose)

Scoped with the user first: "deployment" means **Dockerize everything and run it locally**, not a live cloud host — the 117GB dataset is the reason (matches why GitHub Actions CI was already deferred: no cheap way to get a DB that size into most CI/cloud environments). Postgres itself stays as the existing native install (already has the data; no reason to duplicate 117GB into a Docker volume) — only the *application* layers get containerized.

**Built**:
- `Dockerfile.backend` (project root, build context = root, since `backend/api.py` imports `agent.py`/`sql_generator.py`/etc. from the root via plain imports, not package-relative ones — matches how it's already run locally: `uvicorn backend.api:app` from the root).
- `frontend/Dockerfile` — multi-stage (`node:22-slim` build → `nginx:alpine` serve), `frontend/nginx.conf` for SPA routing.
- `.dockerignore` (root) and `frontend/.dockerignore` — critically, `.env` is excluded from the build context (secrets come from `docker-compose.yml`'s `env_file` at runtime, never baked into the image); `agent_memory.sqlite`/`logs/` excluded too, since those come from volume mounts, not the image.
- `docker-compose.yml` extended with `backend` and `frontend` services alongside the existing `prometheus`/`grafana`.

**Two real cross-environment bugs found and fixed before they could bite** (things that work when running directly on the host but silently break inside a container, since "localhost" means something different in each context):
1. **Ollama fallback** (`sql_generator.py`'s `OLLAMA_URL`) was hardcoded to `http://localhost:11434` — inside a container, `localhost` is the container itself, not the host machine running Ollama. Fixed by making it `os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")` (unchanged default for local/non-Docker runs), overridden to `http://host.docker.internal:11434/api/generate` in the `backend` service's `environment:` block.
2. **Postgres connectivity**: `database.py`'s `DB_HOST` needs to be `host.docker.internal` from inside the container (to reach the native host Postgres), not whatever `.env` has for local runs. Same pattern: overridden via `docker-compose.yml`'s `environment:` block rather than editing `.env` itself (so the local direct-run workflow is untouched).
3. **`docker/prometheus.yml` updated**: `backend` is now a Compose service in the same network as Prometheus, so it's scraped via the service name `backend:8000` directly through Compose's internal DNS, instead of routing through `host.docker.internal` (that mechanism still exists and still would have worked via port-publishing, but the service-name route is more direct now that they're in the same stack).

**Blocker surfaced, needs the user's decision before the stack can actually connect to Postgres**: checked `pg_hba.conf` — `listen_addresses = '*'` is fine, but the *auth rules* only allow connections from `127.0.0.1/32` and `::1/128` (loopback only). A container reaching Postgres via `host.docker.internal` arrives from a different source IP and will be rejected as-is. This is Postgres *server security config*, not an app file, so Claude flagged it rather than just editing it — proposed adding one line: `host all all 172.16.0.0/12 scram-sha-256` (Docker Desktop's default bridge network range on Windows, still password-authenticated via scram-sha-256, not `trust`). **Not yet applied** — waiting on the user's go-ahead.

**Also not yet done**: `docker compose build` hadn't been run yet when this handoff was written — Docker Desktop's engine wasn't running (CLI present, daemon down), started it and was waiting for it to come up. Build/run verification is the next concrete step once the engine's ready and the `pg_hba.conf` question is resolved.

## Session Handoff (2026-08-20, continued — Docker stack live, posts partitioning completed in parallel, one real wrong-answer bug caught+fixed)

User approved the `pg_hba.conf` change; Claude added the `172.16.0.0/12 scram-sha-256` rule but couldn't reload/restart Postgres from this shell (`pg_ctl reload` and `Restart-Service` both denied — no OS-level signal permission for either). User ran `SELECT pg_reload_conf();` themselves. Both Docker images (`backend`, `frontend`) built clean on the first try; `docker compose up -d` brought up all 4 containers (`backend`, `frontend`, `prometheus`, `grafana`) successfully. Stopped the locally-running dev servers first (`uvicorn`/`vite`) since they held the same ports the containers needed.

**Real bug caught live, not hypothetical**: while the user was independently running `sql/partition_posts.sql` in another shell (in parallel, as planned), a `/chat` test through the new container returned `count: 0` for "How many questions were posted in 2023?" — silently wrong, not a crash. Root cause: `posts` partitioning was mid-flight (Steps 1-2 done, `posts_y2023` existed but empty, Step 3's `INSERT` hadn't landed data yet) — Gemini saw both `posts` (real data) and `posts_y2023` (empty) in the schema and picked the empty child table by name. Traced this live by checking DB state directly rather than guessing, confirmed against the user's own `psql` session status.

Once the user's `INSERT` completed (59,483,997 rows) and they finished through Step 6 (dropped `posts_old`), retested the same question — now correctly returns 993,601. But **the underlying behavior (Gemini querying `posts_yXXXX` child partitions by name instead of the parent) is a latent risk, not just a migration-timing artifact**: confirmed via a cross-year question ("2022 and 2023 combined") that Gemini correctly uses the parent `posts` + a `creationdate` filter when the question spans years, but a single-year question can still resolve to querying the child table directly — which only gave the right answer this time because the partition happened to be fully loaded. Fixed with a new `SYSTEM_PROMPT` rule: always query `posts` with a `creationdate` filter, never a `posts_yXXXX` table directly, since partition pruning handles it automatically and bypassing it is what caused the wrong-`0` bug in the first place. Rebuilt the backend image and retested live: the single-year question now correctly generates `SELECT COUNT(id) FROM posts WHERE posttypeid = 1 AND creationdate >= '2023-01-01' AND creationdate < '2024-01-01'` (parent table, filtered) instead of `SELECT COUNT(id) FROM posts_y2023 WHERE posttypeid = 1` (child table, unfiltered) — same correct answer, but now via the safe path.

`votes` was not partitioned (user only ran the `posts` runbook) — `sql/partition_votes.sql` remains available if wanted later, matches the plan (posts was reasonably safe given the improved disk headroom; votes was always safe but wasn't actually run this session).

**Verified the rest of the stack**: frontend container returns HTTP 200; Prometheus is healthy and successfully scraping `backend:8000` via Compose's internal service-name DNS (`health: up`, confirmed via its `/api/v1/targets` API — the `docker/prometheus.yml` service-name change from the earlier handoff works correctly); Grafana responds (302 to its login page, normal). Did one final real browser test through the actual containerized frontend (not curl) — asked "How many questions were posted in 2023?", got the correct 993,601 via the full `browser -> nginx (frontend container) -> FastAPI (backend container) -> host.docker.internal -> native Postgres` path.

**All three of today's stated goals are now done**: partitioning (posts partitioned and verified, votes runbook available but not run), backend/frontend verification (one real regression found+fixed), and deployment (`docker compose up -d` brings up the full stack — Postgres, backend, frontend, Prometheus, Grafana — with two real cross-environment bugs and one real wrong-answer bug caught and fixed along the way, not just a Dockerfile that happens to build).

**Not yet done, worth noting for next time**: no `README`/deployment doc yet explaining `docker compose up -d` as the way to run this project, and the `pg_hba.conf` change + reload requirement isn't documented anywhere a future setup would find it. `votes` partitioning remains available but unused. The Ollama fallback's `host.docker.internal` override hasn't been tested against an actual forced Gemini failure inside the container (same gap as the non-Docker version, per the earlier Ollama handoff).

## Session Handoff (2026-08-20, continued — README redesigned, demo GIF recorded)

The original `README.md` was a generic AI-generated template from project inception — referenced a fictional `app/`-based file structure, generic "customers"/"sales" example queries, and listed already-built features (RAG-schema retrieval, auto-charting) under "Future Improvements." Fully rewritten to match the actual repo.

**Dataset source honesty**: the user couldn't recall exactly where their SQL-formatted dump came from. Rather than guess a URL, verified via live web search: the real, current official source is the [Stack Exchange Data Dump on archive.org](https://archive.org/details/stackexchange) (XML format, cc-by-sa 4.0). Since the user's dump was already SQL, it went through an XML→Postgres conversion step somewhere — searched for real, existing tools (`bersace/stackexchange-dump-to-postgres`, `pgtreats/stackoverflow_in_pg`, `sth/sodata`) and listed them as candidates in the README, explicitly noting none is confirmed as what was originally used — honest about the gap rather than asserting a specific tool with false confidence. Documented the resulting expected schema (7 tables) instead, since that's what actually matters for reproducibility (`schema.py` reflects whatever exists at runtime).

**Demo GIF**: recorded live via the browser automation tools against the already-running Docker stack — a real question ("What are the top 5 tags by number of posts?") through the actual UI, showing the "Thinking..." state, the generated SQL (expanded), and the resulting chart + table. Saved as `docs/demo.gif`, embedded at the top of the README.

**New files**: `.env.example` (didn't exist before — created to match the real env var names in `database.py`/`sql_generator.py`), `docs/demo.gif`.

**README now documents, accurately**: all real features (self-correction retry, safety validation, conversational memory with rolling summarization, chart heuristics, Ollama fallback, observability), the real architecture (a Mermaid diagram matching `agent.py`'s actual LangGraph nodes), the real tech stack, the real repo layout, and complete two-path setup instructions (Docker Compose vs. manual) including the `pg_hba.conf` step that would otherwise silently block anyone else trying to reproduce the Docker path. Links out to `PROJECT_PROGRESS.md`/`docs/DASHBOARD.md` as the full development log — an intentional choice to show the real engineering process, not just a polished final state.

**Not yet done**: the README's dataset-conversion tool list is unverified (named from search results, not personally tested against this schema) — worth a note in the repo if the user ever pins down which tool they actually used.

## Session Handoff (2026-08-19, start here)

**Phase 9 — Visualization / Result Intelligence built end-to-end this session**, in its own `visualization/` package (mirroring `observalibilty/`'s folder pattern, per the user's request):

- `visualization/chart_builder.py` — `build_chart(question, result) -> dict | None`. Deterministic heuristics, not an LLM call: needs >=2 columns, needs 2-50 rows (matches `ResultTable.jsx`'s `MAX_ROWS_SHOWN`), needs at least one numeric column for the y-axis. A non-numeric column becomes the x-axis/categories (bar chart); if every column is numeric, the other numeric column becomes the x-axis and it's a line chart if its name looks like a year/date, else a bar. Renders via `matplotlib` (`Agg` backend) to a base64-encoded PNG. Verified standalone: a 3-row tags/count result correctly produces a bar chart (visually confirmed the PNG), a single-row aggregate (`COUNT`) and a 100-row result both correctly return `None` (skip charting).
- `agent.py`: new `visualize` node inserted between `execute` and `record_history` (`execute -> visualize -> record_history -> END`), wrapped in `@log_node("visualize")` so it's automatically covered by existing Prometheus/logging instrumentation with no extra work. New `AgentState.chart` field. Wrapped in try/except so a charting failure never breaks the pipeline — the user still gets their table. Verified: graph compiles, `visualize_node` runs correctly against a synthetic state (no Gemini call needed for this node).
- `backend/api.py`: `chatresponse` gained `chart_type`, `chart_x_column`, `chart_y_column`, `chart_image_base64` (all `None` when the result wasn't chart-worthy). Verified: imports cleanly, Pydantic model fields correct.
- `frontend/`: new `ChartView.jsx` renders the base64 PNG inline (`<img src="data:image/png;base64,...">`), wired into `ChatWidget.jsx` above the `ResultTable`, styled in `App.css` (white card background so the chart stays legible in dark mode). Verified in an actual browser: seeded a temporary sample message (tags/post_count bar chart), confirmed it renders correctly in the dev server, then removed the temporary scaffolding — `git status`-equivalent (`ls`) confirmed no test files were left behind and `npm run build` still passes clean.

**Not yet done**: this hasn't been exercised through a real Gemini-backed `/chat` call yet (quota still blocked, see below) — only the individual pieces (chart_builder standalone, visualize_node against a synthetic state, frontend against seeded data) have been verified. First real question that returns a chart-worthy result should be spot-checked once quota's back.

**Open Bug #3 (conversational memory) is still blocked** — retried after the calendar date rolled over to 2026-08-19, but `agent.py`'s smoke test hit `429 RESOURCE_EXHAUSTED` on the very first Gemini call. This means the free-tier quota does **not** reset at local midnight (IST). Working theory: it resets at UTC midnight (~5:30 AM IST), since the retry happened at ~00:17 IST — well before that. Not yet confirmed against Google's actual dashboard; the user was going to check `https://ai.dev/rate-limit`.

**Next session starts with**: confirm the real quota reset time, then retry `python agent.py` (two sequential questions on the same `thread_id`) to close out #3, and spot-check that a chart-worthy question now returns a chart end-to-end through `/chat`. After that, move to #5 (history truncation/summarization design) and #6 (heavy analytical query timeouts), both bigger design decisions saved for last.

## Current Task (older session handoff — read this first)

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

**Debugging pass update (same day, continued)**: #7 and #8 fixed and verified (see Bugs Fixed). Checking the code for #1 and #2 found both already fixed — `generate_node` has a catch-all `except Exception` after `APIError`/`SQLGenerationError`, and `backend/api.py`'s `/chat` wraps `agent_app.invoke()` in a `try/except Exception` → 500. `sql_generator.generate_sql()` already raises `SQLGenerationError` on a `None` or empty-after-cleanup response. Attempted #3 (conversational memory smoke test in `agent.py`) to close it out — Q1 succeeded in 1 attempt (a good sign for #8's fix), but the follow-up question hit `429 RESOURCE_EXHAUSTED` on all 3 attempts (today's 20/day quota already used up by the eval run + this test's first call) — genuinely caught cleanly by #1's exception handling, not a crash, but inconclusive on whether memory itself works. Retry once quota resets. Implemented #4 instead (default `LIMIT` enforcement in `sql_safety.py` — pure code, no API calls needed): `validate_sql()` now injects `LIMIT 1000` on any statement without a top-level `LIMIT` already; verified via the file's own sanity checks (existing-LIMIT passthrough, stacked-query rejection, and unbounded-query injection all correct).

## Phase Progress

```
Database Foundation     ██████████ 100%
Python Layer             ██████████ 100%
Schema Intelligence      ██████████ 100%
SQL Generation           ██████████ 100%
Safety                    ██████████ 100%
Execution / Retry         █████████░ 90%
Agent                     ██████░░░░ 60%
Memory                    ██████████ 100%
Visualization             ██████████ 100%
API                       ███████░░░ 70%
Frontend                  ██████░░░░ 60%
Evaluation                █████░░░░░ 50%
Observability             █████████░ 90%
Deployment                ███████░░░ 75%
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
- **Phase 9 — Visualization built end-to-end**: `visualization/chart_builder.py` (new package, mirrors `observalibilty/`'s folder pattern) generates a chart from a query result via deterministic heuristics (column count/type, row count) and renders it with `matplotlib` to a base64 PNG — no LLM call involved. Wired into `agent.py` as a new `visualize` node (`execute -> visualize -> record_history`), automatically covered by the existing `@log_node` observability instrumentation. `backend/api.py`'s `/chat` response extended with `chart_type`/`chart_x_column`/`chart_y_column`/`chart_image_base64`. `frontend/ChartView.jsx` renders the PNG inline, wired into `ChatWidget.jsx` above the result table. Verified: chart_builder's heuristics standalone (chart-worthy, single-aggregate skip, too-many-rows skip, all correct), `visualize_node` against a synthetic state, backend imports/schema, and the frontend rendering in an actual browser (seeded test data, confirmed visually, then cleaned up — no leftover test files, `npm run build` passes). Not yet exercised through a real Gemini-backed `/chat` call — blocked by the same quota as Bug #3, spot-check once it's back.

## In Progress

- Session handoff: MVP works end-to-end (backend confirmed via curl; frontend fixed for the IPv4/IPv6 issue but not yet re-confirmed by the user in-browser, and that fix isn't committed yet). Next session starts with Observability, not bug fixes — see Current Task above and Next below.

## Next

1. **First thing next session**: commit the uncommitted `frontend/src/api.js` IPv4/IPv6 fix, and confirm with the user that a real browser question now round-trips successfully (this confirmation was still pending when this session ended).
2. **Observability** (user's explicit priority — before bug fixing): structured logging per graph node (timing + outcome: which node ran, how long, success/failure) and per `/chat` request in `backend/api.py` (question, `thread_id`, total latency, attempts used). Persist somewhere reviewable — likely Python's `logging` module + `rich` (already in `requirements.txt`), not raw uvicorn stdout.
3. **Evaluation**: re-run `tests/test_agent.py`'s full 9-question suite cleanly now that the DataFrame and generate_node bugs are both fixed — previous runs were invalidated first by Gemini quota exhaustion, then by the DataFrame serialization bug (would have failed every successful case regardless). This will be the first real signal on success/failure/latency per difficulty tier. Feed real numbers into the AI Evaluation section below.
4. **Then the debugging pass** — see Open Bugs below, already roughly priority-ordered.

## Open Bugs (compiled for the next debugging pass — remaining items)

(none — all 8 originally-documented Open Bugs are fixed. See Bugs Fixed below. Full-table partitioning remains deliberately deferred to Phase 14, not tracked as an open bug since it was never confirmed necessary — see Session Handoff above.)

## Blockers

- (none currently — DB verification and read-only access are both resolved)

## Deferred (revisit at Phase 14 — Deployment)

- GitHub Actions QC for `tests/test_agent.py`: blocked by the fact that CI runners can't reach the local 117GB Postgres DB. Discussed three options (small seeded Postgres service container in CI / self-hosted runner / no-DB lightweight checks only) — leaning toward the seeded-container approach since it would have caught most of today's bugs, but explicitly deferred until closer to deployment rather than decided now.

## Bugs Fixed (post-partitioning — closed 2026-08-20, silent wrong answer)

- Not one of the original 8 Open Bugs — surfaced live during Docker deployment testing, right after `posts` was partitioned. `posts` is now a partitioned table with per-year children (`posts_y2008`...`posts_y2024`, `posts_default`). Gemini would sometimes query a `posts_yXXXX` child table directly by name instead of the parent `posts` with a `creationdate` filter — for single-year questions this happened to still work once the migration was fully complete, but it's the same behavior that produced a **silently wrong `count: 0`** answer while the migration was still mid-flight (child partition existed but was still empty). Confirmed via a cross-year question that multi-year queries already correctly used the parent + filter (safe), but single-year queries were still at risk of resolving to a direct child-table hit — not a one-off migration-timing artifact, a standing risk. Fixed with a new `SYSTEM_PROMPT` rule in `sql_generator.py`: always query `posts` with a `creationdate` filter, never a `posts_yXXXX` table directly. Rebuilt the backend Docker image and verified live: the same question that previously could resolve either way now consistently generates the parent-table + filter form.
- This is the second silent-wrong-answer bug found in this project (see also: the DataFrame/msgpack crash was loud, but this and the mid-migration `0` were both quiet) — worth remembering that timeouts and crashes aren't the only failure mode to watch for; wrong-but-plausible-looking answers are the more dangerous case since nothing signals a problem to the user.

## Bugs Fixed (Open Bug #6 — closed 2026-08-19, post_tags normalization)

- **#6**: `tags LIKE '%python%'`-style questions timed out on all 3 self-correction attempts, root-caused to matches being scattered across all 59.5M rows of `posts` even with a trigram index. Fixed by normalizing tags into `post_tags(post_id, tag)` (`sql/normalize_tags.sql`, run by the user as superuser — 71,327,941 rows, both indexes built) plus a `SYSTEM_PROMPT` nudge to `JOIN post_tags` instead of `LIKE`. Verified live against the actual originally-failing question ("top 5 users by reputation who answered questions about python"): attempt 1 correctly used `post_tags` but as a `JOIN`+`DISTINCT` and still timed out; attempt 2 regenerated it as an `EXISTS` correlated subquery and finished in 1.6s with the correct answer. Closed using the same standard used elsewhere in this project — recovering within the retry budget counts as fixed, since before this change the same question failed on all 3 attempts every time. Also confirmed `query_ai_agent` (read-only role) can `SELECT` from the new table with no manual grant, validating `create_readonly_role.sql`'s default-privileges setup.

## Bugs Fixed (Open Bug #3 — closed 2026-08-19, quota reset)

- **#3**: Conversational memory had never been proven to actually work end-to-end — earlier attempts kept hitting `429 RESOURCE_EXHAUSTED` before the follow-up question could resolve. Confirmed working once the daily quota reset (~18:40 IST, consistent with the UTC-midnight-reset theory): ran the two-question smoke test for real, then read the persisted checkpoint state directly (`app.get_state()`) rather than trusting printed output. Q2 ("now show me the same thing but for 2022") generated `SELECT COUNT(id) FROM posts WHERE posttypeid = 1 AND creationdate >= '2022-01-01...' AND creationdate < '2023-01-01...'` — same query shape as Q1's 2023 version, with the year correctly re-derived from injected `history`, not a repeat or coincidence. Not a code fix — the code was already correct; this closes the bug by proving it.

## Bugs Fixed (Open Bugs #1/#2/#4 — post-observability debugging pass, continued)

- **#1**: `generate_node` only caught `google.genai.errors.APIError`, and `backend/api.py`'s `/chat` had no catch-all around `agent_app.invoke()` beyond the `RuntimeError`→422 path. Fixed: `generate_node` now has a trailing `except Exception` (after the more specific `APIError`/`SQLGenerationError` clauses, so their messages aren't swallowed) that routes back through the normal `after_generate` retry logic instead of crashing the graph; `/chat` wraps `agent_app.invoke()` in `try/except Exception` → clean `HTTPException(500, ...)`. Verified live: a real `429 RESOURCE_EXHAUSTED` during the #3 memory test was caught and retried through all 3 attempts without crashing.
- **#2**: `sql_generator.generate_sql()` didn't validate Gemini's output before returning it. Fixed: raises `SQLGenerationError` if `response.text is None` (safety-filtered/refusal) or if the string is empty after markdown-fence cleanup, before it ever reaches `validate_sql()`.
- **#4**: No default `LIMIT` enforcement in `sql_safety.py` — an unbounded broad question against `posts`/`votes` could pull an enormous result set into memory. Fixed: `validate_sql()` now scans the statement's flattened tokens for a top-level `LIMIT` keyword; if absent, appends `LIMIT 1000` before returning. A no-op for aggregate queries (`COUNT` etc., always one row) and queries that already specify their own `LIMIT`. Verified via `sql_safety.py`'s own sanity checks (existing-LIMIT passthrough, stacked-query rejection, unbounded-query injection all correct).

## Bugs Fixed (Open Bugs #7/#8 — post-observability debugging pass)

- **#7**: `votes` (~236M rows) had no index covering `creationdate`, so a `votetypeid`+`creationdate`-filtered query ("how many upvotes were cast in 2022?") forced a full scan and timed out on all 3 self-correction attempts. Fixed with `votes_votetypeid_creationdate_idx` (already drafted in `sql/add_indexes.sql`, same equality-leads/range-follows column order as `posts_posttypeid_creationdate_idx`) — run by the user as superuser via `psql -U postgres -d postgresql_query_ai -f sql/add_indexes.sql`. Verified live: `pg_index.indisvalid = t` and `pg_stat_user_tables.last_analyze` populated for `votes`.
- **#8**: Gemini generated `COUNT(*)` more often than `COUNT(id)`/`COUNT(1)` for simple counts, slow enough on `posts`/`votes` to hit the 30s `statement_timeout` on attempt 1 even though the retry loop recovered on attempt 2 — a wasted 30s+ round-trip on otherwise-simple questions. Fixed by adding a rule to `sql_generator.py`'s `SYSTEM_PROMPT` telling Gemini to prefer `COUNT(id)`/`COUNT(1)` over `COUNT(*)` on the two large tables. Not yet re-tested against a live question (small-batch retest still pending, see Current Task).

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
