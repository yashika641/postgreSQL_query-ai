-- Fixes the still-open half of Open Bug #6: `tags LIKE '%python%'` matches
-- are scattered across all 59.5M rows of `posts`. Even with the pg_trgm GIN
-- index (posts_tags_trgm_idx), fetching the matching rows still costs
-- ~3.15M planner cost units (see PROJECT_PROGRESS.md's Bugs Fixed log) --
-- not a missing-index problem, a physical-scatter problem. A normalized
-- post_tags(post_id, tag) table turns tag search into a plain equality
-- lookup on a small, tightly indexed table instead of a wide table scan.
--
-- Run as superuser: psql -U postgres -d postgresql_query_ai -f sql/normalize_tags.sql
--
-- Sized safely: posts is 68GB with ~18M posttypeid=1 rows carrying tags;
-- post_tags will hold a few tens of millions of (post_id, tag) rows at a
-- few tens of bytes each -- single-digit GB, not a disk-space risk like
-- partitioning posts itself would be (only 83GB free at last check).

CREATE TABLE IF NOT EXISTS post_tags (
    post_id BIGINT NOT NULL,
    tag TEXT NOT NULL
);

-- posts.tags is Stack Overflow's packed format: "<python><django><flask>".
-- unnest(string_to_array(...)) explodes each post's tags into one row per
-- tag. One-time batch load, not CONCURRENTLY-able (plain INSERT) -- but
-- post_tags has no readers yet, so no contention with live traffic.
INSERT INTO post_tags (post_id, tag)
SELECT id, unnest(string_to_array(trim(both '<>' FROM tags), '><'))
FROM posts
WHERE tags IS NOT NULL AND tags <> '';

CREATE INDEX CONCURRENTLY IF NOT EXISTS post_tags_tag_idx ON post_tags (tag);
CREATE INDEX CONCURRENTLY IF NOT EXISTS post_tags_post_id_idx ON post_tags (post_id);

ANALYZE post_tags;

-- No explicit GRANT needed: create_readonly_role.sql set up default
-- privileges so query_ai_agent gets SELECT on future tables automatically
-- -- verify with a live SELECT as query_ai_agent after this runs.
