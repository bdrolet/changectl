from pathlib import Path

import pytest

from clients.storage import LocalStorage, from_env, object_key


def test_local_roundtrip(tmp_path: Path) -> None:
    s = LocalStorage(tmp_path)
    s.put("documents/d/r/a.bin", b"\x00hello", "application/octet-stream")
    assert s.get("documents/d/r/a.bin") == b"\x00hello"
    assert s.signed_url("documents/d/r/a.bin", "a.bin").startswith("file://")


def test_object_key_sanitizes() -> None:
    assert object_key("d", "r", "BOM v2 (final).xlsx") == "documents/d/r/BOM_v2__final_.xlsx"
    assert object_key("d", "r", "").endswith("/file")


def test_from_env_local_without_bucket(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CHANGECTL_BUCKET", raising=False)
    monkeypatch.setenv("CHANGECTL_LOCAL_STORAGE", str(tmp_path))
    s = from_env()
    assert isinstance(s, LocalStorage)
    s.put("k", b"x", "text/plain")
    assert (tmp_path / "k").read_bytes() == b"x"
