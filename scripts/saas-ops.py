"""Local synthetic encrypted backups, disposable restore drills and anonymous operating checks.

Never restores over the active stack. Private outputs stay under ignored .local-saas.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from stmtconv.config import load_hosted_settings
from stmtconv.web.backup import BackupError, archive, create_key, digest, seal, unpack, unseal
from stmtconv.web.database import database, migrate
from stmtconv.web.models import (
    AiRun,
    Artifact,
    BackupReceipt,
    Base,
    Connection,
    Job,
    RestoreReceipt,
    now,
)
from stmtconv.web.operations import snapshot
from stmtconv.web.recovery import quarantine, replay_removals
from stmtconv.web.storage import ObjectStore
from stmtconv.web.vault import Vault

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local-saas"
BACKUPS = LOCAL / "backups"
CONFIGS = (
    "server.env",
    "migrate.env",
    "worker.env",
    "postgres.env",
    "keycloak.env",
    "s3.json",
    "realm.json",
    "bootstrap.json",
    "init.sql",
    "ai-key.env",
)
COMPOSE = ["docker", "compose", "--profile", "conversion", "-f", str(ROOT / "compose.saas.yaml")]
STORAGE_IMAGE = (
    "chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d"
)
IMAGE = "postgres@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24"


def command(args, *, input_file=None, output_file=None):
    result = subprocess.run(
        args,
        cwd=ROOT,
        stdin=input_file,
        stdout=output_file or subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise BackupError(
            "An operating command failed. Private command output is withheld; no success is claimed."
        )
    return result.stdout.decode().strip() if output_file is None else ""


def config():
    c = load_hosted_settings(LOCAL / "server.env")
    url = make_url(c.database_url.get_secret_value())
    if (
        c.mode != "local"
        or url.host != "127.0.0.1"
        or url.database != "dockling"
        or c.base_url != "http://127.0.0.1:8000"
    ):
        raise BackupError(
            "This utility supports only the documented local synthetic stack. Use the hosted runbook for production."
        )
    return c


def quiesced(c):
    try:
        connection = socket.create_connection(("127.0.0.1", 8000), timeout=1)
    except ConnectionRefusedError:
        pass
    except OSError:
        raise BackupError(
            "API quiescence is unverified; a timeout is not proof it stopped."
        ) from None
    else:
        connection.close()
        raise BackupError(
            "Stop the local API first; a cross-service backup needs quiesced writers."
        )
    for service in ("worker", "identity"):
        identifier = command(COMPOSE + ["ps", "-a", "-q", service])
        if (
            identifier
            and command(["docker", "inspect", "--format", "{{.State.Running}}", identifier])
            == "true"
        ):
            raise BackupError(
                "Stop worker and identity with docker compose before backup or restore drills. Keep PostgreSQL and storage running."
            )
    engine = database(c)
    try:
        with Session(engine) as db:
            if db.scalar(select(func.count(AiRun.id)).where(AiRun.cleanup_done.is_(False))):
                raise BackupError(
                    "AI cleanup is unverified. Resolve process teardown before creating a consistent backup."
                )
    finally:
        engine.dispose()


def counts(engine):
    with Session(engine) as db:
        return {
            table.name: db.scalar(select(func.count()).select_from(table))
            for table in Base.metadata.sorted_tables
        }


def backup(c, key, days):
    quiesced(c)
    if not 1 <= days <= 30:
        raise BackupError("Choose an explicit local backup expiry from 1 to 30 days.")
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    created = now()
    expires = created + timedelta(days=days)
    destination = BACKUPS / (created.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex + ".dockbak")
    store = ObjectStore(c)
    engine = database(c)
    try:
        metadata = {
            "row_counts": counts(engine),
            "objects": [],
            "config_names": list(CONFIGS),
            "created_at": created.isoformat(),
            "expires_at": expires.isoformat(),
            "source_commit": command(["git", "rev-parse", "HEAD"]),
            "source_dirty": bool(command(["git", "status", "--porcelain"])),
        }
        with Session(engine) as db:
            metadata["schema_version"] = db.scalar(text("SELECT version_num FROM alembic_version"))
            expected = {
                a.object_key: (a.bytes, a.sha256)
                for a in db.scalars(select(Artifact).where(Artifact.state == "active"))
            }
        with tempfile.TemporaryDirectory(prefix="backup-", dir=LOCAL) as temporary:
            stage = Path(temporary)
            files = {}
            for name in CONFIGS:
                source = LOCAL / name
                if not source.is_file() or source.is_symlink():
                    raise BackupError(
                        "Matched private configuration/vault material is missing; do not generate replacements."
                    )
                target = stage / name
                with target.open("xb") as output:
                    target.chmod(0o600)
                    output.write(source.read_bytes())
                files["configs/" + name] = target
            for dbname in ("dockling", "keycloak"):
                target = stage / (dbname + ".dump")
                with target.open("xb") as output:
                    target.chmod(0o600)
                    command(
                        COMPOSE
                        + ["exec", "-T", "postgres", "pg_dump", "-U", "postgres", "-Fc", dbname],
                        output_file=output,
                    )
                files["databases/" + dbname + ".dump"] = target
            inventory = []
            paginator = store.client.get_paginator("list_objects_v2")
            seen = set()
            total = 0
            for page in paginator.paginate(Bucket=store.bucket):
                for item in page.get("Contents", []):
                    if len(inventory) >= 9000:
                        raise BackupError("Local backup object limit exceeded.")
                    object_key = item["Key"]
                    if object_key in seen:
                        raise BackupError("Duplicate object inventory.")
                    seen.add(object_key)
                    name = f"objects/{len(inventory):06d}.bin"
                    target = stage / (str(len(inventory)) + ".bin")
                    response = store.client.get_object(Bucket=store.bucket, Key=object_key)
                    size = 0
                    h = hashlib.sha256()
                    with response["Body"] as body, target.open("xb") as output:
                        target.chmod(0o600)
                        while data := body.read(1024 * 1024):
                            size += len(data)
                            total += len(data)
                            if total > 1800 * 1024**2:
                                raise BackupError("Local backup size limit exceeded.")
                            h.update(data)
                            output.write(data)
                    if (
                        size != item["Size"]
                        or object_key in expected
                        and (size, h.hexdigest()) != expected[object_key]
                    ):
                        raise BackupError(
                            "Active artifact integrity failed; do not certify this backup."
                        )
                    inventory.append(
                        {"name": name, "key": object_key, "bytes": size, "sha256": h.hexdigest()}
                    )
                    files[name] = target
            if not set(expected) <= seen:
                raise BackupError("An active database artifact is missing from private storage.")
            metadata["objects"] = inventory
            plain = stage / "bundle.tar"
            archive(files, metadata, plain)
            checksum = seal(plain, destination, key, created=created, expires=expires)
        # The receipt follows durable sealed-file completion, and is outside its snapshot.
        owner = database(load_hosted_settings(LOCAL / "migrate.env"))
        try:
            with Session(owner) as db, db.begin():
                db.add(
                    BackupReceipt(
                        sha256=checksum,
                        created_at=created,
                        expires_at=expires,
                        objects=len(inventory),
                        bytes=destination.stat().st_size,
                        schema_version=metadata["schema_version"],
                    )
                )
        finally:
            owner.dispose()
        return {
            "status": "sealed",
            "file": str(destination.relative_to(ROOT)),
            "sha256": checksum,
            "objects": len(inventory),
            "bytes": destination.stat().st_size,
            "expires_at": expires.isoformat(),
        }
    finally:
        engine.dispose()


def owned_backup(path):
    if (
        path.is_symlink()
        or path.resolve().parent != BACKUPS.resolve()
        or not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{32}\.dockbak", path.name)
    ):
        raise BackupError(
            "Choose an owned archive inside .local-saas/backups; external files will not be changed."
        )
    return path


def rehearse_schema(container, restored_owner, stage):
    """Upgrade an isolated prior schema, then restore its ledger snapshot after a simulated rollback."""
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig

    from stmtconv.web.models import BillingEvidence, BillingInvoice, CommercialPlan, User, Workspace

    command(
        [
            "docker",
            "exec",
            container,
            "createdb",
            "-U",
            "postgres",
            "-O",
            "dockling_owner",
            "dockling_schema_probe",
        ]
    )
    url = make_url(restored_owner.database_url.get_secret_value()).set(
        database="dockling_schema_probe"
    )
    settings = restored_owner.model_copy(
        update={"database_url": SecretStr(url.render_as_string(hide_password=False))}
    )

    def revision(target):
        engine = database(settings)
        try:
            with engine.begin() as connection:
                cfg = AlembicConfig()
                cfg.set_main_option("script_location", str(ROOT / "src/stmtconv/web/migrations"))
                cfg.attributes["connection"] = connection
                alembic_command.upgrade(cfg, target)
        finally:
            engine.dispose()

    revision("0011_accounts_billing")
    engine = database(settings)
    try:
        with Session(engine) as db, db.begin():
            user = User(
                issuer=settings.oidc_issuer,
                subject=str(uuid4()),
                email="schema-restore@example.test",
                email_verified=True,
            )
            workspace = Workspace(name="Fictional schema rollback")
            db.add_all([user, workspace])
            db.flush()
            plan = CommercialPlan(
                actor_id=user.id,
                data={
                    "name": "Fictional rollback proof",
                    "pages_per_month": 100,
                    "seats": 1,
                    "monthly_amount": "25.00",
                    "currency": "USD",
                    "approved_for_customers": False,
                },
            )
            db.add(plan)
            db.flush()
            invoice = BillingInvoice(
                workspace_id=workspace.id,
                plan_id=plan.id,
                status="paid",
                version=3,
                valid_until=now() + timedelta(days=1),
            )
            db.add(invoice)
            db.flush()
            db.add(
                BillingEvidence(
                    workspace_id=workspace.id,
                    invoice_id=invoice.id,
                    actor_id=user.id,
                    version=3,
                    status="paid",
                    reference="fictional-rollback-ledger",
                )
            )
    finally:
        engine.dispose()
    baseline = stage / "prior-schema.dump"
    with baseline.open("xb") as output:
        baseline.chmod(0o600)
        command(
            [
                "docker",
                "exec",
                container,
                "pg_dump",
                "-U",
                "postgres",
                "-Fc",
                "dockling_schema_probe",
            ],
            output_file=output,
        )
    revision("head")
    engine = database(settings)
    try:
        with Session(engine) as db:
            if (
                db.scalar(text("SELECT version_num FROM alembic_version")) != "0012_operations"
                or db.scalar(select(func.count(BillingEvidence.id))) != 1
            ):
                raise BackupError(
                    "Forward migration did not preserve its fictional immutable ledger."
                )
    finally:
        engine.dispose()
    # Only this disposable container/database is dropped; never downgrade or
    # erase the live source ledger, and never use this path for production.
    command(
        [
            "docker",
            "exec",
            container,
            "dropdb",
            "-U",
            "postgres",
            "--force",
            "dockling_schema_probe",
        ]
    )
    command(
        [
            "docker",
            "exec",
            container,
            "createdb",
            "-U",
            "postgres",
            "-O",
            "dockling_owner",
            "dockling_schema_probe",
        ]
    )
    with baseline.open("rb") as source:
        command(
            [
                "docker",
                "exec",
                "-i",
                container,
                "pg_restore",
                "-U",
                "postgres",
                "--exit-on-error",
                "--dbname",
                "dockling_schema_probe",
            ],
            input_file=source,
        )
    engine = database(settings)
    try:
        with Session(engine) as db:
            if (
                db.scalar(text("SELECT version_num FROM alembic_version"))
                != "0011_accounts_billing"
                or db.scalar(text("SELECT to_regclass('web_backup_receipts')")) is not None
            ):
                raise BackupError("Restored prior schema did not match its snapshot.")
            invoice = db.scalar(select(BillingInvoice))
            plan = db.scalar(select(CommercialPlan))
            if (
                not invoice
                or invoice.status != "paid"
                or not plan
                or plan.data["monthly_amount"] != "25.00"
                or db.scalar(select(func.count(BillingEvidence.id))) != 1
            ):
                raise BackupError(
                    "Matched schema rollback did not preserve exact invoice/evidence records."
                )
    finally:
        engine.dispose()
    revision("head")
    revision("head")
    return True


def restore_drill(c, key, source):
    quiesced(c)
    source = owned_backup(source)
    checksum = digest(source)
    started = time.monotonic()
    suffix = uuid4().hex
    name = "dockling-restore-" + suffix
    volume = name + "-pg"
    bucket = name
    storage_name = name + "-s3"
    storage_volume = name + "-objects"
    created_container = created_volume = False
    created_storage_container = created_storage_volume = False
    checks = None
    target_engine = owner_engine = None
    try:
        with tempfile.TemporaryDirectory(prefix="restore-", dir=LOCAL) as temporary:
            stage = Path(temporary)
            plain = stage / "bundle.tar"
            _, expires = unseal(source, plain, key)
            if expires <= now():
                raise BackupError(
                    "Expired backups cannot certify current recovery. Keep them fenced and follow retention policy."
                )
            extracted = stage / "verified"
            meta = unpack(plain, extracted)
            if set(meta) != {
                "row_counts",
                "objects",
                "config_names",
                "created_at",
                "expires_at",
                "source_commit",
                "source_dirty",
                "schema_version",
            } or meta["config_names"] != list(CONFIGS):
                raise BackupError("Unsupported restore manifest.")
            command(
                ["docker", "volume", "create", "--label", "dockling.restore-drill=true", volume]
            )
            created_volume = True
            init = extracted / "configs/init.sql"
            # The host parent is 0700; only the explicitly mounted temporary bootstrap
            # file becomes container-readable, as in the documented local setup.
            init.chmod(0o644)
            command(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    name,
                    "--label",
                    "dockling.restore-drill=true",
                    "--network",
                    "bridge",
                    "-p",
                    "127.0.0.1::5432",
                    "--env-file",
                    str(extracted / "configs/postgres.env"),
                    "--mount",
                    f"type=volume,source={volume},target=/var/lib/postgresql/data",
                    "--mount",
                    f"type=bind,source={init},target=/docker-entrypoint-initdb.d/10-dockling.sql,readonly",
                    IMAGE,
                ]
            )
            created_container = True
            for _ in range(90):
                result = subprocess.run(
                    ["docker", "exec", name, "pg_isready", "-U", "postgres"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if result.returncode == 0:
                    # Initialization opens a temporary Unix server first; wait for TCP.
                    result = subprocess.run(
                        ["docker", "exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    if result.returncode == 0:
                        break
                time.sleep(0.5)
            else:
                raise BackupError("Disposable restore database did not become ready.")
            init.chmod(0o600)
            for dbname in ("dockling", "keycloak"):
                with (extracted / ("databases/" + dbname + ".dump")).open("rb") as input_file:
                    command(
                        [
                            "docker",
                            "exec",
                            "-i",
                            name,
                            "pg_restore",
                            "-U",
                            "postgres",
                            "--exit-on-error",
                            "--dbname",
                            dbname,
                        ],
                        input_file=input_file,
                    )
            port = int(
                command(
                    [
                        "docker",
                        "inspect",
                        "--format",
                        '{{(index (index .NetworkSettings.Ports "5432/tcp") 0).HostPort}}',
                        name,
                    ]
                )
            )
            restored = load_hosted_settings(extracted / "configs/server.env")
            restored_owner = load_hosted_settings(extracted / "configs/migrate.env")

            def relocated(settings):
                url = make_url(settings.database_url.get_secret_value()).set(
                    host="127.0.0.1", port=port
                )
                return settings.model_copy(
                    update={
                        "database_url": SecretStr(url.render_as_string(hide_password=False)),
                        "s3_bucket": bucket,
                    }
                )

            restored, restored_owner = relocated(restored), relocated(restored_owner)
            target_engine = database(restored)
            owner_engine = database(restored_owner)
            if counts(target_engine) != meta["row_counts"]:
                raise BackupError(
                    "Restored metadata counts do not match the authenticated snapshot."
                )
            with Session(target_engine) as db:
                if (
                    db.scalar(text("SELECT version_num FROM alembic_version"))
                    != meta["schema_version"]
                ):
                    raise BackupError("Restored schema does not match its snapshot.")
                vault = Vault(restored)
                keys = 0
                for connection in db.scalars(
                    select(Connection).where(Connection.ciphertext.is_not(None))
                ):
                    if connection.ciphertext:
                        vault.decrypt(connection.workspace_id, connection.id, connection.ciphertext)
                        keys += 1
                if db.scalar(
                    text("SELECT has_table_privilege(current_user,'web_backup_receipts','INSERT')")
                ):
                    raise BackupError("Restored API role can forge operational evidence.")
            identity_rows = command(
                [
                    "docker",
                    "exec",
                    name,
                    "psql",
                    "-U",
                    "postgres",
                    "-d",
                    "keycloak",
                    "-Atc",
                    "SELECT count(*) FROM user_entity",
                ]
            )
            if not identity_rows.isdecimal() or int(identity_rows) < 7:
                raise BackupError("Restored identity records are incomplete.")
            # Migration rehearsal is forward-only and repeatable; rollback restores a
            # matched database/object/vault snapshot rather than deleting a ledger.
            migrate(restored_owner)
            migrate(restored_owner)
            with Session(owner_engine) as db, db.begin():
                quarantine(db)
            command(
                [
                    "docker",
                    "volume",
                    "create",
                    "--label",
                    "dockling.restore-drill=true",
                    storage_volume,
                ]
            )
            created_storage_volume = True
            storage_config = extracted / "configs/s3.json"
            storage_config.chmod(0o644)
            command(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    storage_name,
                    "--label",
                    "dockling.restore-drill=true",
                    "--network",
                    "bridge",
                    "-p",
                    "127.0.0.1::8333",
                    "--mount",
                    f"type=volume,source={storage_volume},target=/data",
                    "--mount",
                    f"type=bind,source={storage_config},target=/etc/seaweedfs/s3.json,readonly",
                    STORAGE_IMAGE,
                    "server",
                    "-ip=127.0.0.1",
                    "-ip.bind=0.0.0.0",
                    "-dir=/data",
                    "-volume.max=16",
                    "-master.volumeSizeLimitMB=64",
                    "-filer",
                    "-s3",
                    "-s3.config=/etc/seaweedfs/s3.json",
                ]
            )
            created_storage_container = True
            storage_port = int(
                command(
                    [
                        "docker",
                        "inspect",
                        "--format",
                        '{{(index (index .NetworkSettings.Ports "8333/tcp") 0).HostPort}}',
                        storage_name,
                    ]
                )
            )
            restored = restored.model_copy(
                update={"s3_endpoint": f"http://127.0.0.1:{storage_port}"}
            )
            store = ObjectStore(restored)
            for _ in range(60):
                try:
                    store.ensure_bucket()
                    break
                except Exception:
                    time.sleep(0.5)
            else:
                raise BackupError("Disposable private storage did not become ready.")
            storage_config.chmod(0o600)
            inventory = meta["objects"]
            if not isinstance(inventory, list) or len(inventory) > 9000:
                raise BackupError("Invalid restored object inventory.")
            for entry in inventory:
                if (
                    not isinstance(entry, dict)
                    or set(entry) != {"name", "key", "bytes", "sha256"}
                    or not re.fullmatch(r"objects/[0-9]{6}\.bin", entry["name"])
                ):
                    raise BackupError("Invalid restored object mapping.")
                with (extracted / entry["name"]).open("rb") as data:
                    store.client.put_object(
                        Bucket=bucket,
                        Key=entry["key"],
                        Body=data,
                        ContentLength=entry["bytes"],
                        ChecksumSHA256=base64.b64encode(bytes.fromhex(entry["sha256"])).decode(),
                    )
            target_store = ObjectStore(restored)
            with Session(target_engine) as db:
                for artifact in db.scalars(select(Artifact).where(Artifact.state == "active")):
                    target_store.verified(artifact)
            for entry in inventory:
                body = store.client.get_object(Bucket=bucket, Key=entry["key"])["Body"]
                value = hashlib.sha256()
                size = 0
                with body:
                    while data := body.read(1024 * 1024):
                        value.update(data)
                        size += len(data)
                if (size, value.hexdigest()) != (entry["bytes"], entry["sha256"]):
                    raise BackupError("Restored object integrity failed.")
            # A stale backup cannot undo a newer deletion. Read the verified,
            # quiesced live source journal, then replay only exact workspace/job pairs.
            source_engine = database(c)
            try:
                with Session(source_engine) as db:
                    tombstones = {
                        (job.workspace_id, job.id): job.deletion_state
                        for job in db.scalars(select(Job).where(Job.deletion_state != "active"))
                    }
            finally:
                source_engine.dispose()
            with Session(owner_engine) as db, db.begin():
                replay = replay_removals(db, target_store, tombstones)
            schema_rehearsed = rehearse_schema(name, restored_owner, stage)
            from fastapi.testclient import TestClient

            from stmtconv.web.app import create_app

            application = create_app(restored)
            try:
                with TestClient(application, base_url=restored.base_url) as client:
                    if client.get("/api/v1/session").status_code != 401 or client.get(
                        "/api/v1/health/live"
                    ).json() != {"status": "alive"}:
                        raise BackupError("Restored API authentication boundary failed.")
            finally:
                application.state.engine.dispose()
            seconds = int(time.monotonic() - started)
            checks = {
                "database": True,
                "identity": True,
                "objects": len(inventory),
                "vault_keys": keys,
                "api_evidence_write_denied": True,
                "sessions_revoked": True,
                "processing_fenced": True,
                "live_tombstones_replayed": replay["jobs_fenced"],
                "forward_migration_repeated": True,
                "prior_schema_restore_rehearsed": schema_rehearsed,
                "api_auth_denied": True,
                "seconds": seconds,
            }
    finally:
        if target_engine is not None:
            target_engine.dispose()
        if owner_engine is not None:
            owner_engine.dispose()
        if created_storage_container:
            command(["docker", "rm", "-f", storage_name])
        if created_storage_volume:
            command(["docker", "volume", "rm", storage_volume])
        if created_container:
            command(["docker", "rm", "-f", name])
        if created_volume:
            command(["docker", "volume", "rm", volume])

    if checks is None:
        raise BackupError("Restore checks did not complete.")
    checks["isolated_resources_removed"] = True
    seconds = int(time.monotonic() - started)
    checks["seconds"] = seconds
    source_owner = database(load_hosted_settings(LOCAL / "migrate.env"))
    try:
        with Session(source_owner) as db, db.begin():
            record = db.scalar(select(BackupReceipt).where(BackupReceipt.sha256 == checksum))
            if record is None:
                raise BackupError(
                    "No matching sealed-backup receipt exists; cannot certify this drill."
                )
            db.add(RestoreReceipt(backup_id=record.id, seconds=seconds, checks=checks))
    finally:
        source_owner.dispose()
    return {
        "status": "verified_isolated_restore",
        **checks,
        "production_recovery_target": "not_promised",
    }


def verification_fixture(c, *, cleanup=False):
    """Ignored, fictional vault fixture only; never invokes a provider or changes a customer workspace."""
    from uuid import UUID

    from stmtconv.web.connections import ConnectionCreate
    from stmtconv.web.models import Job, Membership, User, Workspace

    quiesced(c)
    marker = LOCAL / "restore-proof.json"
    owner = database(load_hosted_settings(LOCAL / "migrate.env"))
    try:
        with Session(owner) as db, db.begin():
            if marker.exists():
                saved = json.loads(marker.read_text())
                workspace = db.get(Workspace, UUID(saved["workspace"]))
                connection = db.get(Connection, UUID(saved["connection"]))
                if (
                    not workspace
                    or not connection
                    or workspace.name != "Fictional restore-key verification"
                    or connection.workspace_id != workspace.id
                    or db.scalar(select(func.count(Job.id)).where(Job.workspace_id == workspace.id))
                ):
                    raise BackupError(
                        "The disposable vault fixture no longer matches; do not remove unrelated records."
                    )
                if cleanup:
                    db.delete(connection)
                    for member in db.scalars(
                        select(Membership).where(Membership.workspace_id == workspace.id)
                    ):
                        db.delete(member)
                    db.flush()
                    db.delete(workspace)
                    marker.unlink()
                    return {"status": "fictional_vault_fixture_removed"}
                return {"status": "fictional_vault_fixture_present"}
            if cleanup:
                return {"status": "no_fixture_to_remove"}
            user = db.scalar(
                select(User).where(
                    User.email == "owner-a@example.test", User.email_verified.is_(True)
                )
            )
            if user is None:
                raise BackupError("Verified fictional setup owner is missing.")
            workspace = Workspace(name="Fictional restore-key verification")
            db.add(workspace)
            db.flush()
            db.add(Membership(workspace_id=workspace.id, user_id=user.id, role="owner"))
            connection = Connection(
                id=uuid4(),
                workspace_id=workspace.id,
                name="Fictional key; never contact provider",
                config=ConnectionCreate(
                    name="Fictional restore proof", base_url="https://api.example.com/v1"
                ).model_dump(exclude={"name"}),
            )
            connection.ciphertext = Vault(c).encrypt(
                workspace.id, connection.id, "fictional-restore-proof-not-a-real-key"
            )
            db.add(connection)
            marker.write_text(
                json.dumps({"workspace": str(workspace.id), "connection": str(connection.id)})
            )
            marker.chmod(0o600)
        return {"status": "fictional_encrypted_key_fixture_created", "provider_calls": 0}
    finally:
        owner.dispose()


def purge(key, apply):
    eligible = 0
    removed = 0
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    for source in sorted(BACKUPS.glob("*.dockbak")):
        owned_backup(source)
        with tempfile.TemporaryDirectory(prefix="expiry-", dir=LOCAL) as temporary:
            _, expiry = unseal(source, Path(temporary) / "bundle.tar", key)
        if expiry <= now():
            eligible += 1
            if apply:
                source.unlink()
                removed += 1
    return {
        "status": "applied" if apply else "dry_run",
        "eligible": eligible,
        "removed": removed,
        "provider_backups": "separate_host_policy_required",
    }


def expiry_drill():
    """Exercise real expiry deletion in a separate temporary archive directory only."""
    global LOCAL, BACKUPS
    saved_local, saved_backups = LOCAL, BACKUPS
    try:
        with tempfile.TemporaryDirectory(prefix="expiry-drill-", dir=saved_local) as directory:
            LOCAL = Path(directory)
            BACKUPS = LOCAL / "backups"
            BACKUPS.mkdir(mode=0o700)
            key = LOCAL / "test-key.bin"
            create_key(key)
            plain = LOCAL / "empty.tar"
            archive({}, {"fictional": True}, plain)
            expired = BACKUPS / (now().strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex + ".dockbak")
            valid = BACKUPS / (now().strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex + ".dockbak")
            seal(
                plain,
                expired,
                key,
                created=now() - timedelta(days=2),
                expires=now() - timedelta(days=1),
            )
            seal(plain, valid, key, created=now(), expires=now() + timedelta(days=1))
            preview = purge(key, False)
            if preview["eligible"] != 1 or preview["removed"] != 0 or not expired.exists():
                raise BackupError("Expiry dry-run changed files or missed its synthetic fixture.")
            applied = purge(key, True)
            if applied["removed"] != 1 or expired.exists() or not valid.exists():
                raise BackupError(
                    "Expiry apply failed to preserve its unexpired synthetic archive."
                )
            return {
                "status": "verified_synthetic_expiry",
                "dry_run_preserved": True,
                "expired_removed": 1,
                "unexpired_preserved": True,
                "source_backups_untouched": True,
            }
    finally:
        LOCAL, BACKUPS = saved_local, saved_backups


def main():
    os.chdir(ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "key-init",
            "backup",
            "restore-drill",
            "purge",
            "expiry-drill",
            "check",
            "verification-fixture",
            "fixture-cleanup",
        ],
    )
    parser.add_argument("--key", type=Path, default=LOCAL / "backup-key.bin")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    c = config()
    if args.action == "key-init":
        create_key(args.key)
        result = {
            "status": "private_backup_key_created",
            "next": "Store an independent secure copy; never commit or include this key in the backup archive.",
        }
    elif args.action == "backup":
        result = backup(c, args.key, args.days)
    elif args.action == "restore-drill":
        if args.backup is None:
            parser.error("restore-drill requires --backup")
        result = restore_drill(c, args.key, args.backup)
    elif args.action in {"verification-fixture", "fixture-cleanup"}:
        result = verification_fixture(c, cleanup=args.action == "fixture-cleanup")
    elif args.action == "purge":
        result = purge(args.key, args.apply)
    elif args.action == "expiry-drill":
        result = expiry_drill()
    else:
        engine = database(c)
        try:
            with Session(engine) as db:
                result = snapshot(db, ObjectStore(c), c).model_dump()
        finally:
            engine.dispose()
        print(json.dumps(result, sort_keys=True))
        if result["status"] == "attention":
            raise SystemExit(2)
        return
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        import traceback

        from botocore.exceptions import ClientError
        from sqlalchemy.exc import DBAPIError

        if isinstance(error, DBAPIError):
            detail = error.orig.args[0] if error.orig.args else None
            code = str(detail.get("C", "")) if isinstance(detail, dict) else ""
            if re.fullmatch(r"[0-9A-Z]{5}", code):
                print("Database check failed: SQL state " + code, file=sys.stderr)
        for frame in traceback.extract_tb(error.__traceback__):
            if frame.filename == __file__:
                print("Operating check location: saas-ops.py:" + str(frame.lineno), file=sys.stderr)

        if isinstance(error, ClientError):
            # SDK operation and fixed error code only; never print keys, URLs,
            # response internals, command stderr or customer/object identifiers.
            code = str(error.response.get("Error", {}).get("Code", "unknown"))
            if re.fullmatch(r"[A-Za-z0-9_]{1,60}", code):
                print(
                    "Private storage operation failed: " + error.operation_name + " / " + code,
                    file=sys.stderr,
                )
        print(
            "Operating check failed ("
            + type(error).__name__
            + "); no successful backup/restore/purge is claimed. Review the local runbook.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
