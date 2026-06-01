"""
5_embedding_generator.py — Generate sentence embeddings for each section.

Model: sentence-transformers/all-MiniLM-L6-v2 (384-dim, ~80MB VRAM)
Input: clean_text from preprocessor (step 3)
Output: adds 'embedding' key (384-dim float list) to each section dict,
        saves step5_{project_name}.json per WP.

Usage (standalone):
    from pipeline.5_embedding_generator import generate_embeddings, embed_file
    generate_embeddings(sections)           # in-place, adds 'embedding' key
    embed_file("WP_019", sections, "out")   # generates + saves JSON
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_model = None
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def _get_model():
    """Lazy-load the sentence-transformer model (single instance)."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(_MODEL_NAME)
            logger.info(f"Loaded embedding model: {_MODEL_NAME}")
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for embedding generation. "
                "Install with: pip install sentence-transformers"
            )
    return _model


def generate_embeddings(sections: list[dict], batch_size: int = 32) -> list[dict]:
    """Add 'embedding' key to each section dict in-place.

    Args:
        sections: List of section dicts with at least 'clean_text'.
        batch_size: Batch size for model.encode().

    Returns:
        Same list with 'embedding' added to each section.
    """
    model = _get_model()

    texts = []
    for s in sections:
        text = s.get("clean_text", "").strip()
        if not text:
            text = s.get("heading", "untitled")
        texts.append(text)

    embeddings = model.encode(
        texts, batch_size=batch_size, show_progress_bar=False, normalize_embeddings=True
    )

    for section, emb in zip(sections, embeddings):
        section["embedding"] = emb.tolist()

    logger.info(f"Generated {len(sections)} embeddings ({len(embeddings[0])}-dim)")
    return sections


def embed_file(
    wp_id: str,
    sections: list[dict],
    output_dir: str = "output_md",
    project_name: str = "",
) -> dict:
    """Generate embeddings and save as step5 JSON.

    Args:
        wp_id: Whitepaper ID (e.g. "WP_019").
        sections: List of section dicts (must have clean_text from preprocessor).
        output_dir: Base output directory.
        project_name: Project name for folder/file naming.

    Returns:
        Dict with status, embedding_count, embedding_dim, json_path.
    """
    try:
        generate_embeddings(sections)

        output_data = []
        for s in sections:
            output_data.append(
                {
                    "section_id": s.get("segment_id", ""),
                    "heading": s.get("heading", ""),
                    "embedding": s.get("embedding", []),
                }
            )

        folder = Path(output_dir) / f"{wp_id}_{project_name}"
        folder.mkdir(parents=True, exist_ok=True)
        json_path = folder / f"step5_{project_name}.json"
        json_path.write_text(
            json.dumps(output_data, ensure_ascii=False),
            encoding="utf-8",
        )

        dim = len(sections[0]["embedding"]) if sections else 0
        logger.info(f"  {wp_id}: saved {len(output_data)} embeddings to {json_path}")
        return {
            "status": "ok",
            "embedding_count": len(output_data),
            "embedding_dim": dim,
            "json_path": str(json_path),
        }

    except Exception as e:
        logger.error(f"  {wp_id}: embedding generation failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "embedding_count": 0,
        }
