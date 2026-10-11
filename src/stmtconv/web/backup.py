"""Streaming authenticated backup encryption and bounded, traversal-safe archive reads."""

import hashlib
import json
import os
import stat
import struct
import tarfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO, cast

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = b"DOCKBKP1"
HEADER = struct.Struct(">8sQQ12s")
CHUNK = 1024 * 1024
MAX_BYTES = 2 * 1024**3
MAX_FILES = 10000


class BackupError(ValueError):
    """Safe operator error; never include the original exception or private contents."""


def _private(path: Path) -> None:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise BackupError("Use an owned regular private file with mode 0600.")


def _create(path: Path) -> BinaryIO:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    return os.fdopen(descriptor, "wb")


def create_key(path: Path) -> None:
    with _create(path) as stream:
        stream.write(os.urandom(32))


def key_bytes(path: Path) -> bytes:
    _private(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        value = stream.read(33)
    if len(value) != 32:
        raise BackupError(
            "Use the independent 256-bit backup key; never substitute the BYOK vault key."
        )
    return value


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            value.update(chunk)
    return value.hexdigest()


def seal(plain: Path, destination: Path, key: Path, *, created: datetime, expires: datetime) -> str:
    _private(plain)
    secret = key_bytes(key)
    if plain.stat().st_size > MAX_BYTES or expires <= created:
        raise BackupError("Backup size or expiry is outside the permitted bounds.")
    nonce = os.urandom(12)
    header = HEADER.pack(MAGIC, int(created.timestamp()), int(expires.timestamp()), nonce)
    encryptor = Cipher(algorithms.AES(secret), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header)
    made = False
    try:
        with _create(destination) as output, plain.open("rb") as source:
            made = True
            output.write(header)
            for chunk in iter(lambda: source.read(CHUNK), b""):
                output.write(encryptor.update(chunk))
            output.write(encryptor.finalize())
            output.write(encryptor.tag)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        if made:
            destination.unlink(missing_ok=True)
        raise BackupError(
            "The encrypted backup was not completed; no success receipt was written."
        ) from None
    return digest(destination)


def unseal(source: Path, destination: Path, key: Path) -> tuple[datetime, datetime]:
    """Authenticate the entire ciphertext before any archive member is parsed or restored."""
    _private(source)
    secret = key_bytes(key)
    length = source.stat().st_size
    if length < HEADER.size + 16 or length > MAX_BYTES + HEADER.size + 16:
        raise BackupError("The backup length is invalid or exceeds its limit.")
    made = False
    try:
        with source.open("rb") as encrypted:
            header = encrypted.read(HEADER.size)
            magic, start, end, nonce = HEADER.unpack(header)
            if magic != MAGIC or end <= start:
                raise ValueError
            encrypted.seek(-16, os.SEEK_END)
            tag = encrypted.read(16)
            encrypted.seek(HEADER.size)
            decryptor = Cipher(algorithms.AES(secret), modes.GCM(nonce, tag)).decryptor()
            decryptor.authenticate_additional_data(header)
            with _create(destination) as output:
                made = True
                remaining = length - HEADER.size - 16
                while remaining:
                    chunk = encrypted.read(min(remaining, CHUNK))
                    if not chunk:
                        raise ValueError
                    output.write(decryptor.update(chunk))
                    remaining -= len(chunk)
                output.write(decryptor.finalize())
        return datetime.fromtimestamp(start, UTC), datetime.fromtimestamp(end, UTC)
    except Exception:
        if made:
            destination.unlink(missing_ok=True)
        raise BackupError(
            "Backup authentication failed; nothing may be restored or purged."
        ) from None


def archive(files: Mapping[str, Path], metadata: dict[str, object], destination: Path) -> None:
    if len(files) > MAX_FILES or "manifest.json" in files:
        raise BackupError("Invalid backup inventory.")
    entries = []
    total = 0
    made = False
    try:
        with _create(destination) as output:
            made = True
            with tarfile.open(fileobj=output, mode="w") as bundle:
                for name, path in sorted(files.items()):
                    _safe_name(name)
                    _private(path)
                    size = path.stat().st_size
                    total += size
                    if total > MAX_BYTES - 10 * 1024**2:
                        raise BackupError("Backup inventory exceeds its limit.")
                    entries.append({"name": name, "bytes": size, "sha256": digest(path)})
                    entry = tarfile.TarInfo(name)
                    entry.size, entry.mode, entry.mtime = size, 0o600, 0
                    with path.open("rb") as stream:
                        bundle.addfile(entry, stream)
                from io import BytesIO

                content = json.dumps(
                    {"format": 1, "files": entries, "metadata": metadata}, sort_keys=True
                ).encode()
                if len(content) > 10 * 1024**2:
                    raise BackupError("Backup manifest exceeds its limit.")
                entry = tarfile.TarInfo("manifest.json")
                entry.size, entry.mode, entry.mtime = len(content), 0o600, 0
                bundle.addfile(entry, BytesIO(content))
    except Exception:
        if made:
            destination.unlink(missing_ok=True)
        raise BackupError("The backup inventory could not be archived.") from None


def _safe_name(name: str) -> None:
    path = PurePosixPath(name)
    if (
        not name
        or len(name) > 200
        or "\\" in name
        or path.is_absolute()
        or any(p in {".", ".."} for p in name.split("/"))
    ):
        raise BackupError("Unsafe archive member rejected.")


def unpack(source: Path, destination: Path) -> dict[str, object]:
    """Never use extractall, trust tar paths, follow links, or accept unlisted members."""
    _private(source)
    if destination.exists() or source.stat().st_size > MAX_BYTES:
        raise BackupError("Restore needs a new private directory and a bounded archive.")
    destination.mkdir(mode=0o700)
    actual: dict[str, dict[str, object]] = {}
    total = 0
    try:
        with tarfile.open(source, "r:") as bundle:
            for entry in bundle:
                _safe_name(entry.name)
                if (
                    not entry.isfile()
                    or entry.name in actual
                    or len(actual) >= MAX_FILES + 1
                    or entry.size < 0
                ):
                    raise BackupError("Duplicate, linked or invalid archive member rejected.")
                total += entry.size
                if total > MAX_BYTES or entry.name == "manifest.json" and entry.size > 10 * 1024**2:
                    raise BackupError("Archive exceeds restore bounds.")
                target = destination / entry.name
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                stream = bundle.extractfile(entry)
                if stream is None:
                    raise BackupError("Archive member is unavailable.")
                with stream, _create(target) as output:
                    remaining = entry.size
                    value = hashlib.sha256()
                    while remaining:
                        chunk = stream.read(min(remaining, CHUNK))
                        if not chunk:
                            raise BackupError("Truncated archive member rejected.")
                        output.write(chunk)
                        value.update(chunk)
                        remaining -= len(chunk)
                actual[entry.name] = {
                    "name": entry.name,
                    "bytes": entry.size,
                    "sha256": value.hexdigest(),
                }
        manifest = json.loads((destination / "manifest.json").read_bytes())
        if (
            not isinstance(manifest, dict)
            or set(manifest) != {"format", "files", "metadata"}
            or manifest["format"] != 1
        ):
            raise BackupError("Invalid manifest.")
        expected = manifest["files"]
        if (
            not isinstance(expected, list)
            or len(expected) != len(actual) - 1
            or any(
                not isinstance(e, dict) or set(e) != {"name", "bytes", "sha256"} for e in expected
            )
        ):
            raise BackupError("Incomplete manifest.")
        actual.pop("manifest.json")
        if len({e["name"] for e in expected}) != len(expected) or any(
            actual.get(e["name"]) != e for e in expected
        ):
            raise BackupError("Restored inventory integrity failed.")
        if not isinstance(manifest["metadata"], dict):
            raise BackupError("Invalid metadata.")
        return cast(dict[str, object], manifest["metadata"])
    except Exception:
        import shutil

        shutil.rmtree(destination)
        raise BackupError("Archive validation failed; no restore was performed.") from None
