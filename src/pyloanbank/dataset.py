"""Base :mod:`cldfbench` dataset with shared Loanwordbank conventions."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from functools import cached_property
from pathlib import Path
from typing import Any, ClassVar, Literal, Sequence

import tomllib
from cldfbench import Dataset as CldfbenchDataset
from cldfbench.catalogs import CLTS as CLTSCatalog
from cldfcatalog import Config
from pyclts import CLTS as PyCLTS
from pyclts.models import Consonant, Diphthong, UnknownSound, Vowel
from pyclts.util import nfd
from segments import Profile, Tokenizer

CLDFBENCH_MAKECLDF_BASENAME = "cldfbench_makecldf.toml"
EXTRA_COLS_AGGREGATE_BASENAME = "ExtraCols.toml"

CLDF_TABLE_CSV_BASENAME: dict[str, str] = {
    "LanguageTable": "languages.csv",
    "FormTable": "forms.csv",
    "ParameterTable": "parameters.csv",
    "CognateTable": "cognates.csv",
    "EntryTable": "entries.csv",
    "SenseTable": "senses.csv",
    "CodeTable": "codes.csv",
}
CLDF_TABLE_INSTANCE_ATTR: dict[str, str] = {
    "LanguageTable": "languages",
    "FormTable": "forms",
    "ParameterTable": "parameters",
    "CognateTable": "cognates",
    "EntryTable": "entries",
    "SenseTable": "senses",
    "CodeTable": "codes",
}

# Tables already present in pycldf's default module metadata
# (copy_metadata / from_metadata).
_MODULE_SHIPPED_TABLES: dict[str, frozenset[str]] = {
    "Wordlist": frozenset({"FormTable"}),
    "Dictionary": frozenset({"EntryTable", "SenseTable"}),
}
# Write / init order for merged pipeline tables
# (unknown names sort last by name).
_PIPELINE_TABLE_ORDER: tuple[str, ...] = (
    "CodeTable",
    "ParameterTable",
    "FormTable",
    "CognateTable",
    "EntryTable",
    "SenseTable",
)


def _pipeline_tables(module: str, add_components: Sequence[str]) -> list[str]:
    names = frozenset(add_components) | _MODULE_SHIPPED_TABLES[module]
    order = {t: i for i, t in enumerate(_PIPELINE_TABLE_ORDER)}

    def sort_key(t: str) -> tuple[int, str]:
        return (order[t], t) if t in order else (len(_PIPELINE_TABLE_ORDER), t)

    return sorted(names, key=sort_key)


def read_cldfbench_makecldf_toml(etc_dir: Path) -> dict[str, Any]:
    with open(Path(etc_dir) / CLDFBENCH_MAKECLDF_BASENAME, "rb") as f:
        return tomllib.load(f)


def _aggregate_extra_columns(
    doc: dict[str, Any], table_name: str
) -> list[Any] | None:
    if table_name not in doc:
        return None
    block = doc[table_name]
    if not isinstance(block, dict):
        return None
    cols = block.get("column")
    return cols if isinstance(cols, list) else None


class LoanwordbankDataset(CldfbenchDataset):
    """Loanwordbank defaults: README badges, bib, CLTS, makecldf TOML.

    Includes ``*.prf`` tokenizer wiring and shared profiles.
    """

    #: Must match :meth:`cldf_specs` ``module=`` (which tables ship in default
    #: metadata).
    cldf_module: ClassVar[str] = "Wordlist"
    #: From ``[makecldf] tables`` in TOML: ``add_component`` targets only
    #: (not already in module defaults).
    makecldf_add_components: ClassVar[Sequence[str]] = ()
    #: Union of module defaults and ``makecldf_add_components``; row lists and
    #: write order.
    makecldf_tables: ClassVar[Sequence[str]] = ()
    makecldf_remove_columns: ClassVar[Sequence[tuple[str, str]]] = ()
    extra_columns_tables: ClassVar[Sequence[str] | None] = None
    extra_columns_skip_missing: ClassVar[bool] = True
    raw_data_csv: ClassVar[str | None] = None
    raw_data_read_csv_kwargs: ClassVar[dict[str, Any]] = {}
    segment_tokenizer_column: ClassVar[str] = "mapping"
    _cldfbench_makecldf_cfg: ClassVar[dict[str, Any] | None] = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._cldfbench_makecldf_cfg = None
        dir_ = getattr(cls, "dir", None)
        if dir_ is None:
            return
        etc = Path(dir_) / "etc"
        if not (etc / CLDFBENCH_MAKECLDF_BASENAME).is_file():
            return
        cfg = read_cldfbench_makecldf_toml(etc)
        cls._cldfbench_makecldf_cfg = cfg
        mc = cfg["makecldf"]
        add = list(mc.get("tables", []))
        cls.makecldf_add_components = add
        cls.makecldf_tables = _pipeline_tables(
            getattr(cls, "cldf_module", "Wordlist"), add
        )
        if raw_csv := mc.get("raw_data_csv"):
            cls.raw_data_csv = raw_csv
        if remove_cols := mc.get("remove_columns"):
            cls.makecldf_remove_columns = [tuple(pair) for pair in remove_cols]
        if (delim := mc.get("raw_data_delimiter")) is not None:
            cls.raw_data_read_csv_kwargs = {"delimiter": delim}
        extra = cfg.get("extra_columns")
        if extra and "tables_with_extra_columns" in extra:
            cls.extra_columns_tables = list(extra["tables_with_extra_columns"])

    @property
    def cldfbench_makecldf_cfg(self) -> dict[str, Any] | None:
        return getattr(type(self), "_cldfbench_makecldf_cfg", None)

    @cached_property
    def cldfbench_compiled_regex(self) -> dict[str, re.Pattern]:
        cfg = self.cldfbench_makecldf_cfg or {}
        sec = cfg.get("regex") or {}
        return {k: re.compile(v) for k, v in sec.items()}

    @cached_property
    def cldfbench_text_replacement_pairs(self) -> list[tuple[str, str]]:
        rows = (self.cldfbench_makecldf_cfg or {}).get(
            "text_replacement_pairs"
        ) or []
        return [(p["old"], p["new"]) for p in rows]

    @cached_property
    def clts(self) -> PyCLTS:
        return PyCLTS()

    @cached_property
    def cv(self):
        return self.clts.soundclass("cv")

    @cached_property
    def sca(self):
        return self.clts.soundclass("sca")

    def get_cv_profile(self, segment_string: str) -> list[str]:
        return self.clts.bipa.translate(segment_string, self.cv).split(" ")

    def get_sca_profile(self, segment_string: str) -> list[str]:
        return self.clts.bipa.translate(segment_string, self.sca).split(" ")

    def write_cldf_table(self, args, log_path: str, **writer_kwargs) -> None:
        args.writer.write(**writer_kwargs)
        args.log.info(f"wrote {log_path}")

    @cached_property
    def tokenizers(self) -> dict[str, Tokenizer]:
        return {
            f.name: Tokenizer(profile=Profile.from_file(f))
            for f in sorted(self.etc_dir.glob("*.prf"))
        }

    def profile_for_language_id(self, language_id: str) -> str:
        return next(
            r["Profile"] for r in self.languages if r["ID"] == language_id
        )

    def get_segments(self, text: str, language_id: str) -> str:
        p = self.profile_for_language_id(language_id)
        return self.tokenizers[p](
            text, column=type(self).segment_tokenizer_column
        )

    @staticmethod
    def _form_or_headword_string(row: dict, kind: Literal["form", "entry"]) -> str | None:
        if kind == "form":
            for key in ("Forms", "Form"):
                v = row.get(key)
                if v is not None and str(v).strip():
                    return str(v).strip()
            return None
        v = row.get("Headword")
        if v is not None and str(v).strip():
            return str(v).strip()
        return None

    def _phoneme_tokens_for_inventory(self, text: str, language_id: str) -> list[str]:
        s = (text or "").strip()
        if not s:
            return []
        if " " in s:
            return [t for t in (x.strip() for x in s.split()) if t]
        try:
            out = str(self.get_segments(s, language_id) or "").strip()
            if out:
                return [t for t in (x.strip() for x in out.split()) if t]
        except (StopIteration, KeyError, TypeError, ValueError):
            pass
        return [s]

    def _phonemes_by_language_id(self) -> dict[str, set[str]]:
        collected: dict[str, set[str]] = {r["ID"]: set() for r in self.languages}
        for table_cname, kind in (("FormTable", "form"), ("EntryTable", "entry")):
            rows: list[dict] | None = self.makecldf_rows.get(table_cname)
            if not rows and table_cname in CLDF_TABLE_INSTANCE_ATTR:
                rows = getattr(
                    self, CLDF_TABLE_INSTANCE_ATTR[table_cname], None
                ) or []
            if not rows:
                continue
            for row in rows:
                lang_id = row.get("Language_ID")
                if not lang_id or lang_id not in collected:
                    continue
                text = self._form_or_headword_string(row, kind)
                if not text:
                    continue
                for tok in self._phoneme_tokens_for_inventory(
                    text, str(lang_id)
                ):
                    if tok:
                        collected[str(lang_id)].add(tok.strip())
        return collected

    # Centrality for Vowel: front / back (including near- variants) for sub-inventories.
    _BIPA_FRONT_CENTRALITY: frozenset[str] = frozenset(
        ("front", "near-front")
    )
    _BIPA_BACK_CENTRALITY: frozenset[str] = frozenset(
        ("back", "near-back")
    )

    @staticmethod
    def _cv_profile_cell(row: dict) -> str | None:
        for key in ("CV_profile", "CV_Profile"):
            v = row.get(key)
            if v is not None and str(v).strip():
                return str(v).strip()
        return None

    def _majority_cv_label_per_segment(
        self,
    ) -> dict[str, dict[str, str]]:
        """Map (Language_ID, segment) -> most frequent CV label (e.g. V, C) from Segments+CV columns."""
        counts: dict[str, dict[str, Counter[str]]] = defaultdict(
            lambda: defaultdict(Counter)
        )
        for table_cname in ("FormTable", "EntryTable"):
            rows: list[dict] | None = self.makecldf_rows.get(table_cname)
            if not rows and table_cname in CLDF_TABLE_INSTANCE_ATTR:
                rows = getattr(
                    self, CLDF_TABLE_INSTANCE_ATTR[table_cname], None
                ) or []
            for row in rows or []:
                lang_id = row.get("Language_ID")
                if not lang_id:
                    continue
                segm = str(row.get("Segments") or "").strip()
                cv_s = self._cv_profile_cell(row)
                if not segm or not cv_s:
                    continue
                s_toks = [x.strip() for x in segm.split() if x.strip()]
                c_toks = [x.strip() for x in cv_s.split() if x.strip()]
                n = min(len(s_toks), len(c_toks))
                for i in range(n):
                    counts[str(lang_id)][s_toks[i]][c_toks[i]] += 1
        out: dict[str, dict[str, str]] = {}
        for lang_id, segmap in counts.items():
            out[lang_id] = {
                seg: c.most_common(1)[0][0] for seg, c in segmap.items() if c
            }
        return out

    def _classify_token_for_languagetable_sublists(
        self,
        token: str,
        lang_id: str,
        cv_maj: dict[str, dict[str, str]],
    ) -> tuple[bool, bool, bool, bool]:
        """Return (vowels, consonants, front_vowels, back_vowels) for one inventory token."""
        t = nfd((token or "").strip())
        if not t:
            return (False, False, False, False)
        s = self.clts.bipa.resolve_sound(t)
        if isinstance(s, Vowel):
            c = (getattr(s, "featuredict", None) or {}).get("centrality")
            f = c in self._BIPA_FRONT_CENTRALITY if c else False
            b_ = c in self._BIPA_BACK_CENTRALITY if c else False
            return (True, False, f, b_)
        if isinstance(s, Consonant):
            return (False, True, False, False)
        if isinstance(s, Diphthong):
            return (True, False, False, False)
        if s.type in ("unknownsound", "unknown") or isinstance(
            s, UnknownSound
        ):
            return self._classify_unknown_inventory_token(
                t, str(lang_id), cv_maj
            )
        return (False, False, False, False)

    def _classify_unknown_inventory_token(
        self, token: str, lang_id: str, cv_maj: dict[str, dict[str, str]]
    ) -> tuple[bool, bool, bool, bool]:
        lab = cv_maj.get(lang_id, {}).get(token, "")
        if lab in ("V", "v"):
            return (True, False, False, False)
        if lab in ("C", "c"):
            return (False, True, False, False)
        try:
            pr = [x for x in self.get_cv_profile(token) if str(x).strip()]
        except (TypeError, ValueError, KeyError, AttributeError):
            pr = []
        if not pr:
            return (False, False, False, False)
        first = str(pr[0])
        if first in ("V", "v", "0"):
            return (True, False, False, False)
        if first in ("C", "c", "1"):
            return (False, True, False, False)
        return (False, False, False, False)

    def _ensure_languagetable_inventories_columns(self, writer) -> None:
        table = writer.cldf["LanguageTable"]
        present = {c.name for c in table.tableSchema.columns}
        to_add: list[dict] = []
        if "Phonemes" not in present:
            to_add.append(
                {
                    "name": "Phonemes",
                    "datatype": "string",
                    "dc:description": (
                        "Inventory of attested segment tokens (phonemes) in this language, as a "
                        "list of space-separated BIPA/segment strings. The inventory is built "
                        "by scanning the `Form` / `Forms` column in FormTable and the `Headword` "
                        "column in EntryTable; for each value, if it is not already "
                        "space-segmented, the language's `etc/*.prf` profile is applied to split it "
                        "(see `get_segments`)."
                    ),
                    "dc:extent": "multivalued",
                    "separator": " ",
                }
            )
        for name, desc in (
            (
                "Vowels",
                "Subset of `Phonemes` for this language: segments classified as vowel-like "
                "by the CLTS BIPA transcription system, or (for unknown strings) the label "
                "`V` in aligned `Segments`+`CV_profile`/`CV_Profile` data or the `cv` sound "
                "class via `get_cv_profile`. Diphthongs are listed as whole segments.",
            ),
            (
                "Consonants",
                "Subset of `Phonemes` classified as consonant-like by BIPA, or by `C` in "
                "CV-aligned data / `get_cv_profile`.",
            ),
            (
                "Front_Vowels",
                "Vowels among `Vowels` with BIPA centrality `front` or `near-front` (excludes "
                "diphthongs, which are only in `Vowels`).",
            ),
            (
                "Back_Vowels",
                "Vowels among `Vowels` with BIPA centrality `back` or `near-back` (excludes "
                "diphthongs).",
            ),
        ):
            if name not in present:
                to_add.append(
                    {
                        "name": name,
                        "datatype": "string",
                        "dc:description": desc,
                        "dc:extent": "multivalued",
                        "separator": " ",
                    }
                )
        for spec in to_add:
            writer.cldf.add_columns("LanguageTable", spec)

    def _populate_languagetable_inventory_columns(self) -> None:
        inv = self._phonemes_by_language_id()
        for row in self.languages:
            # `separator` in metadata means csvw's Column.write joins a list, not a string
            # (a string would be iterated character-by-character).
            row["Phonemes"] = sorted(inv.get(str(row["ID"]), set()))
        cv_maj = self._majority_cv_label_per_segment()
        for row in self.languages:
            lid = str(row["ID"])
            toks = row.get("Phonemes", [])
            if not isinstance(toks, list):
                toks = [t for t in str(toks).split() if t] if toks else []
            vow: set[str] = set()
            con: set[str] = set()
            fr: set[str] = set()
            back: set[str] = set()
            for t in toks:
                v, c, f, b_ = self._classify_token_for_languagetable_sublists(
                    t, lid, cv_maj
                )
                if v:
                    vow.add(t)
                if c:
                    con.add(t)
                if f:
                    fr.add(t)
                if b_:
                    back.add(t)
            row["Vowels"] = sorted(vow)
            row["Consonants"] = sorted(con)
            row["Front_Vowels"] = sorted(fr)
            row["Back_Vowels"] = sorted(back)

    def readme_lead(self, args=None) -> str:
        n = self.dir.name
        v = f"https://github.com/loanwordbank/{n}/actions/workflows/cldf-validation.yaml"
        b = f"https://github.com/loanwordbank/{n}/actions/workflows/build.yaml"
        val = f"[![CLDF-validation]({v}/badge.svg)]({v})"
        build = f"[![Build]({b}/badge.svg)]({b})"
        return f"{val} {build}\n\n"

    def cmd_readme(self, args):
        return self.readme_lead(args) + super().cmd_readme(args)

    def readme_text_after_makecldf(self, args) -> str:
        return self.cmd_readme(args)

    def write_readme_after_makecldf(self, args) -> None:
        self.dir.write("README.md", self.readme_text_after_makecldf(args))
        args.log.info("wrote README.md")

    def makecldf_table_log_path(self, args, table_name: str) -> str:
        return f"cldf/{CLDF_TABLE_CSV_BASENAME[table_name]}"

    def makecldf_instance_attr_name(self, table_name: str) -> str:
        return CLDF_TABLE_INSTANCE_ATTR[table_name]

    def makecldf_rows_for_table(self, table_name: str) -> list:
        if table_name in self.makecldf_rows:
            return self.makecldf_rows[table_name]
        return getattr(self, self.makecldf_instance_attr_name(table_name))

    def flush_makecldf_tables(
        self, args, *specs: str | tuple[str, list[Any]]
    ) -> None:
        for spec in specs:
            name, rows = (
                spec
                if isinstance(spec, tuple)
                else (spec, self.makecldf_rows_for_table(spec))
            )
            self.write_cldf_table(
                args, self.makecldf_table_log_path(args, name), **{name: rows}
            )

    def load_langs(self) -> None:
        self.languages = self.etc_dir.read_csv(
            CLDF_TABLE_CSV_BASENAME["LanguageTable"],
            dicts=True,
        )

    def cmd_makecldf(self, args):
        args.writer.cldf.sources.add(*self.raw_dir.read_bib())
        args.log.info(self.log_sources_bib_written())
        args.writer.cldf.add_provenance(
            wasDerivedFrom=[
                CLTSCatalog(Config.from_file().get_clone("clts")).json_ld()
            ]
        )
        self.makecldf_rows = {}
        args.writer.cldf.add_component("LanguageTable")
        for comp in type(self).makecldf_add_components:
            args.writer.cldf.add_component(comp)
        self.load_langs()
        self.remove_makecldf_columns(args.writer)
        self.apply_extra_columns_for_makecldf(args.writer)
        self._ensure_languagetable_inventories_columns(args.writer)
        self._init_raw_data()
        self._init_makecldf_instance_table_lists()
        self._cmd_makecldf_body(args)
        self._fill_makecldf_rows_from_instance_attrs()
        self._populate_languagetable_inventory_columns()

        def emit(table: str, rows: list):
            self.write_cldf_table(
                args,
                self.makecldf_table_log_path(args, table),
                **{table: rows},
            )

        emit("LanguageTable", self.makecldf_rows_for_table("LanguageTable"))
        for name in self.makecldf_tables:
            emit(name, self.makecldf_rows_for_table(name))
        self.write_readme_after_makecldf(args)

    def _init_raw_data(self) -> None:
        self.data = None
        name = type(self).raw_data_csv
        if not name:
            return
        try:
            self.data = self.raw_dir.read_csv(
                name, dicts=True, **dict(type(self).raw_data_read_csv_kwargs)
            )
        except Exception:
            self.data = None

    def _init_makecldf_instance_table_lists(self) -> None:
        for name in self.makecldf_tables:
            attr = self.makecldf_instance_attr_name(name)
            if name == "CodeTable":
                setattr(
                    self,
                    attr,
                    self.etc_dir.read_csv(
                        CLDF_TABLE_CSV_BASENAME["CodeTable"], dicts=True
                    ),
                )
            else:
                setattr(self, attr, [])

    def _fill_makecldf_rows_from_instance_attrs(self) -> None:
        for name in self.makecldf_tables:
            attr = self.makecldf_instance_attr_name(name)
            self.makecldf_rows[name] = getattr(self, attr)

    def _cmd_makecldf_body(self, args) -> None:
        raise NotImplementedError

    def log_sources_bib_written(self) -> str:
        return "wrote cldf/sources.bib"

    def remove_makecldf_columns(self, writer) -> None:
        for table, column in type(self).makecldf_remove_columns:
            writer.cldf.remove_columns(table, column)

    def apply_extra_columns_for_makecldf(self, writer) -> None:
        cls = type(self)
        self.apply_extra_columns(
            writer,
            cls.extra_columns_tables,
            skip_missing=cls.extra_columns_skip_missing,
        )

    def apply_extra_columns(
        self,
        writer,
        table_names: Sequence[str] | None = None,
        *,
        skip_missing: bool = True,
    ) -> None:
        names = (
            list(writer.cldf.components)
            if table_names is None
            else list(table_names)
        )
        agg_path = self.etc_dir / EXTRA_COLS_AGGREGATE_BASENAME
        aggregate = None
        if agg_path.is_file():
            with open(agg_path, "rb") as f:
                aggregate = tomllib.load(f)
        per_dir = self.etc_dir / "ExtraCols"
        for table_name in names:
            extra = (
                _aggregate_extra_columns(aggregate, table_name)
                if aggregate
                else None
            )
            if extra is None:
                path = per_dir / f"{table_name}.toml"
                if skip_missing and not path.is_file():
                    continue
                with open(path, "rb") as f:
                    extra = tomllib.load(f)["column"]
            if extra:
                writer.cldf.add_columns(table_name, *extra)
