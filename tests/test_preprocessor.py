import importlib.util


def load_preprocessor():
    spec = importlib.util.spec_from_file_location(
        "preprocessor", "pipeline/4_preprocessor.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_strip_markdown_removes_comments():
    pre = load_preprocessor()
    text = "<!-- segment_id: WP_001_S001 | step: 2 -->\n\nToken supply is 100 billion."
    result = pre.strip_markdown(text)
    assert "<!--" not in result
    assert "Token supply is 100 billion." in result


def test_strip_markdown_removes_table_pipes():
    pre = load_preprocessor()
    text = "| Column A | Column B |\n|---|---|\n| val1 | val2 |"
    result = pre.strip_markdown(text)
    assert "|" not in result


def test_clean_text_lowercases_and_removes_punct():
    pre = load_preprocessor()
    result = pre.clean_text("Hello, World! This is a TEST.")
    assert result == result.lower()
    assert "," not in result and "!" not in result


def test_preprocess_sections_returns_tokens_per_section():
    pre = load_preprocessor()
    sections = [
        {"segment_id": "WP_001_S001", "heading": "Tokenomics",
         "body": "Token supply is 100 billion on BNB Chain BEP-20."},
    ]
    result = pre.preprocess_sections(sections)
    assert result[0]["segment_id"] == "WP_001_S001"
    assert isinstance(result[0]["tokens"], list)
    assert len(result[0]["tokens"]) > 0
    assert "token" in result[0]["tokens"]
