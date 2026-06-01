"""Pipeline service — wrapper around batch_runner for single-WP processing."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Callable, TypeAlias

from flask import current_app

logger = logging.getLogger(__name__)

# Max pages allowed — reject heavy-image PDFs
MAX_PAGES = 200
JSONDict: TypeAlias = dict[str, Any]
ProgressCallback: TypeAlias = Callable[[int, int, str], None]

TOTAL_PIPELINE_STEPS = 9
PROGRESS_STEP_NAMES = {
    1: "Mengekstrak teks dari PDF",
    2: "Memisahkan segmen dokumen",
    3: "Membersihkan dan memproses teks",
    4: "Mengekstrak kata kunci",
    5: "Mengklasifikasi segmen",
    6: "Menghasilkan embedding",
    7: "Memeriksa kualitas linguistik",
    8: "Mendeteksi kemiripan sumber",
    9: "Menghitung skor kredibilitas",
}

CORRUPT_PDF_HINTS = (
    "EOF marker",
    "malformed pdf",
    "cannot open broken document",
    "failed to load document",
    "cannot read",
    "invalid pdf",
    "corrupt",
    "damaged",
)


def _report_progress(progress_callback: ProgressCallback | None, step: int) -> None:
    if progress_callback is None:
        return
    progress_callback(step, TOTAL_PIPELINE_STEPS, PROGRESS_STEP_NAMES[step])


def _classify_error_type(message: str) -> str:
    lowered = (message or "").lower()
    if any(hint in lowered for hint in CORRUPT_PDF_HINTS):
        return "corrupt_pdf"
    return "pipeline_error"


def _extract_scored_keywords(
    vectorizer: Any, doc_text: str, top_n: int = 20
) -> list[JSONDict]:
    if vectorizer is None or not doc_text.strip():
        return []

    vec = vectorizer.transform([doc_text])
    feature_names = vectorizer.get_feature_names_out()
    scores = vec.toarray()[0]
    ranked = sorted(zip(feature_names, scores), key=lambda item: item[1], reverse=True)
    return [
        {"term": term, "score": round(float(score), 4)}
        for term, score in ranked[:top_n]
        if score > 0
    ]


def _load_upload_embeddings_from_sections(sections: list[JSONDict]) -> list[JSONDict]:
    return [
        {
            "segment_id": section.get("segment_id", ""),
            "heading": section.get("heading", ""),
            "embedding": section.get("embedding", []),
        }
        for section in sections
        if section.get("embedding")
    ]


def analyze_pdf(
    pdf_path: str,
    wp_id: str = "WP_UPLOAD",
    progress_callback: ProgressCallback | None = None,
) -> JSONDict:
    """Run full pipeline on a single uploaded PDF.

    Returns pipeline result dict or error dict.
    """
    project_root = Path(__file__).parent.parent.parent.resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from pipeline.batch_runner import _load, _save_json_backup
    from pipeline.credibility_scorer import score_whitepaper
    from pipeline.whitepaper_gate import assess_whitepaper_candidate

    # Derive project name from filename
    pdf_name = Path(pdf_path).stem
    project_name = pdf_name.replace(" ", "").replace("-", "").replace("_", "")

    # Use a temp output directory
    output_dir = str(Path(current_app.config["UPLOAD_FOLDER"]) / f"output_{wp_id}")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    try:
        extractor = _load("extractor", "pipeline/1_extractor.py")
        segmenter = _load("segmenter", "pipeline/2_segmenter.py")
        preprocessor = _load("preprocessor", "pipeline/4_preprocessor.py")
        keyword_extractor = _load("kw", "pipeline/3_keyword_extractor.py")
        classifier = _load("classifier", "pipeline/7_section_classifier.py")
        embedder = _load("embedding", "pipeline/5_embedding_generator.py")
        linguistic = _load("linguistic", "pipeline/6_linguistic_checker.py")
        plagiarism_mod = _load("plagiarism", "pipeline/8_plagiarism_detector.py")

        _report_progress(progress_callback, 1)
        extraction_result = extractor.extract_pdf(
            pdf_path,
            wp_id=wp_id,
            project_name=project_name,
            output_dir=output_dir,
        )
        if extraction_result.get("status") != "ok":
            error_message = extraction_result.get("error", "Extraction failed")
            return {
                "status": "error",
                "error": error_message,
                "error_type": _classify_error_type(error_message),
            }

        # Enforce page limit
        page_count = extraction_result.get("page_count") or 0
        if page_count > MAX_PAGES:
            return {
                "status": "error",
                "error": f"PDF terlalu panjang ({page_count} halaman, maksimum {MAX_PAGES}).",
                "error_type": "low_quality_extraction",
            }

        # Reject low-quality extraction (image-heavy / noisy PDFs)
        quality = extraction_result.get("quality") or {}
        if quality.get("is_low_quality"):
            return {
                "status": "error",
                "error": quality.get("reason", "Kualitas ekstraksi teks terlalu rendah."),
                "error_type": "low_quality_extraction",
            }

        sections: list[JSONDict] = []
        result: JSONDict = {
            "wp_id": wp_id,
            "project_name": project_name,
            "filename": Path(pdf_path).name,
            "quality_label": "",
            "profile_label": "",
            "document_gate": None,
            "status": "ok",
            "error": None,
            "page_count": extraction_result.get("page_count"),
            "extraction_method": extraction_result.get("extraction_method", "auto"),
            "section_count": 0,
            "sections": sections,
            "section_labels": [],
            "keywords": {},
            "tfidf_scores": [],
            "plagiarism_rate": 0.0,
            "plagiarism_flagged_count": 0,
            "plagiarism_flags": [],
            "embedding_count": 0,
            "embedding_dim": 0,
            "linguistic_error_rate": 0.0,
            "linguistic_total_errors": 0,
            "linguistic_error_categories": {},
        }

        _report_progress(progress_callback, 2)
        step1_path = extraction_result.get("md_path")
        segment_result = segmenter.segment_file(
            step1_path,
            wp_id,
            project_name,
            output_dir=output_dir,
        )
        if segment_result.get("status") != "ok":
            error_message = segment_result.get("error", "Segmentation failed")
            return {
                "status": "error",
                "error": error_message,
                "error_type": _classify_error_type(error_message),
            }
        sections = segment_result.get("sections", [])
        result["sections"] = sections
        result["section_count"] = len(sections)

        _report_progress(progress_callback, 3)
        preprocessor.preprocess_sections(sections)

        _report_progress(progress_callback, 4)
        full_clean = " ".join(section.get("clean_text", "") for section in sections)
        vectorizer = (
            keyword_extractor.fit_tfidf([full_clean]) if full_clean.strip() else None
        )
        vectorizer_filtered = (
            keyword_extractor.fit_tfidf_filtered([full_clean]) if full_clean.strip() else None
        )
        tfidf_scored = _extract_scored_keywords(vectorizer, full_clean, top_n=20)
        tfidf_stopword_scored = (
            keyword_extractor.extract_keywords_stopword_scored(vectorizer_filtered, full_clean, top_n=40)
            if vectorizer_filtered is not None
            else []
        )
        result["keywords"] = {
            "tfidf": [item["term"] for item in tfidf_scored],
            "tfidf_scored": tfidf_scored,
            "tfidf_stopword_scored": tfidf_stopword_scored,
            "ner_entities": keyword_extractor.extract_ner_entities(
                (extraction_result.get("markdown") or "")[:50000]
            ),
        }
        result["tfidf_scores"] = [item["score"] for item in tfidf_scored]

        _report_progress(progress_callback, 5)
        classifier.set_mode("fine-tuned")
        classify_result = classifier.classify_file(
            step1_path,
            sections,
            wp_id,
            project_name,
            output_dir=output_dir,
            mode="fine-tuned",
        )
        result["sections"] = classify_result.get("sections", sections)
        result["section_labels"] = [
            {
                "heading": section.get("heading", ""),
                "label": section.get("predicted_label", ""),
                "confidence": round(float(section.get("confidence", 0.0) or 0.0), 4),
            }
            for section in result["sections"]
        ]
        if classify_result.get("status") == "ok":
            gate_result = assess_whitepaper_candidate(
                extraction_result.get("markdown", ""),
                page_count,
                result["sections"],
            )
            result["document_gate"] = gate_result
            if not gate_result.get("is_whitepaper"):
                return {
                    "status": "error",
                    "error": gate_result.get(
                        "reason",
                        "Dokumen tidak terdeteksi sebagai whitepaper proyek.",
                    ),
                    "error_type": "non_whitepaper",
                    "document_gate": gate_result,
                }
        if classify_result.get("status") != "ok":
            result["status"] = "partial_error"
            result["error"] = classify_result.get("error", "classification failed")

        _report_progress(progress_callback, 6)
        embed_result = embedder.embed_file(
            wp_id,
            result["sections"],
            output_dir=output_dir,
            project_name=project_name,
        )
        result["embedding_count"] = embed_result.get("embedding_count", 0)
        result["embedding_dim"] = embed_result.get("embedding_dim", 0)
        if embed_result.get("status") != "ok" and result["status"] == "ok":
            result["status"] = "partial_error"
            result["error"] = embed_result.get("error", "embedding generation failed")

        _report_progress(progress_callback, 7)
        linguistic_result = linguistic.check_file(
            wp_id,
            result["sections"],
            output_dir=output_dir,
            project_name=project_name,
        )
        result["linguistic_error_rate"] = linguistic_result.get("error_rate", 0)
        result["linguistic_total_errors"] = linguistic_result.get("total_errors", 0)
        result["linguistic_error_categories"] = linguistic_result.get(
            "error_categories", {}
        )
        if linguistic_result.get("status") != "ok" and result["status"] == "ok":
            result["status"] = "partial_error"
            result["error"] = linguistic_result.get("error", "linguistic check failed")

        _report_progress(progress_callback, 8)
        upload_embeddings = _load_upload_embeddings_from_sections(result["sections"])
        if upload_embeddings:
            from backend.services.db_service import load_corpus_embeddings

            corpus_embeddings = load_corpus_embeddings()

            # Exclude corpus entries that are the same document re-uploaded under a
            # different wp_id.  Same PDF → mean-max cosine-sim ≈ 1.0 across sections;
            # genuinely different documents stay well below SELF_MATCH_THRESHOLD (0.97).
            filtered_corpus = {
                cid: cembs
                for cid, cembs in corpus_embeddings.items()
                if not plagiarism_mod.is_duplicate_document(upload_embeddings, cembs)
            }
            if len(filtered_corpus) < len(corpus_embeddings):
                excluded = len(corpus_embeddings) - len(filtered_corpus)
                logger.info(
                    f"Plagiarism corpus: excluded {excluded} duplicate-document "
                    f"entr{'y' if excluded == 1 else 'ies'} for {wp_id}"
                )

            combined_embeddings = dict(filtered_corpus)
            combined_embeddings[wp_id] = upload_embeddings
            plagiarism_result = plagiarism_mod.detect_plagiarism(
                combined_embeddings,
                threshold=0.85,
            ).get(wp_id, {})
            result["plagiarism_rate"] = plagiarism_result.get("plagiarism_rate", 0.0)
            result["plagiarism_flagged_count"] = plagiarism_result.get(
                "flagged_count", 0
            )
            result["plagiarism_flags"] = plagiarism_result.get("plagiarism_flags", [])

        _report_progress(progress_callback, 9)
        credibility = score_whitepaper(result)
        result.update(
            {
                "credibility_score": credibility.get("credibility_score", 0),
                "credibility_label": credibility.get("credibility_label", ""),
                "profile_label_inferred": credibility.get("profile_label", ""),
                "profile_label": credibility.get("profile_label", ""),
                "profile_confidence": credibility.get("profile_confidence", ""),
                "profile_similarity": credibility.get("profile_similarity", {}),
                "label_distribution": credibility.get("label_distribution", {}),
                "signal_breakdown": credibility.get("signal_breakdown", {}),
                "red_flags": credibility.get("red_flags", []),
                "investor_summary": credibility.get("investor_summary", ""),
                "summary_headline": credibility.get("summary_headline", ""),
                "summary_paragraph": credibility.get("summary_paragraph", ""),
            }
        )

        _save_json_backup([result], output_dir)
        return result

    except Exception as e:
        logger.error(f"Pipeline failed for {pdf_path}: {e}")
        return {
            "status": "error",
            "error": str(e),
            "error_type": _classify_error_type(str(e)),
        }
