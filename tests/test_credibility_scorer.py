"""Tests for pipeline/credibility_scorer.py"""
import importlib.util, sys, os

# Load module directly
spec = importlib.util.spec_from_file_location(
    "credibility_scorer",
    os.path.join(os.path.dirname(__file__), "..", "pipeline", "credibility_scorer.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _make_section_labels(label_counts: dict) -> list[dict]:
    """Helper to build section_labels list from {label: count} dict."""
    labels = []
    for lbl, cnt in label_counts.items():
        for _ in range(cnt):
            labels.append({"heading": f"H-{lbl}", "label": lbl})
    return labels


class TestLabelDistribution:
    def test_empty(self):
        dist = mod.compute_label_distribution([])
        assert all(v == 0.0 for v in dist.values())

    def test_single_label(self):
        labels = [{"heading": "H", "label": "tokenomics"}] * 5
        dist = mod.compute_label_distribution(labels)
        assert dist["tokenomics"] == 1.0
        assert dist["roadmap"] == 0.0

    def test_mixed(self):
        labels = _make_section_labels({"tokenomics": 2, "roadmap": 3})
        dist = mod.compute_label_distribution(labels)
        assert abs(dist["tokenomics"] - 0.4) < 1e-6
        assert abs(dist["roadmap"] - 0.6) < 1e-6


class TestProfileInference:
    def test_technical_pattern(self):
        labels = _make_section_labels({
            "technical architecture": 20,
            "project overview": 3,
            "security and audit": 5,
        })
        dist = mod.compute_label_distribution(labels)
        profile, confidence, sims = mod.infer_profile(dist, len(labels))
        assert profile == "technical_only"
        assert confidence == "high"
        assert sims["technical_only"] > sims["investor_oriented"]

    def test_short_document(self):
        labels = _make_section_labels({"tokenomics": 2, "roadmap": 1})
        dist = mod.compute_label_distribution(labels)
        profile, confidence, _ = mod.infer_profile(dist, 3)
        assert profile == "undetermined"
        assert confidence == "very_low"

    def test_confidence_levels(self):
        labels = _make_section_labels({"tokenomics": 7, "project overview": 3})
        dist = mod.compute_label_distribution(labels)

        _, c1, _ = mod.infer_profile(dist, 8)
        assert c1 == "low"

        _, c2, _ = mod.infer_profile(dist, 15)
        assert c2 == "medium"

        _, c3, _ = mod.infer_profile(dist, 25)
        assert c3 == "high"


class TestCoverageScore:
    def test_full_coverage(self):
        dist = {lbl: 0.05 for lbl in mod.ALL_LABELS}
        score = mod.compute_coverage_score(dist, "hybrid")
        assert score == 1.0

    def test_no_coverage(self):
        dist = {lbl: 0.0 for lbl in mod.ALL_LABELS}
        score = mod.compute_coverage_score(dist, "technical_only")
        assert score == 0.0

    def test_core_only(self):
        dist = {lbl: 0.0 for lbl in mod.ALL_LABELS}
        for lbl in mod.COVERAGE_TIERS["technical_only"]["core"]:
            dist[lbl] = 0.3
        score = mod.compute_coverage_score(dist, "technical_only")
        assert score > 0.3  # core labels have highest weight


class TestSignals:
    def test_plagiarism_score(self):
        assert mod.compute_plagiarism_score(0.0) == 1.0
        assert mod.compute_plagiarism_score(1.0) == 0.0
        assert abs(mod.compute_plagiarism_score(0.5) - 0.5) < 1e-6

    def test_linguistic_score(self):
        assert mod.compute_linguistic_score(0.0) == 1.0
        assert mod.compute_linguistic_score(50.0) == 0.0
        assert mod.compute_linguistic_score(25.0) == 0.5

    def test_keyword_relevance_empty(self):
        assert mod.compute_keyword_relevance(None) == 0.5
        assert mod.compute_keyword_relevance([]) == 0.5

    def test_keyword_relevance_values(self):
        assert mod.compute_keyword_relevance([0.5, 0.5], 1.0) == 0.5
        assert mod.compute_keyword_relevance([1.0, 1.0], 1.0) == 1.0

    def test_content_balance(self):
        labels = _make_section_labels({"technical architecture": 8, "tokenomics": 2})
        score = mod.compute_content_balance(labels)
        assert score == 1.0  # all substantive

    def test_content_balance_heavy_legal(self):
        labels = _make_section_labels({"risk and legal": 8, "tokenomics": 2})
        score = mod.compute_content_balance(labels)
        assert score < 0.5  # legal-heavy penalty


class TestRedFlags:
    def test_missing_all_core(self):
        dist = {lbl: 0.0 for lbl in mod.ALL_LABELS}
        dist["market analysis"] = 1.0
        flags = mod.generate_red_flags("hybrid", dist, 0.0, 0.0, 20, 0.8)
        assert any("prioritas utama" in f for f in flags)

    def test_high_plagiarism(self):
        dist = {lbl: 0.09 for lbl in mod.ALL_LABELS}
        flags = mod.generate_red_flags("hybrid", dist, 0.6, 0.0, 20, 0.8)
        assert any("plagiarisme" in f for f in flags)

    def test_short_document(self):
        dist = {lbl: 0.0 for lbl in mod.ALL_LABELS}
        flags = mod.generate_red_flags("hybrid", dist, 0.0, 0.0, 3, 0.8)
        assert any("terlalu sedikit" in f for f in flags)


class TestScoreWhitepaper:
    def test_good_wp(self):
        labels = _make_section_labels({
            "technical architecture": 15,
            "tokenomics": 8,
            "use cases and ecosystem": 10,
            "project overview": 5,
            "roadmap": 3,
            "security and audit": 2,
            "governance": 2,
        })
        wp = {
            "wp_id": "WP_TEST",
            "project_name": "TestCoin",
            "section_labels": labels,
            "plagiarism_rate": 0.05,
            "linguistic_error_rate": 3.0,
            "tfidf_scores": [0.3, 0.25, 0.2],
        }
        result = mod.score_whitepaper(wp, corpus_keyword_max=0.5)
        assert result["credibility_label"] == "good"
        assert result["credibility_score"] >= 70
        assert result["profile_label"] in ("technical_only", "hybrid")

    def test_poor_wp(self):
        labels = _make_section_labels({"risk and legal": 3})
        wp = {
            "wp_id": "WP_BAD",
            "project_name": "ScamCoin",
            "section_labels": labels,
            "plagiarism_rate": 0.6,
            "linguistic_error_rate": 40.0,
        }
        result = mod.score_whitepaper(wp)
        assert result["credibility_label"] == "poor"
        assert result["credibility_score"] < 40
        assert len(result["red_flags"]) > 0


class TestScoreCorpus:
    def test_corpus_scoring(self):
        wps = [
            {
                "wp_id": "WP_A",
                "project_name": "A",
                "section_labels": _make_section_labels({
                    "technical architecture": 10, "tokenomics": 5,
                }),
                "plagiarism_rate": 0.0,
                "linguistic_error_rate": 2.0,
            },
            {
                "wp_id": "WP_B",
                "project_name": "B",
                "section_labels": _make_section_labels({"risk and legal": 3}),
                "plagiarism_rate": 0.5,
                "linguistic_error_rate": 30.0,
            },
        ]
        results = mod.score_corpus(wps)
        assert len(results) == 2
        assert results[0]["credibility_score"] > results[1]["credibility_score"]
