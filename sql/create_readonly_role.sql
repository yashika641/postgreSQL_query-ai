-- Least-privilege read-only role for the query-ai agent.
-- Run as a superuser (e.g. `postgres`), connected to the postgresql_query_ai database:
--   psql -U postgres -d postgresql_query_ai -f sql/create_readonly_role.sql

-- 1. Create the login role. Replace the password before running,
--    or better: set it interactively with \password after creation
--    so it never sits in this file / git history.
CREATE ROLE query_ai_agent WITH LOGIN PASSWORD 'CHANGE_ME';

-- 2. Let it connect to the database and see the schema.
GRANT CONNECT ON DATABASE postgresql_query_ai TO query_ai_agent;
GRANT USAGE ON SCHEMA public TO query_ai_agent;

-- 3. Grant SELECT on everything that exists now...
GRANT SELECT ON ALL TABLES IN SCHEMA public TO query_ai_agent;

-- 4. ...and on anything created later by the owning role, so you don't
--    have to remember to re-grant after future migrations/restores.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO query_ai_agent;

-- 5. Defense in depth: even if a future GRANT is missed, force every
--    session opened by this role into a read-only transaction. This
--    turns any accidental/attempted write into a clean Postgres error
--    ("cannot execute INSERT in a read-only transaction") rather than
--    relying solely on missing privileges.
ALTER ROLE query_ai_agent SET default_transaction_read_only = on;

-- 6. Keep runaway generated queries from hanging the connection.
ALTER ROLE query_ai_agent SET statement_timeout = '30s';
