"""Windows compatibility tests.

Legend used in the test docstrings:

* **[SIMULATED]** runs the real implementation of a Windows code path through
  an injectable seam (for example ``split_args(..., windows=True)``).
* **[MOCKED Win32]** replaces registry/user32/powercfg APIs with fakes because
  those APIs do not exist on this host. The surrounding logic is real.
* **[REAL]** exercises real code with no platform substitution.

The Linux suite can therefore prove the logic but not that Windows itself
accepts the calls; only a run on Windows can do that.
"""

from __future__ import annotations

import ctypes
import os
import struct
import sys
import time
import types
from pathlib import Path

import pytest

import build
from core import paths, startup
from core.application import SeekRApplication
from core.config_manager import ConfigManager
from core.database import Database
from core.hooks import NullHooks
from core.hotkey_manager import HotkeyManager
from core.hotkeys import MOD_ALT, parse_hotkey
from core.single_instance import SingleInstance
from features import applications, files, power, process_manager, system_info, util, window_search
from features.applications import AppService, ApplicationsProvider


# --------------------------------------------------------------------- helpers
class FakeUser32:
    """Records RegisterHotKey calls for the hotkey manager contract tests."""

    def __init__(self) -> None:
        self.registrations: list[tuple[int, int]] = []
        self.fail_next = False

    def RegisterHotKey(self, _hwnd, _hotkey_id, modifiers, virtual_key):  # noqa: N802
        if self.fail_next:
            self.fail_next = False
            return 0
        self.registrations.append((modifiers, virtual_key))
        return 1

    def UnregisterHotKey(self, _hwnd, _hotkey_id):  # noqa: N802
        return 1


# ------------------------------------------------------------------ arguments
def test_split_args_windows_quoting():
    """[SIMULATED] Windows quoting keeps spaces and strips quote characters."""
    assert util.split_args(
        r'"C:\Program Files\My App\app.exe" --title "hello world"', windows=True
    ) == [r"C:\Program Files\My App\app.exe", "--title", "hello world"]
    assert util.split_args(r"C:\Tools\app.exe -x", windows=True) == [r"C:\Tools\app.exe", "-x"]
    assert util.split_args('"unterminated argument', windows=True) == ["unterminated argument"]
    # Shell metacharacters are ordinary characters: nothing is interpreted.
    assert util.split_args('powershell -Command "Get-Item C:\\a & b"', windows=True)[-1] == "Get-Item C:\\a & b"


def test_split_args_posix_still_works():
    """[REAL] The POSIX splitter is unchanged."""
    assert util.split_args("alpha 'beta gamma'", windows=False) == ["alpha", "beta gamma"]


def test_explorer_select_command_quotes_spaces():
    """[SIMULATED] Explorer receives /select with a quoted path."""
    command = util.explorer_select_command(r"C:\Users\Name\My Files\report.txt")
    assert command == r'explorer.exe /select,"C:\Users\Name\My Files\report.txt"'
    with pytest.raises(ValueError):
        util.explorer_select_command('C:\\bad"name.txt')


def test_force_foreground_rejects_an_empty_handle():
    """[REAL] The focus helper safely rejects an empty handle everywhere."""
    assert util.force_foreground(0) is False
    if os.name != "nt":
        assert util.force_foreground(1234) is False


# ---------------------------------------------------------------- known folders
def test_known_folder_lookup_is_safe():
    """[REAL] Known Folder lookup returns a path on Windows and None elsewhere."""
    folder = paths.known_folder("documents")
    if os.name == "nt":
        assert folder is None or folder.is_absolute()
    else:
        assert folder is None


def test_default_document_dirs_uses_known_folders(tmp_path, monkeypatch):
    """[SIMULATED] Redirected/OneDrive folders are used and de-duplicated."""
    desktop = tmp_path / "OneDrive" / "Desktop"
    documents = tmp_path / "OneDrive" / "Documents"
    desktop.mkdir(parents=True)
    documents.mkdir(parents=True)
    mapping = {"desktop": desktop, "documents": documents, "downloads": None}
    monkeypatch.setattr(paths, "known_folder", lambda name: mapping[name])
    monkeypatch.setattr(paths, "os", types.SimpleNamespace(name="nt"))
    result = paths.default_document_dirs()
    assert result == [str(desktop), str(documents)]

    mapping["downloads"] = desktop  # duplicate path must collapse
    assert paths.default_document_dirs() == [str(desktop), str(documents)]


def test_windows_hidden_attribute_helper():
    """[SIMULATED] Hidden and system attributes are honoured without dotfiles."""
    hidden = types.SimpleNamespace(st_file_attributes=0x2)
    system = types.SimpleNamespace(st_file_attributes=0x4)
    plain = types.SimpleNamespace(st_file_attributes=0x80)
    assert files._windows_hidden(hidden) is True
    assert files._windows_hidden(system) is True
    assert files._windows_hidden(plain) is False
    assert files._windows_hidden(object()) is False


# ----------------------------------------------------------- application scan
def test_program_files_scan_deduplicates_and_skips_noise(tmp_path):
    """[REAL] The Program Files scanner is depth/name filtered and de-duplicated."""
    root = tmp_path / "Program Files"
    (root / "Alpha").mkdir(parents=True)
    (root / "Alpha" / "alpha.exe").write_bytes(b"MZ")
    (root / "Alpha" / "uninstall.exe").write_bytes(b"MZ")
    (root / "Beta").mkdir()
    (root / "Beta" / "beta.exe").write_bytes(b"MZ")
    (root / "Gamma" / "installer").mkdir(parents=True)
    (root / "Gamma" / "installer" / "setup.exe").write_bytes(b"MZ")
    (root / "WindowsApps").mkdir()
    (root / "WindowsApps" / "store.exe").write_bytes(b"MZ")

    config = ConfigManager(tmp_path / "config.json")
    database = Database(tmp_path / "apps.db")
    try:
        service = AppService(config, database)
        found = service._scan_program_files(roots=[root, root])
        names = sorted(entry["name"] for entry in found)
        assert names == ["alpha", "beta"]
    finally:
        database.close()


def test_application_scan_respects_start_menu_toggle(tmp_path, monkeypatch):
    """[SIMULATED] Disabling Start Menu indexing really disables the scan."""
    menu = tmp_path / "applications"
    menu.mkdir()
    (menu / "thing.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Thing\nExec=/bin/true\n", encoding="utf-8"
    )
    # Windows scans .lnk files; Linux/macOS scan .desktop files.
    (menu / "thing.lnk").write_bytes(b"shortcut")
    monkeypatch.setattr(applications, "start_menu_directories", lambda: [menu])
    config = ConfigManager(tmp_path / "config.json")
    config.set("applications.index_start_menu", False)
    database = Database(tmp_path / "apps.db")
    try:
        assert AppService(config, database).scan() == []
        config.set("applications.index_start_menu", True)
        assert [entry["name"] for entry in AppService(config, database).scan()] == ["Thing"]
    finally:
        database.close()


def test_custom_application_folder_scans_lnk_files(tmp_path, monkeypatch):
    """[SIMULATED] Additional folders contribute .lnk entries on Windows."""

    class _WindowsOS:
        name = "nt"

        def __getattr__(self, item):
            return getattr(os, item)

    custom = tmp_path / "Portable Apps"
    custom.mkdir()
    (custom / "Portable Tool.lnk").write_bytes(b"shortcut")
    config = ConfigManager(tmp_path / "config.json")
    config.set("applications.index_start_menu", False)
    config.set("applications.directories", [str(custom)])
    database = Database(tmp_path / "apps.db")
    monkeypatch.setattr(applications, "os", _WindowsOS())
    try:
        service = AppService(config, database)
        entries = service.scan()
        assert [entry["name"] for entry in entries] == ["Portable Tool"]
        assert entries[0]["source"] == "custom"
    finally:
        database.close()


class _WindowsOS:
    name = "nt"

    def __getattr__(self, item):
        return getattr(os, item)


def test_application_provider_never_indexes_on_the_gui_thread(tmp_path, monkeypatch):
    """[SIMULATED] A cold index request is delegated instead of blocking search."""
    config = ConfigManager(tmp_path / "config.json")
    database = Database(tmp_path / "apps.db")
    hooks = NullHooks()
    try:
        service = AppService(config, database)

        def _forbidden(*_args, **_kwargs):
            raise AssertionError("application discovery must not run inside search()")

        monkeypatch.setattr(service, "refresh", _forbidden)
        provider = ApplicationsProvider(config, database, hooks, service)
        provider._last_index_request = 0.0
        results = provider.search("chrome", 5)
        assert results and results[0].title.startswith("Indexing applications")
        assert ("refresh_indexes", ("applications",)) in hooks.calls
    finally:
        database.close()


# ---------------------------------------------------------------- hotkeys
def test_hotkey_registration_and_failure_reporting(qapp, monkeypatch):
    """[MOCKED Win32] Registration flags, error messages and previous-hotkey restore."""
    fake = FakeUser32()
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: fake, raising=False)
    monkeypatch.setattr(ctypes, "set_last_error", lambda _value: None, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 1409, raising=False)

    manager = HotkeyManager()
    manager.available = True
    manager._user32 = fake
    try:
        assert manager.register("Alt+Space") is True
        assert manager.current == "Alt+Space"
        modifiers, virtual_key = fake.registrations[-1]
        assert modifiers & MOD_ALT
        assert virtual_key == 0x20

        fake.fail_next = True
        assert manager.register("Ctrl+Shift+K") is False
        assert "already registered" in manager.last_error
        # The failed attempt must not leave the user without a working hotkey.
        assert manager.current == "Alt+Space"
        assert fake.registrations[-1] == (MOD_ALT | 0x4000, 0x20)
    finally:
        manager.cleanup()


def test_hotkey_parser_windows_virtual_keys():
    """[REAL] Parsing produces Win32 modifier flags and virtual-key codes."""
    assert parse_hotkey("Alt+Space") == (0x0001, 0x20)
    assert parse_hotkey("Ctrl+Shift+K") == (0x0002 | 0x0004, ord("K"))
    with pytest.raises(Exception):
        parse_hotkey("NoModifier")


# -------------------------------------------------------------- startup entry
class _FakeKey:
    def __init__(self, store: dict) -> None:
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def test_startup_registry_toggle(tmp_path, monkeypatch):
    """[MOCKED Win32] The Run key is written, read and removed."""
    values: dict[str, str] = {}

    def _query(_key, name):
        if name not in values:
            raise FileNotFoundError(name)
        return values[name], 1

    fake_winreg = types.SimpleNamespace(
        HKEY_CURRENT_USER=object(),
        KEY_READ=1,
        KEY_SET_VALUE=2,
        REG_SZ=1,
        OpenKey=lambda *_args: _FakeKey(values),
        CreateKeyEx=lambda *_args: _FakeKey(values),
        SetValueEx=lambda _key, name, _res, _type, value: values.__setitem__(name, value),
        QueryValueEx=_query,
        DeleteValue=lambda _key, name: values.pop(name, None),
    )
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)
    monkeypatch.setattr(startup, "os", types.SimpleNamespace(name="nt"))

    assert startup.is_enabled() is False
    ok, message = startup.set_enabled(True)
    assert ok and "start with Windows" in message
    assert startup.is_enabled() is True
    assert startup._launch_command().startswith('"')
    ok, _ = startup.set_enabled(False)
    assert ok and startup.is_enabled() is False


# --------------------------------------------------------------------- power
def test_powercfg_uses_exit_status(monkeypatch):
    """[MOCKED Win32] powercfg failures are detected by exit code, not English text."""
    monkeypatch.setattr(power, "os", types.SimpleNamespace(name="nt"))
    monkeypatch.setattr(power, "_powercfg_path", lambda: "powercfg.exe")
    calls: list[list[str]] = []

    def fake_run(args, timeout=12.0):
        calls.append(args)
        return 1, "Access is denied."

    monkeypatch.setattr(power, "_run", fake_run)
    ok, message = power.set_scheme("381b4222-f694-41f0-9685-ff5bb260df2e")
    assert ok is False and "denied" in message
    assert calls == [["powercfg.exe", "/setactive", "381b4222-f694-41f0-9685-ff5bb260df2e"]]

    monkeypatch.setattr(power, "_run", lambda args, timeout=12.0: (0, ""))
    ok, _ = power.set_scheme("381b4222-f694-41f0-9685-ff5bb260df2e")
    assert ok is True

    calls.clear()
    ok, _ = power.set_scheme("not-a-guid")
    assert ok is False and calls == []


# ---------------------------------------------------------------- system info
def test_windows_gpu_query_forces_utf8(monkeypatch):
    """[SIMULATED] The PowerShell GPU probe forces UTF-8 and hidden output."""
    recorded: dict = {}

    def fake_run(args, timeout=8.0, encoding=None):
        recorded["args"] = args
        recorded["encoding"] = encoding
        return '[{"Name":"Test GPU","AdapterRAM":2048,"DriverVersion":"1.2.3"}]'

    monkeypatch.setattr(system_info, "_run_quiet", fake_run)
    gpus = system_info._windows_gpus()
    assert gpus[0]["name"] == "Test GPU"
    assert recorded["encoding"] == "utf-8"
    assert "[Console]::OutputEncoding" in " ".join(recorded["args"])


def test_gpu_probe_never_blocks_the_caller(monkeypatch):
    """[REAL] GPU collection happens on a daemon thread with a 30 s cache."""
    # A controller started by another test may still be warming the GPU cache;
    # wait for that probe so its result cannot be attributed to this test's
    # monkeypatched collector (Windows WMI can be slow).
    deadline = time.time() + 10
    while system_info._gpu_cache.get("loading") and time.time() < deadline:
        time.sleep(0.05)
    system_info._gpu_cache.update({"value": [], "loaded_at": 0.0, "loading": False})
    calls: list[int] = []

    def slow_collect():
        calls.append(1)
        time.sleep(0.2)
        return [{"name": "Threaded GPU"}]

    monkeypatch.setattr(system_info, "_collect_gpus", slow_collect)
    started = time.perf_counter()
    assert system_info.gpu_info() == []
    assert (time.perf_counter() - started) < 0.1

    deadline = time.time() + 3
    while time.time() < deadline and not system_info._gpu_cache["value"]:
        time.sleep(0.02)
    assert system_info.gpu_info() == [{"name": "Threaded GPU"}]
    assert len(calls) == 1
    system_info._gpu_cache.update({"value": [], "loaded_at": 0.0, "loading": False})


# ------------------------------------------------------------------- files
def test_file_index_limit_is_not_reported_as_cancellation(tmp_path):
    """[REAL] Hitting max_files truncates the index but is not a cancellation."""
    root = tmp_path / "docs"
    root.mkdir()
    # max_files is clamped to a minimum of 1000 by the configuration layer.
    for index in range(1002):
        (root / f"file-{index}.txt").write_text("x", encoding="utf-8")
    config = ConfigManager(tmp_path / "config.json")
    config.set("files.directories", [str(root)])
    config.set("files.max_files", 1000)
    database = Database(tmp_path / "files.db")
    try:
        stats = files.FileIndexer(config, database).index()
        assert stats["limit_reached"] is True
        assert stats["cancelled"] is False
        assert stats["indexed"] == 1000
    finally:
        database.close()


# ---------------------------------------------------------------- processes
def test_critical_processes_are_protected():
    """[REAL] System-critical processes and SeekR itself cannot be terminated."""
    assert process_manager._is_protected(4, "System") is True
    assert process_manager._is_protected(123, "lsass.exe") is True
    assert process_manager._is_protected(os.getpid(), "python") is True
    assert process_manager._is_protected(4242, "notepad.exe") is False
    ok, message = process_manager.terminate_process(os.getpid())
    assert ok is False and "itself" in message


# ------------------------------------------------------------ single instance
def test_single_instance_forwards_only_one_show(qapp):
    """[REAL] A second process raises the launcher exactly once."""
    key = f"SeekR.Test.{os.getpid()}.{time.time_ns()}"
    primary = SingleInstance(key)
    secondary = SingleInstance(key)
    received: list[int] = []
    primary.show_requested.connect(lambda: received.append(1))
    try:
        assert primary.listen() is True
        assert secondary.notify_existing() is True
        deadline = time.time() + 2
        while time.time() < deadline and not received:
            qapp.processEvents()
            time.sleep(0.01)
        qapp.processEvents()
        time.sleep(0.15)
        qapp.processEvents()
        assert received == [1]
    finally:
        secondary.close()
        primary.close()


# --------------------------------------------------------------------- tray
def test_tray_menu_is_retained_and_created_on_demand(qapp, tmp_path, monkeypatch):
    """[REAL Qt / MOCKED availability] No duplicate tray icons, menu kept alive."""
    from PySide6.QtWidgets import QSystemTrayIcon

    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    config = ConfigManager(tmp_path / "config.json")
    config.set("general.show_tray_icon", False)
    database = Database(tmp_path / "tray.db")
    controller = SeekRApplication(qapp, config, database)
    try:
        controller._create_tray()
        assert controller.tray is None

        config.set("general.show_tray_icon", True)
        controller._on_config_changed("general.show_tray_icon", True)
        assert controller.tray is not None
        assert controller._tray_menu is not None
        assert any(action.text().startswith("Quit") for action in controller._tray_menu.actions())

        existing = controller.tray
        controller._create_tray()
        assert controller.tray is existing  # no duplicate icon

        visibility: list[bool] = []
        monkeypatch.setattr(
            QSystemTrayIcon, "setVisible", lambda _tray, visible: visibility.append(visible)
        )
        config.set("general.show_tray_icon", False)
        controller._on_config_changed("general.show_tray_icon", False)
        assert visibility == [False]
    finally:
        controller.shutdown()


# -------------------------------------------------------------------- window
def test_window_search_handles_empty_or_unsupported_hosts():
    """[REAL] Window search returns a list and explains an invalid switch."""
    windows = window_search.list_windows()
    assert isinstance(windows, list)
    ok, message = window_search.switch_to_window(0)
    assert ok is False
    if os.name == "nt":
        assert "no longer" in message.lower()
    else:
        assert "Windows" in message


# ---------------------------------------------------------------- packaging
def test_build_output_paths_and_icon():
    """[REAL] Build targets and the packaged multi-size icon are correct."""
    assert build.output_target(False, "nt").name == "SeekR.exe"
    assert build.output_target(True, "nt").parent.name == "SeekR"
    assert build.output_target(False, "posix").name == "SeekR"

    icon = Path(build.ICON).read_bytes()
    reserved, kind, count = struct.unpack("<HHH", icon[:6])
    assert (reserved, kind) == (0, 1)
    assert count == 7
    sizes = []
    for index in range(count):
        width, height, _colors, _res, _planes, _bpp, length, offset = struct.unpack(
            "<BBBBHHII", icon[6 + 16 * index : 6 + 16 * (index + 1)]
        )
        sizes.append(256 if width == 0 else width)
        assert icon[offset : offset + 8] == b"\x89PNG\r\n\x1a\n"
        assert length > 0
    assert 16 in sizes and 256 in sizes
    png = Path(build.ROOT / "assets" / "icons" / "seekr.png").read_bytes()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")


def test_text_preview_decodes_windows_utf16(tmp_path):
    """[REAL] Notepad-style UTF-16 and UTF-8 BOM text is readable."""
    from features import quicklook

    utf16 = tmp_path / "utf16.txt"
    utf16.write_bytes(b"\xff\xfe" + "Merhaba dünya".encode("utf-16-le"))
    assert quicklook.load_text_preview(utf16) == "Merhaba dünya"

    bom = tmp_path / "bom.txt"
    bom.write_bytes(b"\xef\xbb\xbf" + "hello".encode("utf-8"))
    assert quicklook.load_text_preview(bom) == "hello"


def test_screenshot_directory_setting_is_used(tmp_path):
    """[REAL] The configured screenshot folder is created and used."""
    from features import screenshots

    target = tmp_path / "Captures"
    config = ConfigManager(tmp_path / "config.json")
    config.set("screenshots.directory", str(target))
    assert screenshots.screenshot_directory(config) == target
    assert target.is_dir()


def test_windows_test_uses_temp_file_for_dependency_check():
    """[REAL] The PowerShell runner must not pass multiline source via python -c."""
    from pathlib import Path

    script = Path("tools/windows_test.ps1").read_text(encoding="utf-8")
    assert 'seekr_dep_check.py' in script
    assert '"-c", $dependencyScript' not in script


def test_dependency_checker_succeeds_as_script_file(tmp_path):
    """[REAL] Running the dependency checker as a .py file (not -c) succeeds."""
    import subprocess

    venv_python = Path(".venv/Scripts/python.exe")
    if not venv_python.exists():
        venv_python = Path(".venv/bin/python")
    if not venv_python.exists():
        pytest.skip("No .venv available")

    checker = tmp_path / "seekr_dep_check.py"
    checker.write_text(
        'import importlib.util\n'
        'import sys\n'
        '\n'
        'required = [\n'
        '    ("PySide6", "PySide6"),\n'
        '    ("psutil", "psutil"),\n'
        '    ("sympy", "sympy"),\n'
        '    ("tzdata", "tzdata"),\n'
        '    ("PyInstaller", "pyinstaller"),\n'
        '    ("pytest", "pytest"),\n'
        ']\n'
        'missing = []\n'
        'for module, package in required:\n'
        '    try:\n'
        '        found = importlib.util.find_spec(module) is not None\n'
        '    except Exception:\n'
        '        found = False\n'
        '    print(f"{package}: {\'OK\' if found else \'MISSING\'}")\n'
        '    if not found:\n'
        '        missing.append(package)\n'
        'print("Python:", sys.version.split()[0])\n'
        'if missing:\n'
        '    print("Missing: " + ", ".join(missing))\n'
        '    sys.exit(1)\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(venv_python), str(checker)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for package in ("PySide6", "psutil", "sympy", "tzdata", "pyinstaller", "pytest"):
        assert f"{package}: OK" in result.stdout.lower() or f"{package}: OK" in result.stdout


def test_dependency_checker_fails_on_missing_package(tmp_path):
    """[REAL] A missing package makes the checker exit non-zero with a clear message."""
    import subprocess

    venv_python = Path(".venv/Scripts/python.exe")
    if not venv_python.exists():
        venv_python = Path(".venv/bin/python")
    if not venv_python.exists():
        pytest.skip("No .venv available")

    checker = tmp_path / "seekr_dep_check.py"
    checker.write_text(
        'import importlib.util\n'
        'import sys\n'
        '\n'
        'required = [("definitely_missing_xyz", "definitely-missing-xyz")]\n'
        'missing = []\n'
        'for module, package in required:\n'
        '    try:\n'
        '        found = importlib.util.find_spec(module) is not None\n'
        '    except Exception:\n'
        '        found = False\n'
        '    print(f"{package}: {\'OK\' if found else \'MISSING\'}")\n'
        '    if not found:\n'
        '        missing.append(package)\n'
        'if missing:\n'
        '    print("Missing: " + ", ".join(missing))\n'
        '    sys.exit(1)\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(venv_python), str(checker)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "MISSING" in result.stdout
    assert "definitely-missing-xyz" in result.stdout


def test_windows_paths_survive_config_roundtrip(tmp_path):
    """[REAL] Backslashes and UNC paths are preserved in config.json."""
    config = ConfigManager(tmp_path / "config.json")
    drives = [r"C:\Users\Test\Documents", r"\\server\share\data"]
    config.set("files.directories", drives)
    reloaded = ConfigManager(tmp_path / "config.json")
    assert reloaded.get("files.directories") == drives
