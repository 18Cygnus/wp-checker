"""
2_preprocessor.py — Clean and tokenize section text for NLP downstream.

Input: sections list from 7_segmenter.py
Output: same list with added 'tokens' and 'clean_text' fields per section.

Note: This step does NOT produce a step3 .md file — it enriches the
sections data structure consumed by keyword_extractor and classifier.

Flaw #6 fix: added fix_encoding_artifacts() and fix_spaced_text() to handle
Docling PDF extraction artifacts before standard cleaning.
"""

import re
import logging

import spacy

logger = logging.getLogger(__name__)

try:
    _nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
except OSError:
    _nlp = None
    logger.warning("spaCy model not found. Run: python -m spacy download en_core_web_sm")


# --- Flaw #6: Encoding artifact mapping ---
ENCODING_FIXES = {
    "\u017f": "(",     # ſ (long s) → opening paren
    "\u0180": ")",     # ƀ (b-bar) → closing paren
    "\u026a": "i",     # ɪ (small cap I)
    "\u0269": "l",     # ɩ (iota) → l
    "\u0131": "i",     # ı (dotless i)
    "\u0142": "l",     # ł (l-stroke)
    "\u2019": "'",     # right single quote → apostrophe
    "\u2018": "'",     # left single quote → apostrophe
    "\u201c": '"',     # left double quote
    "\u201d": '"',     # right double quote
    "\u2013": "-",     # en dash → hyphen
    "\u2014": "-",     # em dash → hyphen
}


def fix_encoding_artifacts(text: str) -> str:
    """Replace known PDF encoding artifacts with correct characters."""
    for bad, good in ENCODING_FIXES.items():
        text = text.replace(bad, good)
    return text


def fix_spaced_text(text: str) -> str:
    """Fix text where characters are incorrectly space-separated by PDF extraction.

    Detects sequences of 3+ single-character "words" separated by spaces,
    which indicates a spaced-out extraction artifact.

    Example: 'w wa lled garden' -> 'walled garden'
    """
    def _collapse(m):
        return m.group(0).replace(" ", "")

    # Match 3+ consecutive single-char tokens (e.g., "w a l l e d")
    text = re.sub(r'(?:(?<=\s)|(?<=^))(\w\s){3,}\w(?=\s|$)', _collapse, text)
    return text


def strip_markdown(text: str) -> str:
    """Remove markdown and HTML comment syntax, leaving plain text."""
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    text = re.sub(r'\|[^\n]+\|', ' ', text)
    text = re.sub(r'\|', ' ', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'`[^`]+`', ' ', text)
    text = re.sub(r'[*_]{1,3}', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clean_text(text: str) -> str:
    """Lowercase and remove punctuation, keeping alphanumeric and spaces."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s\-]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def tokenize(text: str) -> list[str]:
    """Lemmatize and remove stopwords using spaCy."""
    if _nlp is None:
        return [t for t in text.split() if len(t) > 2]

    doc = _nlp(text)
    tokens = [
        token.lemma_.lower()
        for token in doc
        if not token.is_stop
        and not token.is_punct
        and not token.is_space
        and len(token.lemma_) > 2
    ]
    return tokens


def preprocess_sections(sections: list[dict]) -> list[dict]:
    """Add 'clean_text' and 'tokens' to each section dict.

    Args:
        sections: List of section dicts from segmenter (must have 'body' key).

    Returns:
        Same list with 'clean_text' and 'tokens' added in-place.
    """
    for section in sections:
        raw = section.get("body", "")

        # Flaw #6: fix extraction artifacts before standard cleaning
        raw = fix_encoding_artifacts(raw)
        raw = fix_spaced_text(raw)

        stripped = strip_markdown(raw)
        cleaned = clean_text(stripped)
        section["clean_text"] = cleaned
        section["tokens"] = tokenize(cleaned)
    return sections
