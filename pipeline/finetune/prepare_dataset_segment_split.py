"""
Segment-Level Train/Val/Test Split (for comparison with WP-level split).

Unlike prepare_dataset.py which splits by WP, this splits individual segments
randomly regardless of WP membership. This is expected to produce optimistically
biased results due to intra-WP leakage.

Output goes to data/annotations/segment_split/ to avoid overwriting WP-level files.

Usage:
    python -m pipeline.finetune.prepare_dataset_segment_split [--seed 42]
"""

import argparse
import json
import random
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

LABELED_DATASET = PROJECT_ROOT / "data" / "annotations" / "labeled_dataset.json"
LABEL_JSON = PROJECT_ROOT / "data" / "annotations" / "label.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "annotations" / "segment_split"

MAX_WEIGHT_CAP = 5.0

# Target ratios: ~62% train, ~15% val, ~22% test (similar to WP-level proportions)
VAL_RATIO = 0.15
TEST_RATIO = 0.22


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Segment-level dataset split")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    dataset = load_json(LABELED_DATASET)
    all_labels = load_json(LABEL_JSON)[0]["labels"]

    print(f"Dataset: {len(dataset)} segments, {len(all_labels)} labels")
    print(f"Seed: {args.seed}")
    print(f"Split mode: SEGMENT-LEVEL (random per segment)\n")

    # Extract labels for stratification
    labels_arr = [r["label"] for r in dataset]

    # First split: train+val vs test
    train_val_data, test_data, train_val_labels, _ = train_test_split(
        dataset, labels_arr,
        test_size=TEST_RATIO,
        random_state=args.seed,
        stratify=labels_arr,
    )

    # Second split: train vs val
    val_ratio_adjusted = VAL_RATIO / (1 - TEST_RATIO)
    train_val_labels2 = [r["label"] for r in train_val_data]
    train_data, val_data, _, _ = train_test_split(
        train_val_data, train_val_labels2,
        test_size=val_ratio_adjusted,
        random_state=args.seed,
        stratify=train_val_labels2,
    )

    total = len(train_data) + len(val_data) + len(test_data)
    assert total == len(dataset), f"Segment leak: {total} != {len(dataset)}"

    # WP overlap analysis
    train_wps = {r["wp_id"] for r in train_data}
    val_wps = {r["wp_id"] for r in val_data}
    test_wps = {r["wp_id"] for r in test_data}
    print(f"WP overlap (expected with segment-level split):")
    print(f"  Train∩Val:  {len(train_wps & val_wps)} WPs")
    print(f"  Train∩Test: {len(train_wps & test_wps)} WPs")
    print(f"  Val∩Test:   {len(val_wps & test_wps)} WPs")

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
            print(f"    {label:<30s} {c:>4d} ({c/len(split_data)*100:5.1f}%)")

    # Save splits
    save_json(train_data, OUTPUT_DIR / "train.json")
    save_json(val_data, OUTPUT_DIR / "val.json")
    save_json(test_data, OUTPUT_DIR / "test.json")
    print(f"\nSaved to {OUTPUT_DIR}/:")
    print(f"  train.json ({len(train_data)}), val.json ({len(val_data)}), test.json ({len(test_data)})")

    # Class weights from train
    label_ids = np.array([r["label_id"] for r in train_data])
    class_ids = np.arange(len(all_labels))
    weights = compute_class_weight("balanced", classes=class_ids, y=label_ids)
    weights = np.clip(weights, a_min=None, a_max=MAX_WEIGHT_CAP)

    weights_dict = {label: round(float(weights[i]), 4) for i, label in enumerate(all_labels)}
    print("\nClass weights (from train split, capped at 5.0x):")
    for label, w in weights_dict.items():
        print(f"  {label:<30s} {w:.4f}")

    weights_config = {
        "method": "balanced_inverse_frequency",
        "max_weight_cap": MAX_WEIGHT_CAP,
        "computed_from": "train_split_only",
        "split_mode": "segment_level",
        "train_segments": len(train_data),
        "weights": weights_dict,
    }
    save_json(weights_config, OUTPUT_DIR / "class_weights.json")
    print("Saved: class_weights.json")

    # Split config
    split_config = {
        "random_state": args.seed,
        "split_date": str(date.today()),
        "split_mode": "segment_level",
        "note": "Segments split randomly; WPs may appear in multiple splits (data leakage expected)",
        "total_segments": len(dataset),
        "train_segments": len(train_data),
        "val_segments": len(val_data),
        "test_segments": len(test_data),
        "wp_overlap_train_val": len(train_wps & val_wps),
        "wp_overlap_train_test": len(train_wps & test_wps),
    }
    save_json(split_config, OUTPUT_DIR / "split_config.json")
    print("Saved: split_config.json")


if __name__ == "__main__":
    main()
