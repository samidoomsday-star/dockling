"""Workspace vault metadata; credentials are authenticated ciphertext only."""

from alembic import op

revision = "0008_connections"
down_revision = "0007_output_validation"
branch_labels = None
depends_on = None
SQL = """
CREATE TABLE web_connections (
 id uuid PRIMARY KEY, workspace_id uuid NOT NULL REFERENCES web_workspaces(id),
 name varchar(80) NOT NULL, version bigint NOT NULL DEFAULT 1 CHECK(version>=1),
 active boolean NOT NULL DEFAULT true, ciphertext varchar(6000),config jsonb NOT NULL,
 models jsonb NOT NULL DEFAULT '[]',selected_model varchar(200),effort varchar(30) NOT NULL DEFAULT 'provider_default',
 terms_version varchar(200),tested_at timestamptz,test_code varchar(80),UNIQUE(workspace_id,id));
GRANT SELECT,INSERT,UPDATE,DELETE ON web_connections TO dockling_app;
"""


def upgrade() -> None:
    for statement in SQL.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Restore the matching encrypted database and vault-key backup.")
