-- Run in a SEPARATE psql session from the one building the index --
-- that session is busy until CREATE INDEX CONCURRENTLY finishes.
--
--   psql -U postgres -d postgresql_query_ai -f sql/check_index_progress.sql
--
-- Re-run this any time to check progress; it returns one row per
-- in-progress CREATE INDEX, empty if none is running (finished or hasn't
-- started).

SELECT
    p.pid,
    p.phase,
    p.blocks_total,
    p.blocks_done,
    ROUND(100.0 * p.blocks_done / NULLIF(p.blocks_total, 0), 1) AS pct_blocks_done,
    p.tuples_total,
    p.tuples_done,
    now() - a.query_start AS elapsed,
    a.query
FROM pg_stat_progress_create_index p
JOIN pg_stat_activity a ON a.pid = p.pid;
