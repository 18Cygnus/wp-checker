"""Heuristics to reject uploaded PDFs that are unlikely to be whitepapers.

This is a conservative gate for uploads, not a replacement for credibility
scoring. It combines cheap document-structure signals with section-label
coverage from the classifier. The goal is to reject obvious non-whitepaper
documents while keeping short litepapers accepted when they still expose clear
whitepaper cues.
"""

from __future__ import annotations

import re
from typing import Any


JSONDict = dict[str, Any]

ACCEPT_THRESHOLD = 5
MIN_CONFIDENCE = 0.35

WHITEPAPER_TEXT_HINTS = (
    "whitepaper",
    "litepaper",
    "tokenomics",
    "token distribution",
    "token supply",
    "roadmap",
    "governance",
    "staking",
    "validator",
    "consensus",
    "mainnet",
    "testnet",
    "blockchain",
    "protocol",
    "smart contract",
    "technical architecture",
    "architecture",
    "ecosystem",
    "use case",
    "treasury",
    "audit",
    "defi",
)

WHITEPAPER_HEADING_HINTS = (
    "abstract",
    "introduction",
    "problem statement",
    "project overview",
    "technical architecture",
    "architecture",
    "tokenomics",
    "token distribution",
    "roadmap",
    "governance",
    "security",
    "audit",
    "use cases",
    "ecosystem",
    "risk",
    "legal",
    "team",
    "advisors",
)

NON_WHITEPAPER_HINTS = (
    "invoice",
    "receipt",
    "purchase order",
    "bill to",
    "statement of account",
    "bank statement",
    "financial statement",
    "annual report",
    "quarterly report",
    "user manual",
    "installation guide",
    "curriculum vitae",
    "resume",
    "syllabus",
    "lesson plan",
    "meeting minutes",
    "privacy policy",
    "terms of service",
    "employment contract",
    "catalog",
    "brochure",
    "skripsi",
    "tesis",
    "journal article",
    "research article",
)

SUBSTANTIVE_WHITEPAPER_LABELS = {
    "project overview",
    "problem statement",
    "technical architecture",
    "tokenomics",
    "roadmap",
    "governance",
    "security and audit",
    "use cases and ecosystem",
}


def _normalize_text(text: str) -> str:
    lowered = (text or "").lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", lowered).strip()


def _find_hits(texts: list[str], terms: tuple[str, ...]) -> list[str]:
    haystack = "\n".join(_normalize_text(text) for text in texts if text)
    hits = []
    for term in terms:
        if re.search(rf"\b{re.escape(term)}\b", haystack):
            hits.append(term)
    return hits


def _extract_headings(markdown: str) -> list[str]:
    return [
        heading.strip()
        for heading in re.findall(r"^#{1,6}\s+(.+)$", markdown or "", re.MULTILINE)
        if heading.strip()
    ]


def assess_whitepaper_candidate(
    markdown: str,
    page_count: int,
    sections: list[JSONDict],
) -> JSONDict:
    """Return whether the uploaded document looks like a whitepaper.

    The gate is intentionally conservative. It only rejects when the document
    lacks whitepaper signals across structure, terminology, and classifier
    coverage, or when it strongly matches well-known non-whitepaper document
    types.
    """

    headings = _extract_headings(markdown)
    preview_text = (markdown or "")[:8000]
    text_hits = _find_hits([preview_text, *headings[:12]], WHITEPAPER_TEXT_HINTS)
    heading_hits = _find_hits(headings[:12], WHITEPAPER_HEADING_HINTS)
    negative_hits = _find_hits([preview_text, *headings[:12]], NON_WHITEPAPER_HINTS)

    predicted_labels = []
    confidences = []
    for section in sections:
        label = (section.get("predicted_label") or section.get("label") or "").strip().lower()
        confidence = float(section.get("confidence", 0.0) or 0.0)
        if label:
            predicted_labels.append(label)
            confidences.append(confidence)

    unique_gate_labels = sorted(
        {label for label in predicted_labels if label in SUBSTANTIVE_WHITEPAPER_LABELS}
    )
    high_conf_labels = sorted(
        {
            label
            for label, confidence in zip(predicted_labels, confidences)
            if label in SUBSTANTIVE_WHITEPAPER_LABELS and confidence >= MIN_CONFIDENCE
        }
    )
    avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

    section_count = len(sections)

    if section_count < 2 and len(text_hits) < 2 and len(heading_hits) < 2:
        return {
            "is_whitepaper": False,
            "score": 0,
            "reason": "Dokumen terlalu minim struktur whitepaper untuk dianalisis.",
            "signals": {
                "page_count": page_count,
                "section_count": section_count,
                "text_hits": text_hits,
                "heading_hits": heading_hits,
                "negative_hits": negative_hits,
                "unique_gate_labels": unique_gate_labels,
                "high_confidence_labels": high_conf_labels,
                "average_confidence": avg_confidence,
            },
        }

    if len(negative_hits) >= 2 and not text_hits and len(unique_gate_labels) < 2:
        return {
            "is_whitepaper": False,
            "score": 0,
            "reason": "Dokumen lebih mirip laporan atau formulir operasional daripada whitepaper.",
            "signals": {
                "page_count": page_count,
                "section_count": section_count,
                "text_hits": text_hits,
                "heading_hits": heading_hits,
                "negative_hits": negative_hits,
                "unique_gate_labels": unique_gate_labels,
                "high_confidence_labels": high_conf_labels,
                "average_confidence": avg_confidence,
            },
        }

    score = 0
    score += min(len(text_hits), 4)
    score += 2 if len(heading_hits) >= 2 else 1 if len(heading_hits) == 1 else 0
    score += 1 if section_count >= 3 else 0
    score += 1 if section_count >= 6 else 0
    score += 2 if len(unique_gate_labels) >= 2 else 0
    score += 1 if len(unique_gate_labels) >= 4 else 0
    score += 1 if avg_confidence >= 0.45 else 0
    score -= min(len(negative_hits), 4)

    is_whitepaper = score >= ACCEPT_THRESHOLD
    reason = (
        "Dokumen memiliki cukup sinyal struktur whitepaper."
        if is_whitepaper
        else "Struktur dan isi dokumen tidak cukup menyerupai whitepaper proyek."
    )

    return {
        "is_whitepaper": is_whitepaper,
        "score": score,
        "reason": reason,
        "signals": {
            "page_count": page_count,
            "section_count": section_count,
            "text_hits": text_hits,
            "heading_hits": heading_hits,
            "negative_hits": negative_hits,
            "unique_gate_labels": unique_gate_labels,
            "high_confidence_labels": high_conf_labels,
            "average_confidence": avg_confidence,
        },
    }