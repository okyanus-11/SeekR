from __future__ import annotations

from features.diagnostics import build_diagnostic_report, redact_diagnostic_text


def test_diagnostic_redaction_removes_common_private_values(monkeypatch, tmp_path):
    monkeypatch.setattr("features.diagnostics.Path.home", lambda: tmp_path / "Alice")
    raw = (
        "password=secret-value api_key:abc123 Bearer ghp_abcdefghijklmnop "
        "alice@example.com 192.168.1.42 C:\\Users\\Alice\\Documents "
        "query='private search phrase'"
    )
    cleaned = redact_diagnostic_text(raw)
    for private in (
        "secret-value", "abc123", "ghp_abcdefghijklmnop",
        "alice@example.com", "192.168.1.42", "C:\\Users\\Alice",
        "private search phrase",
    ):
        assert private not in cleaned
    assert "<REDACTED>" in cleaned
    assert "<EMAIL>" in cleaned
    assert "<IP_ADDRESS>" in cleaned


def test_diagnostic_report_excludes_logs_by_default(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "seekr.log").write_text("password=should-not-appear", encoding="utf-8")
    monkeypatch.setattr("features.diagnostics.paths.log_dir", lambda: log_dir)
    report = build_diagnostic_report()
    assert "SeekR diagnostic report" in report
    assert "password=should-not-appear" not in report
    assert "Recent application logs" not in report


def test_diagnostic_report_includes_only_redacted_logs_when_opted_in(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "seekr.log").write_text(
        "ERROR | module | password=private-value user@example.com query='secret words'",
        encoding="utf-8",
    )
    monkeypatch.setattr("features.diagnostics.paths.log_dir", lambda: log_dir)
    report = build_diagnostic_report(include_logs=True)
    assert "Recent application logs" in report
    assert "private-value" not in report
    assert "user@example.com" not in report
    assert "secret words" not in report
