"""Reusable utilities for the Upper Bound VEP workshop notebook.

Validation, ESM-1b encoding, metric computation, and BYOD report generation.
Designed to run in Google Colab on a T4 GPU (free tier).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import torch

AA_ALPHABET = "ACDEFGHIKLMNPQRSTVWY"
AA_FULL_NAMES = {
    "A": "Alanine", "C": "Cysteine", "D": "Aspartate", "E": "Glutamate",
    "F": "Phenylalanine", "G": "Glycine", "H": "Histidine", "I": "Isoleucine",
    "K": "Lysine", "L": "Leucine", "M": "Methionine", "N": "Asparagine",
    "P": "Proline", "Q": "Glutamine", "R": "Arginine", "S": "Serine",
    "T": "Threonine", "V": "Valine", "W": "Tryptophan", "Y": "Tyrosine",
}


@dataclass(frozen=True)
class MutationSpec:
    """A single point mutation."""
    wt_aa: str
    position: int  # 1-indexed
    mut_aa: str

    def __str__(self) -> str:
        return f"{self.wt_aa}{self.position}{self.mut_aa}"


def validate_sequence(sequence: str, max_length: int = 1024) -> str:
    """Validate a protein sequence. Returns the (possibly truncated) sequence.

    Raises ValueError for empty sequences or invalid characters.
    Prints a warning and truncates if longer than max_length.
    """
    if not sequence:
        raise ValueError("Sequence is empty")
    if sequence.lstrip().startswith(">"):
        raise ValueError(
            "Input looks like FASTA (starts with '>'). "
            "Please paste only the sequence, without the header line."
        )
    sequence = "".join(sequence.split()).upper()  # strips all whitespace incl. newlines, tabs, \xa0
    for i, aa in enumerate(sequence):
        if aa not in AA_ALPHABET:
            raise ValueError(
                f"Invalid amino acid '{aa}' at position {i + 1}. "
                f"Valid residues: {AA_ALPHABET}"
            )
    if len(sequence) > max_length:
        print(
            f"Warning: Sequence too long ({len(sequence)} AA). "
            f"ESM-1b max context is {max_length}. Truncating to first {max_length}."
        )
        sequence = sequence[:max_length]
    return sequence


def parse_mutation(mutation_str: str) -> MutationSpec:
    """Parse a mutation string like 'A23T' into a MutationSpec.

    Raises ValueError if the format is invalid.
    """
    match = re.fullmatch(r"([A-Z])(\d+)([A-Z])", mutation_str.strip().upper())
    if not match:
        raise ValueError(
            f"Could not parse mutation '{mutation_str}'. "
            f"Expected format: 'A23T' (wt_aa, position, mut_aa)."
        )
    wt_aa, pos_str, mut_aa = match.groups()
    if wt_aa not in AA_ALPHABET:
        raise ValueError(f"Invalid amino acid '{wt_aa}' in mutation '{mutation_str}'")
    if mut_aa not in AA_ALPHABET:
        raise ValueError(f"Invalid amino acid '{mut_aa}' in mutation '{mutation_str}'")
    return MutationSpec(wt_aa=wt_aa, position=int(pos_str), mut_aa=mut_aa)


def validate_mutation(sequence: str, mutation: MutationSpec) -> None:
    """Verify a mutation makes sense against a sequence.

    Raises ValueError with a specific, actionable message if:
    - Position is out of range
    - WT residue doesn't match the sequence
    - WT and MUT residues are identical
    """
    if mutation.position < 1 or mutation.position > len(sequence):
        raise ValueError(
            f"Position {mutation.position} out of range "
            f"(sequence length: {len(sequence)})"
        )
    actual_aa = sequence[mutation.position - 1]
    if actual_aa != mutation.wt_aa:
        actual_name = AA_FULL_NAMES.get(actual_aa, actual_aa)
        raise ValueError(
            f"Position {mutation.position} is {actual_name} ({actual_aa}), "
            f"not {mutation.wt_aa}. Did you mean {actual_aa}{mutation.position}{mutation.mut_aa}?"
        )
    if mutation.wt_aa == mutation.mut_aa:
        raise ValueError(
            f"WT and MUT residues are identical ({mutation.wt_aa}) — this is not a mutation"
        )


def apply_mutation(sequence: str, mutation: MutationSpec) -> str:
    """Apply a mutation to a sequence and return the mutant sequence."""
    validate_mutation(sequence, mutation)
    return sequence[:mutation.position - 1] + mutation.mut_aa + sequence[mutation.position:]


def truncate_around_mutation(
    sequence: str, position_1idx: int, window: int = 1024,
) -> tuple[str, int]:
    """Center-window a sequence around a mutation position.

    Returns (truncated_seq, new_position_1idx). For sequences shorter than
    `window`, returns the original sequence and position unchanged. The mutation
    position is preserved relative to the returned sequence.
    """
    if len(sequence) <= window:
        return sequence, position_1idx
    half = window // 2
    start = max(0, position_1idx - 1 - half)
    end = start + window
    if end > len(sequence):
        end = len(sequence)
        start = end - window
    new_pos = position_1idx - start
    return sequence[start:end], new_pos


class ESM1bEncoder:
    """Thin wrapper around ESM-1b via HuggingFace transformers.

    Loads facebook/esm1b_t33_650M_UR50S, which is fully open (no auth required).
    Returns per-sequence mean-pooled embeddings and per-residue logits.
    """

    MODEL_NAME = "facebook/esm1b_t33_650M_UR50S"
    EMBED_DIM = 1280
    # Max residue count the encoder can ingest. ESM-1b's position-embedding
    # table has 1024 slots, and the HF tokenizer prepends BOS and appends EOS,
    # so a sequence of L residues becomes L+2 tokens. L must therefore be
    # <= 1022. All call sites (validate_sequence(max_length=MAX_LEN),
    # truncate_around_mutation(window=MAX_LEN)) treat MAX_LEN as residues.
    MAX_LEN = 1022

    def __init__(self, device: str | None = None) -> None:
        from transformers import AutoModelForMaskedLM, AutoTokenizer

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        print(f"Loading ESM-1b on {device}... (first load takes ~1 min)")
        self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)
        self.model = AutoModelForMaskedLM.from_pretrained(
            self.MODEL_NAME,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        )
        self.model.to(device)
        self.model.eval()
        print("ESM-1b loaded.")

    @torch.no_grad()
    def encode(self, sequence: str) -> tuple[np.ndarray, np.ndarray]:
        """Encode a protein sequence.

        Returns:
            embedding: (1280,) mean-pooled over sequence positions (excluding special tokens)
            logits: (seq_len + 2, 33) per-token logits including BOS/EOS
            Logit layout: index 0 is BOS, indices 1..L are positions 1..L
            (1-indexed residue), index L+1 is EOS. For residue-level LLR at
            1-indexed position p, use logits[p, ...].
        """
        sequence = validate_sequence(sequence, max_length=self.MAX_LEN)
        inputs = self.tokenizer(sequence, return_tensors="pt").to(self.device)
        outputs = self.model(**inputs, output_hidden_states=True)

        # Hidden states from final layer, skip BOS/EOS for pooling
        hidden = outputs.hidden_states[-1][0]  # (seq_len + 2, 1280)
        embedding = hidden[1:-1].mean(dim=0).float().cpu().numpy()

        logits = outputs.logits[0].float().cpu().numpy()  # (seq_len + 2, vocab)

        if np.isnan(embedding).any():
            raise RuntimeError("Embedding contains NaN — possible OOM, try a shorter sequence")
        return embedding, logits


def encode_variant(
    encoder: "ESM1bEncoder", sequence: str, mutation_str: str,
) -> dict[str, np.ndarray]:
    """Encode both WT and MUT forms of a variant.

    Returns a dict with:
        wt_sequence, mut_sequence: strings
        wt_embedding, mut_embedding: (1280,) arrays
        wt_logits, mut_logits: (L+2, 33) arrays for LLR computation
        mutation: MutationSpec
    """
    sequence = validate_sequence(sequence, max_length=encoder.MAX_LEN)
    mutation = parse_mutation(mutation_str)
    mut_sequence = apply_mutation(sequence, mutation)

    wt_emb, wt_logits = encoder.encode(sequence)
    mut_emb, mut_logits = encoder.encode(mut_sequence)

    return {
        "wt_sequence": sequence,
        "mut_sequence": mut_sequence,
        "wt_embedding": wt_emb,
        "mut_embedding": mut_emb,
        "wt_logits": wt_logits,
        "mut_logits": mut_logits,
        "mutation": mutation,
    }


def compute_delta_norm(wt_embedding: np.ndarray, mut_embedding: np.ndarray) -> float:
    """L2 norm of the embedding delta."""
    return float(np.linalg.norm(mut_embedding - wt_embedding))


def compute_cosine_distance(wt_embedding: np.ndarray, mut_embedding: np.ndarray) -> float:
    """Cosine distance = 1 - cosine similarity."""
    dot = float(np.dot(wt_embedding, mut_embedding))
    norms = float(np.linalg.norm(wt_embedding) * np.linalg.norm(mut_embedding))
    if norms < 1e-10:
        # Cosine similarity is undefined when either vector has zero norm
        # (the zero vector has no direction). Return NaN rather than 0.0
        # to avoid falsely signalling "identical direction".
        return float("nan")
    return 1.0 - dot / norms


def compute_llr(
    wt_logits: np.ndarray,
    mut_logits: np.ndarray,
    mutation: MutationSpec,
    wt_token_id: int,
    mut_token_id: int,
) -> float:
    """Log-likelihood "surprise ratio" across WT and MUT contexts.

    Computes:
        LLR = log P_wt(wt_aa | wt_sequence) - log P_mut(mut_aa | mut_sequence)

    i.e. how much log-probability is lost when we move from the WT model
    evaluating the WT residue at the mutation site to the MUT model
    evaluating the MUT residue at the same site. Both terms are evaluated
    at `mutation.position`, each in its own context.

    Sign convention (single source of truth for downstream reports):
        - LLR > 0  -> MUT model is LESS confident in the MUT residue than
                      the WT model was in the WT residue. Bigger confidence
                      drop at the mutation site, often correlates with
                      pathogenicity.
        - LLR ~ 0  -> The model is about equally confident in both states.
        - LLR < 0  -> MUT model is MORE confident in the MUT residue than
                      the WT model was in the WT residue (unusual; typically
                      benign or a case where MUT fits the context better).

    Note on indexing: the ESM-1b token array has BOS at index 0, so
    sequence position p (1-indexed) maps directly to token index p.
    """
    pos = mutation.position  # 1-indexed sequence pos -> token index p (BOS at index 0)

    def log_softmax(x: np.ndarray) -> np.ndarray:
        x_max = np.max(x)
        shifted = x - x_max
        return shifted - np.log(np.sum(np.exp(shifted)))

    wt_log_probs = log_softmax(wt_logits[pos])
    mut_log_probs = log_softmax(mut_logits[pos])
    # Surprise ratio: log P_wt(wt | wt_seq) - log P_mut(mut | mut_seq).
    # Higher value = bigger confidence drop at the mutation site.
    return float(wt_log_probs[wt_token_id] - mut_log_probs[mut_token_id])


def compute_lid(
    query: np.ndarray,
    reference: np.ndarray,
    k: int = 20,
) -> float:
    """Local Intrinsic Dimensionality via maximum-likelihood estimator (Amsaleg 2015).

    LID = -(k - 1) / sum(log(r_i / r_k)) for i in [1, k-1]
    where r_i is the distance to the i-th nearest neighbor and r_k is the
    distance to the k-th (farthest of the k) nearest neighbor.

    Lower LID = more constrained local geometry (often pathogenic in VEP).
    """
    n_ref = len(reference)
    k = min(k, n_ref - 1)
    if k < 2:
        return float("nan")

    dists = np.linalg.norm(reference - query[None, :], axis=1)
    dists.sort()
    # Skip zero distances (exact duplicates)
    dists = dists[dists > 1e-10]
    if len(dists) < k:
        k = len(dists)
    if k < 2:
        return float("nan")

    nearest = dists[:k]
    r_k = nearest[-1]
    if r_k < 1e-10:
        return float("nan")
    log_ratios = np.log(nearest[:-1] / r_k)
    lid = -(k - 1) / np.sum(log_ratios)
    return float(lid)


def _percentile_rank(value: float, ref: dict[str, float]) -> float:
    """Percentile rank via piecewise-linear interpolation over reference quantiles.

    Uses whatever pN keys are in the reference dict (at minimum p5, p50, p95).
    Values below the smallest quantile clamp to 0, above the largest clamp to 100.
    """
    # Collect (percentile, value) pairs from keys like p5, p50, p95
    pairs = []
    for k, v in ref.items():
        if isinstance(k, str) and k.startswith("p") and k[1:].isdigit():
            pairs.append((float(k[1:]), float(v)))
    if len(pairs) < 2:
        return float("nan")
    pairs.sort(key=lambda pv: pv[1])
    quantiles = [p for p, _ in pairs]
    values = [v for _, v in pairs]
    if value <= values[0]:
        return quantiles[0]
    if value >= values[-1]:
        return quantiles[-1]
    # Linear interp
    for i in range(len(values) - 1):
        if values[i] <= value <= values[i + 1]:
            span = values[i + 1] - values[i]
            if span < 1e-10:
                return quantiles[i]
            frac = (value - values[i]) / span
            return quantiles[i] + frac * (quantiles[i + 1] - quantiles[i])
    return float("nan")


def score_variant_report(
    mutation: MutationSpec,
    metrics: dict[str, float],
    reference_distributions: dict[str, dict[str, float]],
) -> str:
    """Generate a human-readable report for a BYOD variant.

    Contextualizes each metric against the reference distribution of the
    workshop dataset (mean, SD, per-class medians) and flags whether the
    variant looks more pathogenic-like or benign-like on each score.
    """
    lines = [
        f"Variant Effect Report: {mutation}",
        "=" * 60,
        "",
    ]

    metric_map = {
        "delta_norm": ("delta_norm_protein", "Delta norm (L2)", True),
        "cosine_dist": ("cosine_dist_protein", "Cosine distance", True),
        "llr": ("llr_protein", "LLR (log-likelihood ratio)", True),
        "lid": ("lid_protein", "LID (local intrinsic dim)", False),
    }

    for key, (ref_key, label, higher_is_pathogenic) in metric_map.items():
        if key not in metrics:
            continue
        value = metrics[key]
        lines.append(f"\u2022 {label}: {value:.3f}")
        if ref_key not in reference_distributions:
            lines.append("    (no reference distribution available)")
            continue
        d = reference_distributions[ref_key]
        pct = _percentile_rank(value, d)
        lines.append(f"    Reference mean: {d['mean']:.3f} \u00b1 {d['std']:.3f}")
        lines.append(f"    Percentile rank: {pct:.1f}%")
        if higher_is_pathogenic:
            verdict = "pathogenic-like" if pct >= 75 else ("benign-like" if pct <= 25 else "intermediate")
        else:
            verdict = "pathogenic-like" if pct <= 25 else ("benign-like" if pct >= 75 else "intermediate")
        lines.append(f"    Directional verdict: {verdict} (percentile-based)")

        path_med = d.get("pathogenic_median")
        ben_med = d.get("benign_median")
        if path_med is not None and ben_med is not None:
            path_dist = abs(value - path_med)
            ben_dist = abs(value - ben_med)
            closer = "pathogenic" if path_dist < ben_dist else "benign"
            lines.append(
                f"    Class medians: pathogenic={path_med:.3f}, benign={ben_med:.3f} "
                f"\u2192 value is closer to **{closer}**"
            )
        lines.append("")

    lines.append("-" * 60)
    lines.append("Note: this is a zero-shot score. Accuracy depends on the model")
    lines.append("and reference dataset. Always cross-check with specialized tools")
    lines.append("like AlphaMissense for clinically-relevant variants.")
    return "\n".join(lines)
