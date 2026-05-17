from types import SimpleNamespace

import pytest

from app.utils import rate_limit as rate_limit_module


def _request(ip: str):
    return SimpleNamespace(
        headers={},
        client=SimpleNamespace(host=ip),
    )


def test_rate_limit_blocks_after_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit_module.settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(rate_limit_module.settings, "RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(rate_limit_module.time, "monotonic", lambda: 100.0)
    rate_limit_module._buckets.clear()

    dependency = rate_limit_module.rate_limit("test", limit=2)
    request = _request("203.0.113.10")

    dependency(request)
    dependency(request)

    with pytest.raises(Exception) as exc_info:
        dependency(request)

    assert getattr(exc_info.value, "status_code", None) == 429
