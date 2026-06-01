"""
1_extractor.py — PDF to structured markdown extraction using Docling.

Produces per-whitepaper structured markdown with heading hierarchy preserved.
Output is used as input for segmenter.py (paragraph segmentation).

Flaw #4 fix: added enable_ocr parameter for image-only PDFs, plus
is_image_only() detection and validate_ocr_output() quality check.
"""

import re
import json
import logging
from pathlib import Path

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

from pipeline import save_step_md

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

_converter = None
_converter_ocr = None


def _get_converter(enable_ocr: bool = False) -> DocumentConverter:
    """Create a DocumentConverter with memory-safe PDF pipeline options.

    Args:
        enable_ocr: If True, enable OCR for image-only PDFs.
    """
    global _converter, _converter_ocr

    if enable_ocr:
        if _converter_ocr is None:
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = True
            pipeline_options.do_table_structure = True
            pipeline_options.generate_page_images = False
            pipeline_options.images_scale = 1.0

            _converter_ocr = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options,
                        backend=PyPdfiumDocumentBackend,
                    )
                }
            )
        return _converter_ocr
    else:
        if _converter is None:
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = False
            pipeline_options.do_table_structure = True
            pipeline_options.generate_page_images = False
            pipeline_options.images_scale = 1.0

            _converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options,
                        backend=PyPdfiumDocumentBackend,
                    )
                }
            )
        return _converter


def is_image_only(md_content: str, threshold: float = 0.9) -> bool:
    """Check if extracted markdown is predominantly image placeholders.

    Returns True if >90% of non-empty lines are image tags.
    """
    lines = [l.strip() for l in md_content.strip().splitlines() if l.strip()]
    if not lines:
        return True
    image_patterns = ("<!-- image -->", "![image]", "![](", "![")
    image_lines = [l for l in lines if any(p in l for p in image_patterns)]
    return len(image_lines) / len(lines) > threshold


def assess_extraction_quality(md_content: str, page_count: int) -> dict:
    """Assess overall extraction quality and return quality flags.

    Returns dict with:
        - char_count: total non-whitespace characters
        - chars_per_page: average chars per page
        - low_content_ratio: True if <100 chars/page (likely image-heavy)
        - noise_ratio: fraction of lines that look like OCR noise
        - is_low_quality: True if extraction quality is too poor to continue
        - reason: human-readable explanation if is_low_quality
    """
    text = md_content.strip() if md_content else ""
    char_count = len(text.replace("\n", "").replace(" ", ""))
    chars_per_page = (char_count / page_count) if page_count > 0 else 0

    # Count lines that are predominantly non-alphanumeric (OCR noise indicator)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    noise_lines = 0
    for line in lines:
        alphanumeric = sum(c.isalnum() or c.isspace() for c in line)
        if len(line) > 5 and alphanumeric / len(line) < 0.4:
            noise_lines += 1
    noise_ratio = (noise_lines / len(lines)) if lines else 0.0

    low_content_ratio = page_count > 0 and chars_per_page < 100
    is_low_quality = (
        (page_count > 0 and char_count < 200) or
        (low_content_ratio and noise_ratio > 0.3)
    )

    reason = None
    if is_low_quality:
        if char_count < 200:
            reason = f"Extracted text too short ({char_count} chars total)"
        else:
            reason = (
                f"Low content ratio ({chars_per_page:.0f} chars/page) "
                f"with high noise ({noise_ratio:.0%} noisy lines)"
            )

    return {
        "char_count": char_count,
        "chars_per_page": round(chars_per_page, 1),
        "low_content_ratio": low_content_ratio,
        "noise_ratio": round(noise_ratio, 3),
        "is_low_quality": is_low_quality,
        "reason": reason,
    }


def validate_ocr_output(md_content: str) -> dict:
    """Check if OCR produced usable output.

    Returns dict with text_length, heading_count, usable, needs_manual_review.
    """
    text_only = re.sub(r'<!--.*?-->', '', md_content, flags=re.DOTALL).strip()
    headings = re.findall(r'^#{1,3}\s+', md_content, re.MULTILINE)

    return {
        "text_length": len(text_only),
        "heading_count": len(headings),
        "usable": len(text_only) >= 500 and len(headings) >= 2,
        "needs_manual_review": len(text_only) >= 200,
    }


def extract_pdf(pdf_path: str, wp_id: str = None,
                project_name: str = None,
                output_dir: str = "output_md",
                enable_ocr: bool = False) -> dict:
    """
    Extract a PDF whitepaper to structured markdown using Docling.

    Args:
        pdf_path: Path to the PDF file.
        wp_id: Whitepaper ID (e.g. "WP_019"). Defaults to filename stem.
        project_name: Short project name (e.g. "Canton"). Defaults to filename stem.
        output_dir: Directory to save the .md output file.
        enable_ocr: If True, enable OCR (for image-only PDFs).

    Returns:
        dict with keys:
            - wp_id: whitepaper ID
            - project_name: project name used for file naming
            - filename: original filename
            - pdf_path: absolute path used
            - md_path: path to saved markdown file
            - markdown: full markdown string
            - page_count: estimated page count
            - extraction_method: "auto", "ocr", or "auto+ocr_retry"
            - ocr_validation: dict (only if OCR was used)
            - status: "ok" or "error"
            - error: error message if status == "error"
    """
    path = Path(pdf_path)
    _wp_id = wp_id or path.stem
    _project_name = project_name or path.stem

    result_base = {
        "wp_id": _wp_id,
        "project_name": _project_name,
        "filename": path.name,
        "pdf_path": str(path.resolve()),
        "md_path": None,
        "markdown": None,
        "page_count": None,
        "failed_pages": [],
        "extraction_method": "ocr" if enable_ocr else "auto",
        "status": "ok",
        "error": None,
    }

    try:
        converter = _get_converter(enable_ocr=enable_ocr)
        conv_result = converter.convert(str(path))
        markdown = conv_result.document.export_to_markdown()

        # Estimate page count from Docling's page list
        try:
            page_count = len(conv_result.document.pages)
        except Exception:
            page_count = markdown.count("\n---\n") + 1

        # Detect page-level failures from Docling's error log
        failed_pages = []
        try:
            for page_no, page in conv_result.document.pages.items():
                if hasattr(page, '_backend') and page._backend is None:
                    failed_pages.append(page_no)
        except Exception:
            pass

        quality = assess_extraction_quality(markdown, page_count)
        if quality["low_content_ratio"]:
            logger.warning(
                f"{path.name}: Low content ratio "
                f"({quality['chars_per_page']} chars/page, "
                f"noise={quality['noise_ratio']:.0%})"
            )

        if failed_pages:
            logger.warning(
                f"{path.name}: Pages {failed_pages} may have failed during preprocessing"
            )

        # Flaw #4: detect image-only and retry with OCR if not already using it
        if not enable_ocr and is_image_only(markdown):
            logger.info(f"{path.name}: image-only detected, retrying with OCR...")
            ocr_result = extract_pdf(
                pdf_path, wp_id=_wp_id, project_name=_project_name,
                output_dir=output_dir, enable_ocr=True
            )
            ocr_result["extraction_method"] = "auto+ocr_retry"
            ocr_validation = validate_ocr_output(ocr_result.get("markdown", ""))
            ocr_result["ocr_validation"] = ocr_validation
            if not ocr_validation["usable"]:
                logger.warning(
                    f"{path.name}: OCR output not usable "
                    f"(text={ocr_validation['text_length']} chars, "
                    f"headings={ocr_validation['heading_count']}). "
                    f"Manual extraction recommended."
                )
            return ocr_result

        # If OCR was explicitly requested, validate output
        if enable_ocr:
            ocr_validation = validate_ocr_output(markdown)
            result_base["ocr_validation"] = ocr_validation

        # Save markdown via shared utility
        md_path = save_step_md(_wp_id, _project_name, markdown,
                                step=1, output_dir=output_dir)

        result_base.update({
            "md_path": str(md_path),
            "markdown": markdown,
            "page_count": page_count,
            "failed_pages": failed_pages,
            "quality": quality,
        })

    except Exception as e:
        logger.error(f"Extraction failed for {path.name}: {e}")
        result_base.update({
            "status": "error",
            "error": str(e),
        })

    return result_base


def extract_batch(metadata: list, output_dir: str = "output_md") -> list:
    """
    Extract a list of whitepapers from metadata manifest.

    Args:
        metadata: list of dicts with at least 'folder' and 'filename' keys.
        output_dir: Directory to save .md output files.

    Returns:
        List of extraction result dicts (one per entry).
    """
    results = []
    total = len(metadata)
    for i, item in enumerate(metadata, 1):
        pdf_path = Path(item["folder"]) / item["filename"]
        wp_id = item.get("id", pdf_path.stem)
        project_name = item.get("project_name") or item.get("nama_proyek", pdf_path.stem).replace(" ", "")
        print(f"[{i}/{total}] Extracting {item['filename']} ...")
        result = extract_pdf(str(pdf_path), wp_id=wp_id,
                              project_name=project_name, output_dir=output_dir)
        if result["status"] == "ok":
            print(f"  OK — {result['page_count']} pages, {len(result['markdown'])} chars")
        else:
            print(f"  ERROR — {result['error']}")
        results.append(result)
    return results


if __name__ == "__main__":
    import sys

    # Quick CLI test: python 1_extractor.py <path_to_pdf>
    if len(sys.argv) < 2:
        print("Usage: python 1_extractor.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"\nExtracting: {pdf_path}")
    result = extract_pdf(pdf_path, output_dir="output_md")

    if result["status"] == "ok":
        print(f"\nStatus    : OK")
        print(f"Pages     : {result['page_count']}")
        print(f"Chars     : {len(result['markdown'])}")
        print(f"Method    : {result['extraction_method']}")
        print(f"Saved to  : {result['md_path']}")
        print(f"\n--- First 1500 chars of markdown ---\n")
        print(result["markdown"][:1500])
    else:
        print(f"\nStatus : ERROR")
        print(f"Error  : {result['error']}")
