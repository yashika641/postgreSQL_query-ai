-- Partitions `votes` by creationdate (RANGE, yearly) for future scalability.
-- NOT a fix for an open bug -- Open Bug #7 (votes.creationdate had no index)
-- is already fixed via votes_votetypeid_creationdate_idx. This is a
-- forward-looking improvement: date-filtered queries against votes (236M
-- rows) will get partition pruning on top of the existing index, and
-- future growth stays manageable per-partition instead of one giant table.
--
-- SAFE TO RUN: votes is 18GB, needs ~18-25GB temp headroom, and 87GB was
-- free at last check. (posts, at 68GB, is NOT safe to partition the same
-- way right now -- see PROJECT_PROGRESS.md's disk-space finding. Do not
-- reuse this script for posts without re-checking free disk space first.)
--
-- RUN THIS INTERACTIVELY, ONE STEP AT A TIME -- not as one blind
-- `psql -f` pass. Check each step's output (row counts, index validity)
-- before moving to the next. The swap step (Step 5) is the point where a
-- mistake gets expensive; everything before it is cheap to abandon.
--
-- Connect as superuser: psql -U postgres -d postgresql_query_ai


-- ============================================================
-- STEP 1: Create the partitioned parent table
-- ============================================================
-- LIKE votes INCLUDING DEFAULTS copies columns/types/defaults, but NOT
-- indexes or constraints -- Postgres partitioned tables can't have a
-- unique/PK constraint unless it includes the partition key column, so
-- votes' existing bare `PRIMARY KEY (id)` can't be copied as-is (see
-- Step 2).

CREATE TABLE votes_partitioned (LIKE votes INCLUDING DEFAULTS)
    PARTITION BY RANGE (creationdate);

-- Composite PK: still effectively unique in practice (each id has exactly
-- one creationdate), but satisfies Postgres's "PK must include the
-- partition key" rule for partitioned tables.
ALTER TABLE votes_partitioned ADD PRIMARY KEY (id, creationdate);


-- ============================================================
-- STEP 2: Create yearly partitions + a DEFAULT catch-all
-- ============================================================
-- Range covers the dump's actual data (2008-07-31 to 2023-12-03,
-- confirmed via `SELECT min/max(creationdate) FROM votes`), plus one
-- extra year of buffer and a DEFAULT partition as a safety net for
-- anything outside the named ranges.

CREATE TABLE votes_y2008 PARTITION OF votes_partitioned FOR VALUES FROM ('2008-01-01') TO ('2009-01-01');
CREATE TABLE votes_y2009 PARTITION OF votes_partitioned FOR VALUES FROM ('2009-01-01') TO ('2010-01-01');
CREATE TABLE votes_y2010 PARTITION OF votes_partitioned FOR VALUES FROM ('2010-01-01') TO ('2011-01-01');
CREATE TABLE votes_y2011 PARTITION OF votes_partitioned FOR VALUES FROM ('2011-01-01') TO ('2012-01-01');
CREATE TABLE votes_y2012 PARTITION OF votes_partitioned FOR VALUES FROM ('2012-01-01') TO ('2013-01-01');
CREATE TABLE votes_y2013 PARTITION OF votes_partitioned FOR VALUES FROM ('2013-01-01') TO ('2014-01-01');
CREATE TABLE votes_y2014 PARTITION OF votes_partitioned FOR VALUES FROM ('2014-01-01') TO ('2015-01-01');
CREATE TABLE votes_y2015 PARTITION OF votes_partitioned FOR VALUES FROM ('2015-01-01') TO ('2016-01-01');
CREATE TABLE votes_y2016 PARTITION OF votes_partitioned FOR VALUES FROM ('2016-01-01') TO ('2017-01-01');
CREATE TABLE votes_y2017 PARTITION OF votes_partitioned FOR VALUES FROM ('2017-01-01') TO ('2018-01-01');
CREATE TABLE votes_y2018 PARTITION OF votes_partitioned FOR VALUES FROM ('2018-01-01') TO ('2019-01-01');
CREATE TABLE votes_y2019 PARTITION OF votes_partitioned FOR VALUES FROM ('2019-01-01') TO ('2020-01-01');
CREATE TABLE votes_y2020 PARTITION OF votes_partitioned FOR VALUES FROM ('2020-01-01') TO ('2021-01-01');
CREATE TABLE votes_y2021 PARTITION OF votes_partitioned FOR VALUES FROM ('2021-01-01') TO ('2022-01-01');
CREATE TABLE votes_y2022 PARTITION OF votes_partitioned FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');
CREATE TABLE votes_y2023 PARTITION OF votes_partitioned FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE votes_y2024 PARTITION OF votes_partitioned FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE votes_default PARTITION OF votes_partitioned DEFAULT;


-- ============================================================
-- STEP 3: Copy the data in (the expensive part -- ~236M rows)
-- ============================================================
-- One statement, but Postgres routes each row to the right partition
-- automatically based on creationdate. This is the step that needs the
-- ~18-25GB of headroom -- check `df -h` / free disk before running it,
-- not just before starting the whole script.

INSERT INTO votes_partitioned SELECT * FROM votes;

-- Sanity check: row counts must match before continuing.
-- SELECT count(*) FROM votes;              -- compare against:
-- SELECT count(*) FROM votes_partitioned;


-- ============================================================
-- STEP 4: Recreate indexes on the partitioned parent
-- ============================================================
-- Creating an index on a partitioned parent automatically creates and
-- maintains matching indexes on every current AND future partition --
-- this one statement replaces votes_votetypeid_creationdate_idx across
-- all 17 partitions.

CREATE INDEX ON votes_partitioned (votetypeid, creationdate);

ANALYZE votes_partitioned;


-- ============================================================
-- STEP 5: Swap (point of no easy return -- verify Steps 1-4 fully first)
-- ============================================================
-- Brief exclusive lock during the rename. Do this during low-traffic time.

ALTER TABLE votes RENAME TO votes_old;
ALTER TABLE votes_partitioned RENAME TO votes;

-- Verify the app's read-only role can still query it (default privileges
-- from create_readonly_role.sql should cover the new table automatically,
-- same as post_tags did -- but CONFIRM, don't assume):
--   psql -U query_ai_agent -d postgresql_query_ai -c "SELECT count(*) FROM votes LIMIT 1;"
--
-- Also retest a real question through agent.py that filters votes by date
-- (e.g. "how many upvotes were cast in 2022?") to confirm the app still
-- works end-to-end against the swapped table.


-- ============================================================
-- STEP 6: Reclaim disk space (ONLY after Step 5 is fully verified)
-- ============================================================
-- Do not run this until you've confirmed the app works correctly against
-- the new `votes`. This is the actual irreversible step -- votes_old is
-- your rollback path (`ALTER TABLE votes RENAME TO votes_broken; ALTER
-- TABLE votes_old RENAME TO votes;`) until you drop it.

-- DROP TABLE votes_old;
