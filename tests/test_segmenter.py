import importlib.util
from pathlib import Path


def load_segmenter():
    spec = importlib.util.spec_from_file_location(
        "segmenter", "pipeline/2_segmenter.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SAMPLE_MD = """\
## Abstract

This is the abstract paragraph about blockchain.
It has multiple sentences here.

## 1. Introduction

Background context about the problem domain.
More sentences here to exceed minimum length requirement.

## 2. Tokenomics

Token supply is 100 billion on BNB Chain.
Distribution is 25% to investors and 20% to team.
"""


def test_segment_extracts_sections():
    seg = load_segmenter()
    sections = seg.segment_markdown(SAMPLE_MD, wp_id="WP_TEST")
    assert len(sections) == 3
    assert sections[0]["heading"] == "Abstract"
    assert sections[1]["heading"] == "1. Introduction"
    assert sections[2]["heading"] == "2. Tokenomics"


def test_segment_assigns_para_ids():
    seg = load_segmenter()
    sections = seg.segment_markdown(SAMPLE_MD, wp_id="WP_TEST")
    assert sections[0]["segment_id"] == "WP_TEST_S001"
    assert sections[1]["segment_id"] == "WP_TEST_S002"
    assert sections[2]["segment_id"] == "WP_TEST_S003"


def test_segment_annotates_md_output():
    seg = load_segmenter()
    sections = seg.segment_markdown(SAMPLE_MD, wp_id="WP_TEST")
    enriched = seg.build_enriched_md(sections)
    assert "<!-- segment_id: WP_TEST_S001 | heading: Abstract | step: 2 -->" in enriched
    assert "## Abstract" in enriched


def test_segment_pdf_result(tmp_path):
    seg = load_segmenter()
    step1_path = Path("output_md") / "WP_019_Canton" / "step1_Canton.md"
    if not step1_path.exists():
        import pytest; pytest.skip("Run extractor first to generate step1_Canton.md")
    result = seg.segment_file(str(step1_path), wp_id="WP_019",
                               project_name="Canton",
                               output_dir=str(tmp_path))
    assert result["status"] == "ok"
    assert result["section_count"] >= 3
    assert Path(result["md_path"]).parent.name == "WP_019_Canton"
    assert Path(result["md_path"]).name == "step2_Canton.md"
