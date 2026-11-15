# SeekR — Windows performance

Windows performance has now been measured on a real Windows 11 machine for
source-mode startup, headless controller/provider paths, synthetic SQLite and
filesystem workloads, and a short hidden-app idle sample. Results and
methodology are recorded in [PERFORMANCE.md](PERFORMANCE.md).

## Environment

| Field | Value |
|---|---|
| Windows | Windows 11 build 26300 |
| Python / Qt / SQLite | Python 3.14.7 / PySide6 6.12.0 / SQLite 3.50.4 |
| Processor | Intel 64-bit Family 6 Model 186 |
| Hardware / OS details | RAM, storage, GPU driver, Defender state, and display configuration not recorded |
| Build type | Source mode; packaged onefile/onedir builds not measured |

## Measured results

- Source-mode import/controller readiness: five-run median 791 ms (range
  663–1,155 ms) after lazy SymPy loading, versus 2,302 ms (range 1,547–2,804
  ms) before.
- Warmed headless provider queries: 0.103–0.498 ms median in the included
  benchmark. A specific 100k-file search was 17.83 ms median after correcting
  unnecessary candidate broadening.
- Extension browse at 100k indexed rows: 0.163 ms median after the ordered
  compound-index change, compared with 106.439 ms before.
- Synthetic indexing of 10,000 files plus 100 directories: 315 ms. A 10 ms
  main-thread timer had 1.915 ms p95 and 4.742 ms maximum lateness.
- 50,000 unique icon paths retained at most 512 entries; measured RSS growth
  was 0.184 MiB, compared with 17.74 MiB before the cache bound.
- Short idle samples showed stable memory near 125 MiB RSS, but idle CPU
  results were inconsistent (1.014% over 15 seconds previously; 4.03% over
  31 seconds in the latest sample). They are not a controlled before/after
  comparison.

These are source/headless or synthetic workload results, not release-build
measurements. Cold/warm packaged startup, visible window paint, hotkey-to-show
latency, large real user directories, long-duration idle CPU, and multi-hour
memory growth remain unmeasured. Onefile extraction, Defender scanning,
Start Menu icon extraction, and redirected/network profiles may materially
change Windows results.

For exact benchmark values, caveats, and the ranked bottlenecks, see
[PERFORMANCE.md](PERFORMANCE.md).
