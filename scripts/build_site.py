"""Cache mamba environments, generate comparable notebooks, and build the site."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import nbformat
import yaml
from jupyterlite_xeus.create_conda_env import create_conda_env_from_env_file

from runtime_config import ROOT, VARIANTS, notebook_for


def main():
    started = time.perf_counter()
    generated = ROOT / "_site_content"
    generated.mkdir(exist_ok=True)
    for variant, config in VARIANTS.items():
        nbformat.write(notebook_for(variant), generated / config["notebook"])

    root_prefix = ROOT / ".cache/xeus"
    os.environ["CONDA_PKGS_DIRS"] = str(root_prefix / "pkgs")
    timings = {"environments": []}
    prefixes = []
    for filename in ["environment.yml", "environment-runtime.yml"]:
        file = ROOT / filename
        data = yaml.safe_load(file.read_text())
        prefix = root_prefix / "envs" / data["name"]
        stamp = root_prefix / (data["name"] + ".sha256")
        fingerprint = hashlib.sha256(file.read_bytes()).hexdigest()
        cached = prefix.is_dir() and stamp.exists() and stamp.read_text() == fingerprint
        before = time.perf_counter()
        if not cached:
            create_conda_env_from_env_file(root_prefix, data, ROOT)
            stamp.write_text(fingerprint)
        timings["environments"].append({
            "name": data["name"], "cache_hit": cached,
            "resolve_download_install_seconds": time.perf_counter() - before,
        })
        prefixes.append(prefix)

    before = time.perf_counter()
    # Override environment_file to reuse cached prefixes instead of recreating them.
    subprocess.run([
        "jupyter", "lite", "build", "--contents", str(generated),
        "--output-dir", str(ROOT / "_output"),
        *[f"--XeusAddon.prefix={prefix}" for prefix in prefixes],
    ], cwd=ROOT, check=True)
    timings["pack_and_site_build_seconds"] = time.perf_counter() - before
    timings["total_build_seconds"] = time.perf_counter() - started
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    path = artifacts / "build-timings.json"
    # Preserve the most recent non-cached installation measurement across rebuilds.
    if path.exists():
        previous = json.loads(path.read_text())
        for current in timings["environments"]:
            old = next((e for e in previous["environments"] if e["name"] == current["name"]), {})
            current["last_uncached_install_seconds"] = (
                old.get("last_uncached_install_seconds") if current["cache_hit"]
                else current["resolve_download_install_seconds"]
            )
    else:
        for current in timings["environments"]:
            current["last_uncached_install_seconds"] = (
                None if current["cache_hit"] else current["resolve_download_install_seconds"]
            )
    path.write_text(json.dumps(timings, indent=2) + "\n")
    print(json.dumps(timings, indent=2))


if __name__ == "__main__":
    main()
