"""
3_keyword_extractor.py — TF-IDF keyword extraction + spaCy NER.

TF-IDF is fit on the full 45-WP corpus (corpus-level vectorizer).
NER extracts named entities (ORG, PRODUCT, MONEY, PERCENT, GPE).

Usage:
    vectorizer = fit_tfidf(corpus_texts)   # call once on all 45 WPs
    keywords = extract_keywords(vectorizer, doc_text, top_n=20)
    entities = extract_ner_entities(doc_text)
"""

import logging
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

_NER_LABELS = {"ORG", "PRODUCT", "MONEY", "PERCENT", "GPE", "PERSON"}

try:
    _nlp_ner = spacy.load("en_core_web_sm")
except OSError:
    _nlp_ner = None
    logger.warning("spaCy model not found. Run: python -m spacy download en_core_web_sm")


def fit_tfidf(corpus: list[str],
              max_features: int = 5000,
              ngram_range: tuple = (1, 2)) -> TfidfVectorizer:
    """Fit a TF-IDF vectorizer on the full corpus.

    Args:
        corpus: List of clean_text strings (one per WP).
        max_features: Vocabulary size cap.
        ngram_range: (min_n, max_n) for n-grams.

    Returns:
        Fitted TfidfVectorizer.
    """
    vectorizer = TfidfVectorizer(
        max_features=max_features,
        ngram_range=ngram_range,
        sublinear_tf=True,
    )
    vectorizer.fit(corpus)
    return vectorizer


def extract_keywords(vectorizer: TfidfVectorizer,
                     doc_text: str,
                     top_n: int = 20) -> list[str]:
    """Extract top-N keywords from a document using fitted TF-IDF.

    Args:
        vectorizer: Fitted TfidfVectorizer from fit_tfidf().
        doc_text: Clean text string of the document.
        top_n: Number of keywords to return.

    Returns:
        List of keyword strings sorted by TF-IDF score descending.
    """
    vec = vectorizer.transform([doc_text])
    feature_names = vectorizer.get_feature_names_out()
    scores = vec.toarray()[0]
    ranked = sorted(
        zip(feature_names, scores),
        key=lambda x: x[1],
        reverse=True,
    )
    return [word for word, score in ranked[:top_n] if score > 0]


def fit_tfidf_filtered(corpus: list[str],
                       max_features: int = 5000,
                       ngram_range: tuple = (1, 2)) -> TfidfVectorizer:
    """Fit a TF-IDF vectorizer with English stopwords filtered out.

    Produces a separate vectorizer used for the word-cloud display.
    The original fit_tfidf() is left unchanged so downstream pipeline
    steps that depend on it are not affected.

    Args:
        corpus: List of clean_text strings (one per WP).
        max_features: Vocabulary size cap.
        ngram_range: (min_n, max_n) for n-grams.

    Returns:
        Fitted TfidfVectorizer with stop_words="english".
    """
    vectorizer = TfidfVectorizer(
        max_features=max_features,
        ngram_range=ngram_range,
        sublinear_tf=True,
        stop_words="english",
    )
    vectorizer.fit(corpus)
    return vectorizer


def extract_keywords_stopword_scored(vectorizer: TfidfVectorizer,
                                     doc_text: str,
                                     top_n: int = 40) -> list[dict]:
    """Extract top-N keywords from a document, with stopwords filtered.

    Uses a vectorizer fitted with stop_words="english" so common English
    function words are excluded from the results.

    Args:
        vectorizer: Fitted TfidfVectorizer (from fit_tfidf_filtered()).
        doc_text: Clean text string of the document.
        top_n: Number of keywords to return.

    Returns:
        List of {"term": str, "score": float} sorted by score descending.
    """
    vec = vectorizer.transform([doc_text])
    feature_names = vectorizer.get_feature_names_out()
    scores = vec.toarray()[0]
    ranked = sorted(
        zip(feature_names, scores),
        key=lambda x: x[1],
        reverse=True,
    )
    return [
        {"term": term, "score": round(float(score), 4)}
        for term, score in ranked[:top_n]
        if score > 0
    ]


def extract_ner_entities(text: str) -> list[dict]:
    """Extract named entities from raw text using spaCy NER.

    Args:
        text: Raw or lightly cleaned text (not fully lowercased).

    Returns:
        List of {"text": str, "label": str} for relevant entity types.
    """
    if _nlp_ner is None:
        return []
    doc = _nlp_ner(text[:100_000])
    seen = set()
    entities = []
    for ent in doc.ents:
        if ent.label_ in _NER_LABELS:
            key = (ent.text.strip(), ent.label_)
            if key not in seen:
                seen.add(key)
                entities.append({"text": ent.text.strip(), "label": ent.label_})
    return entities
