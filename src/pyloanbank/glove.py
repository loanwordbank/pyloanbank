"""Cached GloVe Wikipedia + Gigaword 100d loading for dataset build scripts."""

from __future__ import annotations

import logging
from pathlib import Path

from gensim.downloader import load as gensim_load
from gensim.models.keyedvectors import KeyedVectors

logging.getLogger("gensim").setLevel(logging.WARNING)
logging.getLogger("gensim.downloader").setLevel(logging.WARNING)


def glove_cache_paths(base: Path) -> tuple[Path, Path]:
    cache_path = base / "glove_wiki_gigaword_100d.gensim"
    return cache_path, Path(f"{cache_path}.vectors.npy")


def _glove_cache_complete(cache_path: Path, vectors_path: Path) -> bool:
    if cache_path.is_symlink():
        target = cache_path.resolve()
        return target.is_file() and Path(f"{target}.vectors.npy").is_file()
    return cache_path.is_file() and vectors_path.is_file()


def _glove_load_path(cache_path: Path) -> Path:
    return cache_path.resolve() if cache_path.is_symlink() else cache_path


def load_glove_model(base: Path) -> KeyedVectors:
    """Load GloVe 100d from cached binary if present, else download and cache."""
    cache_path, vectors_path = glove_cache_paths(base)
    if _glove_cache_complete(cache_path, vectors_path):
        return KeyedVectors.load(str(_glove_load_path(cache_path)))
    if cache_path.exists() or cache_path.is_symlink():
        print(f"Removing incomplete GloVe cache at {cache_path}")
        cache_path.unlink()
    if vectors_path.exists():
        vectors_path.unlink()

    print(
        "Downloading GloVe vectors 'glove-wiki-gigaword-100' (~130 MB). "
        "This may take a few minutes..."
    )
    gensim_logger = logging.getLogger("gensim")
    downloader_logger = logging.getLogger("gensim.downloader")
    old_level = gensim_logger.level
    old_downloader_level = downloader_logger.level
    gensim_logger.setLevel(logging.INFO)
    downloader_logger.setLevel(logging.INFO)
    try:
        model = gensim_load("glove-wiki-gigaword-100")
    finally:
        gensim_logger.setLevel(old_level)
        downloader_logger.setLevel(old_downloader_level)

    model.save(str(cache_path))
    print(f"Saved downloaded vectors to {cache_path}")
    return model
