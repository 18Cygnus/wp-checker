"""
8_plagiarism_detector.py — Cross-WP plagiarism detection via cosine similarity.

Computes pairwise cosine similarity between section embeddings from *different*
whitepapers. Flags pairs with similarity > threshold (default 0.85).

Input:  embeddings_by_wp — dict mapping wp_id -> list of section dicts with 'embedding'
Output: per-WP plagiarism flags and aggregate plagiarism_rate.

Usage:
    from pipeline.8_plagiarism_detector import detect_plagiarism
    results = detect_plagiarism(embeddings_by_wp, threshold=0.85)
"""

import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.85
# Threshold above which two embedding sets are considered the same document.
# Same PDF re-uploaded → mean max-sim ≈ 1.0. Different docs (even same topic) ≈ 0.5-0.85.
SELF_MATCH_THRESHOLD = 0.97


def is_duplicate_document(
    embeddings_a: list[dict],
    embeddings_b: list[dict],
    threshold: float = SELF_MATCH_THRESHOLD,
) -> bool:
    """Return True if two section-embedding lists represent the same document.

    Computes, for each section in A, the maximum cosine similarity to any section
    in B, then takes the mean. A mean ≥ threshold indicates the documents are
    essentially identical (e.g. same PDF re-uploaded under a different wp_id).

    Args:
        embeddings_a: list of {"segment_id", "heading", "embedding"} dicts
        embeddings_b: list of {"segment_id", "heading", "embedding"} dicts
        threshold: mean-max-sim cutoff (default 0.97)

    Returns:
        True if the two sets are from the same document.
    """
    vecs_a = [s["embedding"] for s in embeddings_a if s.get("embedding")]
    vecs_b = [s["embedding"] for s in embeddings_b if s.get("embedding")]
    if not vecs_a or not vecs_b:
        return False

    arr_a = np.array(vecs_a, dtype=np.float32)
    arr_b = np.array(vecs_b, dtype=np.float32)

    sim_matrix = _cosine_similarity_matrix(arr_a, arr_b)  # shape (n_a, n_b)
    mean_max_sim = float(sim_matrix.max(axis=1).mean())
    return mean_max_sim >= threshold


def _cosine_similarity_matrix(
    embeddings_a: np.ndarray, embeddings_b: np.ndarray
) -> np.ndarray:
    """Compute cosine similarity between two sets of normalized embeddings.

    If embeddings are L2-normalized (as from sentence-transformers with
    normalize_embeddings=True), this is just a dot product.
    """
    # Normalize just in case
    norms_a = np.linalg.norm(embeddings_a, axis=1, keepdims=True)
    norms_b = np.linalg.norm(embeddings_b, axis=1, keepdims=True)
    norms_a[norms_a == 0] = 1.0
    norms_b[norms_b == 0] = 1.0
    a_normed = embeddings_a / norms_a
    b_normed = embeddings_b / norms_b
    return a_normed @ b_normed.T


def detect_plagiarism(
    embeddings_by_wp: dict[str, list[dict]], threshold: float = DEFAULT_THRESHOLD
) -> dict[str, dict]:
    """Detect cross-WP plagiarism via cosine similarity on section embeddings.

    Args:
        embeddings_by_wp: {wp_id: [{"segment_id", "heading", "embedding"}, ...]}
        threshold: Similarity threshold for flagging (default 0.85).

    Returns:
        {wp_id: {
            "plagiarism_flags": [{section_id, matched_section_id, matched_wp_id, similarity}],
            "flagged_count": int,
            "total_sections": int,
            "plagiarism_rate": float,
        }}
    """
    wp_ids = sorted(embeddings_by_wp.keys())
    results = {
        wp_id: {
            "plagiarism_flags": [],
            "flagged_count": 0,
            "total_sections": len(embeddings_by_wp[wp_id]),
            "plagiarism_rate": 0.0,
        }
        for wp_id in wp_ids
    }

    # Compare each pair of WPs (avoid self-comparison)
    for i, wp_a in enumerate(wp_ids):
        sections_a = embeddings_by_wp[wp_a]
        if not sections_a:
            continue
        emb_a = np.array([s["embedding"] for s in sections_a], dtype=np.float32)

        for j in range(i + 1, len(wp_ids)):
            wp_b = wp_ids[j]
            sections_b = embeddings_by_wp[wp_b]
            if not sections_b:
                continue
            emb_b = np.array([s["embedding"] for s in sections_b], dtype=np.float32)

            sim_matrix = _cosine_similarity_matrix(emb_a, emb_b)

            # Find pairs above threshold
            above = np.argwhere(sim_matrix > threshold)
            for idx_a, idx_b in above:
                similarity = float(sim_matrix[idx_a, idx_b])
                sec_a = sections_a[idx_a]
                sec_b = sections_b[idx_b]

                # Flag for wp_a
                results[wp_a]["plagiarism_flags"].append(
                    {
                        "section_id": sec_a.get("segment_id", ""),
                        "heading": sec_a.get("heading", ""),
                        "matched_section_id": sec_b.get("segment_id", ""),
                        "matched_wp_id": wp_b,
                        "matched_heading": sec_b.get("heading", ""),
                        "similarity": round(similarity, 4),
                    }
                )
                # Flag for wp_b
                results[wp_b]["plagiarism_flags"].append(
                    {
                        "section_id": sec_b.get("segment_id", ""),
                        "heading": sec_b.get("heading", ""),
                        "matched_section_id": sec_a.get("segment_id", ""),
                        "matched_wp_id": wp_a,
                        "matched_heading": sec_a.get("heading", ""),
                        "similarity": round(similarity, 4),
                    }
                )

    # Compute per-WP aggregate rates
    for wp_id, data in results.items():
        flagged_sections = {f["section_id"] for f in data["plagiarism_flags"]}
        data["flagged_count"] = len(flagged_sections)
        total = data["total_sections"]
        data["plagiarism_rate"] = round(
            data["flagged_count"] / total if total > 0 else 0.0, 4
        )

    logger.info(
        f"Plagiarism detection complete: {len(wp_ids)} WPs, threshold={threshold}"
    )
    return results


def save_plagiarism_results(
    results: dict[str, dict], output_dir: str = "output_md"
) -> str:
    """Save plagiarism results to a JSON file in the output directory.

    Args:
        results: Output from detect_plagiarism().
        output_dir: Base output directory.

    Returns:
        Path to saved JSON file.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(output_dir) / "plagiarism_results.json"
    out_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"Plagiarism results saved to {out_path}")
    return str(out_path)


def load_embeddings_from_step5(
    output_dir: str, metadata: list[dict]
) -> dict[str, list[dict]]:
    """Load step5 JSON embedding files for all WPs.

    Args:
        output_dir: Base output directory containing WP folders.
        metadata: List of WP metadata dicts with 'id' and project name fields.

    Returns:
        {wp_id: [{"segment_id", "heading", "embedding"}, ...]}
    """
    embeddings_by_wp = {}
    for item in metadata:
        wp_id = item["id"]
        project_name = item.get("project_name") or item.get("nama_proyek", "").replace(
            " ", ""
        )
        json_path = (
            Path(output_dir) / f"{wp_id}_{project_name}" / f"step5_{project_name}.json"
        )
        if json_path.exists():
            data = json.loads(json_path.read_text(encoding="utf-8"))
            embeddings_by_wp[wp_id] = data
        else:
            logger.warning(f"  {wp_id}: step5 JSON not found at {json_path}")
    return embeddings_by_wp
