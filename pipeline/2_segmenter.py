"""
7_segmenter.py — Segment enriched markdown by heading structure.

Reads step1_{project_name}.md from extractor, splits into sections using ## headings
as boundaries. Outputs step2_{project_name}.md with segment_id annotations.

Each section annotation format:
    <!-- segment_id: WP_001_S001 | heading: Tokenomics | step: 2 -->

Flaw #1 fix: headings with empty body are skipped and their heading text is
preserved as `parent_heading` metadata on the next non-empty section.
"""

import re
import logging
from pathlib import Path

from pipeline import save_step_md

logger = logging.getLogger(__name__)

_SKIP_HEADINGS = {"references", "table of contents", "contents", "index"}


def segment_markdown(markdown: str, wp_id: str) -> list[dict]:
    """Split markdown into sections by ## headings.

    Args:
        markdown: Full markdown string from extractor (step1).
        wp_id: Whitepaper ID (e.g. "WP_019") for segment_id generation.

    Returns:
        List of section dicts:
            - segment_id: str (e.g. "WP_019_S001")
            - heading: str (heading text without ## prefix)
            - heading_level: int (number of # chars)
            - body: str (paragraph text under this heading)
            - char_count: int
            - parent_heading: str (optional, heading of skipped empty parent)
    """
    pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    matches = list(pattern.finditer(markdown))

    # --- Phase 1: Build raw sections ---
    raw_sections = []
    for i, match in enumerate(matches):
        heading_level = len(match.group(1))
        heading_text = match.group(2).strip()

        if heading_text.lower() in _SKIP_HEADINGS:
            continue

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        body = markdown[start:end].strip()

        raw_sections.append({
            "heading": heading_text,
            "heading_level": heading_level,
            "body": body,
        })

    # --- Phase 2: Filter empty-body headings, preserve as parent_heading ---
    sections = []
    pending_parents = []

    for section in raw_sections:
        if not section["body"].strip():
            pending_parents.append(section["heading"])
            continue
        if pending_parents:
            section["parent_heading"] = " > ".join(pending_parents)
            pending_parents = []
        sections.append(section)

    # --- Phase 3: Assign sequential segment_id after filtering ---
    for idx, section in enumerate(sections, start=1):
        section["segment_id"] = f"{wp_id}_S{idx:03d}"
        section["char_count"] = len(section["body"])

    return sections


def build_enriched_md(sections: list[dict]) -> str:
    """Build enriched markdown string with inline segment annotations."""
    lines = []
    for sec in sections:
        prefix = "#" * sec["heading_level"]
        lines.append(f"{prefix} {sec['heading']}")
        parent = sec.get("parent_heading", "")
        parent_annot = f" | parent: {parent}" if parent else ""
        lines.append(
            f"<!-- segment_id: {sec['segment_id']} | "
            f"heading: {sec['heading']}{parent_annot} | step: 2 -->"
        )
        lines.append("")
        lines.append(sec["body"])
        lines.append("")
    return "\n".join(lines)


def segment_file(md_path: str, wp_id: str, project_name: str,
                 output_dir: str = "output_md") -> dict:
    """Segment a step1 markdown file and save step2 enriched output.

    Args:
        md_path: Path to step1_{project_name}.md
        wp_id: Whitepaper ID
        project_name: Short project name
        output_dir: Directory to write step2 output

    Returns:
        dict with status, md_path, section_count, sections list
    """
    path = Path(md_path)
    result = {
        "wp_id": wp_id,
        "input_path": str(path),
        "md_path": None,
        "section_count": 0,
        "sections": [],
        "status": "ok",
        "error": None,
    }

    try:
        markdown = path.read_text(encoding="utf-8")
        sections = segment_markdown(markdown, wp_id)
        enriched = build_enriched_md(sections)
        md_path_out = save_step_md(wp_id, project_name, enriched,
                                    step=2, output_dir=output_dir)

        result.update({
            "md_path": md_path_out,
            "section_count": len(sections),
            "sections": sections,
        })

    except Exception as e:
        logger.error(f"Segmentation failed for {path.name}: {e}")
        result.update({"status": "error", "error": str(e)})

    return result
