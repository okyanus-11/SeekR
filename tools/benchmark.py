"""Measure SeekR's hot paths and print the results as JSON.

Run from the repository root:

    python tools/benchmark.py

Numbers are produced on the machine that runs the script. They are stored in
docs/PERFORMANCE.md for reference; re-run after performance-sensitive changes.
"""

from __future__ import annotations

import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.application import SeekRApplication  # noqa: E402
from core.config_manager import ConfigManager  # noqa: E402
from core.database import Database  # noqa: E402
from core.fuzzy import fuzzy_score  # noqa: E402
from features.calculator import evaluate  # noqa: E402


def timed(fn, repeats: int) -> list[float]:
    samples: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    return samples


def summarize(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    return {
        "median_ms": round(statistics.median(samples), 3),
        "p95_ms": round(ordered[int(len(ordered) * 0.95) - 1], 3),
        "max_ms": round(max(samples), 3),
    }


def _measure(workdir: Path) -> dict[str, object]:
    from PySide6.QtWidgets import QApplication

    results: dict[str, object] = {
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor() or "unknown",
        }
    }
    config = ConfigManager(workdir / "config.json")
    config.set("files.auto_index", False)
    config.set("applications.refresh_on_start", False)
    config.set("general.show_tray_icon", False)
    config.set("appearance.animations", False)
    db = Database(workdir / "bench.db")
    app = QApplication(sys.argv[:1])
    controller = None
    try:
        # -------------------------------------------------------- controller start
        start = time.perf_counter()
        controller = SeekRApplication(app, config, db)
        controller._create_tray = lambda: None
        controller._start_clipboard_monitor = lambda: None
        controller._auto_index = lambda: None
        controller.start(show_window=False, register_hotkey=False)
        results["startup"] = {
            "controller_start_ms": round((time.perf_counter() - start) * 1000, 1)
        }
        warm_start = time.perf_counter()
        from features.calculator import warm_up

        warm_up()
        calculator_warmup_ms = round((time.perf_counter() - warm_start) * 1000, 1)

        # ------------------------------------------------------------ search paths
        results["search"] = {
            "empty_query_auto": summarize(timed(lambda: controller.engine.search(""), 60)),
            "app_query_auto": summarize(timed(lambda: controller.engine.search("chrome"), 120)),
            "keyword_query": summarize(
                timed(lambda: controller.engine.search("calc: sqrt(144) + 25 * 4"), 120)
            ),
            "web_query": summarize(
                timed(lambda: controller.engine.search("web: python packaging"), 120)
            ),
        }
        results["calculator"] = {
            "warm_up_ms": calculator_warmup_ms,
            **summarize(timed(lambda: evaluate("sqrt(144) + 25 * 4"), 120)),
        }

        # ------------------------------------------------------------------- fuzzy
        pairs = [
            ("discrod", "Discord"),
            ("code", "Visual Studio Code"),
            ("raspberry pi", "raspberry-pi-guide.pdf"),
        ]
        fuzzy_samples = timed(
            lambda: [fuzzy_score(a, b) for a, b in pairs for _ in range(100)], 20
        )
        results["fuzzy"] = {
            "300_comparisons_median_ms": round(statistics.median(fuzzy_samples), 3),
            "microseconds_per_comparison": round(
                statistics.median(fuzzy_samples) * 1000 / 300, 1
            ),
        }

        # ---------------------------------------------------------------- database
        rows = 10000
        start = time.perf_counter()
        for batch in range(0, rows, 100):
            db.upsert_files(
                [
                    {
                        "path": str(workdir / "files" / f"document-{index}.txt"),
                        "name": f"document-{index}.txt",
                        "dir": str(workdir / "files"),
                        "ext": ".txt",
                        "is_dir": False,
                        "size": index,
                        "mtime": time.time(),
                    }
                    for index in range(batch, batch + 100)
                ]
            )
        results["database"] = {
            "insert_10k_files_ms": round((time.perf_counter() - start) * 1000, 1),
            "search_name_median_ms": summarize(
                timed(lambda: db.file_candidates("document-9999", limit=40), 100)
            )["median_ms"],
            "browse_extension_median_ms": summarize(
                timed(lambda: db.files_by_extension(".txt", 40), 60)
            )["median_ms"],
        }
    finally:
        if controller is not None:
            controller.shutdown()
        else:
            db.close()
        app.processEvents()
    return results


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="seekr-bench-") as workdir:
        results = _measure(Path(workdir))
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
