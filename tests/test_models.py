from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

from engine.detect import models


def test_download_verifies_dummy_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payload = b"verified model bytes"
    monkeypatch.setattr(models, "YUNET_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(models, "YUNET_SIZE", len(payload))
    monkeypatch.setattr(models.urllib.request, "urlopen", lambda request, timeout: io.BytesIO(payload))

    path = models.get_yunet_model(tmp_path)

    assert path.read_bytes() == payload
    assert models.verify_yunet(path)


def test_existing_model_with_wrong_checksum_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / models.YUNET_FILENAME
    path.write_bytes(b"wrong")

    with pytest.raises(ValueError, match="checksum mismatch"):
        models.get_yunet_model(tmp_path)


def test_download_retries_gateway_timeouts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # GitHub's file host answered 504 Gateway Time-out to CI twice on 2026-11-08.
    payload = b"verified model bytes"
    monkeypatch.setattr(models, "YUNET_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(models, "YUNET_SIZE", len(payload))
    calls: list[int] = []
    sleeps: list[float] = []

    def flaky(request, timeout):
        calls.append(1)
        if len(calls) < 3:
            raise models.urllib.error.HTTPError(request.full_url, 504, "Gateway Time-out", {}, None)
        return io.BytesIO(payload)

    monkeypatch.setattr(models.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(models.time, "sleep", sleeps.append)

    path = models.get_yunet_model(tmp_path)

    assert path.read_bytes() == payload
    assert len(calls) == 3
    assert sleeps == list(models.RETRY_DELAYS[:2])
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".")]


def test_download_does_not_retry_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[int] = []

    def missing(request, timeout):
        calls.append(1)
        raise models.urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(models.urllib.request, "urlopen", missing)
    monkeypatch.setattr(models.time, "sleep", lambda seconds: None)

    with pytest.raises(models.urllib.error.HTTPError):
        models.get_yunet_model(tmp_path)
    assert len(calls) == 1
