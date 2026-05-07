# pyloanbank

Shared [cldfbench](https://github.com/cldf/cldfbench) base class for [Loanwordbank](https://github.com/loanwordbank) CLDF Wordlist datasets. Subclass `LoanwordbankDataset` so each dataset gets the same README badges, bibliography handling, CLTS provenance, and optional extra column definitions.

## Install

Requires Python 3.11+ and `cldfbench>=1.14` (also declares `pyclts` for direct use in the base class).

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

    def _cmd_makecldf_body(self, args):
        for row in self.data:
            ...
            self.forms.append({...})
            self.parameters.append({...})
```

In `etc/cldfbench_makecldf.toml`, `[makecldf] tables` lists only CLDF components that are **not** already in the module’s default metadata (for Wordlist that is everything except `FormTable`, which ships with the template). Set class attribute `cldf_module = "Dictionary"` when using `CLDFSpec(..., module="Dictionary")`. The base class merges those names with the module defaults into `makecldf_tables` (row lists and write order).

### What you get

- **`[makecldf] tables` / `makecldf_add_components`** — TOML list of table types passed to **`add_component`** only (omit tables already defined by the CLDF module template, e.g. **`FormTable`** on Wordlist, **`EntryTable`** and **`SenseTable`** on Dictionary). **`LanguageTable`** is always added in code and is never listed here. **`makecldf_tables`** (class attribute, set from TOML in **`__init_subclass__`**) is the merged ordered list used for clearing row lists, **`_cmd_makecldf_body`**, and writes — do **not** include **`LanguageTable`**. Then **`remove_makecldf_columns`**, **`apply_extra_columns_for_makecldf`**, init of **`[]`** / codes CSV, **`_cmd_makecldf_body`**, sync to **`self.makecldf_rows`**, and table writes. **`CodeTable`** uses **`etc/codes.csv`** when present in **`makecldf_tables`**. Log paths default to **`cldf/<name>.csv`** via **`CLDF_TABLE_CSV_BASENAME`**; override **`makecldf_table_log_path`** as needed. Mid-pipeline writes: **`flush_makecldf_tables`**. Override **`makecldf_instance_attr_name`** or **`_init_makecldf_instance_table_lists`** for non-default setup. If you do not use **`etc/cldfbench_makecldf.toml`**, set **`makecldf_add_components`** and **`makecldf_tables`** on the class yourself.
- **`makecldf_remove_columns`** — Optional module constant like **`MAKECLDF_REMOVE_COLUMNS = [("EntryTable", "Language_ID")]`** assigned as a class attribute; each **`(table, column)`** pair is passed to **`pycldf.Dataset.remove_columns`** before ExtraCols. Default: empty.
- **`extra_columns_tables`** / **`extra_columns_skip_missing`** — Class attributes for **`apply_extra_columns_for_makecldf`** (default: all components, skip missing definitions). Set **`extra_columns_tables`** to a list of table names and **`extra_columns_skip_missing = False`** when every listed table must define extra columns in **`etc/ExtraCols.toml`** and/or **`etc/ExtraCols/<Table>.toml`**.
- **`cmd_makecldf`** — Implements the pipeline above, then the repo README. Override **`load_langs`** if the language table CSV is not **`etc/`** + **`languages.csv`** (see **`CLDF_TABLE_CSV_BASENAME`**). Implement **`_cmd_makecldf_body`** instead of overriding **`cmd_makecldf`** unless you need full control.
- **`readme_lead` / `cmd_readme`** — Inserts GitHub Actions badges for CLDF validation and build (URLs assume `https://github.com/loanwordbank/<dataset-dir-name>/...`).
- **`cmd_makecldf` start** — Loads BibTeX from **`raw_dir`** into CLDF sources, logs via **`log_sources_bib_written`**, and adds CLTS catalog provenance. Override **`log_sources_bib_written`** if your log message or output path differs (e.g. alternate **`CLDF_DIR`**).
- **`apply_extra_columns` / `apply_extra_columns_for_makecldf`** — Called from **`cmd_makecldf`** after **`remove_makecldf_columns`**, still before **`_cmd_makecldf_body`**. For each table (see **`extra_columns_tables`**), if **`etc/ExtraCols.toml`** exists and contains a top-level **`TableName`** table with a **`column`** list (use e.g. **`[[FormTable.column]]`** in TOML), those columns are registered; otherwise **`etc/ExtraCols/<TableName>.toml`** is used when present (root **`[[column]]`** list). Both shapes match what **`writer.cldf.add_columns`** expects. Override **`apply_extra_columns_for_makecldf`** only if you need non-default behaviour.
- **`self.clts`**, **`self.cv`**, **`self.sca`** — Lazy, cached [pyclts](https://pypi.org/project/pyclts/) `CLTS()` client and `soundclass('cv')` / `soundclass('sca')` profiles. Use **`self.get_cv_profile(segment_string)`** and **`self.get_sca_profile(segment_string)`** for space-split CV/SCA profile lists.
- **`write_cldf_table(args, log_path, **kwargs)`** — Runs `args.writer.write(**kwargs)` then logs `wrote {log_path}`. Used by the default **`cmd_makecldf`** write loop; call directly only for special cases (e.g. **`flush_makecldf_tables`**).
- **`get_segments(text, language_id)`** — Looks up **`Profile`** on **`self.languages`**, uses **`self.tokenizers`**, and returns the space-separated segment string. Set class attribute **`segment_tokenizer_column`** to **`IPA`** when your `.prf` files use that column (default **`mapping`**).
- **`self.tokenizers`** — Cached dict `{ "hun.prf": Tokenizer(...), ... }` from `etc_dir/*.prf` (used by **`get_segments`**).
