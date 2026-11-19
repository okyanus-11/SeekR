from __future__ import annotations

import json
import time

from features.updates import RELEASE_PAGE, UpdateProvider, UpdateService, version_key


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        return self.payload


def test_version_key_compares_numeric_components():
    assert version_key("v2.0.0") > version_key("1.99.99")
    assert version_key("2.0.0") == version_key("v2.0.0")
    assert version_key("2.0.1") > version_key("2.0.0")


def test_update_check_detects_new_release_and_records_timestamp(config, monkeypatch):
    payload = {
        "tag_name": "v2.0.0",
        "html_url": RELEASE_PAGE + "/tag/v2.0.0",
        "assets": [{"name": "SeekR-Setup-2.0.0.exe",
                    "browser_download_url": RELEASE_PAGE + "/download/SeekR-Setup-2.0.0.exe"}],
    }
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse(payload))
    service = UpdateService(config)
    info = service.check_latest()
    assert info["update_available"]
    assert info["latest_version"] == "2.0.0"
    assert info["assets"][0]["name"] == "SeekR-Setup-2.0.0.exe"
    assert config.get("updates.last_check") > 0
    assert service.last_info == info


def test_update_check_rejects_unexpected_release_url(config, monkeypatch):
    payload = {"tag_name": "v99.0.0", "html_url": "https://example.com/releases/latest", "assets": []}
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse(payload))
    service = UpdateService(config)
    try:
        service.check_latest()
    except RuntimeError as exc:
        assert "metadata" in str(exc).lower()
    else:
        raise AssertionError("Unexpected release URL must be rejected")


def test_update_check_due_uses_one_day_interval(config):
    service = UpdateService(config)
    config.set("updates.last_check", time.time())
    assert not service.check_due()
    config.set("updates.last_check", time.time() - 2 * 86400)
    assert service.check_due()


def test_update_provider_is_explicit_and_non_blocking(config, db, hooks):
    provider = UpdateProvider(config, db, hooks)
    results = provider.search("check", 5)
    assert len(results) == 1
    assert results[0].title == "Check for updates"
    assert hooks.calls == []
