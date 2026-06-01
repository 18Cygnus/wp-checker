"""Whitepapers listing endpoint."""

from flask import Blueprint, jsonify
from backend.services.db_service import get_pipeline_results, get_wp_metadata

whitepapers_bp = Blueprint("whitepapers", __name__)


@whitepapers_bp.route("/whitepapers")
def list_whitepapers():
    """GET /api/whitepapers — List all analyzed WPs with summary scores."""
    results = get_pipeline_results()
    metadata = get_wp_metadata()
    meta_map = {m["id"]: m for m in metadata}

    summary = []
    for wp in results:
        wp_id = wp.get("wp_id", "")
        meta = meta_map.get(wp_id, {})
        summary.append({
            "wp_id": wp_id,
            "project_name": wp.get("project_name", meta.get("nama_proyek", "")),
            "quality_label": wp.get("quality_label", meta.get("quality_label", "")),
            "profile_label": wp.get("profile_label", meta.get("profile_label", "")),
            "section_count": wp.get("section_count", 0),
            "page_count": wp.get("page_count", meta.get("jumlah_halaman", 0)),
            "credibility_score": wp.get("credibility_score", 0),
            "credibility_label": wp.get("credibility_label", ""),
            "profile_label_inferred": wp.get("profile_label_inferred", ""),
            "status": wp.get("status", ""),
        })

    return jsonify(summary)


@whitepapers_bp.route("/whitepapers/<wp_id>")
def get_whitepaper(wp_id: str):
    """GET /api/whitepapers/:id — Full analysis for one WP."""
    results = get_pipeline_results()
    for wp in results:
        if wp.get("wp_id") == wp_id:
            return jsonify(wp)

    return jsonify({"error": f"WP {wp_id} not found"}), 404
