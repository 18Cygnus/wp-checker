"""
Evaluate fine-tuned RoBERTa on frozen test set.

Metrics:
  - Accuracy, Macro F1, Weighted F1
  - Per-label Precision, Recall, F1
  - Confusion matrix

Usage:
    python -m pipeline.finetune.evaluate \
        --test data/annotations/test.json \
        --finetuned models/roberta-finetuned-v2/ \
        --output data/annotations/evaluation_report.json
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from torch.utils.data import DataLoader, Dataset
from transformers import (
    RobertaForSequenceClassification,
    RobertaTokenizer,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ── Helpers ────────────────────────────────────────────────────────────────

def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


class SectionDataset(Dataset):
    def __init__(self, records: list[dict], tokenizer, max_len: int):
        self.texts = [r["text"] for r in records]
        self.labels = [r["label_id"] for r in records]
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        encoding = self.tokenizer(
            self.texts[idx],
            truncation=True,
            max_length=self.max_len,
            padding="max_length",
            return_tensors="pt",
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "label": torch.tensor(self.labels[idx], dtype=torch.long),
        }


# ── Metric computation ────────────────────────────────────────────────────

def compute_metrics(y_true: list, y_pred: list, labels: list[str]) -> dict:
    """Compute all evaluation metrics."""
    label_ids = list(range(len(labels)))

    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    weighted_f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)

    per_label_p = precision_score(y_true, y_pred, average=None, labels=label_ids, zero_division=0)
    per_label_r = recall_score(y_true, y_pred, average=None, labels=label_ids, zero_division=0)
    per_label_f1 = f1_score(y_true, y_pred, average=None, labels=label_ids, zero_division=0)

    per_label = {}
    support_counts = {}
    for i, label in enumerate(labels):
        support = sum(1 for y in y_true if y == i)
        support_counts[label] = support
        per_label[label] = {
            "precision": round(float(per_label_p[i]), 4),
            "recall": round(float(per_label_r[i]), 4),
            "f1": round(float(per_label_f1[i]), 4),
            "support": support,
        }

    cm = confusion_matrix(y_true, y_pred, labels=label_ids)

    return {
        "accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "per_label": per_label,
        "confusion_matrix": cm.tolist(),
    }


# ── Fine-tuned RoBERTa evaluation ──────────────────────────────────────────

def evaluate_finetuned(test_data: list[dict], checkpoint_dir: Path,
                       labels_11: list[str], max_seq_len: int = 256) -> dict:
    """Run fine-tuned RoBERTa on test set."""
    print("\n" + "=" * 60)
    print(f"Eksperimen 2: Fine-tuned RoBERTa (Weighted CE)")
    print(f"  Checkpoint: {checkpoint_dir}")
    print("=" * 60)

    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Load hparams for context
    hparams_path = checkpoint_dir / "hparams.json"
    if hparams_path.exists():
        hparams = load_json(hparams_path)
        print(f"  Best epoch: {hparams.get('best_epoch', '?')}")
        print(f"  Best val macro F1: {hparams.get('best_val_macro_f1', '?')}")

    # Load model & tokenizer
    tokenizer = RobertaTokenizer.from_pretrained(str(checkpoint_dir))
    model = RobertaForSequenceClassification.from_pretrained(
        str(checkpoint_dir),
        num_labels=len(labels_11),
    )
    model.to(device)
    model.eval()

    # Build dataloader
    test_dataset = SectionDataset(test_data, tokenizer, max_seq_len)
    test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False, num_workers=0)

    y_true = [r["label_id"] for r in test_data]
    y_pred = []

    print(f"  Running inference on {len(test_data)} segments...")
    t0 = time.time()

    with torch.no_grad():
        for batch in test_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            preds = torch.argmax(outputs.logits, dim=-1)
            y_pred.extend(preds.cpu().numpy().tolist())

    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s ({elapsed/len(test_data)*1000:.1f}ms/sample)")

    metrics = compute_metrics(y_true, y_pred, labels_11)
    metrics["inference_time_sec"] = round(elapsed, 1)
    metrics["model"] = "roberta-base (fine-tuned)"
    metrics["method"] = "weighted CE, clean only"
    metrics["checkpoint"] = str(checkpoint_dir)
    if hparams_path.exists():
        metrics["best_epoch"] = hparams.get("best_epoch")
        metrics["best_val_macro_f1"] = hparams.get("best_val_macro_f1")

    print(f"\n  Accuracy:    {metrics['accuracy']:.4f}")
    print(f"  Macro F1:    {metrics['macro_f1']:.4f}")
    print(f"  Weighted F1: {metrics['weighted_f1']:.4f}")

    return metrics, y_pred


# ── Confusion matrix plot ──────────────────────────────────────────────────

def plot_confusion_matrix(cm, labels, title, output_path: Path):
    """Plot a single confusion matrix."""
    short_labels = [l.replace(" and ", " & ").replace("use cases & ecosystem", "use cases")
                    for l in labels]
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(cm, interpolation="nearest", cmap="Blues")
    ax.set_title(title, fontsize=13, fontweight="bold")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    thresh = cm.max() / 2.0
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, str(cm[i][j]),
                    ha="center", va="center",
                    color="white" if cm[i][j] > thresh else "black",
                    fontsize=8)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(short_labels, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(short_labels, fontsize=9)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved confusion matrix: {output_path}")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Evaluate section classifiers on test set")
    parser.add_argument("--test", type=str, required=True, help="Path to test.json")
    parser.add_argument("--finetuned", type=str, required=True,
                        help="Path to fine-tuned checkpoint dir")
    parser.add_argument("--output", type=str,
                        default="data/annotations/evaluation_report.json",
                        help="Output path for evaluation report")
    parser.add_argument("--max-seq-len", type=int, default=256)
    args = parser.parse_args()

    test_path = PROJECT_ROOT / args.test
    ft_dir = PROJECT_ROOT / args.finetuned
    output_path = PROJECT_ROOT / args.output

    # Load test data
    test_data = load_json(test_path)
    print(f"Test set: {len(test_data)} segments")
    print(f"Test WPs: {sorted(set(r['wp_id'] for r in test_data))}")

    # Load labels dynamically from label.json
    labels_path = PROJECT_ROOT / "data" / "annotations" / "label.json"
    if not labels_path.exists():
        labels_path = PROJECT_ROOT / "label.json"
    labels = load_json(labels_path)[0]["labels"]
    print(f"Labels: {len(labels)}")

    # Label distribution in test
    print("\nTest label distribution:")
    from collections import Counter
    dist = Counter(r["label"] for r in test_data)
    for label in labels:
        count = dist.get(label, 0)
        pct = count / len(test_data) * 100
        print(f"  {label:<28} {count:>4} ({pct:>5.1f}%)")

    # ── Run evaluation ──
    ft_metrics, ft_preds = evaluate_finetuned(test_data, ft_dir, labels, args.max_seq_len)

    # ── Build report ──
    report = {
        "test_set_size": len(test_data),
        "test_wps": sorted(set(r["wp_id"] for r in test_data)),
        "label_count": len(labels),
        "labels": labels,
        "experiments": {
            "finetuned_weighted_ce": ft_metrics,
        },
    }

    # Training diagnostics
    training_log_path = ft_dir / "training_log.json"
    if training_log_path.exists():
        tlog = load_json(training_log_path)
        best_epoch = ft_metrics.get("best_epoch", "?")
        total_epochs = len(tlog)
        report["training_diagnostics"] = {
            "finetuned_weighted_ce": {
                "best_epoch": best_epoch,
                "total_epochs_run": total_epochs,
                "best_val_macro_f1": ft_metrics.get("best_val_macro_f1"),
                "curve_path": str(ft_dir / "training_curves.png"),
            }
        }

    save_json(report, output_path)
    print(f"\nSaved evaluation report: {output_path}")

    # Plot confusion matrix
    cm_path = output_path.parent / (output_path.stem + "_confusion_matrix.png")
    plot_confusion_matrix(
        np.array(ft_metrics["confusion_matrix"]),
        labels,
        f"Fine-tuned RoBERTa — {ft_dir.name}",
        cm_path,
    )


if __name__ == "__main__":
    main()
