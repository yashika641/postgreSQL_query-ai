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
