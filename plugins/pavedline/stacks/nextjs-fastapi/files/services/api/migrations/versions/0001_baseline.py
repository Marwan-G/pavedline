"""Baseline: tenants (global) and idempotency_keys (tenant table).

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The roles (app_owner, app_runtime, app_admin) are created by the platform from db/roles.sql.
    op.execute(
        """
        CREATE TABLE tenants (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          external_id text NOT NULL UNIQUE,
          name text NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # Global table: the runtime role reads it to map a token's organisation to a tenant; it never writes it.
    op.execute("GRANT SELECT ON tenants TO app_runtime")

    op.execute(
        """
        CREATE TABLE idempotency_keys (
          tenant_id uuid NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
          principal text NOT NULL,
          key text NOT NULL CHECK (char_length(key) BETWEEN 1 AND 255),
          request_fingerprint text NOT NULL,
          -- 0 and '{}' only while the claiming transaction is open; never visible once committed
          response_status integer NOT NULL,
          response_body jsonb NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (tenant_id, principal, key)
        )
        """
    )
    op.execute("CREATE INDEX idempotency_keys_created_at_idx ON idempotency_keys (created_at)")
    op.execute("ALTER TABLE idempotency_keys ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE idempotency_keys FORCE ROW LEVEL SECURITY")
    # NULLIF: after a transaction ends, a pooled connection may report '' for the setting; '' becomes
    # NULL, so the policy sees no rows (fails closed) instead of raising on a bad cast.
    op.execute(
        """
        CREATE POLICY tenant_isolation ON idempotency_keys
          USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON idempotency_keys TO app_runtime")


def downgrade() -> None:
    op.execute("DROP TABLE idempotency_keys")
    op.execute("DROP TABLE tenants")
