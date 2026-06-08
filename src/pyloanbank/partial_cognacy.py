"""Derive CognateTable Segment_Slice from alignment strings with surplus markers."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence

GAP_TOKENS = frozenset({"#-", "-", "-#"})

SEGMENT_SLICE_DC_DESCRIPTION = (
    "1-based phoneme range in [forms.csv::Segments](#table-formscsv) for the "
    "inherited portion of the form. When a cognate alignment column contains a "
    "surplus marker ``+``, only phonemes before ``+`` are etymologically "
    "relevant; auto-filled as ``1`` or ``1:N`` during conversion."
)


def _as_token_list(value: str | Sequence[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(t) for t in value]
    return str(value).split()


def _alignment_tokens(alignment: str | Sequence[str]) -> list[str]:
    return _as_token_list(alignment)


def _expand_cluster(token: str) -> list[str]:
    return token.replace(".", " ").split()


def stem_phoneme_count_from_segment_alignment(
    segments: str | Sequence[str],
    alignment: str | Sequence[str],
    *,
    gap_tokens: frozenset[str] = GAP_TOKENS,
) -> int | None:
    """Count phonemes before ``+`` when alignment tokens match a Segments prefix."""
    align_toks = _alignment_tokens(alignment)
    if "+" not in align_toks:
        return None
    plus_i = align_toks.index("+")
    stem = [t for t in align_toks[:plus_i] if t not in gap_tokens]
    seg = _as_token_list(segments)
    if not stem or len(stem) > len(seg):
        return None
    if seg[: len(stem)] != stem:
        return None
    return len(stem)


def stem_phoneme_count_from_cluster_alignment(
    segments: str | Sequence[str],
    clusters: str | Sequence[str],
    alignment: str | Sequence[str],
    *,
    gap_tokens: frozenset[str] = GAP_TOKENS,
) -> int | None:
    """Map cluster-level alignment (with ``+``) to a phoneme prefix length in Segments."""
    align_toks = _alignment_tokens(alignment)
    if "+" not in align_toks:
        return None
    plus_i = align_toks.index("+")
    left_clusters = [t for t in align_toks[:plus_i] if t not in gap_tokens]
    cluster_toks = _as_token_list(clusters)
    stem_ph: list[str] = []
    for cluster in cluster_toks[: len(left_clusters)]:
        stem_ph.extend(_expand_cluster(cluster))
    suffix_ph: list[str] = []
    for cluster in cluster_toks[len(left_clusters) :]:
        suffix_ph.extend(_expand_cluster(cluster))
    seg = _as_token_list(segments)
    if stem_ph + suffix_ph != seg:
        return None
    if not stem_ph:
        return None
    return len(stem_ph)


def stem_phoneme_count_for_alignment(
    form: Mapping[str, str | Sequence[str]],
    alignment: str | Sequence[str],
    *,
    segments_col: str = "Segments",
    clusters_col: str = "Clusters",
    gap_tokens: frozenset[str] = GAP_TOKENS,
) -> int | None:
    """Prefer segment-level alignment; fall back to cluster-level via Clusters."""
    segments = form.get(segments_col)
    if not segments:
        return None
    count = stem_phoneme_count_from_segment_alignment(
        segments, alignment, gap_tokens=gap_tokens
    )
    if count is not None:
        return count
    clusters = form.get(clusters_col)
    if not clusters:
        return None
    return stem_phoneme_count_from_cluster_alignment(
        segments, clusters, alignment, gap_tokens=gap_tokens
    )


def format_segment_slice(stem_phoneme_count: int) -> str:
    if stem_phoneme_count <= 1:
        return "1"
    return f"1:{stem_phoneme_count}"


def apply_segment_slices_from_alignments(
    cognates: list[MutableMapping[str, str | Sequence[str]]],
    *,
    forms_by_id: Mapping[str, Mapping[str, str | Sequence[str]]],
    alignment_columns: Sequence[str],
    segments_col: str = "Segments",
    clusters_col: str = "Clusters",
    slice_col: str = "Segment_Slice",
    gap_tokens: frozenset[str] = GAP_TOKENS,
) -> int:
    """Fill empty ``Segment_Slice`` on cognate rows that have ``+`` in an alignment column.

    Indices are 1-based phoneme positions in the linked form's ``Segments`` column
    (stem before the surplus marker), not morpheme indices with ``+`` in Segments.
    """
    updated = 0
    for row in cognates:
        if slice_col not in row:
            continue
        if str(row.get(slice_col, "")).strip():
            continue
        form_id = row.get("Form_ID")
        if not form_id or form_id not in forms_by_id:
            continue
        form = forms_by_id[form_id]
        for col in alignment_columns:
            alignment = row.get(col)
            if not alignment or "+" not in _alignment_tokens(alignment):
                continue
            count = stem_phoneme_count_for_alignment(
                form,
                alignment,
                segments_col=segments_col,
                clusters_col=clusters_col,
                gap_tokens=gap_tokens,
            )
            if count is None:
                continue
            row[slice_col] = format_segment_slice(count)
            updated += 1
            break
    return updated
