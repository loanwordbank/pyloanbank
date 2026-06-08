from pyloanbank.partial_cognacy import (
    apply_segment_slices_from_alignments,
    format_segment_slice,
    stem_phoneme_count_for_alignment,
)


def test_format_segment_slice():
    assert format_segment_slice(1) == "1"
    assert format_segment_slice(3) == "1:3"


def test_stem_count_from_segment_alignment():
    form = {"Segments": "k a t", "Clusters": "k a t"}
    assert stem_phoneme_count_for_alignment(form, "k a + t") == 2
    assert stem_phoneme_count_for_alignment(form, "k a t") is None
    assert stem_phoneme_count_for_alignment(form, "k + a t") == 1


def test_stem_count_from_cluster_alignment():
    form = {"Segments": "k a t", "Clusters": "k a.t"}
    assert stem_phoneme_count_for_alignment(form, "k + a.t") == 1
    form2 = {"Segments": "k a t", "Clusters": "k.a t"}
    assert stem_phoneme_count_for_alignment(form2, "k.a + t") == 2


def test_apply_segment_slices_accepts_list_alignment():
    cognates = [
        {"ID": "1", "Form_ID": "f1", "Segment_Slice": "", "Uralign": ["a", "+", "b"]},
    ]
    forms = {"f1": {"Segments": ["a", "b"], "Clusters": ["a", "b"]}}
    updated = apply_segment_slices_from_alignments(
        cognates,
        forms_by_id=forms,
        alignment_columns=("Uralign",),
    )
    assert updated == 1
    assert cognates[0]["Segment_Slice"] == "1"


def test_apply_segment_slices_skips_filled_and_no_plus():
    cognates = [
        {"ID": "1", "Form_ID": "f1", "Segment_Slice": "1:2", "Uralign": "a + b"},
        {"ID": "2", "Form_ID": "f2", "Segment_Slice": "", "Uralign": "a b"},
        {"ID": "3", "Form_ID": "f3", "Segment_Slice": "", "Uralign": "a + b"},
    ]
    forms = {
        "f3": {"Segments": "a b", "Clusters": "a b"},
    }
    updated = apply_segment_slices_from_alignments(
        cognates,
        forms_by_id=forms,
        alignment_columns=("Uralign",),
    )
    assert updated == 1
    assert cognates[0]["Segment_Slice"] == "1:2"
    assert cognates[1]["Segment_Slice"] == ""
    assert cognates[2]["Segment_Slice"] == "1"
