from __future__ import annotations

import hashlib
import http.client
import io
import socket
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

    with pytest.raises(models.ModelUnavailable, match="404"):
        models.get_yunet_model(tmp_path)
    assert len(calls) == 1


def test_offline_fails_at_once_with_a_message_a_person_can_act_on(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def offline(request, timeout):
        calls.append(1)
        raise models.urllib.error.URLError(socket.gaierror(-3, "Temporary failure in name resolution"))

    monkeypatch.setattr(models.urllib.request, "urlopen", offline)
    monkeypatch.setattr(models.time, "sleep", sleeps.append)

    with pytest.raises(models.ModelUnavailable) as raised:
        models.get_yunet_model(tmp_path)

    message = str(raised.value)
    assert len(calls) == 1 and sleeps == []
    assert "face model" in message and "internet" in message and str(tmp_path) in message
    assert "Text" in message
    assert list(tmp_path.iterdir()) == []


def test_a_download_cut_short_is_retried_and_leaves_nothing_behind(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payload = b"verified model bytes"
    monkeypatch.setattr(models, "YUNET_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(models, "YUNET_SIZE", len(payload))

    class Dropped(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            raise http.client.IncompleteRead(payload[:7], len(payload) - 7)

    replies = [Dropped(), io.BytesIO(payload)]
    monkeypatch.setattr(models.urllib.request, "urlopen", lambda request, timeout: replies.pop(0))
    monkeypatch.setattr(models.time, "sleep", lambda seconds: None)

    path = models.get_yunet_model(tmp_path)

    assert path.read_bytes() == payload
    assert [item.name for item in tmp_path.iterdir()] == [models.YUNET_FILENAME]


def test_a_reply_that_is_never_the_model_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # A captive portal or proxy answers 200 with its own page.
    calls: list[int] = []

    def portal(request, timeout):
        calls.append(1)
        return io.BytesIO(b"<html>sign in</html>")

    monkeypatch.setattr(models.urllib.request, "urlopen", portal)

    with pytest.raises(models.ModelUnavailable, match="checksum"):
        models.get_yunet_model(tmp_path)
    assert len(calls) == 1 and list(tmp_path.iterdir()) == []
