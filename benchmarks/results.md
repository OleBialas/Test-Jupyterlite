# Browser kernel benchmark

Measured: 2026-11-18T09:58:51.408748+00:00

Times are seconds; table values are medians of successful repetitions.
Kernel setup includes fetching/initializing the runtime and a first trivial execution.
Installation is a separate cell; execution includes imports, simulation, statistics, HDF5 round-trips, plots, and downloads.
The prebuilt Xeus installation cell is a no-op; its packages are loaded during kernel setup and installed at build time (reported below).

| Variant | Cache | Passed | Kernel setup | Install cell | Imports | All demo cells | Total | Rerun, no install |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| pyodide | cold | 1/1 | 9.309 | 8.203 | 19.053 | 22.529 | 40.041 | 3.004 |
| xeus-prebuilt | cold | 1/1 | 10.237 | 0.012 | 31.611 | 35.691 | 45.940 | 3.496 |
| xeus-runtime | cold | 2/2 | 5.978 | 16.742 | 27.753 | 31.505 | 54.225 | 2.922 |

## Method and limitations

- Sequential runs, rotated variant order between repetitions, same machine and headless Chromium.
- Cold means a fresh isolated browser context (empty HTTP cache, IndexedDB, service workers, and kernel). It does not flush OS, server, or CDN caches.
- Warm means a new kernel/page in the same browser context, after a complete first visit. No live Python kernel is reused.
- Rerun reuses the live kernel and executes all demo cells again without the installation cell.
- The JupyterLab UI is loaded separately; frontend load time is recorded in JSON, not included in the table's total.
- Execution is via JupyterLite's actual kernel-message API; no native-Python timings are substituted. PNG/SVG output and the notebook's assertions must pass.
- Cell timings include kernel execution, plot encoding, and message delivery, but not notebook DOM layout/paint.
- Main scientific versions match except h5py: Pyodide ships 3.13.0; Xeus uses 3.16.0 for its HDF5 1.14.6 ABI. Python versions, Wasm ABI/toolchains, transitive dependencies, packaging, and download origins also differ.
- Local static hosting, no throttling, and no cross-origin isolation headers (as on GitHub Pages). Internet package downloads are included; results are not a guarantee for every device or connection.
- Partial/failed installations are failures, not successful fast runs. Raw JSON contains per-cell durations, versions, failures, and each individual sample.

## Build-time provisioning

```json
{
  "environments": [
    {
      "name": "neuroscience-xeus",
      "cache_hit": false,
      "resolve_download_install_seconds": 4.737776341004064,
      "last_uncached_install_seconds": 4.737776341004064
    },
    {
      "name": "neuroscience-xeus-runtime",
      "cache_hit": true,
      "resolve_download_install_seconds": 1.2099917512387037e-06,
      "last_uncached_install_seconds": 2.599489915999584
    }
  ],
  "pack_and_site_build_seconds": 44.29347297101049,
  "total_build_seconds": 49.09138915600488
}
```

Build-time installation uses host-side micromamba; its download cache may be warm. A cached environment's lookup time is not a fresh install measurement.

## Machine

```json
{
  "os": "Linux-6.18.58.1-microsoft-standard-WSL2-x86_64-with-glibc2.36",
  "architecture": "x86_64",
  "logical_cpus": 20,
  "chromium": "159.0.8154.6"
}
```
