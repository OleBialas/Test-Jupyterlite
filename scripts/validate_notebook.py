"""Validate and execute the committed notebook without modifying it."""

from pathlib import Path
from tempfile import TemporaryDirectory

import nbformat
from nbclient import NotebookClient


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "content" / "neuroscience-demo.ipynb"
MARKER = "DEMO_COMPLETE: all nine requested libraries exercised."


def main():
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    nbformat.validate(notebook)
    code = [cell for cell in notebook.cells if cell.cell_type == "code"]
    assert all(cell.execution_count is None and not cell.outputs for cell in code)
    with TemporaryDirectory(prefix="neuroscience-demo-") as directory:
        NotebookClient(
            notebook,
            timeout=300,
            kernel_name="python3",
            resources={"metadata": {"path": directory}},
        ).execute()
    outputs = "\n".join(
        output.get("text", "")
        for cell in code
        for output in cell.outputs
        if output.output_type == "stream"
    )
    assert MARKER in outputs, outputs
    print(f"Executed {len(code)} code cells successfully on CPython.")


if __name__ == "__main__":
    main()
