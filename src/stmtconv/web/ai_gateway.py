"""Trusted, serialized hosted AI gateway. The document parser never gets keys/egress."""

import os
import stat
import threading
from pathlib import Path
from typing import cast
from uuid import UUID

from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from stmtconv.config import HostedSettings
from stmtconv.extract.ai_engine import Rows, output_text, payload
from stmtconv.web import connections
from stmtconv.web.ai_api import checked
from stmtconv.web.ai_core import apply_results, minimized
from stmtconv.web.database import PostgresUnitOfWork
from stmtconv.web.errors import WebError
from stmtconv.web.models import AiAttempt, AiConsent, AiRun, Connection, Event, Job, Workspace
from stmtconv.web.owner_config import processing_settings
from stmtconv.web.repository import membership
from stmtconv.web.review_api import revise, snapshot
from stmtconv.web.vault import Vault


class Gateway:
    def __init__(self, config: HostedSettings, engine: Engine):
        self.config, self.engine = config, engine
        self.uow = PostgresUnitOfWork(engine)
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None

    def _lock(self, db: Session, run: AiRun) -> Job:
        db.scalar(select(Workspace).where(Workspace.id == run.workspace_id).with_for_update())
        db.refresh(run)
        job = db.get(Job, run.job_id)
        if (
            job is None
            or job.workspace_id != run.workspace_id
            or job.deletion_state != "active"
            or run.state != "running"
        ):
            raise WebError(409, "AI_INPUT_REVOKED", "This request is no longer authorized.")
        membership(db, run.workspace_id, run.actor_id, write=True)
        return job

    def process_one(self) -> bool:
        with self.uow.transaction() as db:
            run = db.scalar(
                select(AiRun)
                .where(AiRun.state == "queued")
                .order_by(AiRun.created_at, AiRun.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if run is None:
                return False
            identifier = run.id
            run.state, run.cleanup_done = "running", False
        current_attempt: UUID | None = None
        response = None
        selected = None
        records = None
        results: dict[str, Rows] = {}
        names: list[str] = []
        body: dict[str, object] | None = None
        content: str | None = None
        cells: Rows | None = None
        updated: list[dict[str, object]] | None = None
        consent: AiConsent | None = None
        connection: Connection | None = None
        try:
            with self.uow.transaction() as db:
                run = db.get(AiRun, identifier)
                assert run is not None
                job = self._lock(db, run)
                consent, _ = checked(db, job, self.config, run)
                keys = list(run.page_keys)
                names = cast(list[str], consent.private.get("names", []))
                records = snapshot(db, job).statements
            for page in keys:
                if self.stop.is_set():
                    raise WebError(409, "AI_STOPPED", "The gateway is stopping.")
                with self.uow.transaction() as db:
                    run = db.get(AiRun, identifier)
                    assert run is not None
                    job = self._lock(db, run)
                    consent, connection = checked(db, job, self.config, run)
                    selected = connections.provider(connection, Vault(self.config))
                    attempt = db.scalar(
                        select(AiAttempt).where(
                            AiAttempt.run_id == identifier, AiAttempt.page_key == page
                        )
                    )
                    if attempt is None or attempt.state != "reserved":
                        raise WebError(
                            409,
                            "AI_ATTEMPT_USED",
                            "An external request must never be resent automatically.",
                        )
                    content = minimized(records, page, names)
                    body = payload(selected, content)
                    current_attempt = attempt.id
                    attempt.state = "sending"
                # This intent is committed before external send. No SQL transaction/lock is held.
                response = connections.transport(selected).request(
                    "POST", selected.completion_route, body
                )
                cells = Rows.model_validate_json(output_text(response, selected.api_style))
                with self.uow.transaction() as db:
                    run = db.get(AiRun, identifier)
                    assert run is not None
                    job = self._lock(db, run)
                    checked(db, job, self.config, run)
                    attempt = db.get(AiAttempt, current_attempt)
                    assert attempt is not None
                    attempt.state = "succeeded"
                    # No raw provider response is retained; all publication is atomic below.
                results[page] = cells
                current_attempt = None
                response = selected = None
            updated = apply_results(
                records, results, processing_settings(job.runtime_config), names
            )
            with self.uow.transaction() as db:
                run = db.get(AiRun, identifier)
                assert run is not None
                job = self._lock(db, run)
                checked(db, job, self.config, run)
                revise(
                    db,
                    job,
                    run.actor_id,
                    updated,
                    {"action": "ai.cells", "request_id": str(identifier), "pages": len(keys)},
                )
                run.state = "succeeded"
                db.add(
                    Event(
                        workspace_id=run.workspace_id,
                        job_id=run.job_id,
                        actor_id=run.actor_id,
                        action="ai.request.completed",
                        revision=job.revision,
                    )
                )
        except Exception:
            # If send was begun, uncertainty is retained even when the job was cancelled.
            # A response/schema failure is also conservative: no automatic paid retry.
            with self.uow.transaction() as db:
                run = db.get(AiRun, identifier)
                assert run is not None
                db.scalar(
                    select(Workspace).where(Workspace.id == run.workspace_id).with_for_update()
                )
                db.refresh(run)
                if current_attempt:
                    attempt = db.get(AiAttempt, current_attempt)
                    assert attempt is not None
                    attempt.state = "uncertain"
                    run.error_code = "AI_OUTCOME_UNCERTAIN"
                else:
                    run.error_code = "AI_RESULT_NOT_APPLIED"
                if run.state != "cancelled":
                    run.state = "uncertain" if current_attempt else "failed"
                db.add(
                    Event(
                        workspace_id=run.workspace_id,
                        job_id=run.job_id,
                        actor_id=run.actor_id,
                        action="ai.request.stopped",
                        revision=run.input_revision,
                        code=run.error_code,
                    )
                )
        finally:
            # Release private request/result references before acknowledging cleanup.
            response = selected = records = None
            results.clear()
            names = []
            body = content = cells = updated = None
            consent = connection = None
            with self.uow.transaction() as db:
                run = db.get(AiRun, identifier)
                if run:
                    run.cleanup_done = True
        return True

    def start(self) -> None:
        def loop() -> None:
            # The initial topology has one Linux API process. A DB lock by itself cannot
            # establish that an old process has released private memory after losing SQL.
            # Only a local OS lock permits automatic crash-cleanup acknowledgement.
            import fcntl

            directory = Path("/tmp") / ("dockling-ai-" + str(os.getuid()))
            directory.mkdir(mode=0o700, exist_ok=True)
            metadata = directory.lstat()
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) != 0o700
            ):
                return
            descriptor = os.open(
                directory / "gateway.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
            )
            lock = os.fdopen(descriptor, "r+")
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                lock.close()
                return
            try:
                while not self.stop.is_set():
                    try:
                        self._serve(self.config.mode == "local")
                        break
                    except Exception:
                        # Retry unavailable infrastructure without logging private SQL/provider data.
                        self.stop.wait(1)
            finally:
                lock.close()

        self.thread = threading.Thread(target=loop, name="scoped-ai-gateway", daemon=True)
        self.thread.start()

    def _serve(self, acknowledge_cleanup: bool) -> None:
        with self.engine.connect() as owner:
            if not owner.scalar(text("SELECT pg_try_advisory_lock(7319322)")):
                return
            try:
                self._recover(acknowledge_cleanup)
                while not self.stop.is_set():
                    try:
                        if self.process_one():
                            continue
                    except Exception:
                        pass  # Never print provider/statement/credential exception content.
                    self.stop.wait(1)
            finally:
                owner.execute(text("SELECT pg_advisory_unlock(7319322)"))

    def close(self) -> None:
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=45)

    def _recover(self, acknowledge_cleanup: bool) -> None:
        with self.uow.transaction() as db:
            for run in db.scalars(select(AiRun).where(AiRun.cleanup_done.is_(False))):
                attempts = list(db.scalars(select(AiAttempt).where(AiAttempt.run_id == run.id)))
                uncertain = any(a.state == "sending" for a in attempts)
                for attempt in attempts:
                    if attempt.state == "sending":
                        attempt.state = "uncertain"
                if run.state != "cancelled":
                    run.state = "uncertain" if uncertain else "failed"
                run.error_code = "AI_OUTCOME_UNCERTAIN" if uncertain else "AI_GATEWAY_INTERRUPTED"
                # Hosted multi-process recovery needs a verified process/container
                # teardown receipt in the deployment phase. Withhold deletion now.
                run.cleanup_done = acknowledge_cleanup
