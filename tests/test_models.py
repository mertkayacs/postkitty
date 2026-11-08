from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

from engine import models


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
