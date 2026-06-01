"""Analysis detail endpoints."""

from flask import Blueprint, jsonify
from backend.services.db_service import get_wp_by_id

analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.route("/whitepapers/<wp_id>/sections")
def get_sections(wp_id: str):
    """GET /api/whitepapers/:id/sections — Sections with labels."""
    wp = get_wp_by_id(wp_id)
    if wp is None:
        return jsonify({"error": f"WP {wp_id} not found"}), 404

    sections = wp.get("section_labels", [])
    return jsonify({
        "wp_id": wp_id,
        "section_count": len(sections),
        "sections": sections,
    })


@analysis_bp.route("/whitepapers/<wp_id>/keywords")
def get_keywords(wp_id: str):
    """GET /api/whitepapers/:id/keywords — TF-IDF + NER."""
    wp = get_wp_by_id(wp_id)
    if wp is None:
        return jsonify({"error": f"WP {wp_id} not found"}), 404

    return jsonify({
        "wp_id": wp_id,
        "keywords": wp.get("keywords", {}),
    })


@analysis_bp.route("/whitepapers/<wp_id>/plagiarism")
def get_plagiarism(wp_id: str):
    """GET /api/whitepapers/:id/plagiarism — Similarity flags."""
    wp = get_wp_by_id(wp_id)
    if wp is None:
        return jsonify({"error": f"WP {wp_id} not found"}), 404

    return jsonify({
        "wp_id": wp_id,
        "plagiarism_rate": wp.get("plagiarism_rate", 0),
        "plagiarism_flagged_count": wp.get("plagiarism_flagged_count", 0),
    })


@analysis_bp.route("/whitepapers/<wp_id>/credibility")
def get_credibility(wp_id: str):
    """GET /api/whitepapers/:id/credibility — Score breakdown + red flags."""
    wp = get_wp_by_id(wp_id)
    if wp is None:
        return jsonify({"error": f"WP {wp_id} not found"}), 404

    return jsonify({
        "wp_id": wp_id,
        "credibility_score": wp.get("credibility_score", 0),
        "credibility_label": wp.get("credibility_label", ""),
        "profile_label_inferred": wp.get("profile_label_inferred", ""),
        "profile_confidence": wp.get("profile_confidence", ""),
        "profile_similarity": wp.get("profile_similarity", {}),
        "label_distribution": wp.get("label_distribution", {}),
        "signal_breakdown": wp.get("signal_breakdown", {}),
        "red_flags": wp.get("red_flags", []),
        "investor_summary": wp.get("investor_summary", ""),
    })
