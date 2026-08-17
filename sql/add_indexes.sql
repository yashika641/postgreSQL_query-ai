-- Fixes the statement_timeout hit by executor.py: posts has no index
-- covering creationdate, so any date-filtered question (extremely common
-- for an NL->SQL tool) forces a full scan of 59.5M rows.
--
-- Run as a superuser, connected to the postgresql_query_ai database:
--   psql -U postgres -d postgresql_query_ai -f sql/add_indexes.sql
--
-- CONCURRENTLY avoids taking a lock that blocks reads while the index
-- builds -- important on a table this size, where the build itself can
-- take a while. CONCURRENTLY cannot run inside a transaction block, so
-- each statement here must be executed on its own (psql does this by
-- default -- don't wrap this file in BEGIN/COMMIT).

CREATE INDEX CONCURRENTLY IF NOT EXISTS posts_posttypeid_creationdate_idx
    ON posts (posttypeid, creationdate);

-- Fixes a second statement_timeout hit by executor.py: tag-search questions
-- (e.g. "questions about python") generate `tags LIKE '%<python>%'`, a
-- leading-wildcard pattern that none of the plain btree indexes on `tags`
-- can support -- Postgres falls back to checking the filter row-by-row
-- across every posttypeid=1 row (~18M rows). pg_trgm's GIN index supports
-- substring LIKE search efficiently.
--
-- CREATE EXTENSION requires superuser; run this file as superuser same as
-- above.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX CONCURRENTLY IF NOT EXISTS posts_tags_trgm_idx
    ON posts USING gin (tags gin_trgm_ops);

-- posts has never been ANALYZE'd (pg_stat_user_tables.last_analyze/
-- last_autoanalyze are both NULL). Without column statistics the planner
-- can't estimate the new GIN index's selectivity and silently skips it,
-- falling back to a full filter scan even though the index exists.
ANALYZE posts;
