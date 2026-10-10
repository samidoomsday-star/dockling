"""Retain verified files during password waits; passwords are never persisted."""

from alembic import op

revision = "0004_progressive_intake"
down_revision = "0003_scoped_files"
branch_labels = None
depends_on = None
SQL = [
    r"""
CREATE OR REPLACE FUNCTION dockling_claim(p_hash text) RETURNS jsonb
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
 'original_id',f.artifact_id,'normalized_id',f.normalized_id,'pages',f.pages,'previews',f.previews,'sha256',ar.sha256)
 ORDER BY f.position), '[]'::jsonb) INTO payload FROM public.web_files f JOIN public.web_artifacts ar ON ar.id=f.artifact_id AND ar.workspace_id=f.workspace_id AND ar.job_id=f.job_id
 WHERE f.workspace_id=o.workspace_id AND f.job_id=o.job_id;
 RETURN jsonb_build_object('id',o.id,'workspace_id',o.workspace_id,'job_id',o.job_id,
 'generation',o.lease_generation,'revision',o.input_revision,'action',o.action,
 'options',j.options,'files',payload);
END $$
""",
    r"""
CREATE OR REPLACE FUNCTION dockling_publish(p_id uuid,p_hash text,p_generation integer,p_result jsonb)
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
 IF p_result->>'state' IN ('failed','cancelled') THEN
 UPDATE public.web_operations SET state=p_result->>'state',error_code=p_result->>'code',
 stage='finished',lease_hash=NULL,lease_until=NULL WHERE id=o.id;
 IF p_result->>'state'='awaiting_input' THEN
 UPDATE public.web_files SET password_required=true WHERE workspace_id=o.workspace_id AND job_id=o.job_id
 AND id=(p_result->>'file_id')::uuid;
 END IF;
 RETURN true;
 END IF;
 IF p_result->>'state' NOT IN ('succeeded','awaiting_input') THEN RETURN false; END IF;
 IF p_result->>'state'='succeeded' AND p_result->>'digest' !~ '^[0-9a-f]{64}$' THEN RETURN false; END IF;
 IF o.action='intake' THEN
 IF p_result->>'state'='succeeded' AND jsonb_array_length(p_result->'files') <> (SELECT count(*) FROM public.web_files
 WHERE workspace_id=o.workspace_id AND job_id=o.job_id) THEN RAISE EXCEPTION 'file inventory mismatch'; END IF;
 IF (SELECT count(DISTINCT value->>'id') FROM jsonb_array_elements(p_result->'files')) <> jsonb_array_length(p_result->'files') THEN RAISE EXCEPTION 'duplicate source'; END IF;
 FOR f IN SELECT value FROM jsonb_array_elements(p_result->'files') LOOP
 SELECT ar.id INTO a FROM public.web_artifacts ar WHERE ar.id=(f->>'normalized_id')::uuid
 AND ar.workspace_id=o.workspace_id AND ar.job_id=o.job_id AND ar.kind='normalized' AND
 ((ar.operation_id=o.id AND ar.generation=p_generation AND ar.state='staged') OR
 (ar.state='active' AND EXISTS(SELECT 1 FROM public.web_files sf WHERE sf.workspace_id=o.workspace_id
 AND sf.job_id=o.job_id AND sf.id=(f->>'id')::uuid AND sf.normalized_id=ar.id
 AND sf.pages=f->'pages' AND sf.previews=f->'previews')));
 IF EXISTS(SELECT 1 FROM jsonb_each_text(f->'previews') pv WHERE NOT EXISTS(
 SELECT 1 FROM public.web_artifacts ar WHERE ar.id=pv.value::uuid AND ar.workspace_id=o.workspace_id
 AND ar.job_id=o.job_id AND ar.kind='page' AND (ar.state='active' OR
 (ar.state='staged' AND ar.operation_id=o.id AND ar.generation=p_generation)))) THEN RAISE EXCEPTION 'invalid preview'; END IF;
 IF NOT FOUND THEN RAISE EXCEPTION 'invalid artifact'; END IF;
 UPDATE public.web_files SET normalized_id=a,pages=f->'pages',previews=f->'previews',password_required=false
 WHERE workspace_id=o.workspace_id AND job_id=o.job_id AND id=(f->>'id')::uuid;
 IF NOT FOUND THEN RAISE EXCEPTION 'invalid source'; END IF;
 END LOOP;
 IF p_result->>'state'='awaiting_input' THEN
 UPDATE public.web_files SET password_required=true WHERE workspace_id=o.workspace_id AND job_id=o.job_id
 AND id=(p_result->>'file_id')::uuid;
 IF NOT FOUND THEN RAISE EXCEPTION 'invalid protected source'; END IF;
 IF EXISTS(SELECT 1 FROM public.web_artifacts WHERE operation_id=o.id AND generation=p_generation AND state='staged') THEN
 UPDATE public.web_jobs SET revision=revision+1,content_digest=NULL,status='created' WHERE id=j.id;
 UPDATE public.web_artifacts SET revision=j.revision+1,state='active' WHERE workspace_id=o.workspace_id
 AND job_id=o.job_id AND (state='active' OR (operation_id=o.id AND generation=p_generation AND state='staged'));
 END IF;
 UPDATE public.web_operations SET state='awaiting_input',error_code=p_result->>'code',stage='finished',lease_hash=NULL,lease_until=NULL WHERE id=o.id;
 INSERT INTO public.web_events(id,workspace_id,job_id,actor_id,action,revision,at)
 SELECT o.id,o.workspace_id,o.job_id,o.actor_id,'intake.password_required',revision,now() FROM public.web_jobs WHERE id=j.id;
 RETURN true;
 END IF;
 ELSE
 IF p_result->>'state'<>'succeeded' OR o.action <> 'extract' OR jsonb_array_length(p_result->'statements') < 1 THEN RETURN false; END IF;
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
    for statement in SQL:
        op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Restore a matching backup; preserve password-wait revisions.")
