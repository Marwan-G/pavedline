"""Example: items (tenant table).

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE items (
          id uuid PRIMARY KEY,
          tenant_id uuid NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
          name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200),
          price_minor bigint NOT NULL CHECK (price_minor >= 0),
          currency char(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
          created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX items_tenant_id_id_idx ON items (tenant_id, id)")
    op.execute("ALTER TABLE items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE items FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON items
          USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON items TO app_runtime")


def downgrade() -> None:
    op.execute("DROP TABLE items")
