"""Private S3 adapter: DB ownership and current revision precede every object read."""

import hashlib
from uuid import UUID, uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from botocore.session import Session as SdkSession
from sqlalchemy import select
from sqlalchemy.orm import Session

from stmtconv.config import HostedSettings
from stmtconv.web.errors import WebError, missing
from stmtconv.web.models import Artifact, Job
from stmtconv.web.repository import membership


class ObjectStore:
    def __init__(self, config: HostedSettings):
        self.bucket = config.s3_bucket
        sdk = SdkSession(
            session_vars={
                "profile": (None, None, None, None),
                "config_file": (None, None, "", None),
                "credentials_file": (None, None, "", None),
            }
        )
        self.client = boto3.Session(botocore_session=sdk).client(
            "s3",
            endpoint_url=config.s3_endpoint,
            aws_access_key_id=config.s3_access_key.get_secret_value(),
            aws_secret_access_key=config.s3_secret_key.get_secret_value(),
            region_name="us-east-1",
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=3,
                read_timeout=5,
                retries={"max_attempts": 1},
            ),
        )

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            if str(e.response["Error"]["Code"]) not in {"404", "NoSuchBucket", "NotFound"}:
                raise WebError(
                    503, "STORAGE_UNAVAILABLE", "Private storage is unavailable."
                ) from None
            self.client.create_bucket(Bucket=self.bucket)

    def probe(self) -> None:
        """Local setup proves actual signed write/read/delete, not just bucket existence."""
        self.ensure_bucket()
        key = "_setup-probes/" + uuid4().hex
        content = b"Dockling synthetic storage readiness"
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
            received = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read(
                len(content) + 1
            )
            if received != content:
                raise WebError(503, "STORAGE_UNAVAILABLE", "Private storage could not be verified.")
        finally:
            self.client.delete_object(Bucket=self.bucket, Key=key)

    def healthy(self) -> bool:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False

    def read(self, db: Session, workspace: UUID, actor_id: UUID, artifact_id: UUID) -> bytes:
        membership(db, workspace, actor_id)
        result = db.execute(
            select(Artifact, Job)
            .join(Job, (Artifact.workspace_id == Job.workspace_id) & (Artifact.job_id == Job.id))
            .where(
                Artifact.workspace_id == workspace,
                Artifact.id == artifact_id,
                Job.deletion_state == "active",
            )
        ).first()
        if result is None:
            raise missing()
        artifact, job = result
        if artifact.revision != job.revision:
            raise WebError(409, "STALE_REVISION", "This artifact belongs to an earlier revision.")
        try:
            data: bytes = self.client.get_object(Bucket=self.bucket, Key=artifact.object_key)[
                "Body"
            ].read(artifact.bytes + 1)
        except Exception:
            raise WebError(503, "STORAGE_UNAVAILABLE", "Private storage is unavailable.") from None
        if len(data) != artifact.bytes or hashlib.sha256(data).hexdigest() != artifact.sha256:
            raise WebError(503, "ARTIFACT_INTEGRITY", "This artifact could not be verified.")
        return data
