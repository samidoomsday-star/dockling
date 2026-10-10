"""Constrain file pointers to their workspace and job in PostgreSQL too."""

from alembic import op

revision = "0003_scoped_files"
down_revision = "0002_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE web_artifacts ADD UNIQUE(workspace_id,job_id,id)")
    op.execute("ALTER TABLE web_operations ADD UNIQUE(workspace_id,job_id,id)")
    op.execute("ALTER TABLE web_files DROP CONSTRAINT web_files_artifact_id_fkey")
    op.execute("ALTER TABLE web_files DROP CONSTRAINT web_files_normalized_id_fkey")
    for column in ["artifact_id", "normalized_id"]:
        op.execute(
            f"ALTER TABLE web_files ADD FOREIGN KEY(workspace_id,job_id,{column}) REFERENCES web_artifacts(workspace_id,job_id,id)"
        )


def downgrade() -> None:
    raise RuntimeError("Restore a matching backup; do not weaken tenant constraints.")
