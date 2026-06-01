"""
B1 + B2: WP-Level Train/Val/Test Split + Class Weights

Splits labeled_dataset.json by WP (not section) so all sections from one
whitepaper land in the same split. Stratified by quality_label.

Validates that all labels appear in every split; performs WP swaps if needed.

Computes inverse-frequency class weights from train split only (capped at 5.0x).

Usage:
    python -m pipeline.finetune.prepare_dataset [--seed 42]
"""

import argparse
import json
import random
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.utils.class_weight import compute_class_weight

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

LABELED_DATASET = PROJECT_ROOT / "data" / "annotations" / "labeled_dataset.json"
WP_METADATA_JSON = PROJECT_ROOT / "wp_metadata.json"
LABEL_JSON = PROJECT_ROOT / "data" / "annotations" / "label.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "annotations"

# Split sizes per quality group  (total: 31 train / 8 val / 6 test = 45)
SPLIT_SIZES = {
    "good":    {"train": 11, "val": 3, "test": 2},   # 16 total
    "average": {"train": 10, "val": 3, "test": 2},   # 15 total
    "poor":    {"train": 10, "val": 2, "test": 2},    # 14 total
}

MAX_WEIGHT_CAP = 5.0


# ── helpers ───────────────────────────────────────────────────────────────

def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def labels_in_wps(wp_ids: list[str], dataset: list[dict]) -> set[str]:
    """Return the set of labels present in the given WP ids."""
    return {r["label"] for r in dataset if r["wp_id"] in set(wp_ids)}


def wps_with_label(label: str, wp_ids: list[str], dataset: list[dict]) -> list[str]:
    """Return WP ids (from wp_ids) that contain at least one segment with `label`."""
    return sorted({r["wp_id"] for r in dataset if r["label"] == label and r["wp_id"] in set(wp_ids)})


def segment_count(wp_id: str, dataset: list[dict]) -> int:
    return sum(1 for r in dataset if r["wp_id"] == wp_id)


# ── core split ────────────────────────────────────────────────────────────

def initial_split(wp_metadata: list[dict], seed: int):
    """Stratified random split by quality_label."""
    rng = random.Random(seed)

    quality_groups = defaultdict(list)
    for wp in wp_metadata:
        quality_groups[wp["quality_label"]].append(wp["id"])

    train_wps, val_wps, test_wps = [], [], []

    for quality in ["good", "average", "poor"]:
        ids = sorted(quality_groups[quality])
        rng.shuffle(ids)

        n_train = SPLIT_SIZES[quality]["train"]
        n_val = SPLIT_SIZES[quality]["val"]

        train_wps.extend(ids[:n_train])
        val_wps.extend(ids[n_train:n_train + n_val])
        test_wps.extend(ids[n_train + n_val:])

    return train_wps, val_wps, test_wps


def validate_and_fix_coverage(
    train_wps: list[str],
    val_wps: list[str],
    test_wps: list[str],
    dataset: list[dict],
    all_labels: list[str],
    seed: int,
) -> list[dict]:
    """
    Ensure all 11 labels appear in every split.
    If a label is missing from val or test, swap a donor WP from train.
    Returns list of swap records.
    """
    rng = random.Random(seed + 1)
    swaps = []

    for split_name, split_wps in [("val", val_wps), ("test", test_wps)]:
        present = labels_in_wps(split_wps, dataset)
        missing = set(all_labels) - present

        for label in sorted(missing):
            # Find donor WPs in train that have this label
            donors = wps_with_label(label, train_wps, dataset)
            if not donors:
                print(f"FATAL: No donor WP in train has label '{label}'", file=sys.stderr)
                sys.exit(1)

            # Pick donor closest to median segment count (avoid losing big WP from train)
            seg_counts = {wp: segment_count(wp, dataset) for wp in donors}
            median_count = sorted(seg_counts.values())[len(seg_counts) // 2]
            donor = min(donors, key=lambda wp: abs(seg_counts[wp] - median_count))

            # Pick a WP to swap out of split (random, but prefer one that won't
            # remove a label that would then be missing)
            candidates = list(split_wps)
            rng.shuffle(candidates)
            swap_out = candidates[0]

            # Perform swap
            train_wps.remove(donor)
            split_wps.remove(swap_out)
            train_wps.append(swap_out)
            split_wps.append(donor)

            swaps.append({
                "reason": f"'{label}' missing from {split_name}",
                "donor_to_split": donor,
                "swapped_to_train": swap_out,
            })
            print(f"  SWAP: {donor} -> {split_name}, {swap_out} -> train  "
                  f"(reason: '{label}' missing from {split_name})")

    # Final validation
    for name, wps in [("train", train_wps), ("val", val_wps), ("test", test_wps)]:
        present = labels_in_wps(wps, dataset)
        missing = set(all_labels) - present
        if missing:
            print(f"FATAL: After swaps, {name} still missing: {missing}", file=sys.stderr)
            sys.exit(1)

    return swaps


# ── class weights ─────────────────────────────────────────────────────────

def compute_weights(train_data: list[dict], all_labels: list[str]) -> dict:
    """Inverse-frequency class weights from train split, capped at MAX_WEIGHT_CAP."""
    label_ids = np.array([r["label_id"] for r in train_data])
    class_ids = np.arange(len(all_labels))

    weights = compute_class_weight("balanced", classes=class_ids, y=label_ids)
    weights = np.clip(weights, a_min=None, a_max=MAX_WEIGHT_CAP)

    return {label: round(float(weights[i]), 4) for i, label in enumerate(all_labels)}


# ── main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="WP-level dataset split + class weights")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    dataset = load_json(LABELED_DATASET)
    wp_metadata = load_json(WP_METADATA_JSON)
    all_labels = load_json(LABEL_JSON)[0]["labels"]

    print(f"Dataset: {len(dataset)} segments, {len(wp_metadata)} WPs, {len(all_labels)} labels")
    print(f"Seed: {args.seed}\n")

    # ── B1: Split ──
    train_wps, val_wps, test_wps = initial_split(wp_metadata, args.seed)

    print("Initial split:")
    print(f"  Train: {len(train_wps)} WPs  |  Val: {len(val_wps)} WPs  |  Test: {len(test_wps)} WPs")

    # Validate & fix label coverage
    print("\nLabel coverage check:")
    swaps = validate_and_fix_coverage(train_wps, val_wps, test_wps, dataset, all_labels, args.seed)
    if not swaps:
        print("  All labels present in all splits -- no swaps needed")

    # Sort for determinism
    train_wps.sort()
    val_wps.sort()
    test_wps.sort()

    # Partition segments
    train_set = set(train_wps)
    val_set = set(val_wps)
    test_set = set(test_wps)
    known_wps = train_set | val_set | test_set

    # WPs not in wp_metadata (e.g. partially-annotated extra WPs) go to train
    extra_train_wps = sorted({r["wp_id"] for r in dataset if r["wp_id"] not in known_wps})
    if extra_train_wps:
        print(f"\nExtra WPs not in metadata (forced to train): {extra_train_wps}")
        train_wps.extend(extra_train_wps)
        train_wps.sort()
        train_set = set(train_wps)

    train_data = [r for r in dataset if r["wp_id"] in train_set]
    val_data = [r for r in dataset if r["wp_id"] in val_set]
    test_data = [r for r in dataset if r["wp_id"] in test_set]

    total = len(train_data) + len(val_data) + len(test_data)
    assert total == len(dataset), f"Segment leak: {total} != {len(dataset)}"

    print(f"\nSegment distribution:")
    print(f"  Train: {len(train_data):>5d} segments ({len(train_data)/len(dataset)*100:.1f}%)")
    print(f"  Val:   {len(val_data):>5d} segments ({len(val_data)/len(dataset)*100:.1f}%)")
    print(f"  Test:  {len(test_data):>5d} segments ({len(test_data)/len(dataset)*100:.1f}%)")

    # Per-split label distribution
    for name, split_data in [("Train", train_data), ("Val", val_data), ("Test", test_data)]:
        counts = defaultdict(int)
        for r in split_data:
            counts[r["label"]] += 1
        print(f"\n  {name} label distribution:")
        for label in all_labels:
            c = counts.get(label, 0)
            print(f"    {label:<30s} {c:>4d}")

    # Save splits
    save_json(train_data, OUTPUT_DIR / "train.json")
    save_json(val_data, OUTPUT_DIR / "val.json")
    save_json(test_data, OUTPUT_DIR / "test.json")
    print(f"\nSaved: train.json ({len(train_data)}), val.json ({len(val_data)}), test.json ({len(test_data)})")

    # ── B2: Class weights ──
    weights = compute_weights(train_data, all_labels)

    print("\nClass weights (from train split, capped at 5.0x):")
    for label, w in weights.items():
        print(f"  {label:<30s} {w:.4f}")

    weights_config = {
        "method": "balanced_inverse_frequency",
        "max_weight_cap": MAX_WEIGHT_CAP,
        "computed_from": "train_split_only",
        "train_segments": len(train_data),
        "weights": weights,
    }
    save_json(weights_config, OUTPUT_DIR / "class_weights.json")
    print(f"Saved: class_weights.json")

    # ── split_config.json ──
    # Quality per WP for the config (extra WPs get "extra" quality label)
    wp_quality = {wp["id"]: wp["quality_label"] for wp in wp_metadata}
    for wp in extra_train_wps:
        wp_quality[wp] = "extra"

    def wps_by_quality(wp_list):
        result = defaultdict(list)
        for wp in sorted(wp_list):
            result[wp_quality.get(wp, "extra")].append(wp)
        return dict(result)

    split_config = {
        "random_state": args.seed,
        "split_date": str(date.today()),
        "train_wps": sorted(train_wps),
        "val_wps": sorted(val_wps),
        "test_wps": sorted(test_wps),
        "train_wps_by_quality": wps_by_quality(train_wps),
        "val_wps_by_quality": wps_by_quality(val_wps),
        "test_wps_by_quality": wps_by_quality(test_wps),
        "train_segments": len(train_data),
        "val_segments": len(val_data),
        "test_segments": len(test_data),
        "label_coverage": {
            "train": sorted(labels_in_wps(train_wps, dataset)),
            "val": sorted(labels_in_wps(val_wps, dataset)),
            "test": sorted(labels_in_wps(test_wps, dataset)),
        },
        "swaps_performed": swaps,
    }
    save_json(split_config, OUTPUT_DIR / "split_config.json")
    print(f"Saved: split_config.json")

    # Final summary
    print(f"\n=== DONE ===")
    print(f"Total: {len(dataset)} segments across {len(wp_metadata) + len(extra_train_wps)} WPs ({len(wp_metadata)} metadata + {len(extra_train_wps)} extra)")
    print(f"Split: {len(train_wps)} train / {len(val_wps)} val / {len(test_wps)} test WPs")
    print(f"All {len(all_labels)} labels present in all splits: YES")
    print(f"Swaps: {len(swaps)}")


if __name__ == "__main__":
    main()
