"""Run the actual notebook in a headless browser against the built static site."""

from functools import partial
from contextlib import suppress
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys
from threading import Thread

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
MARKER = "DEMO_COMPLETE: all nine requested libraries exercised."


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    assert (ROOT / "_output" / "lab" / "index.html").exists(), "Run pixi run build first"
    handler = partial(QuietHandler, directory=str(ROOT / "_output"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    Thread(target=server.serve_forever, daemon=True).start()
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    messages = []
    try:
        with sync_playwright() as playwright:
            # Pixi supplies browser shared libraries even on minimal Linux hosts.
            environment = os.environ.copy()
            if sys.platform == "linux":
                environment["LD_LIBRARY_PATH"] = os.pathsep.join(
                    filter(None, [str(Path(sys.prefix) / "lib"), environment.get("LD_LIBRARY_PATH")])
                )
                environment["FONTCONFIG_FILE"] = str(Path(sys.prefix) / "etc/fonts/fonts.conf")
            browser = playwright.chromium.launch(env=environment)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("console", lambda message: messages.append(f"{message.type}: {message.text}"))
            page.on("pageerror", lambda error: messages.append(f"PAGE ERROR: {error}"))
            try:
                # Deliberately avoid isolation headers: GitHub Pages cannot set them.
                page.goto(
                    f"http://127.0.0.1:{server.server_port}/lab/index.html?path=neuroscience-demo.ipynb",
                    timeout=120_000,
                )
                page.locator(".jp-Notebook").wait_for(timeout=120_000)
                page.get_by_role("menuitem", name="Run", exact=True).click()
                page.get_by_role("menuitem", name="Run All Cells", exact=True).click()
                page.wait_for_function(
                    """marker => document.querySelector('.jp-OutputArea-error') ||
                        Array.from(document.querySelectorAll('.jp-OutputArea-output'))
                        .some(output => output.textContent.includes(marker))""",
                    arg=MARKER,
                    timeout=600_000,
                )
                errors = page.locator(".jp-OutputArea-error").all_text_contents()
                assert not errors, "\n".join(errors)
                assert page.locator(".jp-OutputArea-output img").count() >= 1, "Missing plot output"
                print("JupyterLite / Xeus-Python: all notebook cells passed, including HDF5 and plots.")
            finally:
                (artifacts / "console.log").write_text("\n".join(messages))
                # Preserve the original test failure even if Chromium has crashed.
                with suppress(Exception):
                    page.screenshot(path=str(artifacts / "notebook.png"), full_page=True)
                with suppress(Exception):
                    (artifacts / "page.html").write_text(page.content())
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
