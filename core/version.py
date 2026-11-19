"""Central application identity.

Every place that shows the application name, version or repository URL reads
it from here so a release only needs one edit.
"""

APP_NAME = "SeekR"
APP_VERSION = "1.1.2"
APP_VERSION_INFO = (1, 1, 2, 0)
APP_DESCRIPTION = "A fast, keyboard-driven Windows launcher."
APP_AUTHOR = "Okyanus Bora Şevik"
APP_REPO_URL = "https://github.com/okyanus-11/SeekR"
APP_HOMEPAGE = APP_REPO_URL
APP_LICENSE = "MIT"
APP_COPYRIGHT = "Copyright (c) 2026 Okyanus Bora Şevik"
APP_EXE_NAME = "SeekR"
CONFIG_SCHEMA_VERSION = 2

__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "APP_VERSION_INFO",
    "APP_DESCRIPTION",
    "APP_AUTHOR",
    "APP_REPO_URL",
    "APP_HOMEPAGE",
    "APP_LICENSE",
    "APP_COPYRIGHT",
    "APP_EXE_NAME",
    "CONFIG_SCHEMA_VERSION",
]
