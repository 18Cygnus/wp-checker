import importlib.util
import json
from pathlib import Path

import numpy as np


def load_plagiarism_detector():
    spec = importlib.util.spec_from_file_location(
        "plagiarism", "pipeline/8_plagiarism_detector.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_embeddings(n_sections: int, dim: int = 384) -> list[dict]:
    """Generate synthetic section dicts with random embeddings."""
    sections = []
    for i in range(n_sections):
        emb = np.random.randn(dim).astype(np.float32)
        emb = emb / np.linalg.norm(emb)  # normalize
        sections.append(
            {
                "segment_id": f"S{i + 1:03d}",
                "heading": f"Section {i + 1}",
                "embedding": emb.tolist(),
            }
        )
    return sections


def test_detect_no_plagiarism_random_embeddings():
    """Random embeddings should almost never exceed 0.85 threshold."""
    plag = load_plagiarism_detector()

    embeddings_by_wp = {
        "WP_001": _make_embeddings(5, dim=384),
        "WP_002": _make_embeddings(5, dim=384),
    }
    results = plag.detect_plagiarism(embeddings_by_wp, threshold=0.85)

    assert "WP_001" in results
    assert "WP_002" in results
    assert results["WP_001"]["total_sections"] == 5
    assert results["WP_002"]["total_sections"] == 5
    # Random 384-dim vectors almost certainly won't match at 0.85
    assert results["WP_001"]["flagged_count"] == 0
    assert results["WP_002"]["flagged_count"] == 0


def test_detect_plagiarism_identical_sections():
    """Identical embeddings across WPs should be flagged."""
    plag = load_plagiarism_detector()

    shared_emb = np.random.randn(384).astype(np.float32)
    shared_emb = (shared_emb / np.linalg.norm(shared_emb)).tolist()

    embeddings_by_wp = {
        "WP_A": [
            {"segment_id": "A_S001", "heading": "Intro", "embedding": shared_emb},
        ],
        "WP_B": [
            {"segment_id": "B_S001", "heading": "Intro", "embedding": shared_emb},
        ],
    }
    results = plag.detect_plagiarism(embeddings_by_wp, threshold=0.85)

    assert results["WP_A"]["flagged_count"] == 1
    assert results["WP_B"]["flagged_count"] == 1
    assert results["WP_A"]["plagiarism_rate"] == 1.0

    flag = results["WP_A"]["plagiarism_flags"][0]
    assert flag["matched_wp_id"] == "WP_B"
    assert flag["similarity"] >= 0.99


def test_no_self_comparison():
    """Sections within the same WP should NOT be compared."""
    plag = load_plagiarism_detector()

    shared_emb = np.random.randn(384).astype(np.float32)
    shared_emb = (shared_emb / np.linalg.norm(shared_emb)).tolist()

    embeddings_by_wp = {
        "WP_ONLY": [
            {"segment_id": "S001", "heading": "A", "embedding": shared_emb},
            {"segment_id": "S002", "heading": "B", "embedding": shared_emb},
        ],
    }
    results = plag.detect_plagiarism(embeddings_by_wp, threshold=0.85)

    # Single WP = no cross-WP comparison = no flags
    assert results["WP_ONLY"]["flagged_count"] == 0


def test_threshold_respects_value():
    """Test that a low threshold flags more pairs, high threshold flags fewer."""
    plag = load_plagiarism_detector()

    # Create two WPs with slightly correlated embeddings
    base = np.random.randn(384).astype(np.float32)
    base = base / np.linalg.norm(base)
    noise = np.random.randn(384).astype(np.float32) * 0.1
    similar = base + noise
    similar = (similar / np.linalg.norm(similar)).tolist()
    base = base.tolist()

    embeddings_by_wp = {
        "WP_X": [{"segment_id": "X_S001", "heading": "A", "embedding": base}],
        "WP_Y": [{"segment_id": "Y_S001", "heading": "A", "embedding": similar}],
    }

    results_low = plag.detect_plagiarism(embeddings_by_wp, threshold=0.5)
    results_high = plag.detect_plagiarism(embeddings_by_wp, threshold=0.99)

    # Low threshold should flag (the vectors are very similar due to small noise)
    assert results_low["WP_X"]["flagged_count"] >= results_high["WP_X"]["flagged_count"]


def test_save_plagiarism_results(tmp_path):
    plag = load_plagiarism_detector()

    results = {
        "WP_001": {
            "plagiarism_flags": [],
            "flagged_count": 0,
            "total_sections": 3,
            "plagiarism_rate": 0.0,
        },
    }
    saved_path = plag.save_plagiarism_results(results, str(tmp_path))
    assert Path(saved_path).exists()
    assert Path(saved_path).name == "plagiarism_results.json"

    data = json.loads(Path(saved_path).read_text(encoding="utf-8"))
    assert "WP_001" in data
    assert data["WP_001"]["total_sections"] == 3


def test_load_embeddings_from_step5(tmp_path):
    plag = load_plagiarism_detector()

    # Create a fake step5 JSON
    wp_dir = tmp_path / "WP_001_TestProject"
    wp_dir.mkdir()
    emb_data = [{"segment_id": "S001", "heading": "Intro", "embedding": [0.1] * 384}]
    (wp_dir / "step5_TestProject.json").write_text(
        json.dumps(emb_data), encoding="utf-8"
    )

    metadata = [{"id": "WP_001", "project_name": "TestProject"}]
    loaded = plag.load_embeddings_from_step5(str(tmp_path), metadata)

    assert "WP_001" in loaded
    assert len(loaded["WP_001"]) == 1
    assert loaded["WP_001"][0]["segment_id"] == "S001"
    assert len(loaded["WP_001"][0]["embedding"]) == 384
