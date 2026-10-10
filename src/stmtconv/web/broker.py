"""Private Unix-socket capability broker; workers never receive S3 or user credentials."""

import base64
import hashlib
import hmac
import http.client
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn, UnixStreamServer
from typing import cast
from uuid import UUID

from sqlalchemy import func, select

from stmtconv.config import HostedSettings
from stmtconv.web.database import PostgresUnitOfWork
from stmtconv.web.errors import WebError
from stmtconv.web.models import Artifact, Job, Membership, Operation, Workspace
from stmtconv.web.pipeline import ArtifactBundle, PipelineTask
from stmtconv.web.storage import ObjectStore


class PasswordVault:
    """Short-lived memory only; restart/claim crash asks the user to enter again."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.values: dict[UUID, tuple[float, dict[str, str]]] = {}

    def put(self, operation: UUID, file: UUID, password: str) -> None:
        with self.lock:
            self.values = {k: v for k, v in self.values.items() if v[0] > time.monotonic()}
            self.values[operation] = (time.monotonic() + 300, {str(file): password})

    def take(self, operation: UUID) -> dict[str, str]:
        with self.lock:
            value = self.values.pop(operation, None)
            return value[1] if value and value[0] > time.monotonic() else {}


class Broker:
    def __init__(self, config: HostedSettings, uow: PostgresUnitOfWork, store: ObjectStore):
        self.config, self.uow, self.store = config, uow, store
        self.passwords = PasswordVault()
        self.server: UnixStreamServer | None = None

    def call(self, value: dict[str, object]) -> dict[str, object]:
        oid, generation = UUID(str(value["operation"])), int(str(value["generation"]))
        token_hash = hashlib.sha256(str(value["token"]).encode()).hexdigest()
        with self.uow.transaction() as db:
            operation = db.get(Operation, oid)
            if operation is None or operation.lease_hash is None:
                raise ValueError
            from stmtconv.web.models import now

            job = db.scalar(
                select(Job).where(
                    Job.workspace_id == operation.workspace_id, Job.id == operation.job_id
                )
            )
            member = db.scalar(
                select(Membership).where(
                    Membership.workspace_id == operation.workspace_id,
                    Membership.user_id == operation.actor_id,
                    Membership.active.is_(True),
                    Membership.role.in_(["owner", "editor"]),
                )
            )
            if (
                not hmac.compare_digest(operation.lease_hash, token_hash)
                or operation.lease_generation != generation
                or operation.state != "running"
                or operation.lease_until is None
                or operation.lease_until <= now()
                or job is None
                or job.deletion_state != "active"
                or job.revision != operation.input_revision
                or member is None
            ):
                raise ValueError
            if value["action"] == "passwords":
                return {"passwords": self.passwords.take(oid)}
            aid = UUID(str(value["artifact"]))
            if value["action"] == "read":
                artifact = db.scalar(
                    select(Artifact).where(
                        Artifact.id == aid,
                        Artifact.workspace_id == operation.workspace_id,
                        Artifact.job_id == operation.job_id,
                        Artifact.state == "active",
                        Artifact.kind.in_(["original", "normalized"]),
                        Artifact.revision == operation.input_revision,
                    )
                )
                if artifact is None:
                    raise ValueError
                data = self.store.verified(artifact)
                return {"data": base64.b64encode(data).decode()}
            if value["action"] != "stage" or value["kind"] not in {"normalized", "page"}:
                raise ValueError
            db.scalar(
                select(Workspace).where(Workspace.id == operation.workspace_id).with_for_update()
            )
            db.refresh(operation)
            db.refresh(job)
            current_member = db.scalar(
                select(Membership.id).where(
                    Membership.workspace_id == operation.workspace_id,
                    Membership.user_id == operation.actor_id,
                    Membership.active.is_(True),
                    Membership.role.in_(["owner", "editor"]),
                )
            )
            if (
                operation.state != "running"
                or operation.lease_until is None
                or operation.lease_until <= now()
                or operation.lease_hash != token_hash
                or operation.lease_generation != generation
                or job.deletion_state != "active"
                or job.revision != operation.input_revision
                or current_member is None
            ):
                raise ValueError
            data = base64.b64decode(str(value["data"]), validate=True)
            if len(data) > self.config.upload_bytes or not data:
                raise ValueError
            used = (
                db.scalar(
                    select(func.coalesce(func.sum(Artifact.bytes), 0)).where(
                        Artifact.workspace_id == operation.workspace_id, Artifact.state != "removed"
                    )
                )
                or 0
            )
            if used + len(data) > self.config.workspace_bytes:
                raise WebError(
                    429, "TEST_QUOTA", "The workspace's test storage limit has been reached."
                )
            artifact = Artifact(
                id=aid,
                workspace_id=operation.workspace_id,
                job_id=operation.job_id,
                revision=operation.input_revision,
                operation_id=oid,
                generation=generation,
                object_key="pipeline/" + str(oid) + "/" + str(generation) + "/" + str(aid),
                bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                kind=str(value["kind"]),
                state="staged",
            )
            db.add(artifact)
            db.flush()
            self.store.write(artifact, data)
            return {"stored": True}

    def start(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o711)
        if path.exists():
            # Never unlink a live server's socket.
            probe = socket.socket(socket.AF_UNIX)
            try:
                probe.connect(str(path))
            except ConnectionRefusedError:
                path.unlink()
            else:
                raise RuntimeError("A private broker is already running")
            finally:
                probe.close()
        broker = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                pass

            def do_POST(self) -> None:
                self.connection.settimeout(15)
                status = 200
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if self.path != "/capability" or not 0 < length <= 12 * 1024**2:
                        raise ValueError
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict):
                        raise ValueError
                    result = broker.call(payload)
                except Exception:
                    status, result = 403, {"code": "BROKER_DENIED"}
                data = json.dumps(result).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        class Server(ThreadingMixIn, UnixStreamServer):
            daemon_threads = True
            slots = threading.BoundedSemaphore(4)

            def process_request(
                self, request: socket.socket | tuple[bytes, socket.socket], client_address: str
            ) -> None:
                if not self.slots.acquire(blocking=False):
                    self.shutdown_request(request)
                    return
                try:
                    super().process_request(request, client_address)
                except Exception:
                    self.slots.release()
                    raise

            def process_request_thread(
                self, request: socket.socket | tuple[bytes, socket.socket], client_address: str
            ) -> None:
                try:
                    super().process_request_thread(request, client_address)
                finally:
                    self.slots.release()

        self.server = Server(str(path), Handler)
        path.chmod(0o666)  # capability token + private parent; unprivileged worker UID may connect
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()


class SocketConnection(http.client.HTTPConnection):
    def __init__(self, path: Path):
        super().__init__("localhost", timeout=15)
        self.path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(15)
        self.sock.connect(str(self.path))


class BrokerArtifacts:
    def __init__(self, path: Path, task: PipelineTask, token: str):
        self.path, self.task, self.token = path, task, token

    def call(self, action: str, **values: object) -> dict[str, object]:
        body = json.dumps(
            {
                "operation": str(self.task.id),
                "generation": self.task.generation,
                "token": self.token,
                "action": action,
                **values,
            }
        ).encode()
        connection = SocketConnection(self.path)
        try:
            connection.request("POST", "/capability", body, {"Content-Type": "application/json"})
            response = connection.getresponse()
            if response.status != 200:
                raise WebError(409, "LEASE_REVOKED", "The operation is no longer current.")
            value = json.loads(response.read(12 * 1024**2))
            return cast(dict[str, object], value)
        finally:
            connection.close()

    def read(self, artifact: UUID) -> bytes:
        return base64.b64decode(
            str(self.call("read", artifact=str(artifact))["data"]), validate=True
        )

    def stage(self, artifact: ArtifactBundle) -> None:
        self.call(
            "stage",
            artifact=str(artifact.id),
            kind=artifact.kind,
            data=base64.b64encode(artifact.data).decode(),
        )

    def passwords(self) -> dict[str, str]:
        return cast(dict[str, str], self.call("passwords")["passwords"])
