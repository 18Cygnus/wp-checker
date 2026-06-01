"""
seed_mongodb.py — Import corpus pipeline_results.json + step5 embeddings into MongoDB.

Collections created:
  - pipeline_results: One document per WP (keyed by wp_id)
  - embeddings: One document per WP containing section embeddings for plagiarism

Usage:
    python backend/seed_mongodb.py
    python backend/seed_mongodb.py --uri mongodb://localhost:27017/ --db skripsi_wp
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
FINE_TUNE_DIR = PROJECT_ROOT / "fine_tune"
METADATA_PATH = PROJECT_ROOT / "wp_metadata.json"


def seed_pipeline_results(db, results_path: Path):
    """Upsert all pipeline results into MongoDB."""
    if not results_path.exists():
        logger.error(f"pipeline_results.json not found at {results_path}")
        return 0

    results = json.loads(results_path.read_text(encoding="utf-8"))
    col = db["pipeline_results"]
    count = 0
    for entry in results:
        wp_id = entry.get("wp_id")
        if not wp_id:
            continue
        entry["_id"] = wp_id
        entry["source"] = "corpus"  # distinguish from user uploads
        col.replace_one({"_id": wp_id}, entry, upsert=True)
        count += 1

    logger.info(f"Seeded {count} pipeline results into MongoDB")
    return count


def seed_embeddings(db, fine_tune_dir: Path, metadata: list[dict]):
    """Load step5 embeddings and store in MongoDB for plagiarism detection."""
    col = db["embeddings"]
    count = 0

    for item in metadata:
        wp_id = item["id"]
        project_name = (
            item.get("project_name")
            or item.get("nama_proyek", "").replace(" ", "")
        )
        step5_path = (
            fine_tune_dir / f"{wp_id}_{project_name}" / f"step5_{project_name}.json"
        )
        if not step5_path.exists():
            logger.warning(f"  {wp_id}: step5 not found at {step5_path}")
            continue

        sections = json.loads(step5_path.read_text(encoding="utf-8"))
        doc = {
            "_id": wp_id,
            "project_name": project_name,
            "source": "corpus",
            "sections": sections,  # list of {segment_id, heading, embedding}
        }
        col.replace_one({"_id": wp_id}, doc, upsert=True)
        count += 1

    logger.info(f"Seeded {count} embedding documents into MongoDB")
    return count


def main():
    parser = argparse.ArgumentParser(description="Seed MongoDB with corpus data")
    parser.add_argument("--uri", default="mongodb://localhost:27017/")
    parser.add_argument("--db", default="skripsi_wp")
    parser.add_argument("--skip-embeddings", action="store_true",
                        help="Only seed pipeline results, skip large embeddings")
    args = parser.parse_args()

    try:
        from pymongo import MongoClient
    except ImportError:
        logger.error("pymongo not installed. Run: pip install pymongo")
        sys.exit(1)

    client = MongoClient(args.uri)
    db = client[args.db]

    # 1. Seed pipeline results
    results_path = FINE_TUNE_DIR / "pipeline_results.json"
    seed_pipeline_results(db, results_path)

    # 2. Seed embeddings (for plagiarism detection)
    if not args.skip_embeddings:
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        seed_embeddings(db, FINE_TUNE_DIR, metadata)
    else:
        logger.info("Skipping embeddings seed (--skip-embeddings)")

    # 3. Create indexes
    db["pipeline_results"].create_index("wp_id")
    db["pipeline_results"].create_index("source")
    db["embeddings"].create_index("source")
    logger.info("Indexes created")

    logger.info("=== Seed complete ===")


if __name__ == "__main__":
    main()
