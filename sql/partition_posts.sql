-- Partitions `posts` by creationdate (RANGE, yearly) for future scalability.
-- Same technique as sql/partition_votes.sql -- see that file's header for
-- the full rationale (partition pruning on top of existing indexes,
-- per-partition manageability at 59.5M rows).
--
-- DISK CHECK BEFORE RUNNING: posts is 68GB, needs ~68-80GB of temp
-- headroom during Step 3's copy. Re-run `df -h` immediately before Step 3
-- -- don't rely on a reading from earlier in the session. Do this AFTER
-- sql/partition_votes.sql is fully done and votes_old is dropped (Step 6
-- there), so you're never needing both tables' headroom at once.
--
-- RUN INTERACTIVELY, ONE STEP AT A TIME -- check output before continuing.
-- Connect as superuser: psql -U postgres -d postgresql_query_ai


-- ============================================================
-- STEP 1: Create the partitioned parent table
-- ============================================================
-- Same PK wrinkle as votes: posts' current PK is bare `id`, but a
-- partitioned table's PK must include the partition key column. Composite
-- PK (id, creationdate) is still effectively unique in practice.

CREATE TABLE posts_partitioned (LIKE posts INCLUDING DEFAULTS)
    PARTITION BY RANGE (creationdate);

ALTER TABLE posts_partitioned ADD PRIMARY KEY (id, creationdate);


-- ============================================================
-- STEP 2: Create yearly partitions + a DEFAULT catch-all
-- ============================================================
-- Same 2008-2024 range as votes (posts spans the same dump timeframe --
-- confirmed posttypeid=1 runs 2008-07-31 to 2023-12-03; other post types
-- weren't individually checked, hence the DEFAULT partition as a safety
-- net rather than assuming every type falls in this range).

CREATE TABLE posts_y2008 PARTITION OF posts_partitioned FOR VALUES FROM ('2008-01-01') TO ('2009-01-01');
CREATE TABLE posts_y2009 PARTITION OF posts_partitioned FOR VALUES FROM ('2009-01-01') TO ('2010-01-01');
CREATE TABLE posts_y2010 PARTITION OF posts_partitioned FOR VALUES FROM ('2010-01-01') TO ('2011-01-01');
CREATE TABLE posts_y2011 PARTITION OF posts_partitioned FOR VALUES FROM ('2011-01-01') TO ('2012-01-01');
CREATE TABLE posts_y2012 PARTITION OF posts_partitioned FOR VALUES FROM ('2012-01-01') TO ('2013-01-01');
CREATE TABLE posts_y2013 PARTITION OF posts_partitioned FOR VALUES FROM ('2013-01-01') TO ('2014-01-01');
CREATE TABLE posts_y2014 PARTITION OF posts_partitioned FOR VALUES FROM ('2014-01-01') TO ('2015-01-01');
CREATE TABLE posts_y2015 PARTITION OF posts_partitioned FOR VALUES FROM ('2015-01-01') TO ('2016-01-01');
CREATE TABLE posts_y2016 PARTITION OF posts_partitioned FOR VALUES FROM ('2016-01-01') TO ('2017-01-01');
CREATE TABLE posts_y2017 PARTITION OF posts_partitioned FOR VALUES FROM ('2017-01-01') TO ('2018-01-01');
CREATE TABLE posts_y2018 PARTITION OF posts_partitioned FOR VALUES FROM ('2018-01-01') TO ('2019-01-01');
CREATE TABLE posts_y2019 PARTITION OF posts_partitioned FOR VALUES FROM ('2019-01-01') TO ('2020-01-01');
CREATE TABLE posts_y2020 PARTITION OF posts_partitioned FOR VALUES FROM ('2020-01-01') TO ('2021-01-01');
CREATE TABLE posts_y2021 PARTITION OF posts_partitioned FOR VALUES FROM ('2021-01-01') TO ('2022-01-01');
CREATE TABLE posts_y2022 PARTITION OF posts_partitioned FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');
CREATE TABLE posts_y2023 PARTITION OF posts_partitioned FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE posts_y2024 PARTITION OF posts_partitioned FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE posts_default PARTITION OF posts_partitioned DEFAULT;


-- ============================================================
-- STEP 3: Copy the data in (the expensive part -- ~59.5M rows, 68GB)
-- ============================================================
-- CHECK FREE DISK RIGHT BEFORE THIS (`df -h` or equivalent) -- don't trust
-- a number from earlier in the session.

INSERT INTO posts_partitioned SELECT * FROM posts;

-- Sanity check before continuing:
-- SELECT count(*) FROM posts;              -- compare against:
-- SELECT count(*) FROM posts_partitioned;


-- ============================================================
-- STEP 4: Recreate all indexes on the partitioned parent
-- ============================================================
-- Each of these propagates automatically to all 17 partitions. This is
-- posts' full current index set (confirmed via pg_indexes) -- don't skip
-- any, or that partition-pruning benefit gets undercut by a full-table
-- scan on whichever index got missed (e.g. posts_tags_trgm_idx is what
-- Open Bug #6's earlier fix relied on before post_tags existed, and
-- post_tags itself doesn't replace this index -- other tag-LIKE queries
-- might still use it).

CREATE INDEX ON posts_partitioned USING btree (owneruserid);
CREATE INDEX ON posts_partitioned USING btree (parentid);
CREATE INDEX ON posts_partitioned USING btree (posttypeid);
CREATE INDEX ON posts_partitioned USING btree (score, tags);
CREATE INDEX ON posts_partitioned USING btree (tags);
CREATE INDEX ON posts_partitioned USING btree (title);
CREATE INDEX ON posts_partitioned USING btree (posttypeid, creationdate);
CREATE INDEX ON posts_partitioned USING gin (tags gin_trgm_ops);

ANALYZE posts_partitioned;


-- ============================================================
-- STEP 5: Swap (point of no easy return -- verify Steps 1-4 fully first)
-- ============================================================

ALTER TABLE posts RENAME TO posts_old;
ALTER TABLE posts_partitioned RENAME TO posts;

-- Verify the app's read-only role can still query it:
--   psql -U query_ai_agent -d postgresql_query_ai -c "SELECT count(*) FROM posts LIMIT 1;"
--
-- Then retest several real questions through agent.py (a date-filtered
-- count, a tag-scan question, a join question) to confirm the app works
-- end-to-end against the swapped table before reclaiming space.


-- ============================================================
-- STEP 6: Reclaim disk space (ONLY after Step 5 is fully verified)
-- ============================================================
-- posts_old is your rollback path until you drop it.

-- DROP TABLE posts_old;
