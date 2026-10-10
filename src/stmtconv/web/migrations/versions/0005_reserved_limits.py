"""Capture the page quota at enqueue so retries cannot expand it."""

from alembic import op

revision = "0005_reserved_limits"
down_revision = "0004_progressive_intake"
branch_labels = None
depends_on = None
CLAIM = r"""
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
 'options',j.options,'files',payload,'page_limit',o.page_limit);
END $$
"""


def upgrade() -> None:
    op.execute(
        "ALTER TABLE web_operations ADD COLUMN page_limit integer NOT NULL DEFAULT 40 CHECK(page_limit BETWEEN 1 AND 100)"
    )
    op.execute(CLAIM)


def downgrade() -> None:
    raise RuntimeError("Restore a matching backup instead of weakening captured quotas.")
