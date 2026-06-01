"""
A4: Parse annotated step2 markdown files → labeled_dataset.json

Reads fine_tune/WP_*/step2_*.md files and extracts:
- segment_id, wp_id, heading, body text, section_label
- Joins with wp_metadata.json for quality_label and profile_label
- Validates against label.json

Usage:
    python -m pipeline.finetune.parse_annotations
"""

import json
import re
import sys
from glob import glob
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

FINE_TUNE_DIR = PROJECT_ROOT / "fine_tune"
LABEL_JSON = PROJECT_ROOT / "data" / "annotations" / "label.json"
WP_METADATA_JSON = PROJECT_ROOT / "wp_metadata.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "annotations" / "labeled_dataset.json"

# Regex patterns for step2 format
RE_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
RE_SEGMENT_META = re.compile(
    r"segment_id:\s*(WP_\d{3}_S\d+)\s*\|\s*heading:\s*(.+?)(?:\s*\||\s*-->)"
)
RE_SECTION_LABEL = re.compile(r"section_label:\s*(.+?)\s*-->")


def load_valid_labels() -> list[str]:
    with open(LABEL_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return data[0]["labels"]


def load_wp_metadata() -> dict:
    with open(WP_METADATA_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return {wp["id"]: wp for wp in data}


def parse_step2_file(filepath: Path) -> list[dict]:
    """Parse a single step2 markdown file into segments."""
    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()

    segments = []
    current = None

    def save_current():
        if current and current.get("segment_id") and current.get("label"):
            current["body"] = current["body"].strip()
            segments.append(current)

    for line in lines:
        raw = line.rstrip("\n")

        # Check for heading
        heading_match = RE_HEADING.match(raw)
        if heading_match:
            save_current()
            current = {
                "heading": heading_match.group(2).strip(),
                "segment_id": None,
                "label": None,
                "body": "",
            }
            continue

        # Check for segment metadata in HTML comment
        meta_match = RE_SEGMENT_META.search(raw)
        if meta_match:
            new_sid = meta_match.group(1)
            meta_heading = meta_match.group(2).strip()

            if current and current.get("segment_id") and current["segment_id"] != new_sid:
                # New segment without a markdown heading — save previous and start new
                save_current()
                current = {
                    "heading": meta_heading,
                    "segment_id": new_sid,
                    "label": None,
                    "body": "",
                }
            else:
                if current is None:
                    current = {
                        "heading": meta_heading,
                        "segment_id": new_sid,
                        "label": None,
                        "body": "",
                    }
                else:
                    current["segment_id"] = new_sid
            continue

        if current is None:
            continue

        # Check for section_label in HTML comment
        label_match = RE_SECTION_LABEL.search(raw)
        if label_match:
            current["label"] = label_match.group(1).strip()
            continue

        # Skip image placeholder comments
        if raw.strip() == "<!-- image -->":
            continue

        # Skip other HTML comment lines (metadata we already parsed)
        if raw.strip().startswith("<!--") and raw.strip().endswith("-->"):
            continue

        # Accumulate body text
        current["body"] += raw + "\n"

    # Don't forget last segment
    save_current()

    return segments


def main():
    valid_labels = load_valid_labels()
    label_to_id = {label: idx for idx, label in enumerate(valid_labels)}
    wp_metadata = load_wp_metadata()

    # Discover step2 files
    pattern = str(FINE_TUNE_DIR / "WP_*" / "step2_*.md")
    step2_files = sorted(glob(pattern))

    if not step2_files:
        print(f"ERROR: No step2 files found matching {pattern}", file=sys.stderr)
        sys.exit(1)

    all_segments = []
    wp_ids_seen = set()
    errors = []
    warnings = []

    for filepath in step2_files:
        filepath = Path(filepath)
        segments = parse_step2_file(filepath)

        for seg in segments:
            sid = seg["segment_id"]
            wp_id = sid[:6]  # WP_XXX
            wp_ids_seen.add(wp_id)

            # Validate label
            if seg["label"] not in valid_labels:
                errors.append(f"{sid}: unknown label '{seg['label']}' in {filepath.name}")
                continue

            # Validate text
            text = f"{seg['heading']}\n{seg['body']}" if seg["body"] else seg["heading"]
            if not text.strip():
                warnings.append(f"{sid}: empty text, skipping")
                continue

            # Lookup metadata
            meta = wp_metadata.get(wp_id, {})

            all_segments.append({
                "section_id": sid,
                "wp_id": wp_id,
                "project_name": meta.get("nama_proyek", ""),
                "quality_label": meta.get("quality_label", ""),
                "profile_label": meta.get("profile_label", ""),
                "heading": seg["heading"],
                "text": text,
                "label": seg["label"],
                "label_id": label_to_id[seg["label"]],
            })

    # --- Validation Summary ---
    print(f"\nParsed: {len(step2_files)} files, {len(all_segments)} segments")

    # Label distribution
    label_counts = {}
    for seg in all_segments:
        label_counts[seg["label"]] = label_counts.get(seg["label"], 0) + 1

    print("\nLabel Distribution:")
    for label in valid_labels:
        count = label_counts.get(label, 0)
        pct = count / len(all_segments) * 100 if all_segments else 0
        bar = "#" * int(pct)
        print(f"  {label:<30s} {count:>4d}  ({pct:5.1f}%)  {bar}")

    # WP coverage
    expected_wps = set(wp_metadata.keys())
    missing_wps = expected_wps - wp_ids_seen
    if missing_wps:
        errors.append(f"Missing WPs: {sorted(missing_wps)}")

    # Print warnings and errors
    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  WARN: {w}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  ERR: {e}")
        sys.exit(1)

    # Segment count check
    if abs(len(all_segments) - 1409) / 1409 > 0.05:
        print(f"\nWARN: Segment count {len(all_segments)} deviates >5% from expected 1409")

    print(f"\nValidation: OK - All labels valid, {len(warnings)} warnings, "
          f"{len(wp_ids_seen)}/{len(expected_wps)} WPs covered")

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_segments, f, ensure_ascii=False, indent=2)

    print(f"Saved to: {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
