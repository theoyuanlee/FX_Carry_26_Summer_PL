"""Cell builders shared by the notebook build scripts."""
from __future__ import annotations

from pathlib import Path

import nbformat


def md(text: str) -> nbformat.NotebookNode:
    """A markdown cell from a block of text, outer blank lines stripped."""
    return nbformat.v4.new_markdown_cell(text.strip("\n"))


def code(text: str) -> nbformat.NotebookNode:
    """A code cell from a block of source, outer blank lines stripped."""
    return nbformat.v4.new_code_cell(text.strip("\n"))


def write(cells: list, path: str | Path) -> Path:
    """Assemble the cells into a notebook carrying the fxcarry kernel and write it."""
    notebook = nbformat.v4.new_notebook(cells=cells)
    notebook.metadata.kernelspec = {
        "display_name": "fxcarry",
        "language": "python",
        "name": "fxcarry",
    }
    notebook.metadata.language_info = {"name": "python", "version": "3.12"}
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, out)
    return out
