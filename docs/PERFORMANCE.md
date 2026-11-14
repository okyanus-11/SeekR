# SeekR performance

Performance is measured, not assumed. `tools/benchmark.py` exercises the real
hot paths with a real SQLite database and the real provider stack, then prints
JSON.

## How to reproduce

```bash
python tools/benchmark.py
```

The script disables automatic indexing, tray creation, clipboard polling and
animations so the numbers describe search and storage rather than background
warm-up. Each measurement is repeated (60–120 iterations); medians and p95 are
reported. A temporary data directory is used and removed by the OS.

## Results

Environment: Linux 6.1 x86_64 (container), Python 3.12.3, PySide6 6.12.0,
SymPy 1.14.0, SQLite (WAL). 10,000 rows in the file index.

| Path | Median | p95 | Max |
|---|---|---|---|
| Controller start (no tray/hotkey) | 12.4 ms | — | — |
| Search `chrome` (all auto providers) | 0.52 ms | 0.56 ms | 2.71 ms |
| Search `calc: sqrt(144) + 25 * 4` | 0.43 ms | 0.48 ms | 2.59 ms |
| Search `web: python packaging` | 0.07 ms | 0.08 ms | 0.12 ms |
| Empty-query suggestions | 0.07 ms | 0.11 ms | 0.57 ms |
| Calculator evaluation | 0.35 ms | 0.38 ms | 0.44 ms |
| 300 fuzzy comparisons | 2.72 ms (9.1 µs each) | — | — |
| Indexed filename query (`document-9999`) | 0.92 ms | — | — |
| Browse extension page (`.txt`, 40 rows) | 7.2 ms | — | — |
| Insert 10,000 file rows (100 batches) | 398 ms total | — | — |

## Interpretation

- Typical keystroke-to-results work is well under a millisecond at the engine
  layer; the debounce (default 120 ms) and SQLite I/O dominate perceived
  latency, not ranking.
- The single-digit-millisecond outlier on the first query is import/JIT-style
  warm-up inside SymPy and Qt; steady state stays below 1 ms.
- With 10,000 indexed files, a name query is ~1 ms; the LIMIT 40 page scan is
  ~7 ms, so the result list is capped rather than loading the whole index.
- Insert throughput is roughly 25,000 rows/second in batches, which keeps a
  large first index practical in the background.

## Caveats

- These numbers come from Linux, not Windows. Filesystem and antivirus
  overhead on Windows can change indexing and file-query timings; search
  ranking and calculator timings are platform-independent Python work.
- The benchmark database is local and warm; a cold spinning disk is slower.
- GUI rendering cost is not included. The launcher renders at most the
  configured result limit (default 40) with icons cached per path.
