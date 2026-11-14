"""Shared pytest fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from core.config_manager import ConfigManager
from core.database import Database
from core.hooks import NullHooks


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(["pytest"])
    yield app


@pytest.fixture
def config(tmp_path) -> ConfigManager:
    return ConfigManager(tmp_path / "config.json")


@pytest.fixture
def db(tmp_path) -> Database:
    database = Database(tmp_path / "seekr-test.db")
    yield database
    database.close()


@pytest.fixture
def hooks() -> NullHooks:
    return NullHooks()
