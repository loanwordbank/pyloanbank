# pyloanbank

Shared [cldfbench](https://github.com/cldf/cldfbench) base class for [Loanwordbank](https://github.com/loanwordbank) CLDF Wordlist datasets. Subclass `LoanwordbankDataset` so each dataset gets the same README badges, bibliography handling, CLTS provenance, and optional extra column definitions.

## Install

Requires Python 3.11+ and `cldfbench>=1.14`.

```bash
pip install -e .
```

In a monorepo that vendors this package, install it before editable dataset packages, for example:

```bash
pip install -e ./pyloanbank
pip install -e ./path/to/your-dataset[test]
```

## Usage

Define a cldfbench dataset class that subclasses `LoanwordbankDataset` and sets `dir` and `id` as usual for cldfbench:

```python
from pathlib import Path

from cldfbench import CLDFSpec
from pyloanbank import LoanwordbankDataset


class Dataset(LoanwordbankDataset):
    dir = Path(__file__).parent
    id = "my-dataset"

    def cldf_specs(self):
        return CLDFSpec(dir=self.cldf_dir, module="Wordlist")

    def cmd_makecldf(self, args):
        self.add_sources_and_clts_provenance(args)
        # ... build tables ...
        self.apply_extra_columns(args.writer)
```

### What you get

- **`readme_lead` / `cmd_readme`** — Inserts GitHub Actions badges for CLDF validation and build (URLs assume `https://github.com/loanwordbank/<dataset-dir-name>/...`).
- **`add_sources_and_clts_provenance(args)`** — Loads BibTeX from the raw directory into CLDF sources and records CLTS catalog provenance. Override **`log_sources_bib_written`** if your log message or output path differs.
- **`apply_extra_columns(writer, table_names=...)`** — For each CLDF component table, reads `etc/ExtraCols/<TableName>.toml` if present. The file must contain a **`[column]`** list in the shape expected by `writer.cldf.add_columns`. Missing TOML files are skipped unless you pass `skip_missing=False`.
