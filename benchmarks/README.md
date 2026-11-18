# Comparing browser kernels

Run from the repository root:

```sh
pixi run python -m playwright install chromium
pixi run benchmark --repeats 3 --cache both --output benchmarks/results.json
```

The command builds the site, then measures these variants sequentially in
Chromium, rotating their order across repetitions:

1. **Pyodide**: runtime installation with piplite/micropip.
2. **Xeus runtime**: a minimal xpython environment, runtime installation with
   mamba/mambajs, then a separate pip cell for Elephant.
3. **Xeus prebuilt**: the same scientific stack installed by micromamba during
   the site build, with no runtime installation.

The generated `results.md` explains the phases and cache definitions. The raw
`results.json` retains every sample, per-cell timing, package version, failure,
and build-time provisioning measurement. Detailed browser console logs are in
`artifacts/benchmark-logs/` (not committed).

All variants derive their analysis cells from
`content/neuroscience-demo.ipynb`. Main package versions in `environment.yml`
are translated to equivalent PyPI specifications for Pyodide, except h5py:
Pyodide ships 3.13.0 while Xeus uses 3.16.0 for HDF5 1.14.6 compatibility.
Python versions, Wasm builds, transitive dependencies, and installation
formats are not identical; this is a complete-workflow comparison, not a
controlled test of interpreter speed alone.

Cold visits start with an isolated browser context. Warm visits use a new page
and kernel in the same context. A separate rerun measurement reuses the live
kernel but does **not** execute the installation cells again. Build-time mamba
installation is not hidden inside the browser execution measurements.

An optional manual **Benchmark browser kernels** GitHub Actions workflow runs
the same harness and uploads the Markdown report, raw JSON, and diagnostics.
