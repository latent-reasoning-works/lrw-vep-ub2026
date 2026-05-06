"""Unit tests for vep_utils."""
import numpy as np
import pytest
import torch
from vep_utils import (
    AA_ALPHABET,
    MutationSpec,
    apply_mutation,
    parse_mutation,
    validate_sequence,
    validate_mutation,
    ESM1bEncoder,
    encode_variant,
    compute_delta_norm,
    compute_cosine_distance,
    compute_llr,
    compute_lid,
    score_variant_report,
)


def test_aa_alphabet_is_canonical():
    assert AA_ALPHABET == "ACDEFGHIKLMNPQRSTVWY"
    assert len(AA_ALPHABET) == 20


def test_validate_sequence_accepts_valid():
    validate_sequence("MVSKGEELFT")  # does not raise


def test_validate_sequence_rejects_invalid_char():
    with pytest.raises(ValueError, match="Invalid amino acid 'X' at position 3"):
        validate_sequence("MVXKGEELFT")


def test_validate_sequence_rejects_empty():
    with pytest.raises(ValueError, match="Sequence is empty"):
        validate_sequence("")


def test_validate_sequence_warns_on_long_sequence(capsys):
    long_seq = "M" * 1500
    validate_sequence(long_seq, max_length=1024)
    captured = capsys.readouterr()
    assert "truncat" in captured.out.lower() or "too long" in captured.out.lower()


def test_parse_mutation_standard_format():
    m = parse_mutation("A23T")
    assert m.wt_aa == "A"
    assert m.position == 23
    assert m.mut_aa == "T"


def test_parse_mutation_rejects_malformed():
    with pytest.raises(ValueError, match="Could not parse mutation"):
        parse_mutation("A-T")
    with pytest.raises(ValueError, match="Could not parse mutation"):
        parse_mutation("23A")


def test_parse_mutation_rejects_invalid_aa():
    with pytest.raises(ValueError, match="Invalid amino acid"):
        parse_mutation("X23T")
    with pytest.raises(ValueError, match="Invalid amino acid"):
        parse_mutation("A23Z")


def test_validate_mutation_correct_wt():
    sequence = "MVSKGEELFT"  # position 3 (1-indexed) is S
    m = parse_mutation("S3A")
    validate_mutation(sequence, m)  # does not raise


def test_validate_mutation_wrong_wt_suggests_correction():
    sequence = "MVSKGEELFT"  # position 3 is S, not A
    m = parse_mutation("A3T")
    with pytest.raises(ValueError) as exc:
        validate_mutation(sequence, m)
    assert "is Serine (S)" in str(exc.value) or "S3T" in str(exc.value)


def test_validate_mutation_position_out_of_range():
    sequence = "MVSKGEELFT"  # length 10
    m = parse_mutation("A50T")
    with pytest.raises(ValueError, match="out of range"):
        validate_mutation(sequence, m)


def test_validate_mutation_identical_aa():
    sequence = "MVSKGEELFT"
    m = parse_mutation("S3S")
    with pytest.raises(ValueError, match="identical"):
        validate_mutation(sequence, m)


def test_apply_mutation_middle_position():
    m = parse_mutation("S3A")
    assert apply_mutation("MVSKGEELFT", m) == "MVAKGEELFT"


def test_apply_mutation_first_position():
    m = parse_mutation("M1A")
    assert apply_mutation("MVSKGEELFT", m) == "AVSKGEELFT"


def test_apply_mutation_last_position():
    m = parse_mutation("T10A")
    assert apply_mutation("MVSKGEELFT", m) == "MVSKGEELFA"


def test_validate_sequence_rejects_fasta_header():
    with pytest.raises(ValueError, match="FASTA"):
        validate_sequence(">sp|P42212|GFP_AEQVI\nMVSKGEELFT")


def test_validate_sequence_strips_internal_whitespace():
    # newlines/spaces in middle should be silently removed
    result = validate_sequence("MVSK\nGEELFT")
    assert result == "MVSKGEELFT"
    result2 = validate_sequence("MVSK GEELFT")
    assert result2 == "MVSKGEELFT"


@pytest.fixture(scope="module")
def encoder():
    """Load ESM-1b once per test module. Slow first time, cached after."""
    return ESM1bEncoder(device="cpu")  # CPU for CI; real notebook uses GPU


def test_encoder_produces_correct_shape(encoder):
    seq = "MVSKGEELFT"
    emb, logits = encoder.encode(seq)
    assert emb.shape == (1280,), f"Expected (1280,), got {emb.shape}"
    assert logits.shape[0] == len(seq) + 2  # +2 for BOS/EOS tokens
    assert logits.shape[1] == 33  # ESM-1b vocab size


def test_encoder_deterministic(encoder):
    seq = "MVSKGEELFT"
    emb1, _ = encoder.encode(seq)
    emb2, _ = encoder.encode(seq)
    assert np.allclose(emb1, emb2, atol=1e-5)


def test_encoder_handles_different_lengths(encoder):
    emb_short, _ = encoder.encode("MVSK")
    emb_long, _ = encoder.encode("MVSKGEELFTGVVPILVELDGDVNGHK")
    assert emb_short.shape == (1280,)
    assert emb_long.shape == (1280,)


def test_encode_variant_returns_wt_and_mut(encoder):
    sequence = "MVSKGEELFT"
    result = encode_variant(encoder, sequence, "S3A")
    assert "wt_embedding" in result
    assert "mut_embedding" in result
    assert result["wt_embedding"].shape == (1280,)
    assert result["mut_embedding"].shape == (1280,)
    # Different residue should give different embedding
    assert not np.allclose(result["wt_embedding"], result["mut_embedding"])


def test_delta_norm_identical_embeddings_is_zero():
    emb = np.random.randn(1280)
    assert compute_delta_norm(emb, emb) == pytest.approx(0.0)


def test_delta_norm_is_positive():
    a = np.random.randn(1280)
    b = np.random.randn(1280)
    assert compute_delta_norm(a, b) > 0


def test_cosine_distance_identical_is_zero():
    emb = np.random.randn(1280)
    assert compute_cosine_distance(emb, emb) == pytest.approx(0.0, abs=1e-6)


def test_cosine_distance_orthogonal_is_one():
    a = np.array([1.0, 0.0, 0.0])
    b = np.array([0.0, 1.0, 0.0])
    assert compute_cosine_distance(a, b) == pytest.approx(1.0)


def test_compute_llr_increases_with_unlikely_mutation():
    # Tests the LLR contract: when the MUT model is LESS confident in the
    # MUT residue (relative to the WT model's confidence in WT), LLR grows.
    vocab_size = 33
    seq_len = 10
    mutation = MutationSpec(wt_aa="A", position=3, mut_aa="F")
    wt_token_id = 5
    mut_token_id = 7

    # Case 1: Both models highly confident at their respective residue.
    # log P_wt(wt) ~ log P_mut(mut) -> LLR close to 0.
    wt_logits_a = np.full((seq_len + 2, vocab_size), -10.0)
    mut_logits_a = np.full((seq_len + 2, vocab_size), -10.0)
    wt_logits_a[3, wt_token_id] = 10.0   # WT model very confident in WT
    mut_logits_a[3, mut_token_id] = 10.0  # MUT model very confident in MUT
    llr_small = compute_llr(
        wt_logits_a, mut_logits_a, mutation,
        wt_token_id=wt_token_id, mut_token_id=mut_token_id,
    )

    # Case 2: WT model confident in WT, but MUT model UNCONFIDENT in MUT.
    # log P_mut(mut) is much lower -> LLR = log P_wt(wt) - log P_mut(mut) larger.
    wt_logits_b = np.full((seq_len + 2, vocab_size), -10.0)
    mut_logits_b = np.full((seq_len + 2, vocab_size), 0.0)  # flat -> low log-prob
    wt_logits_b[3, wt_token_id] = 10.0   # WT model very confident in WT
    # Leave mut_logits_b[3, mut_token_id] == 0.0 (uniform/unconfident)
    llr_large = compute_llr(
        wt_logits_b, mut_logits_b, mutation,
        wt_token_id=wt_token_id, mut_token_id=mut_token_id,
    )

    assert np.isfinite(llr_small) and np.isfinite(llr_large)
    assert llr_large > llr_small, (
        f"Expected LLR to grow when MUT model is unconfident in MUT residue; "
        f"got llr_small={llr_small}, llr_large={llr_large}"
    )


def test_compute_llr_uses_correct_bos_offset():
    # Sanity: mutation.position = 1 must read token index 1 (the first
    # residue AFTER BOS), NOT token index 0 (which is BOS). Make the BOS
    # slot garbage and position-1 slot controlled; if the function read
    # the wrong index, the result would differ wildly.
    vocab_size = 33
    seq_len = 5
    mutation = MutationSpec(wt_aa="A", position=1, mut_aa="F")
    wt_token_id = 5
    mut_token_id = 7

    wt_logits = np.zeros((seq_len + 2, vocab_size))
    mut_logits = np.zeros((seq_len + 2, vocab_size))

    # Index 0 (BOS slot): wildly different values. If the function reads
    # here, LLR would be dominated by these.
    wt_logits[0, :] = -1000.0
    wt_logits[0, wt_token_id] = 1000.0
    mut_logits[0, :] = 1000.0
    mut_logits[0, mut_token_id] = -1000.0

    # Index 1 (the real position-1 residue): controlled flat logits.
    # log_softmax of a uniform row is -log(vocab_size) for every entry,
    # so llr = -log(V) - (-log(V)) = 0 exactly.
    wt_logits[1, :] = 0.0
    mut_logits[1, :] = 0.0

    llr = compute_llr(
        wt_logits, mut_logits, mutation,
        wt_token_id=wt_token_id, mut_token_id=mut_token_id,
    )
    # If BOS (index 0) were read, LLR would be ~2000. Reading index 1
    # gives exactly 0. Use a tight tolerance to distinguish the two.
    assert np.isfinite(llr)
    assert abs(llr) < 1e-6, (
        f"Expected LLR ~ 0 when reading controlled index 1; got {llr}. "
        f"This suggests the function read the wrong token index (likely BOS)."
    )


def test_cosine_distance_zero_vector_is_nan():
    # Cosine distance is undefined when either input has zero norm
    # (the zero vector has no direction). Expect NaN, not 0.0.
    zero = np.zeros(1280)
    nonzero = np.random.randn(1280)
    assert np.isnan(compute_cosine_distance(zero, nonzero))
    assert np.isnan(compute_cosine_distance(nonzero, zero))
    assert np.isnan(compute_cosine_distance(zero, zero))


def test_compute_lid_returns_positive():
    # Well-separated clusters -> low LID for cluster interior points
    np.random.seed(42)
    reference = np.random.randn(500, 1280)
    query = np.random.randn(1280)
    lid = compute_lid(query, reference, k=20)
    assert lid > 0
    assert np.isfinite(lid)


def test_compute_lid_reduces_k_if_needed():
    # Only 5 reference points, k=20 requested -> should auto-reduce
    reference = np.random.randn(5, 1280)
    query = np.random.randn(1280)
    lid = compute_lid(query, reference, k=20)
    assert np.isfinite(lid)


def test_score_variant_report_structure():
    reference_distributions = {
        "delta_norm_protein": {
            "mean": 1.0, "std": 0.5,
            "p5": 0.3, "p50": 1.0, "p95": 2.0,
            "pathogenic_median": 1.3, "benign_median": 0.8,
        },
        "lid_protein": {
            "mean": 12.0, "std": 3.0,
            "p5": 7.0, "p50": 12.0, "p95": 18.0,
            "pathogenic_median": 10.0, "benign_median": 14.0,
        },
    }
    metrics = {
        "delta_norm": 2.5,  # above p95=2.0 -> clamped to 95th percentile -> pathogenic-like
        "lid": 9.5,
        "llr": 2.1,
        "cosine_dist": 0.15,
    }
    report = score_variant_report(
        mutation=MutationSpec("A", 23, "T"),
        metrics=metrics,
        reference_distributions=reference_distributions,
    )
    assert "A23T" in report
    assert "delta_norm" in report.lower() or "delta norm" in report.lower()
    assert "percentile" in report.lower() or "%ile" in report.lower()
    # delta_norm has higher_is_pathogenic=True; value 2.5 > p95=2.0 -> pathogenic-like
    assert "Directional verdict: pathogenic-like" in report


def test_score_variant_report_handles_missing_reference_entry():
    """Metric present but no reference distribution: graceful fallback."""
    metrics = {"delta_norm": 1.5}
    report = score_variant_report(
        mutation=MutationSpec("S", 10, "A"),
        metrics=metrics,
        reference_distributions={},  # no entry for delta_norm_protein
    )
    assert "(no reference distribution available)" in report


def test_score_variant_report_handles_missing_class_medians():
    """Reference entry has quantiles but no class medians: no crash, no 'closer to' line."""
    reference_distributions = {
        "delta_norm_protein": {
            "mean": 1.0, "std": 0.5,
            "p5": 0.3, "p50": 1.0, "p95": 2.0,
            # No pathogenic_median / benign_median
        },
    }
    metrics = {"delta_norm": 1.2}
    report = score_variant_report(
        mutation=MutationSpec("M", 1, "V"),
        metrics=metrics,
        reference_distributions=reference_distributions,
    )
    assert "closer to" not in report
    assert "Percentile rank" in report


def test_score_variant_report_empty_metrics():
    """Empty metrics dict: report still renders with header and disclaimer."""
    report = score_variant_report(
        mutation=MutationSpec("A", 5, "G"),
        metrics={},
        reference_distributions={},
    )
    assert "A5G" in report
    assert "Note:" in report
