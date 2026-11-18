"""Measure actual browser kernels using Jupyter's message protocol, not native Python."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import partial
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import statistics
import sys
from threading import Thread
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from runtime_config import ROOT, VARIANTS, CONDA_SPECS, PYODIDE_SPECS, notebook_for
from test_browser import MARKER, QuietHandler


class BenchmarkHandler(QuietHandler):
    def do_GET(self):
        if urlsplit(self.path).path.endswith("/jupyter-lite.json"):
            path = Path(self.translate_path(self.path))
            if path.exists():
                config = json.loads(path.read_text())
                # Expose the frontend API only on this local test server.
                config.setdefault("jupyter-config-data", {})["exposeAppInBrowser"] = "true"
                body = json.dumps(config).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
        super().do_GET()


@contextmanager
def serve_site():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(BenchmarkHandler, directory=str(ROOT / "_output"))
    )
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/lab/index.html"
    finally:
        server.shutdown()
        server.server_close()


INITIALIZE = """async name => {
    const timeout = async (promise, milliseconds) => {
        let timer;
        try {
            return await Promise.race([promise, new Promise((_, reject) => {
                timer = setTimeout(() => reject(Error('Kernel operation timed out')), milliseconds);
            })]);
        } finally { clearTimeout(timer); }
    };
    const start = performance.now();
    const kernel = await timeout(window.jupyterapp.serviceManager.kernels.startNew({name}), 180000);
    window.__benchmarkKernel = kernel;
    // startNew returns before the in-browser transport is connected.
    // KernelConnection.info resolves after its initial kernel-info handshake.
    const info = await timeout(kernel.info, 180000);
    window.__benchmarkExecute = async (code, milliseconds = 600000) => {
        const started = performance.now();
        const output = {stdout: '', stderr: '', errors: [], plots: 0};
        const future = kernel.requestExecute({code, stop_on_error: true, store_history: false});
        future.onIOPub = message => {
            const c = message.content;
            if (message.header.msg_type === 'stream') output[c.name] += c.text;
            if (message.header.msg_type === 'error') output.errors.push(c.traceback.join('\\n'));
            if (['display_data', 'execute_result'].includes(message.header.msg_type)) {
                if (c.data['image/png'] || c.data['image/svg+xml']) output.plots += 1;
            }
        };
        const reply = await timeout(future.done, milliseconds);
        output.seconds = (performance.now() - started) / 1000;
        if (reply.content.status !== 'ok' || output.errors.length) {
            throw Error(JSON.stringify({...output, reply: reply.content}));
        }
        return output;
    };
    await window.__benchmarkExecute("print('Kernel ready')");
    return {seconds: (performance.now() - start) / 1000, info};
}"""


def execute_cells(page, cells):
    timings = []
    text = ""
    plots = 0
    for cell in cells:
        print(f"  cell: {cell.id}", flush=True)
        result = page.evaluate("code => window.__benchmarkExecute(code, 180000)", cell.source)
        timings.append({"id": cell.id, "seconds": result["seconds"]})
        text += result["stdout"]
        plots += result["plots"]
    assert MARKER in text, "Notebook did not reach its final assertion"
    assert plots, "Notebook produced no plot output"
    return timings


def measure(context, url, variant, repeat, cache, rerun):
    page = context.new_page()
    messages = []
    page.on("console", lambda message: messages.append(f"{message.type}: {message.text}"))
    page.on("pageerror", lambda error: messages.append(f"PAGE ERROR: {error}"))
    record = {"variant": variant, "repeat": repeat, "cache": cache, "status": "failed", "phase": "frontend"}
    before = time.perf_counter()
    try:
        page.goto(url, timeout=120_000)
        page.wait_for_function("window.jupyterapp !== undefined", timeout=120_000)
        page.evaluate("async () => { await window.jupyterapp.started; await window.jupyterapp.serviceManager.ready; }")
        record["frontend_load_seconds"] = time.perf_counter() - before
        available = page.evaluate("Object.keys(window.jupyterapp.serviceManager.kernelspecs.specs.kernelspecs)")
        kernel = VARIANTS[variant]["kernel"]
        assert kernel in available, f"Kernel {kernel} not found; available: {available}"
        record["phase"] = "kernel setup"
        print(f"{variant} repeat={repeat} cache={cache}: starting kernel", flush=True)
        startup = page.evaluate(INITIALIZE, kernel)
        record["kernel_setup_seconds"] = startup["seconds"]
        record["kernel_info"] = startup["info"]
        notebook = notebook_for(variant)
        installs = [cell for cell in notebook.cells if "installation" in cell.metadata.get("tags", [])]
        record["phase"] = "installation"
        print(f"{variant}: installing packages", flush=True)
        record["installation_seconds"] = 0
        record["installation_output"] = ""
        record["installation_cells"] = []
        for install in installs:
            result = page.evaluate("code => window.__benchmarkExecute(code)", install.source)
            record["installation_seconds"] += result["seconds"]
            record["installation_output"] += result["stdout"] + result["stderr"]
            record["installation_cells"].append({"id": install.id, "seconds": result["seconds"]})
            assert not result["stdout"].lstrip().startswith("Error:"), result["stdout"]
        cells = [cell for cell in notebook.cells if cell.cell_type == "code" and "installation" not in cell.metadata.get("tags", [])]
        record["phase"] = "execution"
        print(f"{variant}: executing {len(cells)} cells", flush=True)
        record["cells"] = execute_cells(page, cells)
        record["imports_seconds"] = record["cells"][0]["seconds"]
        record["execution_seconds"] = sum(cell["seconds"] for cell in record["cells"])
        record["analysis_seconds"] = record["execution_seconds"] - record["imports_seconds"]
        record["total_seconds"] = sum(record[key] for key in [
            "kernel_setup_seconds", "installation_seconds", "execution_seconds"
        ])
        versions = page.evaluate("code => window.__benchmarkExecute(code)",
            "import json\nprint(json.dumps({'python': sys.version.split()[0], 'hdf5': h5py.version.hdf5_version, **{p: version(p) for p in packages + ['scipy', 'matplotlib', 'scikit-learn', 'statsmodels', 'quantities']}}))")
        record["versions"] = json.loads(versions["stdout"].strip())
        expected_specs = PYODIDE_SPECS if variant == "pyodide" else [
            spec.replace("python-neo=", "neo=").replace("=", "==") for spec in CONDA_SPECS
        ]
        for spec in expected_specs + ["elephant==1.2.0"]:
            if "==" in spec:
                name, expected = spec.split("==")
                assert record["versions"].get(name) == expected, f"Version mismatch for {name}"
        if rerun:
            record["rerun_cells"] = execute_cells(page, cells)
            record["rerun_seconds"] = sum(cell["seconds"] for cell in record["rerun_cells"])
        record["status"] = "passed"
        record["phase"] = "complete"
        print(f"{variant}: passed; total {record['total_seconds']:.2f}s", flush=True)
    except Exception as error:
        record["error"] = str(error)
        print(f"{variant}: FAILED: {error}", flush=True)
    finally:
        record["observed_wall_seconds"] = time.perf_counter() - before
        artifacts = ROOT / "artifacts/benchmark-logs"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / f"{variant}-{repeat}-{cache}.log").write_text("\n".join(messages))
        try:
            page.evaluate("""async () => {
                if (window.__benchmarkKernel) await Promise.race([
                    window.__benchmarkKernel.shutdown(),
                    new Promise(resolve => setTimeout(resolve, 15000))
                ]);
            }""")
        except Exception:
            pass
        page.close()
    return record


def markdown_report(report):
    lines = [
        "# Browser kernel benchmark", "", f"Measured: {report['measured_at']}", "",
        "Times are seconds; table values are medians of successful repetitions.",
        "Kernel setup includes fetching/initializing the runtime and a first trivial execution.",
        "Installation is a separate cell; execution includes imports, simulation, statistics, HDF5 round-trips, plots, and downloads.",
        "The prebuilt Xeus installation cell is a no-op; its packages are loaded during kernel setup and installed at build time (reported below).", "",
        "| Variant | Cache | Passed | Kernel setup | Install cell | Imports | All demo cells | Total | Rerun, no install |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    groups = sorted({(row['variant'], row['cache']) for row in report['runs']})
    for variant, cache in groups:
        rows = [r for r in report['runs'] if r['variant'] == variant and r['cache'] == cache]
        good = [r for r in rows if r['status'] == 'passed']
        numbers = []
        for key in ['kernel_setup_seconds', 'installation_seconds', 'imports_seconds', 'execution_seconds', 'total_seconds', 'rerun_seconds']:
            values = [row[key] for row in good if key in row]
            numbers.append(f"{statistics.median(values):.3f}" if values else '—')
        lines.append(f"| {variant} | {cache} | {len(good)}/{len(rows)} | " + " | ".join(numbers) + " |")
    lines += [
        "", "## Method and limitations", "",
        "- Sequential runs, rotated variant order between repetitions, same machine and headless Chromium.",
        "- Cold means a fresh isolated browser context (empty HTTP cache, IndexedDB, service workers, and kernel). It does not flush OS, server, or CDN caches.",
        "- Warm means a new kernel/page in the same browser context, after a complete first visit. No live Python kernel is reused.",
        "- Rerun reuses the live kernel and executes all demo cells again without the installation cell.",
        "- The JupyterLab UI is loaded separately; frontend load time is recorded in JSON, not included in the table's total.",
        "- Execution is via JupyterLite's actual kernel-message API; no native-Python timings are substituted. PNG/SVG output and the notebook's assertions must pass.",
        "- Cell timings include kernel execution, plot encoding, and message delivery, but not notebook DOM layout/paint.",
        "- Main scientific versions match except h5py: Pyodide ships 3.13.0; Xeus uses 3.16.0 for its HDF5 1.14.6 ABI. Python versions, Wasm ABI/toolchains, transitive dependencies, packaging, and download origins also differ.",
        "- Local static hosting, no throttling, and no cross-origin isolation headers (as on GitHub Pages). Internet package downloads are included; results are not a guarantee for every device or connection.",
        "- Partial/failed installations are failures, not successful fast runs. Raw JSON contains per-cell durations, versions, failures, and each individual sample.",
        "", "## Build-time provisioning", "", "```json", json.dumps(report.get('build', {}), indent=2), "```",
        "", "Build-time installation uses host-side micromamba; its download cache may be warm. A cached environment's lookup time is not a fresh install measurement.",
        "", "## Machine", "", "```json", json.dumps(report['machine'], indent=2), "```",
    ]
    failures = [r for r in report['runs'] if r['status'] != 'passed']
    if failures:
        lines += ["", "## Failures", ""]
        for failure in failures:
            lines += [f"### {failure['variant']} / repeat {failure['repeat']} / {failure['cache']}", "", "```text", failure['error'], "```"]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--variants", nargs="+", choices=list(VARIANTS), default=list(VARIANTS))
    parser.add_argument("--cache", choices=["cold", "both"], default="cold")
    parser.add_argument("--skip-rerun", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/benchmark.json")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    report = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "machine": {"os": platform.platform(), "architecture": platform.machine(), "logical_cpus": os.cpu_count()},
        "runs": [],
    }
    build_timings = ROOT / "artifacts/build-timings.json"
    if build_timings.exists():
        report["build"] = json.loads(build_timings.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        args.output.with_suffix(".md").write_text(markdown_report(report))

    environment = os.environ.copy()
    if sys.platform == "linux":
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(filter(None, [
            str(Path(sys.prefix) / "lib"), environment.get("LD_LIBRARY_PATH")
        ]))
        environment["FONTCONFIG_FILE"] = str(Path(sys.prefix) / "etc/fonts/fonts.conf")
    with serve_site() as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(env=environment)
        report["machine"]["chromium"] = browser.version
        for repeat in range(1, args.repeats + 1):
            offset = (repeat - 1) % len(args.variants)
            order = args.variants[offset:] + args.variants[:offset]
            for variant in order:
                with browser.new_context() as context:
                    result = measure(context, url, variant, repeat, "cold", not args.skip_rerun)
                    report["runs"].append(result)
                    save()
                    if args.cache == "both" and result["status"] == "passed":
                        report["runs"].append(measure(context, url, variant, repeat, "warm", not args.skip_rerun))
                        save()
        browser.close()
    print(f"Results: {args.output} and {args.output.with_suffix('.md')}")
    return 1 if any(row["status"] != "passed" for row in report["runs"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
