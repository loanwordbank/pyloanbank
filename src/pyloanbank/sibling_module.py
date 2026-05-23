"""Load a Python module from a sibling file next to a dataset package."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def load_sibling_module(
    package_dir: Path, filename: str, *, qualname: str | None = None
):
    """Import ``filename`` from ``package_dir`` without relying on ``sys.path``."""
    path = package_dir / filename
    module_qualname = qualname or f"{path.stem}_{abs(hash(path)) & 0xFFFF_FFFF:x}"
    spec = importlib.util.spec_from_file_location(module_qualname, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
