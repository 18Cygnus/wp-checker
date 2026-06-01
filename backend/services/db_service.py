"""Database service — MongoDB-first with JSON fallback for read operations.

Data flow:
  - MongoDB is the primary store for pipeline results and embeddings.
  - JSON file (fine_tune/pipeline_results.json) is the fallback when MongoDB
    is unavailable or has no data.
  - Uploaded WP results are always saved to MongoDB (no local JSON merge).
  - Corpus embeddings for plagiarism detection are loaded from MongoDB.
"""

import json
import logging
from pathlib import Path
from flask import current_app

logger = logging.getLogger(__name__)

_mongo_client = None


# ---------------------------------------------------------------------------
# MongoDB connection
# ---------------------------------------------------------------------------
def get_mongo_db():
    """Get MongoDB database connection (lazy singleton)."""
    global _mongo_client
    try:
        if _mongo_client is None:
            from pymongo import MongoClient
            _mongo_client = MongoClient(
                current_app.config["MONGO_URI"],
                serverSelectionTimeoutMS=2000,
            )
            # Ping to verify connection
            _mongo_client.admin.command("ping")
        return _mongo_client[current_app.config["MONGO_DB"]]
    except Exception as e:
        logger.debug(f"MongoDB unavailable: {e}")
        _mongo_client = None
        return None


# ---------------------------------------------------------------------------
# Read — pipeline results (MongoDB-first, JSON fallback)
# ---------------------------------------------------------------------------
def get_pipeline_results() -> list[dict]:
    """Load all pipeline results. MongoDB first, JSON fallback."""
    db = get_mongo_db()
    if db is not None:
        try:
            docs = list(db["pipeline_results"].find({}, {"_id": 0}))
            if docs:
                return docs
        except Exception as e:
            logger.warning(f"MongoDB read failed, falling back to JSON: {e}")

    # Fallback: read from JSON file
    return _load_json_results()


def get_wp_by_id(wp_id: str) -> dict | None:
    """Get a single WP's data by ID. MongoDB first, JSON fallback."""
    db = get_mongo_db()
    if db is not None:
        try:
            doc = db["pipeline_results"].find_one({"_id": wp_id}, {"_id": 0})
            if doc:
                return doc
        except Exception as e:
            logger.debug(f"MongoDB lookup failed for {wp_id}: {e}")

    # Fallback: JSON file
    results = _load_json_results()
    for wp in results:
        if wp.get("wp_id") == wp_id:
            return wp

    # Fallback: uploaded WP output folder
    return _load_uploaded_wp_result(wp_id)


def _load_json_results() -> list[dict]:
    """Load pipeline_results.json from the configured directory."""
    results_dir = current_app.config["PIPELINE_RESULTS_DIR"]
    path = Path(results_dir) / "pipeline_results.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _load_uploaded_wp_result(wp_id: str) -> dict | None:
    """Fallback: try loading result from uploads/output_<wp_id>/."""
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    output_dir = upload_dir / f"output_{wp_id}"
    results_path = output_dir / "pipeline_results.json"
    if results_path.exists():
        data = json.loads(results_path.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data
    return None


# ---------------------------------------------------------------------------
# Write — save uploaded WP results to MongoDB
# ---------------------------------------------------------------------------
def save_wp_result(result: dict) -> bool:
    """Save a single WP pipeline result to MongoDB.

    Returns True if saved successfully, False if MongoDB unavailable.
    """
    wp_id = result.get("wp_id")
    if not wp_id:
        return False

    db = get_mongo_db()
    if db is None:
        logger.warning(f"MongoDB unavailable — cannot save {wp_id}")
        return False

    try:
        doc = {**result, "_id": wp_id, "source": "upload"}
        db["pipeline_results"].replace_one({"_id": wp_id}, doc, upsert=True)
        logger.info(f"Saved {wp_id} to MongoDB (pipeline_results)")
        return True
    except Exception as e:
        logger.error(f"Failed to save {wp_id} to MongoDB: {e}")
        return False


def save_wp_embeddings(wp_id: str, project_name: str, sections: list[dict]) -> bool:
    """Save section embeddings for a WP to MongoDB (for plagiarism detection).

    Args:
        wp_id: Whitepaper ID
        project_name: Project name
        sections: List of dicts with segment_id, heading, embedding
    """
    db = get_mongo_db()
    if db is None:
        return False

    try:
        doc = {
            "_id": wp_id,
            "project_name": project_name,
            "source": "upload",
            "sections": sections,
        }
        db["embeddings"].replace_one({"_id": wp_id}, doc, upsert=True)
        logger.info(f"Saved {wp_id} embeddings to MongoDB")
        return True
    except Exception as e:
        logger.error(f"Failed to save {wp_id} embeddings: {e}")
        return False


# ---------------------------------------------------------------------------
# Read — embeddings for plagiarism detection (corpus from MongoDB)
# ---------------------------------------------------------------------------
def load_corpus_embeddings() -> dict[str, list[dict]]:
    """Load all corpus embeddings from MongoDB for plagiarism comparison.

    Returns:
        {wp_id: [{"segment_id", "heading", "embedding"}, ...]}
    """
    db = get_mongo_db()
    if db is None:
        return {}

    try:
        embeddings_by_wp = {}
        for doc in db["embeddings"].find():
            wp_id = doc["_id"]
            embeddings_by_wp[wp_id] = doc.get("sections", [])
        return embeddings_by_wp
    except Exception as e:
        logger.error(f"Failed to load corpus embeddings: {e}")
        return {}


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------
def get_wp_metadata() -> list[dict]:
    """Load wp_metadata.json."""
    path = Path(current_app.config["WP_METADATA_PATH"])
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def get_wp_step_file(wp_id: str, project_name: str, step: int, ext: str = "md") -> str | None:
    """Read step output file content from fine_tune or uploads folder."""
    # Try fine_tune first
    results_dir = current_app.config["PIPELINE_RESULTS_DIR"]
    folder = Path(results_dir) / f"{wp_id}_{project_name}"
    filename = f"step{step}_{project_name}.{ext}"
    path = folder / filename
    if path.exists():
        return path.read_text(encoding="utf-8")

    # Try uploads output folder
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_folder = upload_dir / f"output_{wp_id}" / f"{wp_id}_{project_name}"
    upload_path = upload_folder / filename
    if upload_path.exists():
        return upload_path.read_text(encoding="utf-8")

    return None
