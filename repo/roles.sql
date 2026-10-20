-- Application role. Re-runnable. __APP_PASSWORD__ is substituted by
-- scripts/migrate_db.py (and the test fixture) before execution.
--
-- Terraform owns the changectl_app password in the deployed project (it
-- creates the Cloud SQL user), so this file only sets a password when it has
-- to create the role itself (local compose) and never ALTERs an existing
-- role's password. The grants run every time.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'changectl_app') THEN
        CREATE ROLE changectl_app LOGIN PASSWORD '__APP_PASSWORD__';
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO changectl_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO changectl_app;
REVOKE UPDATE, DELETE ON events FROM changectl_app;
GRANT SELECT, INSERT ON events TO changectl_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO changectl_app;
