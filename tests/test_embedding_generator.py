import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np


def load_embedding_generator():
    spec = importlib.util.spec_from_file_location(
        "embedding", "pipeline/5_embedding_generator.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_sections():
    return [
        {
            "segment_id": "WP_001_S001",
            "heading": "Abstract",
            "body": "This is the abstract about blockchain.",
            "clean_text": "this is the abstract about blockchain",
        },
        {
            "segment_id": "WP_001_S002",
            "heading": "Tokenomics",
            "body": "Token supply is 100 billion.",
            "clean_text": "token supply is 100 billion",
        },
    ]


def _mock_encode(
    texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True
):
    """Return fake 384-dim normalized embeddings."""
    return np.random.randn(len(texts), 384).astype(np.float32)


def test_generate_embeddings_adds_key():
    emb = load_embedding_generator()
    emb._model = None  # reset cached model

    mock_model = MagicMock()
    mock_model.encode = _mock_encode

    with patch.object(emb, "_get_model", return_value=mock_model):
        sections = _make_sections()
        result = emb.generate_embeddings(sections)

        assert len(result) == 2
        assert "embedding" in result[0]
        assert "embedding" in result[1]
        assert len(result[0]["embedding"]) == 384
        assert isinstance(result[0]["embedding"], list)


def test_generate_embeddings_uses_heading_fallback():
    emb = load_embedding_generator()
    emb._model = None

    captured_texts = []

    def mock_encode_capture(texts, **kwargs):
        captured_texts.extend(texts)
        return np.random.randn(len(texts), 384).astype(np.float32)

    mock_model = MagicMock()
    mock_model.encode = mock_encode_capture

    with patch.object(emb, "_get_model", return_value=mock_model):
        sections = [
            {"segment_id": "WP_001_S001", "heading": "Abstract", "clean_text": ""},
        ]
        emb.generate_embeddings(sections)

        # When clean_text is empty, should fall back to heading
        assert captured_texts[0] == "Abstract"


def test_embed_file_saves_json(tmp_path):
    emb = load_embedding_generator()
    emb._model = None

    mock_model = MagicMock()
    mock_model.encode = _mock_encode

    with patch.object(emb, "_get_model", return_value=mock_model):
        sections = _make_sections()
        result = emb.embed_file(
            "WP_001", sections, output_dir=str(tmp_path), project_name="TestProject"
        )

        assert result["status"] == "ok"
        assert result["embedding_count"] == 2
        assert result["embedding_dim"] == 384

        json_path = Path(result["json_path"])
        assert json_path.exists()
        assert json_path.name == "step5_TestProject.json"
        assert json_path.parent.name == "WP_001_TestProject"

        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert len(data) == 2
        assert data[0]["section_id"] == "WP_001_S001"
        assert len(data[0]["embedding"]) == 384


def test_embed_file_error_returns_status():
    emb = load_embedding_generator()
    emb._model = None

    with patch.object(emb, "_get_model", side_effect=ImportError("no module")):
        sections = _make_sections()
        result = emb.embed_file(
            "WP_001", sections, output_dir="/nonexistent", project_name="Test"
        )

        assert result["status"] == "error"
        assert "no module" in result["error"]
        assert result["embedding_count"] == 0
