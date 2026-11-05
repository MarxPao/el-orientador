"""Local file storage for uploaded PDFs: safe keys, atomic writes, checksums.

Everything lives under one directory (STORAGE_DIR). Keys are server-generated ("<project>/<uuid>.pdf"); a key that
would resolve outside the root is refused, so neither a crafted `storage_path` in the database nor a bad argument
can read or delete files elsewhere. There is no size limit here beyond the disk.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path


class StorageError(ValueError):
    pass


def resolve(root: Path, key: str) -> Path:
    """Absolute path of `key` inside `root`; StorageError when it would escape the root."""
    if not key or "\x00" in key:
        raise StorageError("chave de arquivo inválida")
    base = Path(root).resolve()
    path = (base / key).resolve()
    if path == base or base not in path.parents:
        raise StorageError("chave de arquivo fora do diretório de armazenamento")
    return path


def write_atomic(root: Path, key: str, data: bytes) -> str:
    """Write `data` at `key` so readers never see a half-written file. Returns the SHA-256 hex digest."""
    path = resolve(root, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return hashlib.sha256(data).hexdigest()


def exists(root: Path, key: str) -> bool:
    try:
        return resolve(root, key).is_file()
    except StorageError:
        return False


def delete(root: Path, key: str) -> bool:
    """Remove the file; False when it was already gone or the key is not inside the root."""
    try:
        path = resolve(root, key)
    except StorageError:
        return False
    if not path.is_file():
        return False
    path.unlink()
    return True


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def manifest(root: Path) -> dict[str, str]:
    """{relative key: sha256} for every stored file (temporary files excluded). Used by backup and verify."""
    base = Path(root).resolve()
    out: dict[str, str] = {}
    if not base.exists():
        return out
    for p in sorted(base.rglob("*")):
        if p.is_file() and not p.name.startswith(".tmp-"):
            out[p.relative_to(base).as_posix()] = sha256_file(p)
    return out
