"""Loanwordbank CLDFbench shared utilities."""

from .dataset import (
    CLDF_TABLE_CSV_BASENAME,
    CLDF_TABLE_INSTANCE_ATTR,
    CLDFBENCH_MAKECLDF_BASENAME,
    EXTRA_COLS_AGGREGATE_BASENAME,
    LoanwordbankDataset,
    read_cldfbench_makecldf_toml,
)
from .partial_cognacy import apply_segment_slices_from_alignments
from .glove import load_glove_model
from .sibling_module import load_sibling_module
from .wordvector_gloss import (
    check_wordvector_input_coverage,
    tokenize,
    wordvector_input_column_value,
    wordvector_input_from_gloss,
)

__all__ = [
    "CLDF_TABLE_CSV_BASENAME",
    "CLDF_TABLE_INSTANCE_ATTR",
    "CLDFBENCH_MAKECLDF_BASENAME",
    "EXTRA_COLS_AGGREGATE_BASENAME",
    "LoanwordbankDataset",
    "apply_segment_slices_from_alignments",
    "check_wordvector_input_coverage",
    "load_glove_model",
    "load_sibling_module",
    "read_cldfbench_makecldf_toml",
    "tokenize",
    "wordvector_input_column_value",
    "wordvector_input_from_gloss",
]
__version__ = "0.1.0"
