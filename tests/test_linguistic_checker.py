import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch


def load_linguistic_checker():
    spec = importlib.util.spec_from_file_location(
        "linguistic", "pipeline/6_linguistic_checker.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_sections():
    return [
        {
            "segment_id": "WP_001_S001",
            "heading": "Abstract",
            "body": "This abstract contains blockchan as an intentional typo for testing.",
        },
        {
            "segment_id": "WP_001_S002",
            "heading": "Tokenomics",
            "body": "Token supply includes another blockchan typo to keep counts deterministic.",
        },
    ]


def test_check_sections_adds_error_fields():
    ling = load_linguistic_checker()
    ling._tool = None
    ling._backend = None
    ling._domain_lexicon = None

    mock_sc = MagicMock()
    mock_sc.unknown.return_value = {"blockchan"}

    ling._tool = mock_sc
    ling._backend = "spellchecker"

    sections = _make_sections()
    result = ling.check_sections(sections)

    assert len(result) == 2
    assert "error_count" in result[0]
    assert "errors" in result[0]
    assert result[0]["error_count"] == 1
    assert result[0]["errors"][0]["rule_id"] == "SPELLING"
    assert result[0]["errors"][0]["category"] == "SPELLING"


def test_check_sections_skips_short_body():
    ling = load_linguistic_checker()
    ling._tool = None
    ling._backend = None
    ling._domain_lexicon = None

    mock_sc = MagicMock()
    mock_sc.unknown.return_value = set()

    ling._tool = mock_sc
    ling._backend = "spellchecker"

    sections = [
        {"segment_id": "WP_001_S001", "heading": "Title", "body": "Short."},
    ]
    result = ling.check_sections(sections)

    assert result[0]["error_count"] == 0
    assert result[0]["errors"] == []
    mock_sc.unknown.assert_not_called()


def test_check_sections_empty_body():
    ling = load_linguistic_checker()
    ling._tool = None
    ling._backend = None
    ling._domain_lexicon = None

    mock_sc = MagicMock()
    ling._tool = mock_sc
    ling._backend = "spellchecker"

    sections = [
        {"segment_id": "WP_001_S001", "heading": "Empty", "body": ""},
    ]
    result = ling.check_sections(sections)

    assert result[0]["error_count"] == 0
    mock_sc.unknown.assert_not_called()


def test_check_file_saves_json(tmp_path):
    ling = load_linguistic_checker()
    ling._tool = None
    ling._backend = None
    ling._domain_lexicon = None

    mock_sc = MagicMock()
    mock_sc.unknown.return_value = {"blockchan"}

    ling._tool = mock_sc
    ling._backend = "spellchecker"

    sections = _make_sections()
    result = ling.check_file(
        "WP_001", sections, output_dir=str(tmp_path), project_name="TestProject"
    )

    assert result["status"] == "ok"
    assert result["total_errors"] == 2  # 1 error per section x 2 sections
    assert result["total_words"] > 0
    assert result["error_rate"] > 0
    assert "SPELLING" in result["error_categories"]

    json_path = Path(result["json_path"])
    assert json_path.exists()
    assert json_path.name == "step6_TestProject.json"
    assert json_path.parent.name == "WP_001_TestProject"

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["wp_id"] == "WP_001"
    assert data["backend"] == "spellchecker"
    assert len(data["sections"]) == 2


def test_error_rate_calculation():
    ling = load_linguistic_checker()
    ling._tool = None
    ling._backend = None
    ling._domain_lexicon = None

    mock_sc = MagicMock()
    mock_sc.unknown.return_value = {"blockchan"}

    ling._tool = mock_sc
    ling._backend = "spellchecker"

    sections = [
        {
            "segment_id": "WP_001_S001",
            "heading": "Content",
            "body": ("word " * 98) + "blockchan blockchan",
        },
    ]
    result = ling.check_file("WP_001", sections, output_dir=".", project_name="Test")

    # 2 errors / 100 words * 1000 = 20.0 per 1000 words
    assert result["error_rate"] == 20.0

    # Cleanup
    import shutil

    shutil.rmtree("WP_001_Test", ignore_errors=True)


def test_check_file_error_returns_status():
    ling = load_linguistic_checker()
    ling._tool = None
    ling._backend = None
    ling._domain_lexicon = None

    # Force _init_checker to fail
    with patch.object(ling, "_init_checker", side_effect=ImportError("no checker")):
        sections = _make_sections()
        result = ling.check_file(
            "WP_001", sections, output_dir="/nonexistent", project_name="Test"
        )

        assert result["status"] == "error"
        assert "no checker" in result["error"]
        assert result["total_errors"] == 0


def test_spellchecker_domain_lexicon_filters_known_false_positives():
    ling = load_linguistic_checker()
    ling._tool = None
    ling._backend = None
    ling._domain_lexicon = None

    mock_sc = MagicMock()
    mock_sc.unknown.return_value = {
        "blockchain",
        "validator",
        "onchain",
        "analytics",
        "bitcoin",
        "pieusd",
        "middleware",
        "microtransactions",
        "lamports",
        "leaderboard",
        "contactless",
        "anonymized",
        "plaintext",
        "trustable",
        "prosocial",
        "investable",
        "tokenize",
        "bytecode",
        "merkle",
        "queryable",
        "counterparty",
        "trustlessness",
        "zeroknowledge",
        "upgradability",
        "supermajority",
        "lightclient",
        "nilify",
        "whitelisted",
        "guid",
        "ftnscan",
        "fastexlabs",
        "crossborder",
        "highperformance",
        "realworld",
        "communitydriven",
        "escrowed",
        "convolutional",
        "weth",
        "tinycents",
        "unstake",
        "workarounds",
        "blockchan",
        "createpair",
        "rentpayer",
        "getinboundnonce",
    }

    ling._tool = mock_sc
    ling._backend = "spellchecker"

    sections = [
        {
            "segment_id": "WP_001_S001",
            "heading": "Intro",
            "body": "The blockchain validator runs onchain analytics with middleware for microtransactions, lamports, a leaderboard, contactless flows, anonymized plaintext data, trustable prosocial behavior, investable assets, tokenize support, bytecode merkle queryable counterparty trustlessness zeroknowledge upgradability supermajority lightclient nilify whitelisted guid ftnscan fastexlabs crossborder highperformance realworld communitydriven escrowed convolutional weth tinycents unstake workarounds, and createPair rentPayer getInboundNonce hooks, but blockchan is still wrong.",
        },
    ]
    result = ling.check_sections(sections)

    assert result[0]["error_count"] == 1
    assert result[0]["errors"][0]["rule_id"] == "SPELLING"
    assert "blockchan" in result[0]["errors"][0]["message"]

    queried_words = mock_sc.unknown.call_args[0][0]
    assert "blockchan" in queried_words
    assert "blockchain" not in queried_words
    assert "validator" not in queried_words
    assert "onchain" not in queried_words
    assert "analytics" not in queried_words
    assert "bitcoin" not in queried_words
    assert "pieusd" not in queried_words
    assert "middleware" not in queried_words
    assert "microtransactions" not in queried_words
    assert "lamports" not in queried_words
    assert "leaderboard" not in queried_words
    assert "contactless" not in queried_words
    assert "anonymized" not in queried_words
    assert "plaintext" not in queried_words
    assert "trustable" not in queried_words
    assert "prosocial" not in queried_words
    assert "investable" not in queried_words
    assert "tokenize" not in queried_words
    assert "bytecode" not in queried_words
    assert "merkle" not in queried_words
    assert "queryable" not in queried_words
    assert "counterparty" not in queried_words
    assert "trustlessness" not in queried_words
    assert "zeroknowledge" not in queried_words
    assert "upgradability" not in queried_words
    assert "supermajority" not in queried_words
    assert "lightclient" not in queried_words
    assert "nilify" not in queried_words
    assert "whitelisted" not in queried_words
    assert "guid" not in queried_words
    assert "ftnscan" not in queried_words
    assert "fastexlabs" not in queried_words
    assert "crossborder" not in queried_words
    assert "highperformance" not in queried_words
    assert "realworld" not in queried_words
    assert "communitydriven" not in queried_words
    assert "escrowed" not in queried_words
    assert "convolutional" not in queried_words
    assert "weth" not in queried_words
    assert "tinycents" not in queried_words
    assert "unstake" not in queried_words
    assert "workarounds" not in queried_words
    assert "createpair" not in queried_words
    assert "rentpayer" not in queried_words
    assert "getinboundnonce" not in queried_words
