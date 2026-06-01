"""
credibility_scorer.py — Layer 2: Rule-based credibility assessment.

Responsibility:
1. Infer profile_label via distribution-based matching against prototypes
2. Compute multi-signal credibility_score (0-100)
3. Map to credibility_label (good / average / poor)
4. Generate red_flags and investor_summary

Signals & Weights (tuned via H3 ground-truth grid search):
    - profile_aware_coverage: 20%
    - plagiarism_rate:        25%
    - linguistic_quality:      5%
    - keyword_relevance:       0%  (inversely correlated — disabled)
    - content_balance:        50%

Usage:
    from pipeline.credibility_scorer import score_whitepaper, score_corpus

    # Single WP
    result = score_whitepaper(wp_data)

    # Full corpus (for keyword relevance normalization)
    results = score_corpus(pipeline_results)
"""

import json
import logging
import math
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 9 fine-tuned labels (post-merge: market analysis → use cases and ecosystem;
#                       team and advisors → project overview)
# ---------------------------------------------------------------------------
ALL_LABELS = [
    "technical architecture",
    "use cases and ecosystem",
    "tokenomics",
    "project overview",
    "security and audit",
    "risk and legal",
    "roadmap",
    "governance",
    "problem statement",
]

# ---------------------------------------------------------------------------
# Profile prototypes — derived from ground truth label distributions
# (from fine_tune_label_summary.md per-profile aggregates)
# ---------------------------------------------------------------------------
# Normalized label distribution centroids per profile, computed from the
# 45-WP corpus ground truth. Each is a 9-dim vector summing to 1.0.
#
# Derivation (segment counts → ratio):
#   technical_only  : 13 WPs, 266 total segments
#   investor_oriented: 18 WPs, 406 total segments
#   hybrid          : 14 WPs, 737 total segments
#
# Merge note:
#   market analysis  → absorbed into use cases and ecosystem
#   team and advisors → absorbed into project overview

PROFILE_PROTOTYPES = {
    "technical_only": {
        "technical architecture": 0.519,  # TA-dominant pattern
        "use cases and ecosystem": 0.143,
        "tokenomics": 0.086,
        "project overview": 0.113,
        "security and audit": 0.079,
        "risk and legal": 0.008,
        "roadmap": 0.000,  # zero: no roadmap in any technical_only WP
        "governance": 0.030,
        "problem statement": 0.023,
    },
    "investor_oriented": {
        "technical architecture": 0.113,
        "use cases and ecosystem": 0.271,  # UC+market absorbed
        "tokenomics": 0.177,
        "project overview": 0.187,  # PO+team absorbed
        "security and audit": 0.039,
        "risk and legal": 0.057,
        "roadmap": 0.057,
        "governance": 0.054,
        "problem statement": 0.044,
    },
    "hybrid": {
        "technical architecture": 0.213,
        "use cases and ecosystem": 0.223,
        "tokenomics": 0.157,
        "project overview": 0.086,
        "security and audit": 0.076,
        "risk and legal": 0.086,
        "roadmap": 0.072,
        "governance": 0.053,
        "problem statement": 0.035,
    },
}

# ---------------------------------------------------------------------------
# Profile-aware coverage: label priority tiers per profile
# ---------------------------------------------------------------------------
COVERAGE_TIERS = {
    "technical_only": {
        "core": ["technical architecture", "project overview"],
        "supporting": ["security and audit", "use cases and ecosystem", "tokenomics"],
        "optional": [
            "governance",
            "problem statement",
            "risk and legal",
            "roadmap",
        ],
    },
    "investor_oriented": {
        # project overview absorbs team signal post-merge → elevated to core
        "core": ["project overview", "tokenomics", "use cases and ecosystem"],
        "supporting": ["roadmap", "risk and legal", "technical architecture"],
        "optional": [
            "governance",
            "security and audit",
            "problem statement",
        ],
    },
    "hybrid": {
        "core": ["technical architecture", "tokenomics", "use cases and ecosystem"],
        "supporting": [
            "project overview",
            "roadmap",
            "security and audit",
            "risk and legal",
        ],
        "optional": [
            "governance",
            "problem statement",
        ],
    },
    "undetermined": {
        "core": [
            "project overview",
            "technical architecture",
            "tokenomics",
            "use cases and ecosystem",
        ],
        "supporting": [
            "roadmap",
            "risk and legal",
            "security and audit",
            "governance",
        ],
        "optional": ["problem statement"],
    },
}

# Coverage scoring weights per tier
TIER_POINTS = {"core": 2.0, "supporting": 1.0, "optional": 0.5}

# Substantive labels for content balance scoring
SUBSTANTIVE_LABELS = {
    "technical architecture",
    "tokenomics",
    "use cases and ecosystem",
    "project overview",
    "roadmap",
    "governance",
    "security and audit",
}

LEGAL_HEAVY_LABELS = {"risk and legal"}

# Signal weights (tuned via H3 ground-truth grid search)
WEIGHTS = {
    "profile_aware_coverage": 0.20,
    "plagiarism": 0.25,
    "linguistic": 0.05,
    "keyword": 0.00,
    "content_balance": 0.50,
}


# ---------------------------------------------------------------------------
# Helper: cosine similarity
# ---------------------------------------------------------------------------
def _cosine_sim(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two label distributions (dicts)."""
    keys = set(a.keys()) | set(b.keys())
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    mag_a = math.sqrt(sum(v**2 for v in a.values()))
    mag_b = math.sqrt(sum(v**2 for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# 1. Label distribution + profile inference
# ---------------------------------------------------------------------------
def compute_label_distribution(section_labels: list[dict]) -> dict[str, float]:
    """Compute normalized label distribution from section_labels list."""
    counts = {label: 0 for label in ALL_LABELS}
    for s in section_labels:
        lbl = s.get("label", "")
        if lbl in counts:
            counts[lbl] += 1
    total = sum(counts.values())
    if total == 0:
        return {label: 0.0 for label in ALL_LABELS}
    return {label: count / total for label, count in counts.items()}


def normalize_section_labels(wp_data: dict) -> list[dict]:
    """Return a scorer-friendly section label list from either pipeline shape."""
    section_labels = wp_data.get("section_labels") or []
    if section_labels:
        return section_labels

    normalized = []
    for section in wp_data.get("sections") or []:
        normalized.append(
            {
                "heading": section.get("heading", ""),
                "label": section.get("label") or section.get("predicted_label", ""),
            }
        )
    return normalized


def infer_profile(
    label_distribution: dict[str, float],
    total_sections: int,
) -> tuple[str, str, dict[str, float]]:
    """Infer profile_label via distribution matching against prototypes.

    Returns:
        (profile_label, profile_confidence, profile_similarity)
    """
    # Short-document stability rules
    if total_sections < 5:
        sims = {
            profile: _cosine_sim(label_distribution, proto)
            for profile, proto in PROFILE_PROTOTYPES.items()
        }
        return "undetermined", "very_low", sims

    # Compute similarity to each prototype
    sims = {
        profile: round(_cosine_sim(label_distribution, proto), 4)
        for profile, proto in PROFILE_PROTOTYPES.items()
    }
    best_profile = max(sims, key=sims.get)

    # Confidence based on section count
    if total_sections <= 12:
        confidence = "low"
    elif total_sections <= 19:
        confidence = "medium"
    else:
        confidence = "high"

    return best_profile, confidence, sims


# ---------------------------------------------------------------------------
# 2. Profile-aware coverage score
# ---------------------------------------------------------------------------
def compute_coverage_score(
    label_distribution: dict[str, float],
    profile_label: str,
) -> float:
    """Compute profile-aware coverage score (0.0-1.0).

    Measures presence of expected labels per profile tier.

    Score = achieved_points / max_possible_points

    Each label earns points if present (label_distribution > 0):
      core labels:       2.0 pts each
      supporting labels: 1.0 pts each
      optional labels:   0.5 pts each
    """
    tiers = COVERAGE_TIERS.get(profile_label, COVERAGE_TIERS["undetermined"])

    total_points = 0.0
    max_possible = 0.0

    for tier, labels in tiers.items():
        weight = TIER_POINTS[tier]
        for label in labels:
            max_possible += weight
            if label_distribution.get(label, 0) > 0:
                total_points += weight

    if max_possible == 0:
        return 0.0

    return total_points / max_possible


# ---------------------------------------------------------------------------
# 3. Plagiarism score
# ---------------------------------------------------------------------------
def compute_plagiarism_score(plagiarism_rate: float) -> float:
    """Convert plagiarism_rate to score (0.0-1.0). Lower plagiarism = higher score."""
    return max(0.0, 1.0 - plagiarism_rate)


# ---------------------------------------------------------------------------
# 4. Linguistic quality score
# ---------------------------------------------------------------------------
def compute_linguistic_score(error_rate: float) -> float:
    """Convert error_rate (errors/1000 words) to score (0.0-1.0).

    Normalization: score = 1 - min(error_rate / 50, 1.0)
    50 errors/1000 words is considered very poor → score = 0.
    """
    normalized = min(error_rate / 50.0, 1.0)
    return max(0.0, 1.0 - normalized)


# ---------------------------------------------------------------------------
# 5. Keyword relevance score
# ---------------------------------------------------------------------------
def compute_keyword_relevance(
    tfidf_scores: list[float] | None,
    corpus_max: float = 1.0,
) -> float:
    """Compute keyword relevance score (0.0-1.0).

    Uses average of top-N TF-IDF scores, normalized against corpus max.
    If tfidf_scores is None or empty, returns 0.5 (neutral default).
    """
    if not tfidf_scores:
        return 0.5
    avg = sum(tfidf_scores) / len(tfidf_scores)
    return min(avg / corpus_max, 1.0) if corpus_max > 0 else 0.5


# ---------------------------------------------------------------------------
# 6. Content balance score
# ---------------------------------------------------------------------------
def compute_content_balance(section_labels: list[dict]) -> float:
    """Compute content balance score (0.0-1.0).

    Measures proportion of substantive content vs legal/disclaimer-heavy content.
    A WP dominated by risk/legal sections gets a lower score.
    """
    total = len(section_labels)
    if total == 0:
        return 0.0

    substantive_count = sum(
        1 for s in section_labels if s.get("label", "") in SUBSTANTIVE_LABELS
    )
    legal_count = sum(
        1 for s in section_labels if s.get("label", "") in LEGAL_HEAVY_LABELS
    )

    substantive_ratio = substantive_count / total
    legal_ratio = legal_count / total

    # Base score from substantive ratio
    base_score = substantive_ratio

    # Penalty if legal content is > 30% of total
    if legal_ratio > 0.30:
        penalty = (legal_ratio - 0.30) * 2.0  # steep penalty
        base_score = max(0.0, base_score - penalty)

    return min(1.0, base_score)


# ---------------------------------------------------------------------------
# 7. Red flags
# ---------------------------------------------------------------------------
def generate_red_flags(
    profile_label: str,
    label_distribution: dict[str, float],
    plagiarism_rate: float,
    error_rate: float,
    total_sections: int,
    content_balance: float,
) -> list[str]:
    """Generate list of red flag strings."""
    flags = []
    tiers = COVERAGE_TIERS.get(profile_label, COVERAGE_TIERS["undetermined"])

    # Missing all core sections
    core_present = sum(1 for lbl in tiers["core"] if label_distribution.get(lbl, 0) > 0)
    if core_present == 0:
        flags.append(
            "Semua section prioritas utama tidak ditemukan — "
            "dokumen tidak memiliki konten inti yang diharapkan"
        )
    elif core_present < len(tiers["core"]) / 2:
        missing = [lbl for lbl in tiers["core"] if label_distribution.get(lbl, 0) == 0]
        flags.append(
            f"Sebagian besar section prioritas utama tidak ditemukan: "
            f"{', '.join(missing)}"
        )

    # High plagiarism
    if plagiarism_rate > 0.50:
        flags.append(
            f"Tingkat plagiarisme sangat tinggi ({plagiarism_rate:.0%}) — "
            "lebih dari separuh konten mirip WP lain"
        )
    elif plagiarism_rate > 0.25:
        flags.append(f"Tingkat plagiarisme cukup tinggi ({plagiarism_rate:.0%})")

    # High linguistic error rate
    if error_rate > 30:
        flags.append(
            f"Kualitas bahasa sangat buruk (error rate {error_rate:.1f}/1000 kata)"
        )
    elif error_rate > 15:
        flags.append(
            f"Kualitas bahasa kurang baik (error rate {error_rate:.1f}/1000 kata)"
        )

    # Very short document
    if total_sections < 5:
        flags.append(
            f"Jumlah section terlalu sedikit ({total_sections}) — "
            "dokumen sangat pendek untuk analisis yang stabil"
        )

    # Poor content balance
    if content_balance < 0.3:
        flags.append(
            "Konten didominasi oleh section non-substantif "
            "(legal/disclaimer/boilerplate)"
        )

    return flags


# ---------------------------------------------------------------------------
# 8a. Summary headline (rExecHead — single interpretive sentence)
# ---------------------------------------------------------------------------
def generate_summary_headline(
    credibility_label: str,
    profile_label: str,
    profile_confidence: str,
    red_flags: list[str],
    credibility_score: float,
) -> str:
    """Generate a short interpretive headline for the result card (rExecHead).

    One sentence. Combines quality signal with flag severity.
    Does NOT use absolute wording — follows interpretive tone from brainstorm doc.
    """
    has_critical = any(
        "sangat tinggi" in f or "semua section prioritas" in f for f in red_flags
    )

    if credibility_label == "good":
        if not red_flags:
            return (
                "Whitepaper menunjukkan struktur yang baik dan distribusi konten "
                "yang sehat — tidak ada sinyal peringatan signifikan yang terdeteksi."
            )
        return (
            "Whitepaper memuat banyak sinyal positif, namun beberapa area "
            "perlu dicermati sebelum keputusan investasi."
        )

    elif credibility_label == "average":
        if has_critical:
            return (
                "Whitepaper memiliki struktur yang cukup, namun terdapat "
                "peringatan penting yang perlu ditelaah lebih lanjut."
            )
        return (
            "Whitepaper memuat sinyal yang beragam — beberapa bagian penting "
            "hadir, namun cakupan keseluruhan masih perlu diperkuat."
        )

    else:  # poor
        if has_critical:
            return (
                "Whitepaper menunjukkan keterbatasan struktural yang signifikan "
                "dan terdapat peringatan serius yang perlu diperhatikan."
            )
        return (
            "Whitepaper menunjukkan keterbatasan pada struktur dan cakupan konten "
            "untuk keperluan telaah investor awal."
        )


# ---------------------------------------------------------------------------
# 8b. Summary paragraph (rExecP — 2-3 sentence supporting paragraph)
# ---------------------------------------------------------------------------
def generate_summary_paragraph(
    label_distribution: dict[str, float],
    profile_label: str,
    profile_confidence: str,
    red_flags: list[str],
    credibility_label: str,
) -> str:
    """Generate a short 2-3 sentence paragraph for the result card (rExecP).

    Sentence 1: Top dominant labels + profile tendency (interpretive, not absolute).
    Sentence 2: Notable finding from red flags, or a strength if clean.
    Sentence 3: Fixed rule-based disclaimer.
    """
    # Sentence 1 — top labels + profile tendency
    sorted_labels = sorted(label_distribution.items(), key=lambda x: x[1], reverse=True)
    top_labels = [lbl for lbl, pct in sorted_labels[:3] if pct > 0]

    if top_labels:
        top_str = ", ".join(f"`{lbl}`" for lbl in top_labels)
        if profile_confidence == "high":
            sent1 = (
                f"Dokumen didominasi oleh {top_str}, dengan pola distribusi "
                f"yang lebih dekat ke profil `{profile_label}`."
            )
        elif profile_confidence == "medium":
            sent1 = (
                f"Dokumen didominasi oleh {top_str}; distribusi section "
                f"cenderung menyerupai profil `{profile_label}`."
            )
        elif profile_confidence == "low":
            sent1 = (
                f"Dokumen didominasi oleh {top_str}; indikasi awal mengarah ke "
                f"profil `{profile_label}`, namun jumlah section masih terbatas."
            )
        else:  # very_low
            sent1 = (
                f"Dokumen didominasi oleh {top_str}, namun terlalu pendek "
                f"untuk menentukan profil distribusi yang stabil."
            )
    else:
        sent1 = (
            "Tidak ditemukan label section yang cukup untuk menganalisis "
            "pola distribusi konten."
        )

    # Sentence 2 — notable finding or strength
    if red_flags:
        # Use first flag, lowercased and trimmed for inline use
        flag_text = red_flags[0]
        # Capitalize first letter for sentence start
        flag_text = flag_text[0].upper() + flag_text[1:]
        sent2 = f"Perlu diperhatikan: {flag_text.rstrip('.')}."
    else:
        if credibility_label == "good":
            sent2 = (
                "Tidak ada sinyal peringatan yang terdeteksi dari analisis struktural."
            )
        elif credibility_label == "average":
            sent2 = (
                "Beberapa bagian pendukung hadir namun cakupan keseluruhan "
                "dapat ditingkatkan."
            )
        else:
            sent2 = "Dokumen memerlukan penguatan pada beberapa bagian konten inti."

    # Sentence 3 — fixed disclaimer
    sent3 = (
        "Skor ini merupakan hasil agregasi berbasis aturan dari 5 sinyal "
        "struktural — bukan evaluasi semantik mendalam."
    )

    return " ".join([sent1, sent2, sent3])


# ---------------------------------------------------------------------------
# 8. Investor summary
# ---------------------------------------------------------------------------
def generate_investor_summary(
    wp_id: str,
    project_name: str,
    profile_label: str,
    profile_confidence: str,
    credibility_score: float,
    credibility_label: str,
    label_distribution: dict[str, float],
    red_flags: list[str],
    signal_breakdown: dict[str, float],
) -> str:
    """Generate investor summary narrative in Indonesian."""
    # Top labels
    sorted_labels = sorted(label_distribution.items(), key=lambda x: x[1], reverse=True)
    top_labels = [f"`{lbl}`" for lbl, pct in sorted_labels[:3] if pct > 0]

    # Profile tendency wording
    if profile_confidence == "very_low":
        profile_text = (
            f"Dokumen terlalu pendek untuk menentukan profil. "
            f"Tidak dapat disimpulkan apakah bersifat teknis, investor-oriented, atau hybrid."
        )
    elif profile_confidence == "low":
        profile_text = (
            f"Dokumen ini memiliki indikasi awal mengarah ke profil `{profile_label}`, "
            f"namun jumlah section masih terbatas sehingga kesimpulan ini bersifat tentatif."
        )
    elif profile_confidence == "medium":
        profile_text = (
            f"Pola distribusi section cenderung menyerupai profil `{profile_label}`."
        )
    else:  # high
        profile_text = (
            f"Distribusi section menunjukkan pola yang lebih dekat ke profil "
            f"`{profile_label}`."
        )

    # Build summary
    parts = []
    parts.append(f"## Assessment: {project_name} ({wp_id})\n")

    if top_labels:
        parts.append(
            f"Whitepaper ini didominasi oleh {', '.join(top_labels)}. {profile_text}"
        )
    else:
        parts.append(profile_text)

    parts.append(
        f"\n**Skor Kredibilitas**: {credibility_score:.1f}/100 "
        f"(**{credibility_label.upper()}**)"
    )

    # Signal breakdown
    parts.append("\n**Breakdown Sinyal**:")
    for signal, value in signal_breakdown.items():
        parts.append(f"- {signal}: {value:.2f}")

    if red_flags:
        parts.append("\n**Red Flags**:")
        for flag in red_flags:
            parts.append(f"- ⚠ {flag}")

    parts.append(
        "\nMeskipun pola section menunjukkan kecenderungan profil tertentu, "
        "skor akhir tetap ditentukan oleh plagiarisme, kualitas bahasa, "
        "dan keseimbangan konten secara keseluruhan."
    )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main scoring function — single WP
# ---------------------------------------------------------------------------
def score_whitepaper(
    wp_data: dict,
    corpus_keyword_max: float = 1.0,
) -> dict:
    """Score a single whitepaper and return credibility assessment.

    Args:
        wp_data: dict with keys from pipeline_results.json:
            - section_labels: list of {heading, label}
            - plagiarism_rate: float (0-1)
            - linguistic_error_rate: float (errors/1000 words)
            - keywords: {tfidf: list[str], ...}  (or tfidf_scores: list[float])
            - wp_id, project_name, quality_label, profile_label (ground truth)
        corpus_keyword_max: max avg TF-IDF score across corpus for normalization

    Returns:
        dict with credibility assessment fields
    """
    wp_id = wp_data.get("wp_id", "")
    project_name = wp_data.get("project_name", "")
    section_labels = normalize_section_labels(wp_data)
    total_sections = len(section_labels)

    # 1. Label distribution + profile inference
    label_dist = compute_label_distribution(section_labels)
    profile_label, profile_confidence, profile_similarity = infer_profile(
        label_dist, total_sections
    )

    # 2. Profile-aware coverage
    coverage = compute_coverage_score(label_dist, profile_label)

    # 3. Plagiarism score
    plag_rate = wp_data.get("plagiarism_rate", 0.0)
    plag_score = compute_plagiarism_score(plag_rate)

    # 4. Linguistic quality
    error_rate = wp_data.get("linguistic_error_rate", 0.0)
    ling_score = compute_linguistic_score(error_rate)

    # 5. Keyword relevance
    tfidf_scores = wp_data.get("tfidf_scores")
    kw_score = compute_keyword_relevance(tfidf_scores, corpus_keyword_max)

    # 6. Content balance
    balance_score = compute_content_balance(section_labels)

    # 7. Aggregate
    signal_breakdown = {
        "profile_aware_coverage": round(coverage, 4),
        "plagiarism": round(plag_score, 4),
        "linguistic": round(ling_score, 4),
        "keyword": round(kw_score, 4),
        "content_balance": round(balance_score, 4),
    }

    credibility_score = (
        sum(signal_breakdown[signal] * weight for signal, weight in WEIGHTS.items())
        * 100
    )  # scale to 0-100

    credibility_score = round(min(100.0, max(0.0, credibility_score)), 2)

    # 8. Map to label (thresholds tuned via H3 ground-truth grid search)
    if credibility_score >= 88:
        credibility_label = "good"
    elif credibility_score >= 80:
        credibility_label = "average"
    else:
        credibility_label = "poor"

    # 9. Red flags
    red_flags = generate_red_flags(
        profile_label,
        label_dist,
        plag_rate,
        error_rate,
        total_sections,
        balance_score,
    )

    # 10. Investor summary (full markdown report — for detail/export view)
    investor_summary = generate_investor_summary(
        wp_id,
        project_name,
        profile_label,
        profile_confidence,
        credibility_score,
        credibility_label,
        label_dist,
        red_flags,
        signal_breakdown,
    )

    # 11. UI card summary fields (rExecHead + rExecP in frontend)
    summary_headline = generate_summary_headline(
        credibility_label,
        profile_label,
        profile_confidence,
        red_flags,
        credibility_score,
    )
    summary_paragraph = generate_summary_paragraph(
        label_dist,
        profile_label,
        profile_confidence,
        red_flags,
        credibility_label,
    )

    return {
        "wp_id": wp_id,
        "credibility_score": credibility_score,
        "credibility_label": credibility_label,
        "profile_label": profile_label,
        "profile_confidence": profile_confidence,
        "profile_similarity": profile_similarity,
        "label_distribution": {k: round(v, 4) for k, v in label_dist.items()},
        "signal_breakdown": signal_breakdown,
        "red_flags": red_flags,
        "investor_summary": investor_summary,
        "summary_headline": summary_headline,
        "summary_paragraph": summary_paragraph,
    }


# ---------------------------------------------------------------------------
# Corpus-level scoring
# ---------------------------------------------------------------------------
def score_corpus(pipeline_results: list[dict]) -> list[dict]:
    """Score all WPs in corpus. Computes corpus-level keyword normalization.

    Args:
        pipeline_results: list of per-WP dicts from pipeline_results.json

    Returns:
        list of credibility assessment dicts (one per WP)
    """
    # Compute corpus-level max TF-IDF for keyword normalization
    all_tfidf_avgs = []
    for wp in pipeline_results:
        scores = wp.get("tfidf_scores")
        if scores:
            all_tfidf_avgs.append(sum(scores) / len(scores))
    corpus_keyword_max = max(all_tfidf_avgs) if all_tfidf_avgs else 1.0

    results = []
    for wp_data in pipeline_results:
        try:
            result = score_whitepaper(wp_data, corpus_keyword_max=corpus_keyword_max)
            results.append(result)
        except Exception as e:
            logger.error(f"Scoring failed for {wp_data.get('wp_id', '?')}: {e}")
            results.append(
                {
                    "wp_id": wp_data.get("wp_id", ""),
                    "credibility_score": 0,
                    "credibility_label": "poor",
                    "error": str(e),
                }
            )

    return results


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------
def score_from_pipeline_results(
    pipeline_results_path: str,
    output_path: str | None = None,
) -> list[dict]:
    """Load pipeline_results.json, score all WPs, save results.

    Args:
        pipeline_results_path: path to pipeline_results.json
        output_path: optional path to save credibility results JSON

    Returns:
        list of scored WP dicts
    """
    path = Path(pipeline_results_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    scored = score_corpus(data)

    # Merge back into pipeline data
    score_map = {r["wp_id"]: r for r in scored}
    for wp in data:
        wp_id = wp.get("wp_id")
        if wp_id in score_map:
            wp.update(score_map[wp_id])

    # Save enriched pipeline results
    if output_path is None:
        output_path = str(path)
    Path(output_path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(f"Credibility scores saved to {output_path}")

    return scored


# ---------------------------------------------------------------------------
# Validation against ground truth
# ---------------------------------------------------------------------------
def validate_against_ground_truth(
    pipeline_results_path: str,
    metadata_path: str = "wp_metadata.json",
) -> dict:
    """Validate credibility and profile outputs against ground truth labels.

    Returns validation report dict.
    """
    pipeline_data = json.loads(Path(pipeline_results_path).read_text(encoding="utf-8"))
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))

    gt_map = {m["id"]: m for m in metadata}

    # Score corpus
    scored = score_corpus(pipeline_data)
    score_map = {r["wp_id"]: r for r in scored}

    # Credibility validation
    cred_labels = ["good", "average", "poor"]
    cred_confusion = {true: {pred: 0 for pred in cred_labels} for true in cred_labels}
    cred_correct = 0
    cred_total = 0

    # Profile validation
    prof_labels = ["technical_only", "investor_oriented", "hybrid"]
    prof_confusion = {true: {pred: 0 for pred in prof_labels} for true in prof_labels}
    prof_correct = 0
    prof_total = 0

    # Per-bucket profile accuracy
    buckets = {"<5": [], "5-12": [], "13-19": [], ">=20": []}

    for wp_id, result in score_map.items():
        gt = gt_map.get(wp_id, {})
        gt_quality = gt.get("quality_label", "")
        gt_profile = gt.get("profile_label", "")

        pred_cred = result.get("credibility_label", "")
        pred_profile = result.get("profile_label", "")

        # Credibility
        if gt_quality in cred_labels and pred_cred in cred_labels:
            cred_confusion[gt_quality][pred_cred] += 1
            cred_total += 1
            if gt_quality == pred_cred:
                cred_correct += 1

        # Profile
        if gt_profile in prof_labels and pred_profile in prof_labels:
            prof_confusion[gt_profile][pred_profile] += 1
            prof_total += 1
            if gt_profile == pred_profile:
                prof_correct += 1

        # Bucket
        total_sec = len(
            result.get("label_distribution", {})
            or [s for s in (result.get("section_labels") or []) if s]
        )
        # Use section count from pipeline data
        for wp_data in pipeline_data:
            if wp_data.get("wp_id") == wp_id:
                total_sec = wp_data.get("section_count", 0)
                break

        if total_sec < 5:
            bucket = "<5"
        elif total_sec <= 12:
            bucket = "5-12"
        elif total_sec <= 19:
            bucket = "13-19"
        else:
            bucket = ">=20"

        buckets[bucket].append(
            {
                "wp_id": wp_id,
                "gt_profile": gt_profile,
                "pred_profile": pred_profile,
                "correct": gt_profile == pred_profile,
            }
        )

    # Bucket accuracy
    bucket_accuracy = {}
    for bucket, items in buckets.items():
        total = len(items)
        correct = sum(1 for i in items if i["correct"])
        bucket_accuracy[bucket] = {
            "total": total,
            "correct": correct,
            "accuracy": correct / total if total > 0 else 0,
        }

    report = {
        "credibility": {
            "accuracy": cred_correct / cred_total if cred_total > 0 else 0,
            "total": cred_total,
            "correct": cred_correct,
            "confusion_matrix": cred_confusion,
        },
        "profile": {
            "accuracy": prof_correct / prof_total if prof_total > 0 else 0,
            "total": prof_total,
            "correct": prof_correct,
            "confusion_matrix": prof_confusion,
        },
        "profile_by_bucket": bucket_accuracy,
    }

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    parser = argparse.ArgumentParser(description="Credibility scoring for whitepapers")
    parser.add_argument(
        "--input",
        "-i",
        default="fine_tune/pipeline_results.json",
        help="Path to pipeline_results.json",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output path (default: overwrite input)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run validation against ground truth",
    )
    parser.add_argument(
        "--metadata",
        default="wp_metadata.json",
        help="Path to wp_metadata.json for validation",
    )
    args = parser.parse_args()

    if args.validate:
        report = validate_against_ground_truth(args.input, args.metadata)
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        scored = score_from_pipeline_results(args.input, args.output)
        for s in scored:
            print(
                f"{s['wp_id']}: {s['credibility_score']:.1f} "
                f"({s['credibility_label']}) "
                f"profile={s.get('profile_label', '?')} "
                f"[{s.get('profile_confidence', '?')}]"
            )
