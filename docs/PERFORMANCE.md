# SeekR performance audit

This audit measured SeekR on the Windows machine listed below. The benchmark
script measures controller and provider hot paths; focused scripts measured
larger SQLite datasets, indexing, icon-cache growth, idle resources, and
source-mode startup. Results are observations from this machine, not universal
targets.

## Environment and methodology

- Windows 11 build 26300, Python 3.14.7, PySide6 6.12.0, SQLite 3.50.4.
- Intel 64-bit Family 6 Model 186; RAM, storage, Defender state, and packaged
  executable behavior were not recorded.
- `python tools/benchmark.py` disables auto-indexing, tray creation, clipboard
  polling, and animations; SQLite and the real search-provider stack are used.
- SQLite and provider-search measurements used generated datasets of 10,000
  and 100,000 files, with 60 warmed repetitions. The 100k provider-search
  result includes SQLite lookup and fuzzy ranking.
- Startup is source-mode timing from Python imports through controller
  readiness, not packaged-executable launch or visible-window paint. Each
  startup result is the median of five runs.
- The indexing test created 10,000 files in 100 child directories and indexed
  those files plus 100 directories. A 10 ms Qt timer ran on the main thread
  while indexing used a worker.
- The idle sample used a hidden UI with indexing and clipboard polling
  disabled. Memory is process RSS/private bytes; CPU is process CPU time over
  the sample window. The before/after idle samples had different durations, so
  CPU readings are not a controlled comparison.

## Findings, severity-ranked

| Severity | Finding | Evidence | Change |
|---|---|---|---|
| High | Single-token file queries unnecessarily broadened a narrow candidate set, then fuzzy-ranked up to 800 rows. | At 10k rows, full provider search was 156.0 ms median; at 100k, 202.0 ms. After the fix: 0.924 ms and 17.83 ms. | Keep broadening for multiword queries; do not broaden single-token queries that already use the full query. |
| High | Extension browsing sorted every matching row for each page. | At 100k rows, median 106.439 ms before; 0.163 ms after. `EXPLAIN QUERY PLAN` now uses `(ext, mtime DESC)` without a temporary sort. | Add the ordered compound index and migrate the old extension index (schema v2). |
| Medium | Importing SymPy synchronously delayed source-mode startup. | Five-run median fell from 2,302 ms (range 1,547–2,804) to 791 ms (range 663–1,155), a 65.6% reduction. | Defer SymPy import and warm it in a background worker. |
| Medium | Icon cache retained an entry for every path encountered. | 50,000 unique nonexistent paths increased RSS by 17.74 MiB before; the bounded cache increased RSS by 0.184 MiB after and retained 512 entries. | Use a 512-entry LRU cache. |
| Medium | Indexing workers could keep their thread-local SQLite connection while a pooled thread remained alive. | Cleanup callback is verified to run on the worker thread and close its connection. No long-duration leak rate was measured. | Close the current worker thread's connection after indexing work, on success or failure. |
| Low | Indexing occupies a worker but still adds some event-loop timer lateness. | Synthetic 10k-file indexing: 442 ms before / 315 ms after; 10 ms timer p95 lateness 2.29 / 1.915 ms and maximum lateness 13.81 / 4.742 ms. | No separate UI change; indexing remains off the GUI thread. |

## Post-change measurements

The latest `python tools/benchmark.py` run reported:

| Path | Median | p95 | Max |
|---|---:|---:|---:|
| Controller start (headless; not process startup) | 31.1 ms | — | — |
| Auto-provider query `chrome` | 0.474 ms | 0.746 ms | 2.021 ms |
| Calculator query `calc: sqrt(144) + 25 * 4` (warmed) | 0.498 ms | 0.653 ms | 2.280 ms |
| Web query `web: python packaging` | 0.103 ms | 0.132 ms | 0.266 ms |
| Empty-query suggestions | 0.124 ms | 0.180 ms | 1.175 ms |
| Calculator evaluation (warmed) | 0.359 ms | 0.617 ms | 0.873 ms |
| 300 fuzzy comparisons | 2.751 ms | — | — |
| Insert 10,000 SQLite file rows | 414.6 ms | — | — |

Additional warmed measurements after the fixes:

| Dataset / operation | Median | p95 |
|---|---:|---:|
| 10k: SQLite filename candidates | 0.849 ms | 1.869 ms |
| 10k: full file-provider search | 0.924 ms | 1.794 ms |
| 10k: extension browse, 40 rows | 0.216 ms | 0.249 ms |
| 100k: SQLite filename candidates | 19.069 ms | 35.690 ms |
| 100k: full file-provider search | 17.830 ms | 24.581 ms |
| 100k: extension browse, 40 rows | 0.163 ms | 0.275 ms |

The ordinary `name_lower` index cannot accelerate `LIKE '%term%'`. At 100k
rows, substring candidate lookup still takes about 19 ms median; this is a
remaining moderate bottleneck. Replacing it with full-text/trigram indexing
could change substring and typo-tolerant matching semantics, so it was not
done in this audit.

## Memory, idle CPU, and limitations

After startup warm-up, a 31-second hidden-app sample measured CPU at 4.03%
average / 6.00% p95, RSS 125.11–125.84 MiB, private bytes 99.86–100.70 MiB,
and 2–5 threads (3 at the end). An earlier 15-second sample measured CPU at
1.014% average / 1.6% p95, RSS 125.25–125.82 MiB, private bytes
99.70–100.11 MiB, and four threads after warm-up. CPU sampling windows and
conditions were not sufficiently identical to attribute the difference; idle
CPU should be re-measured under a controlled longer run. Memory was stable in
both short samples; no hours-long leak test was performed.

SymPy warm-up took 1,148 ms in the latest benchmark. Calculator evaluation is
sub-millisecond after warm-up, but a calculator query made immediately during
the asynchronous import can wait for initialization. Source-mode measurements
do not include PyInstaller extraction, OS cache/Defender effects, actual
window-paint latency, or hotkey-to-visible latency.

No dependency was added. The audit did not change substring search semantics,
the async worker model, or user-facing features.

## Reproduce

```powershell
python tools/benchmark.py
python -m pytest -q
```

The benchmark uses a temporary database and removes it when complete. The
larger filesystem/idle scripts used for this audit are not committed; their
results above are kept separate from the repeatable benchmark output.
