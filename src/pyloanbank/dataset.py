"""Base :mod:`cldfbench` dataset with shared Loanwordbank conventions."""

from __future__ import annotations

import tomllib
from typing import Iterable, Sequence

from cldfbench import Dataset as CldfbenchDataset
from cldfbench.catalogs import CLTS as CLTSCatalog
from cldfcatalog import Config


class LoanwordbankDataset(CldfbenchDataset):
    """
    Common patterns across Loanwordbank CLDF datasets:

    * GitHub Actions badges prepended to generated README
    * ``sources.bib`` plus CLTS provenance
    * Optional ``etc/ExtraCols/<Table>.toml`` column definitions
    """

    def _cldf_validation_badge(self) -> str:
        name = self.dir.name
        cldf_base = (
            f"https://github.com/loanwordbank/{name}/actions/workflows/cldf-validation.yaml"
        )
        build_base = f"https://github.com/loanwordbank/{name}/actions/workflows/build.yaml"
        return (
            f"[![CLDF-validation]({cldf_base}/badge.svg)]({cldf_base}) "
            f"[![Build]({build_base}/badge.svg)]({build_base})\n\n"
        )

    def readme_lead(self, args=None) -> str:
        """Markdown inserted before the default CLDF readme body."""
        return self._cldf_validation_badge()

    def cmd_readme(self, args):
        return self.readme_lead(args) + super().cmd_readme(args)

    def log_sources_bib_written(self) -> str:
        """Log message after writing ``sources.bib`` (override if output dir differs)."""
        return "wrote cldf/sources.bib"

    def add_sources_and_clts_provenance(self, args) -> None:
        args.writer.cldf.sources.add(*self.raw_dir.read_bib())
        args.log.info(self.log_sources_bib_written())
        args.writer.cldf.add_provenance(
            wasDerivedFrom=[CLTSCatalog(Config.from_file().get_clone("clts")).json_ld()]
        )

    def apply_extra_columns(self, writer, table_names: Sequence[str] | None = None, *, skip_missing: bool = True) -> None:
        """
        Load ``etc/ExtraCols/<name>.toml`` (``[column]`` list) and register extra columns.

        Parameters
        ----------
        table_names
            Tables to process; default is all components on ``writer.cldf``.
        skip_missing
            If True, ignore tables with no TOML file. If False, require every file.
        """
        names: Iterable[str]
        if table_names is None:
            names = list(writer.cldf.components)
        else:
            names = table_names
        for table_name in names:
            toml_path = self.etc_dir / "ExtraCols" / f"{table_name}.toml"
            if skip_missing and not toml_path.exists():
                continue
            with open(toml_path, "rb") as f:
                extra = tomllib.load(f)["column"]
            writer.cldf.add_columns(table_name, *extra)
