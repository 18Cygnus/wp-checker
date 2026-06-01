import importlib.util


def load_classifier():
    spec = importlib.util.spec_from_file_location(
        "clf", "pipeline/7_section_classifier.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_classify_paragraph_returns_expected_keys():
    clf = load_classifier()
    result = clf.classify_paragraph(
        "The token supply is 100 billion with 25% allocated to investors."
    )
    assert "predicted_label" in result
    assert "confidence" in result
    assert "all_scores" in result
    assert result["predicted_label"] in clf.SECTION_LABELS
    assert 0.0 <= result["confidence"] <= 1.0


def test_classify_paragraph_returns_all_label_scores():
    clf = load_classifier()
    result = clf.classify_paragraph(
        "Total supply 100 billion tokens. 25% investor allocation. "
        "Vesting 12 months with 3 month cliff. Pre-sale price $0.0001."
    )
    # All 7 labels should have scores
    assert len(result["all_scores"]) == len(clf.SECTION_LABELS)
    assert all(label in result["all_scores"] for label in clf.SECTION_LABELS)
    # Scores should sum to ~1.0 (softmax)
    total = sum(result["all_scores"].values())
    assert 0.95 <= total <= 1.05


def test_build_enriched_md_adds_comments():
    clf = load_classifier()
    sections = [
        {
            "segment_id": "WP_019_S001",
            "heading": "Tokenomics",
            "heading_level": 2,
            "body": "Token supply is 100 billion.",
            "predicted_label": "tokenomics",
            "confidence": 0.91,
        }
    ]
    enriched = clf.build_step4_md(sections)
    assert "<!-- section_label: tokenomics | confidence: 0.91 | step: 4 -->" in enriched
    assert "## Tokenomics" in enriched
