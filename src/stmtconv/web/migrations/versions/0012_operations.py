"""Read-only API backup/restore evidence written by the offline operator."""

from alembic import op

revision = "0012_operations"
down_revision = "0011_accounts_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE web_backup_receipts(id uuid PRIMARY KEY,sha256 varchar(64) NOT NULL UNIQUE,created_at timestamptz NOT NULL DEFAULT now(),expires_at timestamptz NOT NULL,objects bigint NOT NULL CHECK(objects>=0),bytes bigint NOT NULL CHECK(bytes>0),schema_version varchar(80) NOT NULL);
    CREATE TABLE web_restore_receipts(id uuid PRIMARY KEY,backup_id uuid NOT NULL REFERENCES web_backup_receipts(id),verified_at timestamptz NOT NULL DEFAULT now(),seconds bigint NOT NULL CHECK(seconds>=0),checks jsonb NOT NULL);
    GRANT SELECT ON web_backup_receipts,web_restore_receipts TO dockling_app;
    """)


def downgrade() -> None:
    raise RuntimeError("Use a verified matching restore; operational evidence must not be erased.")
