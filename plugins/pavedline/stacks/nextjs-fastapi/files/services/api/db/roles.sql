-- Database roles (spec: three roles). Idempotent. Run by the platform as a superuser, IN THE APPLICATION
-- DATABASE (the schema revokes below are per database), never by a
-- migration and never by the service. Passwords are set outside this file (a secret store or the
-- managed-role definition); never write one here.
--
--   app_owner    owns every table and runs the migrations; the only role with BYPASSRLS
--   app_runtime  what the service connects as: owns nothing, no BYPASSRLS, cannot become app_owner
--   app_admin    audited reporting and administration; not used by the service; no grants by default

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_owner') THEN
    CREATE ROLE app_owner LOGIN NOINHERIT BYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_runtime') THEN
    CREATE ROLE app_runtime LOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_admin') THEN
    CREATE ROLE app_admin LOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
END
$$;

-- Re-assert the attributes on every run, so a drifted role is corrected.
ALTER ROLE app_owner   LOGIN NOINHERIT BYPASSRLS   NOSUPERUSER NOCREATEDB NOCREATEROLE;
ALTER ROLE app_runtime LOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE;
ALTER ROLE app_admin   LOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE;

-- Hardening, re-asserted on every run.
-- No role may create objects in the public schema through PUBLIC; only the owner role (the database
-- owner) creates tables, through migrations.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- The runtime role must never be able to become, or inherit from, the owner. Revoke a drifted
-- membership (guarded, so a fresh cluster does not error).
DO $$
BEGIN
  IF pg_has_role('app_runtime', 'app_owner', 'MEMBER') THEN
    REVOKE app_owner FROM app_runtime;
  END IF;
END
$$;

-- Grants are explicit in each migration (GRANT ... ON <table> TO app_runtime); ALTER DEFAULT PRIVILEGES
-- is deliberately NOT used, so a new table is unreachable by the runtime role until a migration says
-- exactly what it may do.
