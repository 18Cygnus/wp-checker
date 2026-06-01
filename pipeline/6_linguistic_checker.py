"""
6_linguistic_checker.py — Spelling-oriented linguistic check per section.

Uses pyspellchecker with a dataset-derived domain lexicon so project names,
ticker symbols, and Web3 terms are not overcounted as spelling mistakes.

Input:  raw body text per section (NOT clean_text — needs original casing/punctuation)
Output per section: error_count, errors list
Aggregate per WP:  total_errors, total_words, error_rate, error_categories

Usage:
    from pipeline.6_linguistic_checker import check_sections, check_file
    check_sections(sections)                          # in-place, adds error fields
    result = check_file("WP_019", sections, "out")    # check + save JSON
"""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_tool = None
_backend = None
_domain_lexicon = None

DOMAIN_LEXICON_PATH = Path(__file__).with_name("spellchecker_domain_lexicon.json")
WORD_PATTERN = re.compile(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b")


def _init_checker():
    """Initialize the pyspellchecker backend with domain lexicon support."""
    global _tool, _backend

    if _tool is not None:
        return

    try:
        from spellchecker import SpellChecker

        _tool = SpellChecker()
        _backend = "spellchecker"
        lexicon = _load_domain_lexicon()
        if lexicon:
            _tool.word_frequency.load_words(sorted(lexicon))
        logger.info(
            "Linguistic checker: using pyspellchecker with %d domain terms",
            len(lexicon),
        )
        return
    except ImportError:
        pass

    raise ImportError(
        "No linguistic checker available. Install:\n"
        "  pip install pyspellchecker"
    )


def _count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def _normalize_word(word: str) -> str:
    """Normalize a token for lexicon and spellchecker lookups."""
    return re.sub(r"[^A-Za-z]", "", word).lower()


def _load_domain_lexicon() -> set[str]:
    """Load the data-driven domain whitelist once and cache it."""
    global _domain_lexicon

    if _domain_lexicon is not None:
        return _domain_lexicon

    if not DOMAIN_LEXICON_PATH.exists():
        logger.warning("Domain lexicon missing at %s", DOMAIN_LEXICON_PATH)
        _domain_lexicon = set()
        return _domain_lexicon

    data = json.loads(DOMAIN_LEXICON_PATH.read_text(encoding="utf-8"))
    words: set[str] = set()
    for value in data.values():
        if not isinstance(value, list):
            continue
        for item in value:
            normalized = _normalize_word(item)
            if normalized:
                words.add(normalized)

    _domain_lexicon = words
    return _domain_lexicon


def _iter_spellchecker_candidates(text: str) -> list[tuple[str, str]]:
    """Extract candidate tokens, skipping domain words and code identifiers."""
    domain_lexicon = _load_domain_lexicon()
    candidates: list[tuple[str, str]] = []

    for word in WORD_PATTERN.findall(text):
        if "'" in word:
            continue
        if word.isupper() or not word[0].islower():
            continue
        if any(char.isupper() for char in word[1:]):
            continue

        normalized = _normalize_word(word)
        if len(normalized) <= 3:
            continue
        if normalized in domain_lexicon:
            continue

        candidates.append((word, normalized))

    return candidates


def _check_with_spellchecker(text: str) -> list[dict]:
    """Check text using pyspellchecker, excluding known domain terms."""
    candidates = _iter_spellchecker_candidates(text)
    if not candidates:
        return []

    misspelled = _tool.unknown({normalized for _, normalized in candidates})
    errors = []
    for word, normalized in candidates:
        if normalized in misspelled:
            errors.append(
                {
                    "message": f"Possible spelling mistake: '{word}'",
                    "offset": 0,
                    "length": len(word),
                    "rule_id": "SPELLING",
                    "category": "SPELLING",
                    "context": "",
                    "suggestions": [],
                }
            )
    return errors


def check_sections(sections: list[dict]) -> list[dict]:
    """Add linguistic error fields to each section dict in-place.

    Uses raw 'body' text (not clean_text) to preserve original
    casing and punctuation for accurate grammar checking.

    Adds to each section:
        - error_count: int
        - errors: list of error dicts

    Args:
        sections: List of section dicts with 'body' field.

    Returns:
        Same list with error fields added.
    """
    _init_checker()

    for section in sections:
        body = section.get("body", "").strip()
        if not body or len(body) < 20:
            section["error_count"] = 0
            section["errors"] = []
            continue

        errors = _check_with_spellchecker(body)
        section["error_count"] = len(errors)
        section["errors"] = errors

    logger.info(
        f"Checked {len(sections)} sections ({_backend}), "
        f"total errors: {sum(s.get('error_count', 0) for s in sections)}"
    )
    return sections


def check_file(
    wp_id: str,
    sections: list[dict],
    output_dir: str = "output_md",
    project_name: str = "",
) -> dict:
    """Run linguistic checks and save step6 JSON.

    Args:
        wp_id: Whitepaper ID (e.g. "WP_019").
        sections: List of section dicts (must have 'body' field).
        output_dir: Base output directory.
        project_name: Project name for folder/file naming.

    Returns:
        Dict with status, total_errors, total_words, error_rate,
        error_categories, json_path.
    """
    try:
        check_sections(sections)

        total_errors = sum(s.get("error_count", 0) for s in sections)
        total_words = sum(_count_words(s.get("body", "")) for s in sections)
        error_rate = round(
            (total_errors / total_words * 1000) if total_words > 0 else 0.0, 2
        )

        # Aggregate error categories
        error_categories: dict[str, int] = {}
        for section in sections:
            for err in section.get("errors", []):
                cat = err.get("category", "UNKNOWN")
                error_categories[cat] = error_categories.get(cat, 0) + 1

        # Save JSON output
        output_data = {
            "wp_id": wp_id,
            "backend": _backend,
            "total_errors": total_errors,
            "total_words": total_words,
            "error_rate": error_rate,
            "error_categories": error_categories,
            "sections": [
                {
                    "section_id": s.get("segment_id", ""),
                    "heading": s.get("heading", ""),
                    "error_count": s.get("error_count", 0),
                    "word_count": _count_words(s.get("body", "")),
                    "errors": s.get("errors", []),
                }
                for s in sections
            ],
        }

        folder = Path(output_dir) / f"{wp_id}_{project_name}"
        folder.mkdir(parents=True, exist_ok=True)
        json_path = folder / f"step6_{project_name}.json"
        json_path.write_text(
            json.dumps(output_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info(
            f"  {wp_id}: {total_errors} errors in {total_words} words "
            f"(rate: {error_rate}/1000) -> {json_path}"
        )
        return {
            "status": "ok",
            "total_errors": total_errors,
            "total_words": total_words,
            "error_rate": error_rate,
            "error_categories": error_categories,
            "json_path": str(json_path),
        }

    except Exception as e:
        logger.error(f"  {wp_id}: linguistic check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "total_errors": 0,
        }
