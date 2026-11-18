# Neuroscience in your browser

A runnable JupyterLite notebook using **NumPy, xarray, h5netcdf, pandas, h5py,
Neo, Elephant, seaborn, and Pingouin**. It simulates paired neural recordings,
analyzes spike trains, writes and reads real HDF5/NetCDF files, runs a paired
statistical test, and plots the results. No Python server or account is needed.

**[Open the interactive notebook](https://olebialas.github.io/Test-Jupyterlite/lab/index.html?path=neuroscience-demo.ipynb)**
(available after the first successful Pages deployment).

Choose **Run → Run All Cells**. The first run downloads Python and its packages,
so allow a few minutes and keep an internet connection. Change the parameters
in section 2, then rerun that cell and all cells below it.

## Local development with Pixi

```sh
pixi install --locked
pixi run validate             # Execute the notebook on native Python
pixi run build                # Generate _output/, the static Pages artifact
pixi run python -m playwright install --with-deps chromium
pixi run test-browser         # Execute all cells in real browser-side Python
pixi run serve                # Browse http://localhost:8000/lab/index.html
```

The environment was created with `pixi init`. `pixi.toml` and `pixi.lock` define
the development/build environment; the notebook's first cell installs its
browser runtime packages. Native NumPy and other compiled packages come from
Pixi's resolved environment; browser binaries come from **Pyodide 314.0.8**.
The JupyterLite build vendors that Pyodide distribution into the static site.
Other browser packages are fetched from PyPI at runtime.

## Deploy to GitHub Pages

1. In **Settings → Pages → Build and deployment**, select **GitHub Actions**.
2. Commit and push these files to `main` (including `pixi.lock`).
3. The **Test and deploy JupyterLite** workflow executes the notebook on native
   Python, builds the site, and executes it again in Chromium/Pyodide before
   publishing. Use **Actions → Test and deploy JupyterLite → Run workflow** to
   redeploy manually. Pull requests test/build but do not deploy.
4. Open the notebook link above, or the deployment URL reported by the workflow.

For a fork, update the link to `https://OWNER.github.io/REPOSITORY/lab/index.html?path=neuroscience-demo.ipynb`.

## Compatibility and storage

- **Elephant is pinned to 1.2.0**, which publishes a pure-Python wheel usable
  in WebAssembly. Its standard spike statistics and binning are used here.
  Optional native/GPU accelerators are not provided; this is not a claim that
  every Elephant or Neo I/O backend runs in the browser.
- h5py uses Pyodide's actual HDF5 build; xarray explicitly uses the h5netcdf
  engine, and h5netcdf is also called directly. There are no mocked libraries
  or skipped HDF5 steps in the browser.
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
