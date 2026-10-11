"""Backup integrity, independent-key and unsafe-archive negative checks."""

import io
import json
import tarfile
from datetime import timedelta

import pytest

from stmtconv.web.backup import (
    HEADER,
    BackupError,
    archive,
    create_key,
    digest,
    seal,
    unpack,
    unseal,
)
from stmtconv.web.models import now


def sealed(tmp_path):
    key = tmp_path / "backup.key"
    create_key(key)
    value = tmp_path / "private.bin"
    value.write_bytes(b"Fictional private data and fictional credential\n" * 100)
    value.chmod(0o600)
    plain = tmp_path / "bundle.tar"
    archive({"configs/private.bin": value}, {"scope": "fictional"}, plain)
    encrypted = tmp_path / "archive.dockbak"
    at = now()
    checksum = seal(plain, encrypted, key, created=at, expires=at + timedelta(days=7))
    return key, value, encrypted, checksum


def test_streamed_seal_authenticated_inventory_and_private_modes(tmp_path):
    key, value, encrypted, checksum = sealed(tmp_path)
    assert digest(encrypted) == checksum
    assert value.read_bytes() not in encrypted.read_bytes()
    assert encrypted.stat().st_mode & 0o777 == 0o600
    recovered = tmp_path / "restored.tar"
    start, end = unseal(encrypted, recovered, key)
    assert end - start == timedelta(days=7)
    directory = tmp_path / "verified"
    assert unpack(recovered, directory) == {"scope": "fictional"}
    assert (directory / "configs/private.bin").read_bytes() == value.read_bytes()
    assert (directory / "configs/private.bin").stat().st_mode & 0o777 == 0o600
    assert key.name not in [p.name for p in directory.rglob("*")]


@pytest.mark.parametrize("corruption", ["header", "ciphertext", "tag", "truncate"])
def test_corruption_rejected_before_archive_and_partial_plaintext_removed(tmp_path, corruption):
    key, _, encrypted, _ = sealed(tmp_path)
    data = bytearray(encrypted.read_bytes())
    if corruption == "truncate":
        data = data[:-1]
    else:
        index = {"header": 9, "ciphertext": HEADER.size + 10, "tag": len(data) - 1}[corruption]
        data[index] ^= 1
    encrypted.write_bytes(data)
    recovered = tmp_path / "private-restore.tar"
    with pytest.raises(BackupError, match="authentication failed"):
        unseal(encrypted, recovered, key)
    assert not recovered.exists()


def test_wrong_key_permissions_and_no_overwrite(tmp_path):
    key, value, encrypted, _ = sealed(tmp_path)
    wrong = tmp_path / "wrong.key"
    create_key(wrong)
    with pytest.raises(BackupError, match="authentication failed"):
        unseal(encrypted, tmp_path / "restore.tar", wrong)
    assert not (tmp_path / "restore.tar").exists()
    key.chmod(0o644)
    with pytest.raises(BackupError, match="private file"):
        unseal(encrypted, tmp_path / "restore.tar", key)
    key.chmod(0o600)
    original = encrypted.read_bytes()
    with pytest.raises(BackupError):
        seal(value, encrypted, key, created=now(), expires=now() + timedelta(days=1))
    assert encrypted.read_bytes() == original


@pytest.mark.parametrize("kind", ["traversal", "symlink", "duplicate", "unlisted", "wrong_hash"])
def test_malicious_authenticated_archive_inventory_rejected(tmp_path, kind):
    plain = tmp_path / "bad.tar"
    with tarfile.open(plain, "w") as bundle:
        data = b"fictional"
        name = "../escaped" if kind == "traversal" else "objects/item.bin"
        entry = tarfile.TarInfo(name)
        entry.size = len(data)
        if kind == "symlink":
            entry.type = tarfile.SYMTYPE
            entry.linkname = "../../escaped"
            entry.size = 0
        bundle.addfile(entry, io.BytesIO(data) if entry.isfile() else None)
        if kind == "duplicate":
            bundle.addfile(entry, io.BytesIO(data))
        files = (
            [] if kind == "unlisted" else [{"name": name, "bytes": len(data), "sha256": "0" * 64}]
        )
        manifest = json.dumps({"format": 1, "files": files, "metadata": {}}).encode()
        e = tarfile.TarInfo("manifest.json")
        e.size = len(manifest)
        bundle.addfile(e, io.BytesIO(manifest))
    plain.chmod(0o600)
    target = tmp_path / "new-restore"
    with pytest.raises(BackupError, match="Archive validation failed"):
        unpack(plain, target)
    assert not target.exists()
    assert not (tmp_path / "escaped").exists()
