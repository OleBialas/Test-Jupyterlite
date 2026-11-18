"""Shared installation specs and notebook variants for deployment and benchmarks."""

from pathlib import Path
import shlex

import nbformat
import yaml


ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT = yaml.safe_load((ROOT / "environment.yml").read_text())
CONDA_SPECS = [
    spec for spec in ENVIRONMENT["dependencies"]
    if isinstance(spec, str) and not spec.startswith(("python=", "xeus-python="))
]
ELEPHANT_WHEEL = next(
    spec["pip"][0] for spec in ENVIRONMENT["dependencies"] if isinstance(spec, dict)
)
# Match versions where both distributions supply compatible Wasm binaries.
# Pyodide ships h5py 3.13; Xeus needs its newer build for HDF5 1.14 compatibility.
PYODIDE_SPECS = [
    spec.replace("python-neo=", "neo=").replace("h5py=3.16.0", "h5py=3.13.0").replace("=", "==")
    for spec in CONDA_SPECS if not spec.startswith("hdf5=")
]

VARIANTS = {
    "pyodide": {
        "kernel": "python",
        "display": "Python (Pyodide)",
        "notebook": "neuroscience-pyodide.ipynb",
        "setup": "import piplite\nawait piplite.install(" + repr(PYODIDE_SPECS + [ELEPHANT_WHEEL]) + ")",
        "notes": "Pyodide installs the pinned stack at runtime using piplite/micropip. Run this installation cell once before the separate imports cell.",
    },
    "xeus-runtime": {
        "kernel": "xpython (neuroscience-xeus-runtime)",
        "display": "Python (Xeus) [neuroscience-xeus-runtime]",
        "notebook": "neuroscience-xeus-runtime.ipynb",
        "setup": "%mamba install " + shlex.join(CONDA_SPECS),
        "extra_setup": "%pip install elephant==1.2.0",
        "notes": "This minimal Xeus-Python kernel installs the stack at runtime using mamba (mambajs). Elephant's pure-Python wheel is installed separately with pip. Imports remain in the following cell.",
    },
    "xeus-prebuilt": {
        "kernel": "xpython (neuroscience-xeus)",
        "display": "Python (Xeus) [neuroscience-xeus]",
        "notebook": "neuroscience-demo.ipynb",
        "setup": "print('Setup: using the preinstalled scientific environment.')",
        "notes": "The stack is preinstalled with micromamba at site-build time. This cell does no runtime installation; the separate imports cell follows. Elephant uses its official pure-Python wheel.",
    },
}


def notebook_for(variant):
    notebook = nbformat.read(ROOT / "content/neuroscience-demo.ipynb", as_version=4)
    config = VARIANTS[variant]
    notebook.metadata.kernelspec = {
        "name": config["kernel"], "language": "python", "display_name": config["display"]
    }
    if "extra_setup" in config:
        index = next(i for i, cell in enumerate(notebook.cells) if cell.id == "environment-setup")
        notebook.cells.insert(index + 1, nbformat.v4.new_code_cell(
            config["extra_setup"], id="install-elephant", metadata={"tags": ["installation"]}
        ))
    for cell in notebook.cells:
        if cell.id == "environment-setup":
            cell.source = config["setup"]
            cell.metadata.tags = ["installation"]
        elif cell.id == "setup-notes":
            cell.source = "## 1a. Environment setup (separate from imports)\n\n" + config["notes"]
        elif cell.id == "welcome":
            cell.source = (
                "# A tiny neuroscience lab in your browser\n\n"
                f"**Variant: {variant}** — NumPy, xarray, h5netcdf, pandas, h5py, Neo, Elephant, seaborn, Pingouin.\n\n"
                "Choose **Run → Run All Cells**. Initial loading and runtime installation (where applicable) need network access. "
                "Installation and imports are separate. This synthetic teaching example runs locally, without a Python server. "
                "Download generated files at the end to keep them."
            )
        elif cell.id == "imports":
            cell.source = cell.source.replace(
                "'Xeus-Python / WebAssembly'", repr(config["display"] + " / WebAssembly")
            )
    return notebook
