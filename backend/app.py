"""
Flask backend for whitepaper credibility analysis system.

Usage:
    python backend/app.py              # Development server (port 5000)
    python backend/app.py --port 8080  # Custom port
"""

import argparse
import importlib
import sys
import logging
from pathlib import Path
from typing import Any

# Ensure project root on sys.path before any local imports
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from flask import Flask
from flask_cors import CORS
from backend.extensions import limiter

logger = logging.getLogger(__name__)


def create_app(config: dict[str, Any] | None = None) -> Flask:
    """Flask application factory."""
    app = Flask(__name__)

    # Default config
    app.config.update({
        "MONGO_URI": "mongodb://localhost:27017/",
        "MONGO_DB": "skripsi_wp",
        "PIPELINE_RESULTS_DIR": str(_PROJECT_ROOT / "fine_tune"),
        "UPLOAD_FOLDER": str(_PROJECT_ROOT / "uploads"),
        "MAX_CONTENT_LENGTH": 25 * 1024 * 1024,  # 25MB max upload
        "WP_METADATA_PATH": str(_PROJECT_ROOT / "wp_metadata.json"),
    })

    if config:
        app.config.update(config)

    # Ensure upload folder exists
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    # CORS — allow React dev server
    CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "http://localhost:5173"]}})

    limiter.init_app(app)

    # Register blueprints
    from backend.routes.whitepapers import whitepapers_bp
    from backend.routes.analysis import analysis_bp
    from backend.routes.upload import upload_bp

    app.register_blueprint(whitepapers_bp, url_prefix="/api")
    app.register_blueprint(analysis_bp, url_prefix="/api")
    app.register_blueprint(upload_bp, url_prefix="/api")

    # Preload ML models at startup (skip if configured)
    if not app.config.get("SKIP_MODEL_PRELOAD"):
        _preload_models(app)

    @app.route("/api/health")
    def health():
        return {"status": "ok"}

    @app.errorhandler(429)
    def handle_rate_limit(_error: object):
        return {"error": "Terlalu banyak permintaan. Coba lagi nanti."}, 429

    @app.errorhandler(413)
    def handle_request_entity_too_large(_error: object):
        return {"error": "Ukuran file melebihi batas 25 MB."}, 413

    return app


def _preload_models(app: Flask):
    """Preload ML models at startup to avoid per-request loading."""
    with app.app_context():
        try:
            from pipeline.finetune.inference import load_classifier
            classifier = load_classifier()
            app.config["_CLASSIFIER"] = classifier
            logger.info("Fine-tuned classifier preloaded")
        except Exception as e:
            logger.warning(f"Could not preload classifier: {e}")
            app.config["_CLASSIFIER"] = None

        try:
            import os
            sentence_transformers = importlib.import_module("sentence_transformers")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            model = sentence_transformers.SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            app.config["_EMBEDDER"] = model
            logger.info("Sentence-transformer preloaded")
        except Exception as e:
            logger.warning(f"Could not preload embedder: {e}")
            app.config["_EMBEDDER"] = None


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(description="Whitepaper analysis backend")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app()
    app.run(host="0.0.0.0", port=args.port, debug=args.debug)
