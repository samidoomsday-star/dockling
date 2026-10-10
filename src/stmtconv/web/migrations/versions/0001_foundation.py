"""Initial hosted foundation schema: frozen DDL snapshot, not live model create_all."""

from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None

DDL = """
CREATE TABLE web_users (
	id UUID NOT NULL,
	issuer VARCHAR(500) NOT NULL,
	subject VARCHAR(200) NOT NULL,
	email VARCHAR(254),
	email_verified BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (issuer, subject)
)

;

CREATE TABLE web_workspaces (
	id UUID NOT NULL,
	name VARCHAR(80) NOT NULL,
	version BIGINT NOT NULL,
	PRIMARY KEY (id)
)

;

CREATE TABLE web_idempotency (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	actor_id UUID NOT NULL,
	action VARCHAR(150) NOT NULL,
	key VARCHAR(128) NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	response JSONB NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (workspace_id, actor_id, action, key),
	FOREIGN KEY(workspace_id) REFERENCES web_workspaces (id),
	FOREIGN KEY(actor_id) REFERENCES web_users (id)
)

;

CREATE TABLE web_invitations (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	email VARCHAR(254) NOT NULL,
	role VARCHAR(12) NOT NULL,
	token_hash VARCHAR(64) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	status VARCHAR(12) NOT NULL,
	PRIMARY KEY (id),
	CHECK (role IN ('editor','viewer')),
	CHECK (status IN ('pending','accepted','revoked','expired')),
	FOREIGN KEY(workspace_id) REFERENCES web_workspaces (id),
	UNIQUE (token_hash)
)

;

CREATE TABLE web_jobs (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	creator_id UUID NOT NULL,
	name VARCHAR(120) NOT NULL,
	status VARCHAR(24) NOT NULL,
	revision BIGINT NOT NULL,
	currency VARCHAR(3) NOT NULL,
	options JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	deletion_state VARCHAR(12) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (workspace_id, id),
	CHECK (revision >= 1),
	CHECK (status IN ('created','intake_done','extracted','needs_review','reviewed','exported','delivered','closed','failed')),
	FOREIGN KEY(workspace_id) REFERENCES web_workspaces (id),
	FOREIGN KEY(creator_id) REFERENCES web_users (id)
)

;

CREATE TABLE web_memberships (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	user_id UUID NOT NULL,
	role VARCHAR(12) NOT NULL,
	active BOOLEAN NOT NULL,
	version BIGINT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (workspace_id, user_id),
	CHECK (role IN ('owner','editor','viewer')),
	FOREIGN KEY(workspace_id) REFERENCES web_workspaces (id),
	FOREIGN KEY(user_id) REFERENCES web_users (id)
)

;

CREATE TABLE web_sessions (
	id UUID NOT NULL,
	token_hash VARCHAR(64) NOT NULL,
	user_id UUID NOT NULL,
	workspace_id UUID,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	mfa_until TIMESTAMP WITH TIME ZONE,
	mfa BOOLEAN NOT NULL,
	revoked BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (token_hash),
	FOREIGN KEY(user_id) REFERENCES web_users (id),
	FOREIGN KEY(workspace_id) REFERENCES web_workspaces (id)
)

;

CREATE TABLE web_artifacts (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	job_id UUID NOT NULL,
	object_key VARCHAR(500) NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	revision INTEGER NOT NULL,
	kind VARCHAR(40) NOT NULL,
	bytes BIGINT NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(workspace_id, job_id) REFERENCES web_jobs (workspace_id, id),
	UNIQUE (object_key)
)

;

CREATE TABLE web_events (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	job_id UUID,
	actor_id UUID,
	action VARCHAR(80) NOT NULL,
	revision INTEGER,
	code VARCHAR(80),
	at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(workspace_id, job_id) REFERENCES web_jobs (workspace_id, id),
	FOREIGN KEY(workspace_id) REFERENCES web_workspaces (id),
	FOREIGN KEY(actor_id) REFERENCES web_users (id)
)

;

CREATE TABLE web_operations (
	id UUID NOT NULL,
	workspace_id UUID NOT NULL,
	job_id UUID NOT NULL,
	input_revision INTEGER NOT NULL,
	state VARCHAR(20) NOT NULL,
	action VARCHAR(40) NOT NULL,
	lease_generation INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(workspace_id, job_id) REFERENCES web_jobs (workspace_id, id)
)

;
CREATE INDEX ix_web_invitations_workspace_id ON web_invitations (workspace_id);
CREATE INDEX ix_web_jobs_workspace_id ON web_jobs (workspace_id);
CREATE INDEX ix_web_memberships_workspace_id ON web_memberships (workspace_id);
CREATE INDEX ix_web_artifacts_workspace_id ON web_artifacts (workspace_id);
CREATE INDEX ix_web_events_workspace_id ON web_events (workspace_id);
CREATE INDEX ix_web_operations_workspace_id ON web_operations (workspace_id);
"""


def upgrade() -> None:
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)
    op.execute("GRANT USAGE ON SCHEMA public TO dockling_app, dockling_worker")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO dockling_app"
    )
    # Worker has no customer-table privileges until the leased scoped worker boundary (Phase 2).


def downgrade() -> None:
    op.drop_table("web_operations")
    op.drop_table("web_events")
    op.drop_table("web_artifacts")
    op.drop_table("web_sessions")
    op.drop_table("web_memberships")
    op.drop_table("web_jobs")
    op.drop_table("web_invitations")
    op.drop_table("web_idempotency")
    op.drop_table("web_workspaces")
    op.drop_table("web_users")
