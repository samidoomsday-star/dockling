"""Restored authority and jobs stay fenced; newer scoped deletions cannot resurrect data."""

from uuid import UUID

import pytest
from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_foundation import create
from test_pipeline import upload

from stmtconv.web.models import AiAttempt, AiConsent, AiRun, Artifact, Job, Operation, WebSession
from stmtconv.web.recovery import quarantine, replay_removals


def test_restore_quarantine_keeps_uncertain_cost_and_cleanup_fenced(world):
    job = create(world)
    identifier = UUID(job["id"])
    with Session(world["engine"]) as db, db.begin():
        run = AiRun(
            workspace_id=world["workspaces"][0],
            job_id=identifier,
            actor_id=world["users"]["owner0"],
            input_revision=1,
            consent_version=1,
            binding="a" * 64,
            page_keys=["b" * 64],
            state="running",
            cleanup_done=False,
        )
        db.add(run)
        db.flush()
        run_id = run.id
        db.add(
            AiAttempt(
                run_id=run.id,
                workspace_id=run.workspace_id,
                job_id=identifier,
                page_key="b" * 64,
                state="sending",
            )
        )
        db.add(
            AiConsent(
                job_id=identifier,
                workspace_id=run.workspace_id,
                actor_id=run.actor_id,
                granted=True,
                private={"temporary": "fictional"},
            )
        )
        db.add(
            Operation(
                workspace_id=run.workspace_id,
                job_id=identifier,
                input_revision=1,
                action="convert",
                state="running",
                lease_hash="c" * 64,
            )
        )
    with Session(world["engine"]) as db, db.begin():
        quarantine(db)
    with Session(world["engine"]) as db:
        run = db.get(AiRun, run_id)
        assert run.state == "cancelled" and not run.cleanup_done
        assert db.scalar(select(AiAttempt)).state == "uncertain"
        consent = db.get(AiConsent, identifier)
        assert not consent.granted and consent.private == {}
        operation = db.scalar(select(Operation))
        assert operation.state == "cancelled" and operation.lease_hash is None
        assert all(session.revoked for session in db.scalars(select(WebSession)))
    assert world["client"]("owner0").get("/api/v1/session").status_code == 401


def test_newer_tombstone_replays_real_objects_and_preserves_other_tenant(world, store):
    a = create(world)
    b = create(world, "owner1")
    assert upload(world["client"]("owner0"), a["id"]).status_code == 200
    assert upload(world["client"]("owner1"), b["id"]).status_code == 200
    identifier = UUID(a["id"])
    with Session(world["engine"]) as db:
        other = db.scalar(select(Artifact).where(Artifact.job_id == UUID(b["id"])))
        other_key = other.object_key
    with Session(world["engine"]) as db, db.begin():
        wrong = replay_removals(db, store, {(world["workspaces"][1], identifier): "removed"})
        assert wrong == {"jobs_fenced": 0, "objects_removed": 0}
        result = replay_removals(db, store, {(world["workspaces"][0], identifier): "removed"})
        assert result["jobs_fenced"] == 1 and result["objects_removed"] > 0
    with Session(world["engine"]) as db:
        job = db.get(Job, identifier)
        assert job.deletion_state == "pending" and job.removal["certificate"] is None
        for artifact in db.scalars(select(Artifact).where(Artifact.job_id == identifier)):
            assert artifact.state == "removed"
            with pytest.raises(ClientError):
                store.client.head_object(Bucket=store.bucket, Key=artifact.object_key)
    assert store.client.head_object(Bucket=store.bucket, Key=other_key)["ContentLength"] > 0


def test_unverified_removal_cannot_issue_restored_certificate(world, store, monkeypatch):
    job = create(world)
    assert upload(world["client"]("owner0"), job["id"]).status_code == 200
    identifier = UUID(job["id"])
    monkeypatch.setattr(store.client, "delete_object", lambda **kwargs: {})
    with Session(world["engine"]) as db, db.begin():
        with pytest.raises(ValueError, match="unverified"):
            replay_removals(db, store, {(world["workspaces"][0], identifier): "removed"})
    with Session(world["engine"]) as db:
        restored = db.get(Job, identifier)
        assert restored.deletion_state == "pending" and restored.removal["certificate"] is None
