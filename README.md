# Neuroscience in your browser

A runnable JupyterLite notebook using **NumPy, xarray, h5netcdf, pandas, h5py,
Neo, Elephant, seaborn, and Pingouin**. It simulates paired neural recordings,
analyzes spike trains, writes and reads real HDF5/NetCDF files, runs a paired
statistical test, and plots the results. No Python server or account is needed.

**[Open the interactive notebook](https://olebialas.github.io/Test-Jupyterlite/lab/index.html?path=neuroscience-demo.ipynb)**
(available after the first successful Pages deployment).

Choose **Run → Run All Cells**. The default notebook uses **Xeus-Python (xpython)**
with the scientific stack preinstalled by **micromamba at site-build time**.
Its setup and imports are separate cells; rerunning imports never reinstalls
packages. Initial loading still downloads the Wasm runtime and packages.
Change the parameters in section 2, then rerun that cell and all cells below it.

The site also includes two comparison notebooks, generated from the same source:

| Notebook | Kernel | Package installation |
|---|---|---|
| `neuroscience-demo.ipynb` | Xeus-Python | Prebuilt with micromamba |
| `neuroscience-xeus-runtime.ipynb` | Xeus-Python | Browser-side `%mamba` (mambajs), plus Elephant's wheel |
| `neuroscience-pyodide.ipynb` | Pyodide | Browser-side piplite/micropip |

## Local development with Pixi

```sh
pixi install --locked
pixi run validate             # Execute the notebook on native Python
pixi run build                # Generate _output/, the static Pages artifact
pixi run python -m playwright install --with-deps chromium
pixi run test-browser         # Execute all cells in real browser-side Python
pixi run benchmark --repeats 3 --cache both
pixi run serve                # Browse http://localhost:8000/lab/index.html
```

The environment was created with `pixi init`. `pixi.toml` and `pixi.lock` define
the native development/build environment. `environment.yml` defines the full
Xeus environment; `environment-runtime.yml` defines the minimal Xeus kernel used
to benchmark runtime mamba installs. Browser binaries come from
**emscripten-forge-4x / conda-forge** (Xeus-Python 0.19.0) and **Pyodide 314.0.8**.
Builds cache the Xeus environments under `.cache/xeus` and rebuild them when
the environment specifications change. The generated notebooks are in
`_site_content/`; edit the shared demo in `content/neuroscience-demo.ipynb`.

## Reproducible kernel benchmarks

`pixi run benchmark --repeats 3 --cache both` measures all three variants in
headless Chromium against the built static site. Results are written to
`artifacts/benchmark.json` and `artifacts/benchmark.md`, with:

- Kernel setup through the first successful execution, separately from UI load.
- Installation cell time (runtime downloads/solving/unpacking included).
- Each remaining cell, imports, first full execution, and rerun without installs.
- Fresh-browser-cache and optionally warm-browser-cache visits with **new kernels**.
- Exact versions, individual samples, median summaries, and failed runs.
- Build-time Xeus provisioning, reported separately so preinstallation is not
  mistaken for a free/zero-cost install.

The main scientific package versions match **except h5py** (Pyodide 3.13.0;
Xeus 3.16.0, required for its HDF5 ABI). The Python versions, ABI builds,
transitive dependencies, package formats, and network
origins differ, so this compares complete usable environments, not only Python
interpreter speed. Cold means an empty **browser** cache, not cold CDN/OS caches.
Installation is never mixed into the imports timing. Real HDF5 assertions and
plot generation must pass for a run to count as successful.

For CI measurements, use **Actions → Benchmark browser kernels → Run workflow**.
The workflow publishes its Markdown summary and raw JSON/logs as an artifact;
it does not commit results or redeploy the site.

## Deploy to GitHub Pages

1. In **Settings → Pages → Build and deployment**, select **GitHub Actions**.
2. Commit and push these files to `main` (including `pixi.lock`).
3. The **Test and deploy JupyterLite** workflow executes the notebook on native
   Python, builds the site, and executes all three variants in Chromium before
   publishing. Use **Actions → Test and deploy JupyterLite → Run workflow** to
   redeploy manually. Pull requests test/build but do not deploy.
4. Open the notebook link above, or the deployment URL reported by the workflow.

For a fork, update the link to `https://OWNER.github.io/REPOSITORY/lab/index.html?path=neuroscience-demo.ipynb`.

## Compatibility and storage

- **Elephant is pinned to 1.2.0** since no Wasm conda package is available.
  The prebuilt Xeus and Pyodide variants explicitly use its checksum-pinned
  official pure-Python wheel; runtime Xeus resolves that version with pip. All its
  dependencies are installed by mamba in the Xeus environments. Its standard
  spike statistics and binning are used here.
  Optional native/GPU accelerators are not provided; this is not a claim that
  every Elephant or Neo I/O backend runs in the browser.
- h5py uses each runtime's actual HDF5 build; xarray explicitly uses the h5netcdf
  engine, and h5netcdf is also called directly. There are no mocked libraries
  or skipped HDF5 steps in the browser.
- Xeus pins **h5py 3.16.0 / HDF5 1.14.6**. Older h5py 3.13 Wasm builds were
  compiled with HDF5 1.12.3 but their recipe permits incompatible newer HDF5,
  and current xarray's conda metadata requires HDF5 >=1.14. We use a compatible
  newer h5py build rather than disabling the HDF5 safety check. Pyodide uses
  its own compatible bundled build; actual versions are recorded in JSON.
- Files are created in the browser kernel's virtual filesystem, **not** on a
  remote server. Download `demo_recordings.nc` and `demo_spikes.h5` using the
  links in the last cell to keep them. Browser storage may be cleared; download
  your edited notebook as well. Initial loading needs network access and is
  not guaranteed to work offline.
- The synthetic observations illustrate an analysis workflow, not a scientific
  finding. The paired units are simulated neurons; trials are averaged within
  each neuron before inference to avoid treating trials as independent units.
- Browser CI serves plain static HTTP without special cross-origin isolation
  headers, matching GitHub Pages' hosting constraints.
