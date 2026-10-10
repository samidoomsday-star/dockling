"""Durable consent and reserved AI requests; the parser gets no ledger grants."""

from alembic import op

revision = "0009_ai_ledger"
down_revision = "0008_connections"
branch_labels = None
depends_on = None
DDL = r"""
CREATE TABLE web_ai_consents(job_id uuid PRIMARY KEY,workspace_id uuid NOT NULL,version bigint NOT NULL DEFAULT 1,actor_id uuid NOT NULL REFERENCES web_users(id),connection_id uuid REFERENCES web_connections(id),granted boolean NOT NULL DEFAULT false,binding varchar(64) NOT NULL DEFAULT '',page_cap integer NOT NULL CHECK(page_cap BETWEEN 1 AND 100),request_cap integer NOT NULL CHECK(request_cap BETWEEN 1 AND 100),private jsonb NOT NULL DEFAULT '{}',FOREIGN KEY(workspace_id,job_id) REFERENCES web_jobs(workspace_id,id));
CREATE TABLE web_ai_runs(id uuid PRIMARY KEY,workspace_id uuid NOT NULL,job_id uuid NOT NULL,actor_id uuid NOT NULL REFERENCES web_users(id),input_revision bigint NOT NULL,consent_version integer NOT NULL,binding varchar(64) NOT NULL,page_keys jsonb NOT NULL,state varchar(20) NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','running','succeeded','failed','uncertain','cancelled')),error_code varchar(80),cleanup_done boolean NOT NULL DEFAULT true,created_at timestamptz NOT NULL DEFAULT now(),FOREIGN KEY(workspace_id,job_id) REFERENCES web_jobs(workspace_id,id));
CREATE UNIQUE INDEX web_ai_one_live_run ON web_ai_runs(workspace_id,job_id) WHERE state IN ('queued','running');
CREATE TABLE web_ai_attempts(id uuid PRIMARY KEY,run_id uuid NOT NULL REFERENCES web_ai_runs(id),workspace_id uuid NOT NULL,job_id uuid NOT NULL,page_key varchar(64) NOT NULL,state varchar(20) NOT NULL DEFAULT 'reserved' CHECK(state IN ('reserved','sending','succeeded','failed','uncertain','cancelled')),result jsonb NOT NULL DEFAULT '{}',UNIQUE(run_id,page_key),FOREIGN KEY(workspace_id,job_id) REFERENCES web_jobs(workspace_id,id));
GRANT SELECT,INSERT,UPDATE,DELETE ON web_ai_consents,web_ai_runs,web_ai_attempts TO dockling_app;
"""
CLAIM = r"""
CREATE OR REPLACE FUNCTION dockling_claim(p_hash text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE o public.web_operations%ROWTYPE; j public.web_jobs%ROWTYPE; payload jsonb;
BEGIN
 IF p_hash !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'invalid lease'; END IF;
 UPDATE public.web_operations SET state='failed',error_code='RETRIES_EXHAUSTED',lease_hash=NULL
 WHERE state='running' AND lease_until < now() AND attempts >= 3;
 SELECT * INTO o FROM public.web_operations
 WHERE (state='queued' OR (state='running' AND lease_until < now() AND attempts < 3))
 AND NOT (action='close' AND EXISTS(SELECT 1 FROM public.web_ai_runs ai WHERE ai.workspace_id=web_operations.workspace_id AND ai.job_id=web_operations.job_id AND NOT ai.cleanup_done))
 AND NOT (action='close' AND EXISTS(SELECT 1 FROM public.web_scratch_attempts sa WHERE sa.workspace_id=web_operations.workspace_id AND sa.job_id=web_operations.job_id AND NOT sa.completed))
 ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1;
 IF NOT FOUND THEN RETURN NULL; END IF;
 SELECT * INTO j FROM public.web_jobs WHERE workspace_id=o.workspace_id AND id=o.job_id;
 IF (j.deletion_state <> 'active' AND NOT (o.action='close' AND j.deletion_state IN ('pending','partial'))) OR j.revision <> o.input_revision OR NOT EXISTS (
 SELECT 1 FROM public.web_memberships WHERE workspace_id=o.workspace_id AND user_id=o.actor_id
 AND active AND role IN ('owner','editor')) THEN
 UPDATE public.web_operations SET state='cancelled',error_code='INPUT_REVOKED' WHERE id=o.id;
 RETURN NULL;
 END IF;
 UPDATE public.web_operations SET state='running',stage='starting',lease_hash=p_hash,
 lease_generation=lease_generation+1,attempts=attempts+1,lease_until=now()+interval '45 seconds'
 WHERE id=o.id RETURNING * INTO o;
 SELECT coalesce(jsonb_agg(jsonb_build_object('id',f.id,'name',f.name,'kind',f.kind,
 'original_id',f.artifact_id,'normalized_id',f.normalized_id,'pages',f.pages,'previews',f.previews,'sha256',ar.sha256)
 ORDER BY f.position), '[]'::jsonb) INTO payload FROM public.web_files f JOIN public.web_artifacts ar ON ar.id=f.artifact_id AND ar.workspace_id=f.workspace_id AND ar.job_id=f.job_id
 WHERE f.workspace_id=o.workspace_id AND f.job_id=o.job_id;
 RETURN jsonb_build_object('id',o.id,'workspace_id',o.workspace_id,'job_id',o.job_id,
 'generation',o.lease_generation,'revision',o.input_revision,'action',o.action,
 'options',j.options,'files',CASE WHEN o.action IN ('intake','extract') THEN payload ELSE '[]'::jsonb END,'page_limit',o.page_limit,
 'payload',o.payload,'review_state',j.review_state,'statements',coalesce((SELECT statements FROM public.web_snapshots
 WHERE workspace_id=j.workspace_id AND job_id=j.id AND revision=j.revision),'[]'::jsonb));
END $$
"""


def upgrade() -> None:
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)
    op.execute(CLAIM)


def downgrade() -> None:
    raise RuntimeError("Restore a matching backup; AI usage must never reset during migration.")
