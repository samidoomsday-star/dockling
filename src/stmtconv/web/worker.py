"""Leased offline worker. Only scoped SQL functions and a capability socket are available."""

import base64
import hashlib
import json
import multiprocessing
import os
import resource
import secrets
import tempfile
import threading
import time
from dataclasses import dataclass
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import cast
from uuid import UUID

from sqlalchemy import Engine, create_engine, text

from stmtconv.config import (
    WorkerSettings,
    clear_worker_credentials,
    configure_offline,
    load_settings,
    load_worker_settings,
)
from stmtconv.errors import StmtconvError
from stmtconv.web.broker import BrokerArtifacts
from stmtconv.web.pipeline import (
    ArtifactBundle,
    PipelineOperations,
    PipelineResult,
    PipelineTask,
    compute,
)

RESULT_BYTES = 32 * 1024**2


@dataclass(frozen=True)
class ParserLimits:
    seconds: int
    models: Path
    max_pages: int


def encode_result(result: PipelineResult) -> bytes:
    payload = json.dumps(
        {
            "record": result.record,
            "artifacts": [
                {"id": str(a.id), "kind": a.kind, "data": base64.b64encode(a.data).decode()}
                for a in result.artifacts
            ],
        },
        allow_nan=False,
    ).encode()
    if len(payload) > RESULT_BYTES:
        raise ValueError("Parser output limit")
    return payload


def decode_result(data: bytes) -> PipelineResult:
    value = json.loads(data)
    if not isinstance(value, dict) or set(value) != {"record", "artifacts"}:
        raise ValueError("Invalid parser result")
    if (
        not isinstance(value["record"], dict)
        or not isinstance(value["artifacts"], list)
        or len(value["artifacts"]) > 130
    ):
        raise ValueError("Invalid parser result")
    artifacts = []
    for a in value["artifacts"]:
        if (
            not isinstance(a, dict)
            or set(a) != {"id", "kind", "data"}
            or a["kind"] not in {"normalized", "page"}
        ):
            raise ValueError("Invalid parser artifact")
        content = base64.b64decode(a["data"], validate=True)
        if not 0 < len(content) <= 8 * 1024**2:
            raise ValueError("Parser artifact limit")
        artifacts.append(ArtifactBundle(UUID(a["id"]), a["kind"], content))
    return PipelineResult(value["record"], artifacts)


class LeasedPostgres:
    def __init__(self, engine: Engine):
        self.engine = engine

    def claim(self, token: str) -> PipelineTask | None:
        with self.engine.begin() as connection:
            value = connection.scalar(
                text("SELECT dockling_claim(:hash)"),
                {"hash": hashlib.sha256(token.encode()).hexdigest()},
            )
        return PipelineTask.model_validate(value) if value else None

    def heartbeat(self, task: PipelineTask, token: str, stage: str, pages: int) -> bool:
        with self.engine.begin() as connection:
            return bool(
                connection.scalar(
                    text("SELECT dockling_heartbeat(:id,:hash,:gen,:stage,:pages)"),
                    {
                        "id": task.id,
                        "hash": hashlib.sha256(token.encode()).hexdigest(),
                        "gen": task.generation,
                        "stage": stage,
                        "pages": pages,
                    },
                )
            )

    def publish(self, task: PipelineTask, token: str, result: dict[str, object]) -> bool:
        with self.engine.begin() as connection:
            return bool(
                connection.scalar(
                    text("SELECT dockling_publish(:id,:hash,:gen,CAST(:result AS jsonb))"),
                    {
                        "id": task.id,
                        "hash": hashlib.sha256(token.encode()).hexdigest(),
                        "gen": task.generation,
                        "result": json.dumps(result),
                    },
                )
            )


def parser_child(
    pipe: Connection,
    task: PipelineTask,
    documents: dict[str, bytes],
    passwords: dict[str, str],
    cfg: ParserLimits,
    directory: str,
) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (cfg.seconds, cfg.seconds + 1))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    configure_offline(True)
    # Native PDF/OCR diagnostics may contain input text. Keep them out of worker logs.
    with open(os.devnull, "w") as sink:
        os.dup2(sink.fileno(), 1)
        os.dup2(sink.fileno(), 2)
    try:
        settings = load_settings(env_file=Path("/nonexistent"))
        settings.artifacts_path = cfg.models
        settings.num_threads = 2
        settings.ai_api_key = None
        result = compute(
            task,
            documents,
            passwords,
            Path(directory),
            settings,
            cfg.max_pages,
            progress=lambda pages: pipe.send_bytes(json.dumps({"progress": pages}).encode()),
        )
        pipe.send_bytes(encode_result(result))
    except StmtconvError as error:
        pipe.send_bytes(encode_result(PipelineResult({"state": "failed", "code": error.code})))
    except Exception:
        pipe.send_bytes(
            encode_result(PipelineResult({"state": "failed", "code": "DOCUMENT_INVALID"}))
        )
    finally:
        passwords.clear()
        pipe.close()


def process_one(operations: PipelineOperations, cfg: WorkerSettings) -> bool:
    token = secrets.token_hex(32)
    task = operations.claim(token)
    if task is None:
        return False
    artifacts = BrokerArtifacts(cfg.broker_socket, task, token)
    parser: BaseProcess | None = None
    receive: Connection | None = None
    scratch = tempfile.TemporaryDirectory(prefix="parse-", dir="/tmp")
    try:
        if not operations.heartbeat(
            task, token, "inspecting" if task.action == "intake" else "converting", 0
        ):
            return True
        documents = {
            str(f.id): artifacts.read(
                f.normalized_id or f.original_id
                if task.action == "intake"
                else cast("UUID", f.normalized_id)
            )
            for f in task.files
        }
        passwords = artifacts.passwords() if task.action == "intake" else {}
        context = multiprocessing.get_context("spawn")
        receive, send = context.Pipe(duplex=False)
        parser = context.Process(
            target=parser_child,
            args=(
                send,
                task,
                documents,
                passwords,
                ParserLimits(cfg.seconds, cfg.models, cfg.max_pages),
                scratch.name,
            ),
            daemon=True,
        )
        parser.start()
        send.close()
        passwords.clear()
        documents.clear()
        deadline = time.monotonic() + cfg.seconds
        result = None
        received: list[bytes] = []
        completed = [0]
        ready = threading.Event()

        def read_result() -> None:
            try:
                while True:
                    payload = receive.recv_bytes(RESULT_BYTES)
                    message = json.loads(payload)
                    if (
                        isinstance(message, dict)
                        and set(message) == {"progress"}
                        and type(message["progress"]) is int
                        and 0 <= message["progress"] <= cfg.max_pages
                    ):
                        completed[0] = message["progress"]
                    else:
                        received.append(payload)
                        break
            except (EOFError, OSError, ValueError):
                pass
            finally:
                ready.set()

        reader = threading.Thread(target=read_result, daemon=True)
        reader.start()
        while time.monotonic() < deadline:
            if ready.wait(5):
                if received:
                    result = decode_result(received[0])
                break
            if not parser.is_alive():
                break
            if not operations.heartbeat(
                task, token, "inspecting" if task.action == "intake" else "converting", completed[0]
            ):
                return True
        if not isinstance(result, PipelineResult):
            result = PipelineResult({"state": "failed", "code": "WORKER_LIMIT"})
        for bundle in result.artifacts:
            if time.monotonic() > deadline or not operations.heartbeat(
                task, token, "publishing", completed[0]
            ):
                return True
            artifacts.stage(bundle)
        if operations.heartbeat(task, token, "publishing", completed[0]):
            operations.publish(task, token, result.record)
    except Exception:
        try:
            operations.publish(task, token, {"state": "failed", "code": "WORKER_UNAVAILABLE"})
        except Exception:
            pass
    finally:
        if parser:
            if parser.is_alive():
                parser.terminate()
            parser.join(timeout=5)
            if parser.is_alive():
                parser.kill()
                parser.join(timeout=5)
        if receive:
            receive.close()
        scratch.cleanup()
    return True


def main() -> None:
    configure_offline(True)
    cfg = load_worker_settings()
    clear_worker_credentials()
    from stmtconv.model_setup import load_manifest, verify_artifacts

    try:
        verify_artifacts(cfg.models, load_manifest())
    except Exception:
        raise SystemExit(
            "Worker models are missing or differ from the pinned hashes. Run worker-build during setup."
        ) from None
    engine = create_engine(
        cfg.database_url.get_secret_value(),
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"timeout": 5},
    )
    operations: PipelineOperations = LeasedPostgres(engine)
    print("Restricted offline conversion worker started.", flush=True)
    while True:
        try:
            if not process_one(operations, cfg):
                time.sleep(1)
        except Exception:
            # No provider/DB/parser internals or document bytes in process logs.
            print("Worker service unavailable; retrying.", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
