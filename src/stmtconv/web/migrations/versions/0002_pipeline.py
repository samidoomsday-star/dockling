"""Durable private pipeline and narrowly scoped worker functions."""

from alembic import op

revision = "0002_pipeline"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

DDL = """
ALTER TABLE web_jobs ADD content_digest varchar(64);
ALTER TABLE web_jobs ADD CONSTRAINT deletion_states CHECK (deletion_state IN ('active','pending','partial','removed'));
ALTER TABLE web_events ALTER revision TYPE bigint;
ALTER TABLE web_artifacts ALTER revision TYPE bigint;
ALTER TABLE web_artifacts ADD state varchar(12) NOT NULL DEFAULT 'active';
ALTER TABLE web_artifacts ADD operation_id uuid;
ALTER TABLE web_artifacts ADD generation integer;
ALTER TABLE web_artifacts ADD created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE web_artifacts ADD CONSTRAINT artifact_states CHECK (state IN ('staged','active','removed'));
ALTER TABLE web_artifacts ADD CONSTRAINT artifact_size CHECK (bytes >= 0 AND bytes <= 33554432);
ALTER TABLE web_operations ALTER input_revision TYPE bigint;
ALTER TABLE web_operations ADD actor_id uuid REFERENCES web_users(id);
ALTER TABLE web_operations ADD lease_hash varchar(64);
ALTER TABLE web_operations ADD lease_until timestamptz;
ALTER TABLE web_operations ADD attempts integer NOT NULL DEFAULT 0;
ALTER TABLE web_operations ADD stage varchar(30) NOT NULL DEFAULT 'queued';
ALTER TABLE web_operations ADD completed_pages integer NOT NULL DEFAULT 0;
ALTER TABLE web_operations ADD error_code varchar(80);
ALTER TABLE web_operations ADD created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE web_operations ADD CONSTRAINT operation_states CHECK (state IN ('queued','running','awaiting_input','succeeded','failed','cancel_requested','cancelled','uncertain'));
CREATE INDEX web_operations_queue ON web_operations(state,created_at);
CREATE UNIQUE INDEX web_operations_one_active_job ON web_operations(workspace_id,job_id) WHERE state IN ('queued','running','cancel_requested');
CREATE TABLE web_files (
 id uuid PRIMARY KEY, workspace_id uuid NOT NULL, job_id uuid NOT NULL,
 artifact_id uuid NOT NULL REFERENCES web_artifacts(id), normalized_id uuid REFERENCES web_artifacts(id),
 name varchar(120) NOT NULL, kind varchar(12) NOT NULL CHECK(kind IN ('pdf','image')),
 position integer NOT NULL CHECK(position >= 0), pages jsonb NOT NULL DEFAULT '[]',
 previews jsonb NOT NULL DEFAULT '{}', password_required boolean NOT NULL DEFAULT false,
 UNIQUE(workspace_id,job_id,id), UNIQUE(workspace_id,job_id,position),
 FOREIGN KEY(workspace_id,job_id) REFERENCES web_jobs(workspace_id,id)
);
CREATE TABLE web_snapshots (
 id uuid PRIMARY KEY, workspace_id uuid NOT NULL, job_id uuid NOT NULL,
 revision bigint NOT NULL, digest varchar(64) NOT NULL, statements jsonb NOT NULL,
 UNIQUE(workspace_id,job_id,revision),
 FOREIGN KEY(workspace_id,job_id) REFERENCES web_jobs(workspace_id,id)
);
GRANT SELECT,INSERT,UPDATE,DELETE ON web_files,web_snapshots TO dockling_app;
"""

FUNCTIONS = [
    """
CREATE FUNCTION dockling_claim(p_hash text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE o public.web_operations%ROWTYPE; j public.web_jobs%ROWTYPE; payload jsonb;
BEGIN
 IF p_hash !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'invalid lease'; END IF;
 UPDATE public.web_operations SET state='failed',error_code='RETRIES_EXHAUSTED',lease_hash=NULL
 WHERE state='running' AND lease_until < now() AND attempts >= 3;
 SELECT * INTO o FROM public.web_operations
 WHERE state='queued' OR (state='running' AND lease_until < now() AND attempts < 3)
 ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1;
 IF NOT FOUND THEN RETURN NULL; END IF;
 SELECT * INTO j FROM public.web_jobs WHERE workspace_id=o.workspace_id AND id=o.job_id;
 IF j.deletion_state <> 'active' OR j.revision <> o.input_revision OR NOT EXISTS (
 SELECT 1 FROM public.web_memberships WHERE workspace_id=o.workspace_id AND user_id=o.actor_id
 AND active AND role IN ('owner','editor')) THEN
 UPDATE public.web_operations SET state='cancelled',error_code='INPUT_REVOKED' WHERE id=o.id;
 RETURN NULL;
 END IF;
 UPDATE public.web_operations SET state='running',stage='starting',lease_hash=p_hash,
 lease_generation=lease_generation+1,attempts=attempts+1,lease_until=now()+interval '45 seconds'
 WHERE id=o.id RETURNING * INTO o;
 SELECT coalesce(jsonb_agg(jsonb_build_object('id',f.id,'name',f.name,'kind',f.kind,
 'original_id',f.artifact_id,'normalized_id',f.normalized_id,'pages',f.pages)
 ORDER BY f.position), '[]'::jsonb) INTO payload FROM public.web_files f
 WHERE f.workspace_id=o.workspace_id AND f.job_id=o.job_id;
 RETURN jsonb_build_object('id',o.id,'workspace_id',o.workspace_id,'job_id',o.job_id,
 'generation',o.lease_generation,'revision',o.input_revision,'action',o.action,
 'options',j.options,'files',payload);
END $$
""",
    """
CREATE FUNCTION dockling_heartbeat(p_id uuid,p_hash text,p_generation integer,p_stage text,p_pages integer)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 IF p_stage NOT IN ('starting','inspecting','converting','publishing') OR p_pages < 0 OR p_pages > 100 THEN RETURN false; END IF;
 UPDATE public.web_operations o SET lease_until=now()+interval '45 seconds',stage=p_stage,completed_pages=p_pages
 WHERE o.id=p_id AND o.lease_hash=p_hash AND o.lease_generation=p_generation
 AND o.state='running' AND o.lease_until > now() AND EXISTS (
 SELECT 1 FROM public.web_jobs j WHERE j.workspace_id=o.workspace_id AND j.id=o.job_id
 AND j.deletion_state='active' AND j.revision=o.input_revision);
 RETURN FOUND;
END $$
""",
    """
CREATE FUNCTION dockling_publish(p_id uuid,p_hash text,p_generation integer,p_result jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE o public.web_operations%ROWTYPE; j public.web_jobs%ROWTYPE; f jsonb; a uuid;
BEGIN
 SELECT * INTO o FROM public.web_operations WHERE id=p_id;
 IF NOT FOUND THEN RETURN false; END IF;
 -- Same lock order as customer commands: workspace, job, operation.
 PERFORM 1 FROM public.web_workspaces WHERE id=o.workspace_id FOR UPDATE;
 SELECT * INTO j FROM public.web_jobs WHERE workspace_id=o.workspace_id AND id=o.job_id FOR UPDATE;
 SELECT * INTO o FROM public.web_operations WHERE id=p_id FOR UPDATE;
 IF o.lease_hash IS DISTINCT FROM p_hash OR o.lease_generation <> p_generation OR
 o.state <> 'running' OR o.lease_until <= now() OR j.revision <> o.input_revision OR
 j.deletion_state <> 'active' OR NOT EXISTS (SELECT 1 FROM public.web_memberships
 WHERE workspace_id=o.workspace_id AND user_id=o.actor_id AND active AND role IN ('owner','editor'))
 THEN RETURN false; END IF;
 IF p_result->>'state' IN ('failed','awaiting_input','cancelled') THEN
 UPDATE public.web_operations SET state=p_result->>'state',error_code=p_result->>'code',
 stage='finished',lease_hash=NULL,lease_until=NULL WHERE id=o.id;
 IF p_result->>'state'='awaiting_input' THEN
 UPDATE public.web_files SET password_required=true WHERE workspace_id=o.workspace_id AND job_id=o.job_id
 AND id=(p_result->>'file_id')::uuid;
 END IF;
 RETURN true;
 END IF;
 IF p_result->>'state' <> 'succeeded' OR p_result->>'digest' !~ '^[0-9a-f]{64}$' THEN RETURN false; END IF;
 IF o.action='intake' THEN
 IF jsonb_array_length(p_result->'files') <> (SELECT count(*) FROM public.web_files
 WHERE workspace_id=o.workspace_id AND job_id=o.job_id) THEN RAISE EXCEPTION 'file inventory mismatch'; END IF;
 FOR f IN SELECT value FROM jsonb_array_elements(p_result->'files') LOOP
 SELECT id INTO a FROM public.web_artifacts WHERE id=(f->>'normalized_id')::uuid
 AND workspace_id=o.workspace_id AND job_id=o.job_id AND operation_id=o.id
 AND generation=p_generation AND state='staged' AND kind='normalized';
 IF NOT FOUND THEN RAISE EXCEPTION 'invalid artifact'; END IF;
 UPDATE public.web_files SET normalized_id=a,pages=f->'pages',previews=f->'previews',password_required=false
 WHERE workspace_id=o.workspace_id AND job_id=o.job_id AND id=(f->>'id')::uuid;
 IF NOT FOUND THEN RAISE EXCEPTION 'invalid source'; END IF;
 END LOOP;
 ELSE
 IF o.action <> 'extract' OR jsonb_array_length(p_result->'statements') < 1 THEN RETURN false; END IF;
 INSERT INTO public.web_snapshots(id,workspace_id,job_id,revision,digest,statements)
 VALUES(o.id,o.workspace_id,o.job_id,j.revision+1,p_result->>'digest',p_result->'statements');
 END IF;
 UPDATE public.web_jobs SET revision=revision+1,content_digest=p_result->>'digest',
 status=CASE WHEN o.action='intake' THEN 'intake_done' ELSE 'needs_review' END WHERE id=j.id;
 UPDATE public.web_artifacts SET revision=j.revision+1,state='active' WHERE workspace_id=o.workspace_id
 AND job_id=o.job_id AND (state='active' OR (operation_id=o.id AND generation=p_generation AND state='staged'));
 UPDATE public.web_operations SET state='succeeded',stage='finished',lease_hash=NULL,lease_until=NULL WHERE id=o.id;
 INSERT INTO public.web_events(id,workspace_id,job_id,actor_id,action,revision,at)
 VALUES(o.id,o.workspace_id,o.job_id,o.actor_id,'job.'||o.action||'.completed',j.revision+1,now());
 RETURN true;
END $$
""",
]


def upgrade() -> None:
    for sql in DDL.split(";"):
        if sql.strip():
            op.execute(sql)
    for sql in FUNCTIONS:
        op.execute(sql)
    for name, args in [
        ("dockling_claim", "text"),
        ("dockling_heartbeat", "uuid,text,integer,text,integer"),
        ("dockling_publish", "uuid,text,integer,jsonb"),
    ]:
        op.execute(f"REVOKE ALL ON FUNCTION {name}({args}) FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {name}({args}) TO dockling_worker")


def downgrade() -> None:
    raise RuntimeError(
        "Back up the database; Phase 2 downgrade requires an explicit data migration."
    )
