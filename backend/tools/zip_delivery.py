"""
tools/zip_delivery.py — ZIP Packaging for Project Delivery
===========================================================
code_files dict se ZIP banata hai.
Reviewer agent isko use karta hai final deliverable create karne ke liye.

Two modes:
    1. From sandbox folder  → ZIP an existing directory on disk
    2. From code_files dict → write files to temp dir, then ZIP

Usage:
    from tools.zip_delivery import create_zip_from_folder, create_zip_from_files

    # Mode 1: sandbox folder already exists on disk
    zip_path = create_zip_from_folder("/tmp/sandbox_abc", "my_project")

    # Mode 2: create ZIP directly from code_files dict
    zip_path = create_zip_from_files(
        {"main.py": "print('hi')", "utils.py": "..."},
        "my_project",
    )
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger("agentic-platform")


# ─────────────────────────────────────────────────────────────────────────────
# 1. From sandbox folder (directory already on disk)
# ─────────────────────────────────────────────────────────────────────────────

def create_zip_from_folder(
    sandbox_folder: str,
    project_name: str = "project",
) -> str:
    """
    Existing sandbox folder ko ZIP mein compress karta hai.

    Parameters
    ----------
    sandbox_folder : str
        Path to the project directory on disk.
    project_name : str
        Name used for the ZIP file (without .zip extension).

    Returns
    -------
    str — absolute path to the created .zip file.

    Raises
    ------
    FileNotFoundError — if sandbox_folder doesn't exist.
    """
    sandbox_path = Path(sandbox_folder).resolve()
    if not sandbox_path.is_dir():
        raise FileNotFoundError(f"Sandbox folder not found: {sandbox_folder}")

    # Place ZIP next to sandbox folder, not inside it
    zip_base = sandbox_path.parent / f"{project_name}_delivery"
    zip_path = shutil.make_archive(
        base_name=str(zip_base),
        format="zip",
        root_dir=str(sandbox_path),
    )

    logger.info("ZIP created from folder | path=%s", zip_path)
    return zip_path


# ─────────────────────────────────────────────────────────────────────────────
# 2. From code_files dict (no sandbox folder needed)
# ─────────────────────────────────────────────────────────────────────────────

def create_zip_from_files(
    code_files: dict[str, str],
    project_name: str = "project",
    *,
    output_dir: str | None = None,
) -> str:
    """
    code_files dict se ZIP banata hai — files pehle temp dir mein likhta hai,
    phir ZIP create karta hai.

    Parameters
    ----------
    code_files : dict[str, str]
        {relative_file_path: file_content} mapping.
    project_name : str
        Name used for the ZIP file.
    output_dir : str | None
        Where to place the ZIP. Defaults to system temp directory.

    Returns
    -------
    str — absolute path to the created .zip file.
    """
    if not code_files:
        raise ValueError("code_files is empty — nothing to package")

    # Write all files to a temp directory
    tmp_dir = tempfile.mkdtemp(prefix=f"{project_name}_")
    try:
        for file_path, content in code_files.items():
            full_path = Path(tmp_dir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

        # Determine output location
        if output_dir:
            out = Path(output_dir).resolve()
            out.mkdir(parents=True, exist_ok=True)
        else:
            out = Path(tmp_dir).parent

        zip_base = out / f"{project_name}_delivery"
        zip_path = shutil.make_archive(
            base_name=str(zip_base),
            format="zip",
            root_dir=tmp_dir,
        )

        logger.info(
            "ZIP created from code_files | files=%d path=%s",
            len(code_files), zip_path,
        )
        return zip_path

    finally:
        # Clean up temp directory (ZIP is already created)
        shutil.rmtree(tmp_dir, ignore_errors=True)
