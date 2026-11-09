"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""

from alembic import op

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Explicit SQL only (op.execute), never autogenerate. Every tenant table: tenant_id NOT NULL,
    # ENABLE + FORCE ROW LEVEL SECURITY, a policy on app.tenant_id, and explicit GRANTs to app_runtime.
    pass


def downgrade() -> None:
    pass
