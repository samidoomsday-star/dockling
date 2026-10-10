"""Reject incomplete result states and unsafe output names before publication."""

from alembic import op

revision = "0007_output_validation"
down_revision = "0006_review_outputs"
branch_labels = None
depends_on = None
SQL = r"""
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
 (j.deletion_state <> 'active' AND NOT (o.action='close' AND j.deletion_state IN ('pending','partial'))) OR NOT EXISTS (SELECT 1 FROM public.web_memberships
 WHERE workspace_id=o.workspace_id AND user_id=o.actor_id AND active AND role IN ('owner','editor'))
 THEN RETURN false; END IF;
 IF p_result->>'state' IN ('failed','cancelled') THEN
 UPDATE public.web_operations SET state=p_result->>'state',error_code=p_result->>'code',
 stage='finished',lease_hash=NULL,lease_until=NULL WHERE id=o.id;
 IF o.action='close' THEN UPDATE public.web_jobs SET deletion_state='partial' WHERE id=j.id; END IF;
 IF p_result->>'state'='awaiting_input' THEN
 UPDATE public.web_files SET password_required=true WHERE workspace_id=o.workspace_id AND job_id=o.job_id
 AND id=(p_result->>'file_id')::uuid;
 END IF;
 RETURN true;
 END IF;
 IF p_result->>'state' IS NULL OR p_result->>'state' NOT IN ('succeeded','awaiting_input') THEN RETURN false; END IF;
 IF p_result->>'state'='succeeded' AND (p_result->>'digest' IS NULL OR p_result->>'digest' !~ '^[0-9a-f]{64}$') THEN RETURN false; END IF;
 IF o.action IN ('review_workbook','export','delivery') THEN
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(coalesce(p_result->'manifest'->'items','[]'::jsonb)) i
 WHERE i->>'name' IS NULL OR i->>'name' !~ '^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,120}$' OR i->>'name' LIKE '%..%')
 THEN RETURN false; END IF;
 IF p_result->>'state'<>'succeeded' OR p_result->'manifest' IS NULL OR
 (p_result->'manifest'->>'revision')::bigint <> j.revision OR
 jsonb_array_length(p_result->'manifest'->'items') < 1 OR
 jsonb_array_length(p_result->'manifest'->'items') > 100 THEN RETURN false; END IF;
 IF (SELECT count(DISTINCT value->>'id') FROM jsonb_array_elements(p_result->'manifest'->'items')) <> jsonb_array_length(p_result->'manifest'->'items')
 THEN RAISE EXCEPTION 'duplicate artifact'; END IF;
 FOR f IN SELECT value FROM jsonb_array_elements(p_result->'manifest'->'items') LOOP
 IF NOT EXISTS(SELECT 1 FROM public.web_artifacts ar WHERE ar.id=(f->>'id')::uuid
 AND ar.workspace_id=o.workspace_id AND ar.job_id=o.job_id AND ar.operation_id=o.id
 AND ar.generation=p_generation AND ar.state='staged' AND ar.revision=j.revision
 AND ar.sha256=f->>'sha256' AND ar.bytes=(f->>'bytes')::bigint AND ar.kind=f->>'kind'
 AND ar.kind=CASE o.action WHEN 'review_workbook' THEN 'review_workbook' WHEN 'export' THEN 'export' ELSE 'delivery' END)
 THEN RAISE EXCEPTION 'invalid output'; END IF;
 END LOOP;
 IF (SELECT count(*) FROM public.web_artifacts WHERE operation_id=o.id AND generation=p_generation AND state='staged') <> jsonb_array_length(p_result->'manifest'->'items')
 THEN RAISE EXCEPTION 'incomplete output manifest'; END IF;
 IF o.action='export' THEN
 UPDATE public.web_jobs SET export_manifest=p_result->'manifest',delivery_manifest='{}',status='exported' WHERE id=j.id;
 UPDATE public.web_artifacts SET revision=0 WHERE workspace_id=o.workspace_id AND job_id=o.job_id AND state='active' AND kind IN ('export','delivery');
 ELSIF o.action='delivery' THEN
 UPDATE public.web_jobs SET delivery_manifest=p_result->'manifest',status='delivered' WHERE id=j.id;
 UPDATE public.web_artifacts SET revision=0 WHERE workspace_id=o.workspace_id AND job_id=o.job_id AND state='active' AND kind='delivery';
 ELSE
 UPDATE public.web_jobs SET review_state=jsonb_set(review_state,'{workbooks}',p_result->'manifest') WHERE id=j.id;
 UPDATE public.web_artifacts SET revision=0 WHERE workspace_id=o.workspace_id AND job_id=o.job_id AND state='active' AND kind='review_workbook';
 END IF;
 UPDATE public.web_artifacts SET state='active' WHERE operation_id=o.id AND generation=p_generation AND state='staged';
 UPDATE public.web_operations SET state='succeeded',stage='finished',lease_hash=NULL,lease_until=NULL WHERE id=o.id;
 INSERT INTO public.web_events(id,workspace_id,job_id,actor_id,action,revision,at)
 VALUES(o.id,o.workspace_id,o.job_id,o.actor_id,'job.'||o.action||'.completed',j.revision,now());
 RETURN true;
END IF;
IF o.action='review_apply' THEN
 IF p_result->>'state'<>'succeeded' OR jsonb_array_length(p_result->'statements') < 1 THEN RETURN false; END IF;
 INSERT INTO public.web_snapshots(id,workspace_id,job_id,revision,digest,statements)
 VALUES(o.id,o.workspace_id,o.job_id,j.revision+1,p_result->>'digest',p_result->'statements');
 INSERT INTO public.web_review_revisions(id,workspace_id,job_id,actor_id,revision,command,at)
 VALUES(o.id,o.workspace_id,o.job_id,o.actor_id,j.revision+1,jsonb_build_object('edits',p_result->'edits'),now());
 UPDATE public.web_jobs SET revision=revision+1,content_digest=p_result->>'digest',review_state='{}',
 export_manifest='{}',delivery_manifest='{}',status='needs_review' WHERE id=j.id;
 UPDATE public.web_artifacts SET revision=j.revision+1 WHERE workspace_id=o.workspace_id AND job_id=o.job_id AND state='active' AND kind IN ('original','normalized','page');
 UPDATE public.web_operations SET state='succeeded',stage='finished',lease_hash=NULL,lease_until=NULL,payload='{}' WHERE id=o.id;
 INSERT INTO public.web_events(id,workspace_id,job_id,actor_id,action,revision,at)
 VALUES(o.id,o.workspace_id,o.job_id,o.actor_id,'job.review.applied',j.revision+1,now());
 RETURN true;
END IF;
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
 AND job_id=o.job_id AND ((state='active' AND kind IN ('original','normalized','page')) OR (operation_id=o.id AND generation=p_generation AND state='staged'));
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
 review_state='{}',export_manifest='{}',delivery_manifest='{}',status=CASE WHEN o.action='intake' THEN 'intake_done' ELSE 'needs_review' END WHERE id=j.id;
 UPDATE public.web_artifacts SET revision=j.revision+1,state='active' WHERE workspace_id=o.workspace_id
 AND job_id=o.job_id AND ((state='active' AND kind IN ('original','normalized','page')) OR (operation_id=o.id AND generation=p_generation AND state='staged'));
 UPDATE public.web_operations SET state='succeeded',stage='finished',lease_hash=NULL,lease_until=NULL WHERE id=o.id;
 INSERT INTO public.web_events(id,workspace_id,job_id,actor_id,action,revision,at)
 VALUES(o.id,o.workspace_id,o.job_id,o.actor_id,'job.'||o.action||'.completed',j.revision+1,now());
 RETURN true;
END $$
"""


def upgrade() -> None:
    op.execute(SQL)


def downgrade() -> None:
    raise RuntimeError("Restore a matching backup instead of weakening publication checks.")
