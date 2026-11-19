from __future__ import annotations

from pathlib import Path

from features.file_content import FileContentProvider


def _index(db, path: Path):
    db.upsert_files([{
        "path": str(path),
        "name": path.name,
        "dir": str(path.parent),
        "ext": path.suffix.lower(),
        "size": path.stat().st_size,
        "mtime": path.stat().st_mtime,
    }])


def test_content_search_is_disabled_by_default(config, db, hooks, tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    path = root / "guide.txt"
    path.write_text("private phrase", encoding="utf-8")
    config.set("files.directories", [str(root)])
    _index(db, path)

    provider = FileContentProvider(config, db, hooks)
    results = provider.search("private", 5)
    assert len(results) == 1
    assert "disabled" in results[0].title.lower()


def test_content_search_reads_only_configured_indexed_text_files(config, db, hooks, tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    guide = root / "guide.md"
    guide.write_text("The quick brown fox jumps over the lazy dog.", encoding="utf-8")
    binary = root / "image.png"
    binary.write_bytes(b"quick brown fox")
    config.set("files.directories", [str(root)])
    config.set("files.content_search_enabled", True)
    config.set("files.content_search_extensions", [".md"])
    _index(db, guide)
    _index(db, binary)

    provider = FileContentProvider(config, db, hooks)
    results = provider.search("brown fox", 5)
    assert len(results) == 1
    assert results[0].title == "guide.md"
    assert "brown fox" in results[0].subtitle


def test_content_search_skips_files_over_configured_size(config, db, hooks, tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    path = root / "large.txt"
    path.write_text("needle " + ("x" * 200), encoding="utf-8")
    config.set("files.directories", [str(root)])
    config.set("files.content_search_enabled", True)
    config.set("files.content_search_extensions", [".txt"])
    config.set("files.content_search_max_file_bytes", 64)
    _index(db, path)

    provider = FileContentProvider(config, db, hooks)
    assert provider.search("needle", 5) == []


def test_content_search_requires_files_to_be_under_configured_roots(config, db, hooks, tmp_path):
    root = tmp_path / "allowed"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    path = outside / "secret.txt"
    path.write_text("needle", encoding="utf-8")
    config.set("files.directories", [str(root)])
    config.set("files.content_search_enabled", True)
    _index(db, path)

    provider = FileContentProvider(config, db, hooks)
    assert provider.search("needle", 5) == []
