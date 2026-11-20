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
    assert version_key("v2.1.0") > version_key("1.99.99")
    assert version_key("2.0.0") == version_key("v2.0.0")
    assert version_key("2.0.1") > version_key("2.0.0")
    assert version_key("2.0.0-rc.1") < version_key("2.0.0")
    assert version_key("2.0.0-rc.2") > version_key("2.0.0-rc.1")


def test_update_check_detects_new_release_and_records_timestamp(config, monkeypatch):
    payload = {
        "tag_name": "v2.1.0",
        "html_url": RELEASE_PAGE + "/tag/v2.1.0",
        "assets": [{"name": "SeekR-Setup-2.1.0.exe",
                    "browser_download_url": "https://github.com/okyanus-11/SeekR/releases/download/v2.1.0/SeekR-Setup-2.1.0.exe",
                    "digest": "sha256:" + "a" * 64, "size": 123456}],
    }
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse(payload))
    service = UpdateService(config)
    info = service.check_latest()
    assert info["update_available"]
    assert info["latest_version"] == "2.1.0"
    assert info["assets"][0]["name"] == "SeekR-Setup-2.1.0.exe"
    assert info["assets"][0]["sha256"] == "a" * 64
    assert info["assets"][0]["size"] == 123456
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


def test_update_check_ignores_untrusted_or_unhashed_assets(config, monkeypatch):
    payload = {
        "tag_name": "v2.1.0",
        "html_url": RELEASE_PAGE + "/tag/v2.1.0",
        "assets": [
            {"name": "evil.exe", "browser_download_url": "https://example.com/evil.exe",
             "digest": "sha256:" + "b" * 64, "size": 1},
            {"name": "unsigned.exe",
             "browser_download_url": "https://github.com/okyanus-11/SeekR/releases/download/v2.1.0/unsigned.exe",
             "digest": "", "size": 1},
            {"name": "bad-hash.exe",
             "browser_download_url": "https://github.com/okyanus-11/SeekR/releases/download/v2.1.0/bad.exe",
             "digest": "sha1:" + "c" * 40, "size": 1},
        ],
    }
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse(payload))
    info = UpdateService(config).check_latest()
    assert info["assets"] == []


def test_update_provider_exposes_official_asset_and_hash_actions(config, db, hooks):
    provider = UpdateProvider(config, db, hooks)
    provider.service.last_info = {
        "update_available": True,
        "latest_version": "2.1.0",
        "release_url": RELEASE_PAGE + "/tag/v2.1.0",
        "checked_at": time.time(),
        "assets": [{
            "name": "SeekR-Setup.exe",
            "url": "https://github.com/okyanus-11/SeekR/releases/download/v2.1.0/SeekR-Setup.exe",
            "sha256": "f" * 64,
            "size": 123,
        }],
    }
    result = provider.search("check", 1)[0]
    assert len(result.actions) == 4
    result.actions[1].callback()
    result.actions[2].callback()
    result.actions[3].callback()
    assert hooks.calls[-3:] == [
        ("open_url", (provider.service.last_info["assets"][0]["url"],)),
        ("copy_text", ("f" * 64,)),
        ("verify_update_asset", (provider.service.last_info["assets"][0],)),
    ]


def test_update_check_rejects_invalid_release_version(config, monkeypatch):
    payload = {"tag_name": "release-latest", "html_url": RELEASE_PAGE, "assets": []}
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse(payload))
    try:
        UpdateService(config).check_latest()
    except RuntimeError as exc:
        assert "version" in str(exc).lower()
    else:
        raise AssertionError("Invalid release tags must be rejected")


def test_update_asset_verification_accepts_matching_file(tmp_path):
    payload = b"SeekR release artifact test"
    file_path = tmp_path / "SeekR-Setup.exe"
    file_path.write_bytes(payload)
    import hashlib

    asset = {
        "name": "SeekR-Setup.exe",
        "url": "https://github.com/okyanus-11/SeekR/releases/download/v2.1.0/SeekR-Setup.exe",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    }
    valid, message = UpdateService.verify_asset_file(asset, file_path)
    assert valid
    assert "verified" in message.lower()


def test_update_asset_verification_rejects_mismatch_and_untrusted_metadata(tmp_path):
    file_path = tmp_path / "SeekR-Setup.exe"
    file_path.write_bytes(b"not the release artifact")
    asset = {
        "name": "SeekR-Setup.exe",
        "url": "https://github.com/okyanus-11/SeekR/releases/download/v2.1.0/SeekR-Setup.exe",
        "sha256": "0" * 64,
        "size": file_path.stat().st_size,
    }
    valid, message = UpdateService.verify_asset_file(asset, file_path)
    assert not valid
    assert "mismatch" in message.lower()
    asset["url"] = "https://example.com/SeekR-Setup.exe"
    valid, message = UpdateService.verify_asset_file(asset, file_path)
    assert not valid
    assert "trusted" in message.lower()


def test_update_asset_verification_rejects_spoofed_official_host_and_size(tmp_path):
    file_path = tmp_path / "installer.exe"
    file_path.write_bytes(b"release bytes")
    asset = {
        "name": "installer.exe",
        "url": "https://github.com/okyanus-11/SeekR/releases/download/v2.1.0/installer.exe",
        "sha256": "a" * 64,
        "size": file_path.stat().st_size + 1,
    }
    valid, message = UpdateService.verify_asset_file(asset, file_path)
    assert not valid
    assert "size mismatch" in message.lower()
    asset["url"] = "https://github.com.attacker.example/okyanus-11/SeekR/releases/download/v2.1.0/installer.exe"
    valid, message = UpdateService.verify_asset_file(asset, file_path)
    assert not valid
    assert "trusted" in message.lower()
