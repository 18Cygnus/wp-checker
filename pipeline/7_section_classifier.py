"""
7_section_classifier.py — Section classification (fine-tuned RoBERTa).

Uses fine-tuned RoBERTa checkpoint for section classification.
Hardware note: ~0.5GB VRAM.
"""

import logging
import os
from pathlib import Path

import torch

from pipeline import save_step_md

logger = logging.getLogger(__name__)

# ── Zero-shot config (13 labels) ─────────────────────────────────────────

SECTION_LABELS = [
    "project overview",
    "problem statement",
    "technical architecture",
    "tokenomics",
    "token distribution",
    "roadmap",
    "team and advisors",
    "governance",
    "security and audit",
    "use cases and ecosystem",
    "risk and disclaimer",
    "legal and compliance",
    "market analysis",
]

# ── Module-level state ────────────────────────────────────────────────────

_zs_classifier = None  # lazy-loaded zero-shot pipeline
_ft_classifier = None  # lazy-loaded SectionClassifier
_current_mode = "zero-shot"  # default mode
_ft_checkpoint = None  # checkpoint path for fine-tuned mode

DEFAULT_CHECKPOINT = "models/roberta-finetuned-v6-aug"


def set_mode(mode: str, checkpoint: str | None = None):
    """Set the fine-tuned checkpoint for subsequent calls."""
    global _ft_checkpoint
    if checkpoint is not None:
        _ft_checkpoint = checkpoint
    elif _ft_checkpoint is None:
        _ft_checkpoint = DEFAULT_CHECKPOINT
    logger.info(f"Section classifier checkpoint: {_ft_checkpoint}")


def _get_ft_classifier():
    """Lazy-load fine-tuned RoBERTa classifier."""
    global _ft_classifier
    if _ft_classifier is None:
        from pipeline.finetune.inference import SectionClassifier

        checkpoint = _ft_checkpoint or DEFAULT_CHECKPOINT
        _ft_classifier = SectionClassifier(checkpoint)
        logger.info(f"Fine-tuned classifier loaded from {checkpoint}")
    return _ft_classifier


def classify_paragraph(text: str, mode: str | None = None) -> dict:
    """Classify a text paragraph into a section label.

    Args:
        text: Clean paragraph text (markdown stripped).
        mode: Ignored, kept for backward compatibility.

    Returns:
        {"predicted_label": str, "confidence": float, "all_scores": dict}
    """
    clf = _get_ft_classifier()
    return clf.predict(text)


def build_step4_md(sections: list[dict]) -> str:
    """Build enriched markdown with classification annotations (step 4).

    Expects each section dict to have 'predicted_label' and 'confidence'
    added by classify_sections().
    """
    lines = []
    for sec in sections:
        prefix = "#" * sec.get("heading_level", 2)
        lines.append(f"{prefix} {sec['heading']}")
        if "predicted_label" in sec:
            lines.append(
                f"<!-- section_label: {sec['predicted_label']} | "
                f"confidence: {sec['confidence']} | step: 4 -->"
            )
        lines.append("")
        lines.append(sec["body"])
        lines.append("")
    return "\n".join(lines)


def classify_sections(sections: list[dict], mode: str | None = None) -> list[dict]:
    """Run classification on all sections, add results in-place.

    Args:
        sections: List of section dicts (must have 'clean_text' from preprocessor).
        mode: Ignored, kept for backward compatibility.

    Returns:
        Same list with 'predicted_label', 'confidence', 'all_scores' added.
    """
    clf = _get_ft_classifier()
    texts = []
    for s in sections:
        heading = s.get("heading", "")
        body = s.get("clean_text") or s.get("body", "")
        texts.append(f"{heading}\n{body}" if heading and body else (heading or body))

    results = clf.predict_batch(texts)
    for section, result in zip(sections, results):
        section.update(result)
    return sections


def classify_file(
    step2_md_path: str,
    sections: list[dict],
    wp_id: str,
    project_name: str,
    output_dir: str = "output_md",
    mode: str | None = None,
) -> dict:
    """Classify all sections and save step4_{project_name}.md.

    Args:
        step2_md_path: Path to step2 .md (used for reference only).
        sections: Sections list from segmenter + preprocessor.
        wp_id: Whitepaper ID.
        project_name: Short project name.
        output_dir: Directory to write step4 output.
        mode: Override module-level mode ("zero-shot" or "fine-tuned").

    Returns:
        dict with status, md_path, sections (with labels added).
    """
    result = {
        "wp_id": wp_id,
        "md_path": None,
        "sections": sections,
        "status": "ok",
        "error": None,
    }
    try:
        classify_sections(sections, mode=mode)
        enriched = build_step4_md(sections)
        md_path = save_step_md(
            wp_id, project_name, enriched, step=4, output_dir=output_dir
        )
        result["md_path"] = md_path
    except Exception as e:
        logger.error(f"Classification failed for {wp_id}: {e}")
        result.update({"status": "error", "error": str(e)})
    return result
