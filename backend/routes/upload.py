"""Upload and analyze endpoint."""

from __future__ import annotations

import json
import os
import queue
import threading
import time
import uuid
import logging
from pathlib import Path
from typing import Any, TypeAlias, cast
from flask import Blueprint, Response, current_app, jsonify, request
from werkzeug.utils import secure_filename

from backend.extensions import limiter

logger = logging.getLogger(__name__)

upload_bp = Blueprint("upload", __name__)

ALLOWED_EXTENSIONS = {"pdf"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
TOTAL_STEPS = 9
JSONDict: TypeAlias = dict[str, Any]


def _error_response(message: str, status_code: int):
    return jsonify({"error": message}), status_code


def _normalize_label(label: str) -> str:
    return (label or "").strip().lower().replace(" ", "_").replace("-", "_")


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _has_pdf_magic_bytes(file) -> bool:
    stream = cast(Any, file.stream)
    current_position = stream.tell()
    stream.seek(0)
    header = stream.read(4)
    stream.seek(current_position)
    return header == b"%PDF"


def _get_file_size_bytes(file) -> int:
    stream = cast(Any, file.stream)
    current_position = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(current_position)
    return int(size)


def _client_wants_sse() -> bool:
    accept_header = request.headers.get("Accept", "")
    return "text/event-stream" in accept_header.lower()


def _build_coverage_detail(raw_result: JSONDict) -> JSONDict:
    from pipeline.credibility_scorer import COVERAGE_TIERS, TIER_POINTS

    profile_used = raw_result.get("profile_label") or raw_result.get("profile_label_inferred") or "undetermined"
    tiers_config = COVERAGE_TIERS.get(profile_used, COVERAGE_TIERS["undetermined"])
    # raw_result["label_distribution"] keys are space-separated ("technical architecture")
    # while COVERAGE_TIERS labels are also space-separated but _normalize_label converts
    # them to underscores for the lookup — so pre-normalize the distribution keys here.
    label_distribution = {
        _normalize_label(k): v
        for k, v in (raw_result.get("label_distribution", {}) or {}).items()
    }

    achieved_score = 0.0
    max_score = 0.0
    tiers = {}
    for tier_name in ("core", "supporting", "optional"):
        point_per_item = float(TIER_POINTS[tier_name])
        sections = []
        for label in tiers_config.get(tier_name, []):
            detected = label_distribution.get(_normalize_label(label), 0) > 0
            if detected:
                achieved_score += point_per_item
            max_score += point_per_item
            sections.append({"label": _normalize_label(label), "detected": detected})
        tiers[tier_name] = {
            "point_per_item": point_per_item,
            "sections": sections,
        }

    percentage = round((achieved_score / max_score) * 100, 1) if max_score else 0.0
    return {
        "profile_used": profile_used,
        "tiers": tiers,
        "achieved_score": round(achieved_score, 1),
        "max_score": round(max_score, 1),
        "percentage": percentage,
    }


def _build_sections(raw_result: JSONDict) -> list[JSONDict]:
    sections = raw_result.get("sections", []) or []
    if sections:
        return [
            {
                "index": index,
                "title": section.get("heading", ""),
                "classified_label": _normalize_label(section.get("predicted_label") or section.get("label", "")),
                "confidence": round(float(section.get("confidence", 0.0) or 0.0), 4),
                "body": section.get("body") or None,
            }
            for index, section in enumerate(sections, start=1)
        ]

    return [
        {
            "index": index,
            "title": section.get("heading", ""),
            "classified_label": _normalize_label(section.get("label", "")),
            "confidence": round(float(section.get("confidence", 0.0) or 0.0), 4),
            "body": section.get("body") or None,
        }
        for index, section in enumerate(raw_result.get("section_labels", []), start=1)
    ]


def _build_keywords(raw_result: JSONDict) -> list[JSONDict]:
    keyword_data = raw_result.get("keywords", {}) or {}
    scored = keyword_data.get("tfidf_scored")
    if scored:
        return [
            {"term": item.get("term", ""), "score": round(float(item.get("score", 0.0) or 0.0), 4)}
            for item in scored
        ]

    terms = keyword_data.get("tfidf", []) or []
    return [{"term": term, "score": 0.0} for term in terms]


def _build_keywords_stopword_scored(raw_result: JSONDict) -> list[JSONDict]:
    keyword_data = raw_result.get("keywords", {}) or {}
    scored = keyword_data.get("tfidf_stopword_scored")
    if scored:
        return [
            {"term": item.get("term", ""), "score": round(float(item.get("score", 0.0) or 0.0), 4)}
            for item in scored
        ]
    return []


def _build_prd_response(raw_result: JSONDict, analysis_id: str, filename: str, file_size_bytes: int, analysis_time_seconds: float) -> JSONDict:
    page_count = raw_result.get("page_count") or 0
    label_distribution = {
        _normalize_label(label): value
        for label, value in (raw_result.get("label_distribution", {}) or {}).items()
    }
    return {
        "analysis_id": analysis_id,
        "filename": filename,
        "file_size_bytes": file_size_bytes,
        "page_count": page_count,
        "analysis_time_seconds": round(analysis_time_seconds, 2),
        "credibility_score": raw_result.get("credibility_score", 0),
        "credibility_label": raw_result.get("credibility_label", ""),
        "profile_label": raw_result.get("profile_label") or raw_result.get("profile_label_inferred", "undetermined"),
        "profile_confidence": raw_result.get("profile_confidence", ""),
        "profile_similarity": raw_result.get("profile_similarity", {}),
        "label_distribution": label_distribution,
        "signal_breakdown": raw_result.get("signal_breakdown", {}),
        "coverage_detail": _build_coverage_detail(raw_result),
        "sections": _build_sections(raw_result),
        "keywords": _build_keywords(raw_result),
        "keywords_stopword_scored": _build_keywords_stopword_scored(raw_result),
        "red_flags": raw_result.get("red_flags", []),
        "investor_summary": raw_result.get("investor_summary", ""),
        "summary_headline": raw_result.get("summary_headline", ""),
        "summary_paragraph": raw_result.get("summary_paragraph", ""),
    }


def _save_analysis_artifacts(result: JSONDict, wp_id: str, upload_folder: str) -> None:
    from backend.services.db_service import save_wp_result

    _ = save_wp_result(result)

    project_name = result.get("project_name", "")
    output_dir = str(Path(upload_folder) / f"output_{wp_id}")
    _save_upload_embeddings(wp_id, project_name, output_dir)


def _run_pipeline_and_format(pdf_path: Path, filename: str, file_size_bytes: int, wp_id: str, analysis_id: str) -> tuple[JSONDict, JSONDict | None, float]:
    from backend.services.pipeline_service import analyze_pdf

    started_at = time.time()
    result = analyze_pdf(str(pdf_path), wp_id=wp_id)
    elapsed = time.time() - started_at
    response_payload = None
    if result.get("status") != "error":
        response_payload = _build_prd_response(result, analysis_id, filename, file_size_bytes, elapsed)
    return result, response_payload, elapsed


def _get_page_count_from_pdf(pdf_path: Path) -> int:
    for module_name in ("PyPDF2", "pypdf"):
        try:
            pdf_module = __import__(module_name)
            reader = pdf_module.PdfReader(str(pdf_path))
            return len(reader.pages)
        except Exception:
            continue
    return 0


def _pipeline_error_to_response(result: JSONDict):
    detail = result.get("error", "")
    if result.get("error_type") == "corrupt_pdf":
        return _error_response("PDF tidak dapat diproses. Pastikan file tidak corrupt.", 422)
    if result.get("error_type") == "low_quality_extraction":
        message = (
            f"PDF tidak dapat dianalisis karena kualitas teks terlalu rendah. {detail}"
            if detail
            else "PDF tidak dapat dianalisis karena kualitas teks terlalu rendah. "
                 "Kemungkinan PDF berbasis gambar atau teks terenkripsi."
        )
        return _error_response(message.strip(), 422)
    if result.get("error_type") == "non_whitepaper":
        message = (
            f"Dokumen ditolak karena tidak terdeteksi sebagai whitepaper proyek. {detail}"
            if detail
            else "Dokumen ditolak karena tidak terdeteksi sebagai whitepaper proyek. "
                 "Unggah whitepaper, litepaper, atau protocol paper yang relevan."
        )
        return _error_response(message.strip(), 422)
    return _error_response("Terjadi kesalahan saat memproses dokumen.", 500)


def _sse_payload(step: int, step_name: str) -> JSONDict:
    return {
        "step": step,
        "total_steps": TOTAL_STEPS,
        "step_name": step_name,
        "progress_pct": int(round((step / TOTAL_STEPS) * 100)),
    }


@upload_bp.route("/analyze", methods=["POST"])
@limiter.limit("5 per minute")
def analyze():
    """POST /api/analyze — Upload PDF, run pipeline, return results.

    Accepts multipart/form-data with a single 'file' field (PDF).
    MAX 1 file per request.
    """
    if "file" not in request.files:
        return _error_response("Tidak ada file yang diunggah.", 400)

    file = request.files["file"]
    if file.filename == "" or file.filename is None:
        return _error_response("Nama file kosong.", 400)

    if not _allowed_file(file.filename):
        return _error_response("Format file tidak valid. Hanya PDF yang diterima.", 400)

    if not _has_pdf_magic_bytes(file):
        return _error_response("Format file tidak valid. Hanya PDF yang diterima.", 400)

    file_size_bytes = _get_file_size_bytes(file)
    if file_size_bytes > MAX_FILE_SIZE_BYTES:
        return _error_response("Ukuran file melebihi batas 25 MB.", 400)

    # Save uploaded file
    original_filename = file.filename
    filename = secure_filename(file.filename) or f"{uuid.uuid4().hex}.pdf"
    upload_id = uuid.uuid4().hex[:8]
    wp_id = f"WP_UPLOAD_{upload_id}"
    analysis_id = str(uuid.uuid4())
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]) / wp_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = upload_dir / filename
    file.save(str(pdf_path))

    logger.info(f"Uploaded {filename} as {wp_id}, running pipeline...")

    if _client_wants_sse():
        event_queue: queue.Queue[JSONDict] = queue.Queue()
        app = cast(Any, current_app)._get_current_object()
        upload_folder = app.config["UPLOAD_FOLDER"]

        def progress_callback(step: int, _total_steps: int, step_name: str) -> None:
            event_queue.put(_sse_payload(step, step_name))

        def worker() -> None:
            with app.app_context():
                from backend.services.pipeline_service import analyze_pdf

                started_at = time.time()
                try:
                    result = analyze_pdf(str(pdf_path), wp_id=wp_id, progress_callback=progress_callback)
                    if result.get("status") == "error":
                        response, status_code = _pipeline_error_to_response(result)
                        error_payload = response.get_json() or {"error": "Terjadi kesalahan saat memproses dokumen."}
                        event_queue.put({
                            "status": "error",
                            "error": error_payload.get("error", "Terjadi kesalahan saat memproses dokumen."),
                            "status_code": status_code,
                        })
                        return

                    _save_analysis_artifacts(result, wp_id, upload_folder)
                    payload = _build_prd_response(
                        result,
                        analysis_id,
                        original_filename,
                        file_size_bytes,
                        time.time() - started_at,
                    )
                    if not payload["page_count"]:
                        payload["page_count"] = _get_page_count_from_pdf(pdf_path)
                    event_queue.put({"status": "complete", "result": payload})
                except Exception:
                    logger.exception("SSE analysis failed for %s", wp_id)
                    event_queue.put({"status": "error", "error": "Terjadi kesalahan saat memproses dokumen.", "status_code": 500})

        threading.Thread(target=worker, daemon=True).start()

        def generate_stream():
            while True:
                payload = event_queue.get()
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if payload.get("status") in {"complete", "error"}:
                    break

        return Response(
            generate_stream(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    result, response_payload, _elapsed = _run_pipeline_and_format(
        pdf_path,
        original_filename,
        file_size_bytes,
        wp_id,
        analysis_id,
    )

    if result.get("status") == "error":
        return _pipeline_error_to_response(result)

    if response_payload is not None and not response_payload["page_count"]:
        response_payload["page_count"] = _get_page_count_from_pdf(pdf_path)

    _save_analysis_artifacts(result, wp_id, current_app.config["UPLOAD_FOLDER"])

    return jsonify(response_payload)


def _save_upload_embeddings(wp_id: str, project_name: str, output_dir: str):
    """Load step5 embeddings from upload output and save to MongoDB."""
    import json
    from backend.services.db_service import save_wp_embeddings

    step5_path = (
        Path(output_dir) / f"{wp_id}_{project_name}" / f"step5_{project_name}.json"
    )
    if step5_path.exists():
        try:
            sections = json.loads(step5_path.read_text(encoding="utf-8"))
            save_wp_embeddings(wp_id, project_name, sections)
        except Exception as e:
            logger.warning(f"Could not save embeddings for {wp_id}: {e}")
