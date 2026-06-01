"""
batch_runner.py — Orchestrate full NLP pipeline for all 45 whitepapers.

Pipeline per WP:
    Step 1: extract PDF -> step1_{project_name}.md
    Step 2: segment by headings -> step2_{project_name}.md
    Step 3: preprocess (tokenize, clean) -- enriches sections dict
    Step 4: TF-IDF keywords + NER -- corpus-level, run after all extractions
    Step 5: classify sections (fine-tuned RoBERTa) -> step4_{project_name}.md
    Step 6: embedding generation (sentence-transformers) -> step5_{project_name}.json
    Step 7: linguistic check -> step6_{project_name}.json
    Step 8: plagiarism detection (cosine similarity, corpus-level) -> plagiarism_results.json
    Step 9: credibility scoring (rule-based aggregation, corpus-level)
    Final:  save to MongoDB + JSON backup

Usage:
    python pipeline/batch_runner.py                           # full pipeline
    python pipeline/batch_runner.py --step extract            # extract only
    python pipeline/batch_runner.py --step segment            # segment only
    python pipeline/batch_runner.py --step classify           # segment+preprocess+classify
    python pipeline/batch_runner.py --step segment-to-classify # steps 2-5
    python pipeline/batch_runner.py --step embed              # embedding generation
    python pipeline/batch_runner.py --step linguistic         # linguistic error detection
    python pipeline/batch_runner.py --step plagiarism         # plagiarism detection (needs embeddings)
    python pipeline/batch_runner.py --step credibility        # credibility scoring (needs all signals)
    python pipeline/batch_runner.py --wp WP_007,WP_033        # specific WPs
    python pipeline/batch_runner.py --dry-run                 # skip DB write
"""

import argparse
import json
import logging
import importlib.util
import sys
from pathlib import Path

# Ensure project root is on sys.path so submodules can do `from pipeline import ...`
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load(name, rel_path):
    spec = importlib.util.spec_from_file_location(name, rel_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def resolve_output_dir(base: str = "output_md") -> str:
    """Auto-increment output directory if it already exists.

    output_md/ exists -> output_md_2/
    output_md_2/ exists -> output_md_3/
    """
    base_path = Path(base)
    if not base_path.exists():
        return base

    counter = 2
    while True:
        candidate = Path(f"{base}_{counter}")
        if not candidate.exists():
            logger.info(f"Output dir '{base}' exists, using '{candidate}'")
            return str(candidate)
        counter += 1


def filter_metadata(metadata: list[dict], wp_filter: str | None) -> list[dict]:
    """Filter metadata by comma-separated WP IDs."""
    if not wp_filter:
        return metadata
    wp_ids = [w.strip() for w in wp_filter.split(",")]
    filtered = [m for m in metadata if m["id"] in wp_ids]
    if len(filtered) < len(wp_ids):
        found = {m["id"] for m in filtered}
        missing = [w for w in wp_ids if w not in found]
        logger.warning(f"WP IDs not found in metadata: {missing}")
    return filtered


def get_wp_info(item: dict) -> tuple[str, str]:
    """Extract (wp_id, project_name) from a metadata item."""
    wp_id = item["id"]
    project_name = item.get("project_name") or item.get("nama_proyek", "").replace(
        " ", ""
    )
    return wp_id, project_name


def find_step1_path(wp_id: str, project_name: str, output_dir: str) -> Path | None:
    """Locate existing step1 markdown file."""
    path = Path(output_dir) / f"{wp_id}_{project_name}" / f"step1_{project_name}.md"
    return path if path.exists() else None


def update_pipeline_results(output_dir: str, wp_id: str, updates: dict):
    """Merge updates into existing pipeline_results.json for a specific WP."""
    backup_path = Path(output_dir) / "pipeline_results.json"
    existing = []
    if backup_path.exists():
        existing = json.loads(backup_path.read_text(encoding="utf-8"))

    found = False
    for entry in existing:
        if entry.get("wp_id") == wp_id:
            entry.update(updates)
            found = True
            break
    if not found:
        existing.append(updates)

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Step functions
# ---------------------------------------------------------------------------


def step_extract(metadata: list[dict], output_dir: str) -> dict[str, dict]:
    """Step 1: Extract all PDFs to markdown."""
    ext = _load("extractor", "pipeline/1_extractor.py")

    logger.info(f"Step 1: Extracting {len(metadata)} PDFs...")
    extraction_results = {}
    for item in metadata:
        wp_id, project_name = get_wp_info(item)
        pdf_path = item["folder"] + item["filename"]
        r = ext.extract_pdf(
            pdf_path, wp_id=wp_id, project_name=project_name, output_dir=output_dir
        )
        extraction_results[wp_id] = r
        status = "ok" if r["status"] == "ok" else f"ERROR: {r['error']}"
        method = r.get("extraction_method", "auto")
        logger.info(f"  {wp_id} ({item['filename']}): {status} [{method}]")
    return extraction_results


def step_segment(metadata: list[dict], output_dir: str) -> dict[str, dict]:
    """Step 2: Segment markdown by headings. Requires step1 output."""
    seg = _load("segmenter", "pipeline/2_segmenter.py")

    logger.info(f"Step 2: Segmenting {len(metadata)} WPs...")
    segment_results = {}
    for item in metadata:
        wp_id, project_name = get_wp_info(item)
        step1_path = find_step1_path(wp_id, project_name, output_dir)
        if step1_path is None:
            logger.warning(f"  {wp_id}: step1 not found, skipping segmentation")
            segment_results[wp_id] = {"status": "error", "error": "step1 not found"}
            continue

        seg_result = seg.segment_file(
            str(step1_path), wp_id, project_name, output_dir=output_dir
        )
        segment_results[wp_id] = seg_result
        logger.info(f"  {wp_id}: {seg_result['section_count']} sections")
    return segment_results


def step_preprocess(sections_by_wp: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Step 3: Preprocess all sections (tokenize, clean)."""
    pre = _load("preprocessor", "pipeline/4_preprocessor.py")

    logger.info(f"Step 3: Preprocessing sections for {len(sections_by_wp)} WPs...")
    for wp_id, sections in sections_by_wp.items():
        pre.preprocess_sections(sections)
        logger.info(f"  {wp_id}: {len(sections)} sections preprocessed")
    return sections_by_wp


def step_keywords(
    metadata: list[dict],
    output_dir: str,
    sections_by_wp: dict[str, list[dict]],
    extraction_results: dict[str, dict] | None = None,
) -> dict[str, dict]:
    """Step 4: TF-IDF keywords + NER."""
    kw = _load("kw", "pipeline/3_keyword_extractor.py")

    logger.info("Step 4: Extracting keywords...")

    corpus_texts = []
    for wp_id, sections in sections_by_wp.items():
        full_clean = " ".join(s.get("clean_text", "") for s in sections)
        if full_clean.strip():
            corpus_texts.append(full_clean)

    vectorizer = kw.fit_tfidf(corpus_texts) if corpus_texts else None

    keywords_by_wp = {}
    for item in metadata:
        wp_id, project_name = get_wp_info(item)
        sections = sections_by_wp.get(wp_id, [])
        full_clean = " ".join(s.get("clean_text", "") for s in sections)

        if vectorizer and full_clean.strip():
            tfidf_kw = kw.extract_keywords(vectorizer, full_clean, top_n=20)
        else:
            tfidf_kw = []

        raw_md = ""
        if extraction_results and wp_id in extraction_results:
            raw_md = extraction_results[wp_id].get("markdown", "")
        if not raw_md:
            step1_path = find_step1_path(wp_id, project_name, output_dir)
            if step1_path:
                raw_md = step1_path.read_text(encoding="utf-8")

        ner_entities = kw.extract_ner_entities(raw_md[:50000]) if raw_md else []

        keywords_by_wp[wp_id] = {
            "tfidf": tfidf_kw,
            "ner_entities": ner_entities,
        }
        logger.info(
            f"  {wp_id}: {len(tfidf_kw)} keywords, {len(ner_entities)} entities"
        )

    return keywords_by_wp


def step_classify(
    metadata: list[dict],
    output_dir: str,
    sections_by_wp: dict[str, list[dict]],
    classifier_mode: str = "fine-tuned",
) -> dict[str, dict]:
    """Step 5: Section classification (fine-tuned RoBERTa)."""
    clf = _load("classifier", "pipeline/7_section_classifier.py")
    clf.set_mode(classifier_mode)

    logger.info(
        f"Step 5: Classifying sections for {len(sections_by_wp)} WPs ({classifier_mode})..."
    )
    classify_results = {}
    for item in metadata:
        wp_id, project_name = get_wp_info(item)
        sections = sections_by_wp.get(wp_id)
        if sections is None:
            logger.warning(f"  {wp_id}: no sections found, skipping classification")
            classify_results[wp_id] = {"status": "error", "error": "no sections"}
            continue

        step1_path = find_step1_path(wp_id, project_name, output_dir)
        clf_result = clf.classify_file(
            str(step1_path) if step1_path else "",
            sections,
            wp_id,
            project_name,
            output_dir=output_dir,
            mode=classifier_mode,
        )

        # Flaw #3: propagate classification errors
        if clf_result.get("status") != "ok":
            logger.warning(
                f"  {wp_id}: classification failed: {clf_result.get('error')}"
            )
        else:
            # Secondary check: detect all-empty labels
            empty_labels = sum(
                1
                for s in clf_result.get("sections", [])
                if not s.get("predicted_label")
            )
            total = len(clf_result.get("sections", []))
            if total > 0 and empty_labels == total:
                clf_result["status"] = "partial_error"
                clf_result["error"] = "classification produced 0 labels"
                logger.warning(f"  {wp_id}: all {total} sections have empty labels")

        classify_results[wp_id] = clf_result
        logger.info(
            f"  {wp_id}: {len(clf_result.get('sections', []))} sections classified "
            f"[{clf_result['status']}]"
        )

    return classify_results


def step_embed(
    metadata: list[dict], output_dir: str, sections_by_wp: dict[str, list[dict]]
) -> dict[str, dict]:
    """Step 6: Generate sentence embeddings for each WP's sections."""
    emb = _load("embedding", "pipeline/5_embedding_generator.py")

    logger.info(f"Step 6: Generating embeddings for {len(sections_by_wp)} WPs...")
    embed_results = {}
    for item in metadata:
        wp_id, project_name = get_wp_info(item)
        sections = sections_by_wp.get(wp_id)
        if sections is None:
            logger.warning(f"  {wp_id}: no sections found, skipping embedding")
            embed_results[wp_id] = {"status": "error", "error": "no sections"}
            continue

        result = emb.embed_file(
            wp_id, sections, output_dir=output_dir, project_name=project_name
        )
        embed_results[wp_id] = result
        logger.info(
            f"  {wp_id}: {result.get('embedding_count', 0)} embeddings "
            f"[{result['status']}]"
        )
    return embed_results


def step_linguistic(
    metadata: list[dict], output_dir: str, sections_by_wp: dict[str, list[dict]]
) -> dict[str, dict]:
    """Step 7: Linguistic error detection for each WP's sections."""
    ling = _load("linguistic", "pipeline/6_linguistic_checker.py")

    logger.info(f"Step 7: Running linguistic checks on {len(sections_by_wp)} WPs...")
    ling_results = {}
    for item in metadata:
        wp_id, project_name = get_wp_info(item)
        sections = sections_by_wp.get(wp_id)
        if sections is None:
            logger.warning(f"  {wp_id}: no sections found, skipping linguistic check")
            ling_results[wp_id] = {"status": "error", "error": "no sections"}
            continue

        result = ling.check_file(
            wp_id, sections, output_dir=output_dir, project_name=project_name
        )
        ling_results[wp_id] = result
        logger.info(
            f"  {wp_id}: {result.get('total_errors', 0)} errors, "
            f"rate={result.get('error_rate', 0)}/1000 [{result['status']}]"
        )
    return ling_results


def step_credibility(
    metadata: list[dict],
    output_dir: str,
    pipeline_results: list[dict] | None = None,
) -> list[dict]:
    """Step 9: Credibility scoring (corpus-level, after all signals)."""
    cred = _load("credibility", "pipeline/credibility_scorer.py")

    # If pipeline_results not provided, load from file
    if pipeline_results is None:
        results_path = Path(output_dir) / "pipeline_results.json"
        if results_path.exists():
            pipeline_results = json.loads(results_path.read_text(encoding="utf-8"))
        else:
            logger.error("No pipeline_results.json found — run prior steps first")
            return []

    logger.info(f"Step 9: Scoring credibility for {len(pipeline_results)} WPs...")
    scored = cred.score_corpus(pipeline_results)

    # Merge scored data back into pipeline results
    score_map = {r["wp_id"]: r for r in scored}
    for wp in pipeline_results:
        wp_id = wp.get("wp_id")
        if wp_id in score_map:
            wp.update(score_map[wp_id])

    # Save enriched pipeline results
    results_path = Path(output_dir) / "pipeline_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(
        json.dumps(pipeline_results, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    for s in scored:
        logger.info(
            f"  {s['wp_id']}: {s.get('credibility_score', 0):.1f} "
            f"({s.get('credibility_label', '?')}) "
            f"profile={s.get('profile_label', '?')} [{s.get('profile_confidence', '?')}]"
        )

    return scored


def step_plagiarism(
    metadata: list[dict],
    output_dir: str,
    embeddings_by_wp: dict[str, list[dict]] | None = None,
    threshold: float = 0.85,
) -> dict[str, dict]:
    """Step 8: Cross-WP plagiarism detection (corpus-level).

    Runs after all WPs have embeddings. If embeddings_by_wp is not provided,
    loads from step5 JSON files.
    """
    plag = _load("plagiarism", "pipeline/8_plagiarism_detector.py")

    if embeddings_by_wp is None:
        logger.info("Loading embeddings from step5 JSON files...")
        embeddings_by_wp = plag.load_embeddings_from_step5(output_dir, metadata)

    logger.info(
        f"Step 8: Plagiarism detection across {len(embeddings_by_wp)} WPs "
        f"(threshold={threshold})..."
    )
    results = plag.detect_plagiarism(embeddings_by_wp, threshold=threshold)
    plag.save_plagiarism_results(results, output_dir)
    return results


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------


def run_pipeline(
    metadata: list[dict],
    output_dir: str = "output_md",
    batch_size: int = 10,
    skip_db: bool = False,
    classifier_mode: str = "fine-tuned",
) -> list[dict]:
    """Run full pipeline on a list of whitepaper metadata entries."""
    ext = _load("extractor", "pipeline/1_extractor.py")
    seg = _load("segmenter", "pipeline/2_segmenter.py")
    pre = _load("preprocessor", "pipeline/4_preprocessor.py")
    kw = _load("kw", "pipeline/3_keyword_extractor.py")
    clf = _load("classifier", "pipeline/7_section_classifier.py")

    # Set classifier mode
    clf.set_mode(classifier_mode)
    logger.info(f"Classifier mode: {classifier_mode}")

    # --- Step 1: Extract all PDFs ---
    logger.info(f"Step 1: Extracting {len(metadata)} PDFs...")
    extraction_results = {}
    for item in metadata:
        wp_id, project_name = get_wp_info(item)
        pdf_path = item["folder"] + item["filename"]
        r = ext.extract_pdf(
            pdf_path, wp_id=wp_id, project_name=project_name, output_dir=output_dir
        )
        extraction_results[wp_id] = r
        status = "ok" if r["status"] == "ok" else f"ERROR: {r['error']}"
        logger.info(f"  {wp_id} ({item['filename']}): {status}")

    # --- Fit TF-IDF on full corpus ---
    logger.info("Fitting TF-IDF vectorizer on full corpus...")
    corpus_texts = [
        r["markdown"]
        for r in extraction_results.values()
        if r["status"] == "ok" and r.get("markdown")
    ]
    vectorizer = kw.fit_tfidf(corpus_texts) if corpus_texts else None

    # --- Process each WP through steps 2-5 ---
    results = []
    batches = [
        metadata[i : i + batch_size] for i in range(0, len(metadata), batch_size)
    ]
    for batch_idx, batch in enumerate(batches):
        logger.info(f"Processing batch {batch_idx + 1}/{len(batches)}...")
        for item in batch:
            wp_id, project_name = get_wp_info(item)
            ext_result = extraction_results.get(wp_id, {})
            if ext_result.get("status") != "ok":
                results.append(ext_result)
                continue

            result = {
                "wp_id": wp_id,
                "project_name": project_name,
                "filename": item["filename"],
                "quality_label": item.get("quality_label", ""),
                "profile_label": item.get("profile_label", ""),
                "status": "ok",
                "error": None,
                "page_count": ext_result.get("page_count"),
                "extraction_method": ext_result.get("extraction_method", "auto"),
                "sections": [],
                "keywords": {},
            }

            try:
                # Step 2: Segment
                step1_path = ext_result["md_path"]
                seg_result = seg.segment_file(
                    step1_path, wp_id, project_name, output_dir=output_dir
                )
                sections = seg_result["sections"]

                # Step 3: Preprocess
                pre.preprocess_sections(sections)

                # Step 4: Keywords
                full_clean = " ".join(s.get("clean_text", "") for s in sections)
                if vectorizer:
                    tfidf_kw = kw.extract_keywords(vectorizer, full_clean, top_n=20)
                else:
                    tfidf_kw = []
                ner_entities = kw.extract_ner_entities(
                    ext_result.get("markdown", "")[:50000]
                )
                result["keywords"] = {
                    "tfidf": tfidf_kw,
                    "ner_entities": ner_entities,
                }

                # Step 5: Classify sections
                clf_result = clf.classify_file(
                    step1_path,
                    sections,
                    wp_id,
                    project_name,
                    output_dir=output_dir,
                    mode=classifier_mode,
                )
                result["sections"] = clf_result["sections"]

                # Flaw #3: propagate classification errors
                if clf_result.get("status") != "ok":
                    result["status"] = "partial_error"
                    result["error"] = (
                        f"classification failed: {clf_result.get('error', 'unknown')}"
                    )
                    logger.warning(
                        f"  {wp_id}: classification failed but sections preserved"
                    )
                else:
                    empty_labels = sum(
                        1 for s in result["sections"] if not s.get("predicted_label")
                    )
                    if (
                        empty_labels == len(result["sections"])
                        and len(result["sections"]) > 0
                    ):
                        result["status"] = "partial_error"
                        result["error"] = "classification produced 0 labels"

                # Step 6: Embeddings (per-WP)
                emb_mod = _load("embedding", "pipeline/5_embedding_generator.py")
                emb_result = emb_mod.embed_file(
                    wp_id, sections, output_dir=output_dir, project_name=project_name
                )
                result["embedding_count"] = emb_result.get("embedding_count", 0)
                result["embedding_dim"] = emb_result.get("embedding_dim", 0)

                # Step 7: Linguistic checks (per-WP)
                ling_mod = _load("linguistic", "pipeline/6_linguistic_checker.py")
                ling_result = ling_mod.check_file(
                    wp_id, sections, output_dir=output_dir, project_name=project_name
                )
                result["linguistic_error_rate"] = ling_result.get("error_rate", 0)
                result["linguistic_total_errors"] = ling_result.get("total_errors", 0)
                result["linguistic_error_categories"] = ling_result.get(
                    "error_categories", {}
                )

            except Exception as e:
                logger.error(f"  Pipeline error for {wp_id}: {e}")
                result.update({"status": "error", "error": str(e)})

            results.append(result)
            logger.info(
                f"  {wp_id}: {len(result['sections'])} sections, "
                f"{len(result['keywords'].get('tfidf', []))} keywords "
                f"[{result['status']}]"
            )

    # --- Step 8: Plagiarism detection (corpus-level, after all WPs) ---
    try:
        plag_mod = _load("plagiarism", "pipeline/8_plagiarism_detector.py")
        plag_results = plag_mod.load_embeddings_from_step5(output_dir, metadata)
        if plag_results:
            plagiarism = plag_mod.detect_plagiarism(plag_results, threshold=0.85)
            plag_mod.save_plagiarism_results(plagiarism, output_dir)
            # Enrich per-WP results with plagiarism data
            for r in results:
                wp_id = r.get("wp_id")
                if wp_id and wp_id in plagiarism:
                    wp_plag = plagiarism[wp_id]
                    r["plagiarism_rate"] = wp_plag.get("plagiarism_rate", 0)
                    r["plagiarism_flagged_count"] = len(
                        wp_plag.get("flagged_pairs", [])
                    )
            logger.info(
                f"Step 8: Plagiarism detection complete for {len(plag_results)} WPs"
            )
        else:
            logger.warning("Step 8: No embeddings found, skipping plagiarism detection")
    except Exception as e:
        logger.error(f"Step 8: Plagiarism detection failed: {e}")

    # --- Step 9: Credibility scoring (corpus-level) ---
    try:
        cred_scored = step_credibility(metadata, output_dir, pipeline_results=results)
        # Enrich per-WP results with credibility data
        cred_map = {s["wp_id"]: s for s in cred_scored}
        for r in results:
            wp_id = r.get("wp_id")
            if wp_id and wp_id in cred_map:
                cr = cred_map[wp_id]
                r["credibility_score"] = cr.get("credibility_score", 0)
                r["credibility_label"] = cr.get("credibility_label", "")
                r["profile_label_inferred"] = cr.get("profile_label", "")
                r["profile_confidence"] = cr.get("profile_confidence", "")
                r["profile_similarity"] = cr.get("profile_similarity", {})
                r["label_distribution"] = cr.get("label_distribution", {})
                r["signal_breakdown"] = cr.get("signal_breakdown", {})
                r["red_flags"] = cr.get("red_flags", [])
                r["investor_summary"] = cr.get("investor_summary", "")
        logger.info(f"Step 9: Credibility scoring complete for {len(cred_scored)} WPs")
    except Exception as e:
        logger.error(f"Step 9: Credibility scoring failed: {e}")

    # --- Save JSON backup ---
    _save_json_backup(results, output_dir)

    if not skip_db:
        _save_to_mongo(results)

    return results


def run_step(
    step: str, metadata: list[dict], output_dir: str, classifier_mode: str = "fine-tuned"
):
    """Run a specific pipeline step or step range."""

    if step == "extract":
        extraction_results = step_extract(metadata, output_dir)
        for wp_id, r in extraction_results.items():
            entry = {
                "wp_id": wp_id,
                "status": r["status"],
                "extraction_method": r.get("extraction_method", "auto"),
                "page_count": r.get("page_count"),
            }
            if r["status"] != "ok":
                entry["error"] = r.get("error")
            update_pipeline_results(output_dir, wp_id, entry)

    elif step == "segment":
        segment_results = step_segment(metadata, output_dir)
        for wp_id, r in segment_results.items():
            update_pipeline_results(
                output_dir,
                wp_id,
                {
                    "wp_id": wp_id,
                    "section_count": r.get("section_count", 0),
                },
            )

    elif step == "classify":
        # Needs: segment -> preprocess -> classify
        seg_results = step_segment(metadata, output_dir)
        sections_by_wp = {
            wp_id: r["sections"]
            for wp_id, r in seg_results.items()
            if r.get("status") == "ok"
        }

        step_preprocess(sections_by_wp)
        classify_results = step_classify(
            metadata, output_dir, sections_by_wp, classifier_mode=classifier_mode
        )

        for wp_id, r in classify_results.items():
            sections = r.get("sections", [])
            update_pipeline_results(
                output_dir,
                wp_id,
                {
                    "wp_id": wp_id,
                    "section_count": len(sections),
                    "section_labels": [
                        {
                            "heading": s.get("heading", ""),
                            "label": s.get("predicted_label", ""),
                        }
                        for s in sections
                    ],
                    "status": r.get("status", "ok"),
                },
            )

    elif step == "segment-to-classify":
        # Run steps 2-5 in sequence
        seg_results = step_segment(metadata, output_dir)
        sections_by_wp = {
            wp_id: r["sections"]
            for wp_id, r in seg_results.items()
            if r.get("status") == "ok"
        }

        step_preprocess(sections_by_wp)
        keywords_by_wp = step_keywords(metadata, output_dir, sections_by_wp)
        classify_results = step_classify(
            metadata, output_dir, sections_by_wp, classifier_mode=classifier_mode
        )

        for item in metadata:
            wp_id, project_name = get_wp_info(item)
            sections = classify_results.get(wp_id, {}).get("sections", [])
            clf_status = classify_results.get(wp_id, {}).get("status", "error")
            update_pipeline_results(
                output_dir,
                wp_id,
                {
                    "wp_id": wp_id,
                    "project_name": project_name,
                    "filename": item["filename"],
                    "quality_label": item.get("quality_label", ""),
                    "profile_label": item.get("profile_label", ""),
                    "status": clf_status,
                    "section_count": len(sections),
                    "section_labels": [
                        {
                            "heading": s.get("heading", ""),
                            "label": s.get("predicted_label", ""),
                        }
                        for s in sections
                    ],
                    "keywords": keywords_by_wp.get(wp_id, {}),
                },
            )

    elif step == "embed":
        # Needs: segment -> preprocess -> embed
        seg_results = step_segment(metadata, output_dir)
        sections_by_wp = {
            wp_id: r["sections"]
            for wp_id, r in seg_results.items()
            if r.get("status") == "ok"
        }
        step_preprocess(sections_by_wp)
        embed_results = step_embed(metadata, output_dir, sections_by_wp)

        for wp_id, r in embed_results.items():
            update_pipeline_results(
                output_dir,
                wp_id,
                {
                    "wp_id": wp_id,
                    "embedding_count": r.get("embedding_count", 0),
                    "embedding_dim": r.get("embedding_dim", 0),
                    "status": r.get("status", "ok"),
                },
            )

    elif step == "linguistic":
        # Needs: segment (raw body text for linguistic checks)
        seg_results = step_segment(metadata, output_dir)
        sections_by_wp = {
            wp_id: r["sections"]
            for wp_id, r in seg_results.items()
            if r.get("status") == "ok"
        }
        ling_results = step_linguistic(metadata, output_dir, sections_by_wp)

        for wp_id, r in ling_results.items():
            update_pipeline_results(
                output_dir,
                wp_id,
                {
                    "wp_id": wp_id,
                    "linguistic_error_rate": r.get("error_rate", 0),
                    "linguistic_total_errors": r.get("total_errors", 0),
                    "linguistic_error_categories": r.get("error_categories", {}),
                    "status": r.get("status", "ok"),
                },
            )

    elif step == "plagiarism":
        # Corpus-level; loads embeddings from step5 JSON files
        plag_results = step_plagiarism(metadata, output_dir, threshold=0.85)

        for wp_id, r in plag_results.items():
            update_pipeline_results(
                output_dir,
                wp_id,
                {
                    "wp_id": wp_id,
                    "plagiarism_rate": r.get("plagiarism_rate", 0),
                    "plagiarism_flagged_count": len(r.get("flagged_pairs", [])),
                    "status": "ok",
                },
            )

    elif step == "credibility":
        # Corpus-level; requires all prior signals in pipeline_results.json
        scored = step_credibility(metadata, output_dir)
        for s in scored:
            wp_id = s.get("wp_id", "")
            update_pipeline_results(
                output_dir,
                wp_id,
                {
                    "wp_id": wp_id,
                    "credibility_score": s.get("credibility_score", 0),
                    "credibility_label": s.get("credibility_label", ""),
                    "profile_label_inferred": s.get("profile_label", ""),
                    "profile_confidence": s.get("profile_confidence", ""),
                    "profile_similarity": s.get("profile_similarity", {}),
                    "label_distribution": s.get("label_distribution", {}),
                    "signal_breakdown": s.get("signal_breakdown", {}),
                    "red_flags": s.get("red_flags", []),
                    "investor_summary": s.get("investor_summary", ""),
                    "status": "ok",
                },
            )

    else:
        logger.error(f"Unknown step: {step}")
        return

    logger.info(f"Step '{step}' completed.")


# ---------------------------------------------------------------------------
# Save helpers
# ---------------------------------------------------------------------------


def _save_json_backup(results: list[dict], output_dir: str):
    """Save pipeline results as JSON backup."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    backup_path = Path(output_dir) / "pipeline_results.json"
    backup_data = []
    for r in results:
        entry = {k: v for k, v in r.items() if k != "sections"}
        entry["section_count"] = len(r.get("sections", []))
        entry["section_labels"] = [
            {"heading": s.get("heading", ""), "label": s.get("predicted_label", "")}
            for s in r.get("sections", [])
        ]
        # Embedding data
        entry.setdefault("embedding_count", r.get("embedding_count", 0))
        entry.setdefault("embedding_dim", r.get("embedding_dim", 0))
        # Linguistic data
        entry.setdefault("linguistic_error_rate", r.get("linguistic_error_rate", 0))
        entry.setdefault("linguistic_total_errors", r.get("linguistic_total_errors", 0))
        entry.setdefault(
            "linguistic_error_categories", r.get("linguistic_error_categories", {})
        )
        # Plagiarism data
        entry.setdefault("plagiarism_rate", r.get("plagiarism_rate", 0))
        entry.setdefault(
            "plagiarism_flagged_count", r.get("plagiarism_flagged_count", 0)
        )
        # Credibility data
        entry.setdefault("credibility_score", r.get("credibility_score", 0))
        entry.setdefault("credibility_label", r.get("credibility_label", ""))
        entry.setdefault("profile_label_inferred", r.get("profile_label_inferred", ""))
        entry.setdefault("profile_confidence", r.get("profile_confidence", ""))
        entry.setdefault("signal_breakdown", r.get("signal_breakdown", {}))
        entry.setdefault("red_flags", r.get("red_flags", []))
        backup_data.append(entry)
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False)
    logger.info(f"JSON backup saved to {backup_path}")


def _save_to_mongo(results: list[dict]):
    """Save pipeline results to MongoDB."""
    try:
        from pymongo import MongoClient

        client = MongoClient("mongodb://localhost:27017/")
        db = client["skripsi_wp"]
        saved = 0
        for r in results:
            if r.get("status") not in ("ok", "partial_error"):
                continue
            db["pipeline_results"].update_one(
                {"_id": r["wp_id"]},
                {"$set": r},
                upsert=True,
            )
            saved += 1
        logger.info(f"Saved {saved} results to MongoDB")
    except Exception as e:
        logger.error(f"MongoDB save failed: {e}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run NLP pipeline for whitepapers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline/batch_runner.py                           # full pipeline
  python pipeline/batch_runner.py --step extract            # extract only
  python pipeline/batch_runner.py --step segment            # segment only
  python pipeline/batch_runner.py --step classify           # segment+preprocess+classify
  python pipeline/batch_runner.py --step segment-to-classify # steps 2-5
  python pipeline/batch_runner.py --step embed              # embedding generation
  python pipeline/batch_runner.py --step linguistic         # linguistic error detection
  python pipeline/batch_runner.py --step plagiarism         # plagiarism detection (needs embeddings)
  python pipeline/batch_runner.py --step credibility        # credibility scoring (needs all signals)
  python pipeline/batch_runner.py --wp WP_007,WP_033        # specific WPs
  python pipeline/batch_runner.py --step classify --wp WP_030 --dry-run
        """,
    )
    parser.add_argument(
        "--step",
        choices=[
            "extract",
            "segment",
            "classify",
            "segment-to-classify",
            "embed",
            "linguistic",
            "plagiarism",
            "credibility",
            "all",
        ],
        default="all",
        help="Which pipeline step(s) to run (default: all)",
    )
    parser.add_argument(
        "--wp",
        type=str,
        default=None,
        help="Comma-separated WP IDs to process (e.g., WP_007,WP_033)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output_md",
        help="Base output directory (default: output_md)",
    )
    parser.add_argument(
        "--no-increment",
        action="store_true",
        help="Don't auto-increment output dir (overwrite existing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip MongoDB write",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of WPs per batch (default: 10)",
    )
    parser.add_argument(
        "--classifier",
        choices=["fine-tuned"],
        default="fine-tuned",
        help="Section classifier mode (default: fine-tuned)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    with open("wp_metadata.json", encoding="utf-8") as f:
        metadata = json.load(f)

    metadata = filter_metadata(metadata, args.wp)

    if not metadata:
        logger.error("No WPs to process (check --wp filter)")
        sys.exit(1)

    # Resolve output directory with auto-increment
    if args.no_increment:
        output_dir = args.output_dir
    else:
        output_dir = resolve_output_dir(args.output_dir)

    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Processing {len(metadata)} WPs, step={args.step}")

    if args.step == "all":
        run_pipeline(
            metadata,
            output_dir=output_dir,
            batch_size=args.batch_size,
            skip_db=args.dry_run,
            classifier_mode=args.classifier,
        )
    else:
        run_step(
            args.step, metadata, output_dir=output_dir, classifier_mode=args.classifier
        )
