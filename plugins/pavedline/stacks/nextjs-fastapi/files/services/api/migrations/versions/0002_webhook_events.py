"""webhook_events (global): replay protection for signed webhooks.

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
        CREATE TABLE webhook_events (
          provider text NOT NULL CHECK (char_length(provider) BETWEEN 1 AND 32),
          event_id text NOT NULL CHECK (char_length(event_id) BETWEEN 1 AND 255),
          received_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (provider, event_id)
        )
        """
    )
    op.execute("CREATE INDEX webhook_events_received_at_idx ON webhook_events (received_at)")
    # Global table (listed in db/global_tables.txt): ids only, no payload, no tenant data.
    op.execute("GRANT SELECT, INSERT, DELETE ON webhook_events TO app_runtime")


def downgrade() -> None:
    op.execute("DROP TABLE webhook_events")
