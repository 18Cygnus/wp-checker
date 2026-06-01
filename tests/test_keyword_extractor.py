import importlib.util


def load_kw():
    spec = importlib.util.spec_from_file_location(
        "kw", "pipeline/3_keyword_extractor.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CORPUS = [
    "bitcoin blockchain consensus proof of work distributed ledger",
    "tokenomics supply allocation vesting investor roadmap",
    "ethereum smart contract solidity evm defi protocol",
]


def test_fit_tfidf_returns_vectorizer():
    kw = load_kw()
    vec = kw.fit_tfidf(CORPUS)
    assert vec is not None
    assert hasattr(vec, "transform")


def test_extract_keywords_returns_list():
    kw = load_kw()
    vec = kw.fit_tfidf(CORPUS)
    keywords = kw.extract_keywords(vec, CORPUS[0], top_n=5)
    assert isinstance(keywords, list)
    assert len(keywords) <= 5
    assert all(isinstance(k, str) for k in keywords)


def test_extract_keywords_top_terms_relevant():
    kw = load_kw()
    vec = kw.fit_tfidf(CORPUS)
    keywords = kw.extract_keywords(vec, CORPUS[1], top_n=10)
    assert "tokenomics" in keywords or "investor" in keywords


def test_extract_ner_entities():
    kw = load_kw()
    text = "Satoshi Nakamoto published Bitcoin in 2008 in the United States."
    entities = kw.extract_ner_entities(text)
    assert isinstance(entities, list)
    assert len(entities) >= 1
    assert all("text" in e and "label" in e for e in entities)
