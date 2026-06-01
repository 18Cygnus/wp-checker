"""
C1-C4: Fine-tune RoBERTa-base for 11-class section classification.

Includes:
- Weighted CrossEntropyLoss (from class_weights.json)
- Per-epoch eval on val, early stopping on val macro F1
- Best checkpoint saving
- Training curves plot (loss + macro F1)

Usage:
    python -m pipeline.finetune.train \
        --train data/annotations/train.json \
        --val data/annotations/val.json \
        --output models/roberta-finetuned-clean/ \
        --epochs 10 --patience 3 --lr 2e-5
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import f1_score, accuracy_score, classification_report
from torch.utils.data import DataLoader, Dataset
from transformers import (
    RobertaForSequenceClassification,
    RobertaTokenizer,
    get_linear_schedule_with_warmup,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ── Dataset ───────────────────────────────────────────────────────────────

class SectionDataset(Dataset):
    def __init__(self, records: list[dict], tokenizer: RobertaTokenizer, max_len: int):
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


# ── Helpers ───────────────────────────────────────────────────────────────

def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def evaluate(model, dataloader, device, num_labels):
    """Run evaluation, return loss, accuracy, macro F1, per-label F1."""
    model.eval()
    all_preds, all_labels = [], []
    total_loss = 0.0
    loss_fn = nn.CrossEntropyLoss()  # unweighted for val loss

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits

            loss = loss_fn(logits, labels)
            total_loss += loss.item() * labels.size(0)

            preds = torch.argmax(logits, dim=-1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    avg_loss = total_loss / len(all_labels)
    acc = accuracy_score(all_labels, all_preds)
    macro_f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    per_label_f1 = f1_score(
        all_labels, all_preds, average=None, labels=list(range(num_labels)), zero_division=0
    )
    return avg_loss, acc, macro_f1, per_label_f1.tolist(), all_preds, all_labels


def plot_training_curves(log: list[dict], output_path: Path, best_epoch: int):
    """Generate 2-subplot figure: loss curves + macro F1 curves."""
    epochs = [e["epoch"] for e in log]
    train_loss = [e["train_loss"] for e in log]
    val_loss = [e["val_loss"] for e in log]
    train_f1 = [e["train_macro_f1"] for e in log]
    val_f1 = [e["val_macro_f1"] for e in log]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Loss curve
    ax1.plot(epochs, train_loss, "b-o", label="Train Loss", markersize=4)
    ax1.plot(epochs, val_loss, "r-o", label="Val Loss", markersize=4)
    ax1.axvline(x=best_epoch, color="green", linestyle="--", alpha=0.7, label=f"Best epoch ({best_epoch})")
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    ax1.set_title("Training & Validation Loss")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # F1 curve
    ax2.plot(epochs, train_f1, "b-o", label="Train Macro F1", markersize=4)
    ax2.plot(epochs, val_f1, "r-o", label="Val Macro F1", markersize=4)
    ax2.axvline(x=best_epoch, color="green", linestyle="--", alpha=0.7, label=f"Best epoch ({best_epoch})")
    best_val_f1 = log[best_epoch - 1]["val_macro_f1"]
    ax2.annotate(
        f"Best: {best_val_f1:.4f}",
        xy=(best_epoch, best_val_f1),
        xytext=(best_epoch + 0.5, best_val_f1 - 0.05),
        arrowprops=dict(arrowstyle="->", color="green"),
        color="green",
        fontsize=9,
    )
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Macro F1")
    ax2.set_title("Training & Validation Macro F1")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Summary text
    final = log[-1]
    early_stop_text = f"Early stopped at epoch {len(log)}" if len(log) < log[0].get("max_epochs", 10) else f"Completed {len(log)} epochs"
    fig.suptitle(
        f"{early_stop_text}  |  Best epoch: {best_epoch}  |  "
        f"Best val macro F1: {best_val_f1:.4f}",
        fontsize=10,
        y=1.02,
    )

    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved training curves: {output_path}")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fine-tune RoBERTa-base section classifier")
    parser.add_argument("--train", type=str, required=True, help="Path to train.json")
    parser.add_argument("--val", type=str, required=True, help="Path to val.json")
    parser.add_argument("--output", type=str, required=True, help="Output directory for checkpoint")
    parser.add_argument("--weights", type=str, default=None, help="Path to class_weights.json")
    parser.add_argument("--labels", type=str, default=None, help="Path to label.json")
    parser.add_argument("--epochs", type=int, default=10, help="Max epochs")
    parser.add_argument("--patience", type=int, default=3, help="Early stopping patience")
    parser.add_argument("--lr", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size per device")
    parser.add_argument("--grad-accum", type=int, default=2, help="Gradient accumulation steps")
    parser.add_argument("--max-seq-len", type=int, default=256, help="Max sequence length")
    parser.add_argument("--weight-decay", type=float, default=0.01, help="Weight decay")
    parser.add_argument("--warmup-ratio", type=float, default=0.1, help="Warmup ratio")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--model-name", type=str, default="roberta-base", help="Base model")
    parser.add_argument("--hidden-dropout", type=float, default=0.1, help="Hidden & attention dropout prob (default: 0.1)")
    parser.add_argument("--classifier-dropout", type=float, default=None, help="Classifier head dropout (default: same as hidden-dropout)")
    args = parser.parse_args()

    # Reproducibility
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    if device.type == "cuda":
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    # ── Load data ──
    train_data = load_json(Path(args.train))
    val_data = load_json(Path(args.val))
    print(f"\nData: {len(train_data)} train, {len(val_data)} val")

    # Resolve labels
    labels_path = Path(args.labels) if args.labels else PROJECT_ROOT / "data" / "annotations" / "label.json"
    if not labels_path.exists():
        labels_path = PROJECT_ROOT / "label.json"
    all_labels = load_json(labels_path)[0]["labels"]
    num_labels = len(all_labels)
    print(f"Labels: {num_labels} classes")

    # ── Tokenizer & datasets ──
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    tokenizer = RobertaTokenizer.from_pretrained(args.model_name)
    train_dataset = SectionDataset(train_data, tokenizer, args.max_seq_len)
    val_dataset = SectionDataset(val_data, tokenizer, args.max_seq_len)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size * 2, shuffle=False, num_workers=0)

    # ── Class weights ──
    weights_path = Path(args.weights) if args.weights else PROJECT_ROOT / "data" / "annotations" / "class_weights.json"
    if weights_path.exists():
        cw_config = load_json(weights_path)
        weight_dict = cw_config["weights"]
        weight_tensor = torch.tensor(
            [weight_dict[label] for label in all_labels], dtype=torch.float32
        ).to(device)
        print(f"Class weights loaded (capped at {cw_config.get('max_weight_cap', 'N/A')})")
    else:
        weight_tensor = None
        print("No class weights file found, using uniform weights")

    loss_fn = nn.CrossEntropyLoss(weight=weight_tensor)

    # ── Model ──
    classifier_dropout = args.classifier_dropout if args.classifier_dropout is not None else args.hidden_dropout
    model = RobertaForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=num_labels,
        problem_type="single_label_classification",
        hidden_dropout_prob=args.hidden_dropout,
        attention_probs_dropout_prob=args.hidden_dropout,
        classifier_dropout=classifier_dropout,
    )
    model.to(device)

    param_count = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Model: {args.model_name}, {param_count / 1e6:.1f}M trainable params")

    # ── Optimizer & Scheduler ──
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    total_steps = (len(train_loader) // args.grad_accum) * args.epochs
    warmup_steps = int(total_steps * args.warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    effective_batch = args.batch_size * args.grad_accum
    print(f"\nHyperparameters:")
    print(f"  lr={args.lr}, batch={args.batch_size}, grad_accum={args.grad_accum} (effective={effective_batch})")
    print(f"  max_seq_len={args.max_seq_len}, epochs={args.epochs}, patience={args.patience}")
    print(f"  warmup_steps={warmup_steps}/{total_steps}, weight_decay={args.weight_decay}")
    print(f"  hidden_dropout={args.hidden_dropout}, classifier_dropout={classifier_dropout}")

    # ── Training loop ──
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    training_log = []
    best_val_f1 = -1.0
    best_epoch = 0
    patience_counter = 0

    print(f"\n{'='*70}")
    print(f"Starting training...")
    print(f"{'='*70}\n")

    for epoch in range(1, args.epochs + 1):
        epoch_start = time.time()

        # ── Train ──
        model.train()
        train_loss_total = 0.0
        train_preds_all, train_labels_all = [], []
        optimizer.zero_grad()

        for step, batch in enumerate(train_loader):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            loss = loss_fn(logits, labels) / args.grad_accum

            # Skip batch if loss is NaN/Inf to prevent weight corruption
            if not torch.isfinite(loss):
                print(f"  WARNING: non-finite loss at step {step}, skipping batch")
                optimizer.zero_grad()
                continue

            loss.backward()

            # Skip optimizer step if any gradient is NaN/Inf
            has_nan_grad = any(
                p.grad is not None and not torch.isfinite(p.grad).all()
                for p in model.parameters()
            )
            if has_nan_grad:
                print(f"  WARNING: NaN gradient at step {step}, skipping optimizer step")
                optimizer.zero_grad()
                continue

            train_loss_total += loss.item() * args.grad_accum * labels.size(0)

            preds = torch.argmax(logits, dim=-1)
            train_preds_all.extend(preds.cpu().numpy())
            train_labels_all.extend(labels.cpu().numpy())

            if (step + 1) % args.grad_accum == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

        # Handle remaining gradients
        if (step + 1) % args.grad_accum != 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()

        avg_train_loss = train_loss_total / len(train_labels_all)
        train_acc = accuracy_score(train_labels_all, train_preds_all)
        train_macro_f1 = f1_score(train_labels_all, train_preds_all, average="macro", zero_division=0)

        # ── Evaluate ──
        val_loss, val_acc, val_macro_f1, val_per_label_f1, _, _ = evaluate(
            model, val_loader, device, num_labels
        )

        epoch_time = time.time() - epoch_start

        # ── Log ──
        epoch_log = {
            "epoch": epoch,
            "max_epochs": args.epochs,
            "train_loss": round(avg_train_loss, 4),
            "val_loss": round(val_loss, 4),
            "train_accuracy": round(train_acc, 4),
            "val_accuracy": round(val_acc, 4),
            "train_macro_f1": round(train_macro_f1, 4),
            "val_macro_f1": round(val_macro_f1, 4),
            "val_per_label_f1": {all_labels[i]: round(f, 4) for i, f in enumerate(val_per_label_f1)},
            "lr": scheduler.get_last_lr()[0],
            "epoch_time_sec": round(epoch_time, 1),
        }
        training_log.append(epoch_log)

        # Status indicator
        improved = val_macro_f1 > best_val_f1
        status = "** BEST **" if improved else ""

        print(
            f"Epoch {epoch:>2}/{args.epochs}  |  "
            f"Train loss: {avg_train_loss:.4f}  F1: {train_macro_f1:.4f}  |  "
            f"Val loss: {val_loss:.4f}  F1: {val_macro_f1:.4f}  Acc: {val_acc:.4f}  |  "
            f"{epoch_time:.0f}s  {status}"
        )

        # ── Checkpoint ──
        if improved:
            best_val_f1 = val_macro_f1
            best_epoch = epoch
            patience_counter = 0

            model.save_pretrained(output_dir)
            tokenizer.save_pretrained(output_dir)
            print(f"  Checkpoint saved to {output_dir}")
        else:
            patience_counter += 1

        # ── Early stopping ──
        if patience_counter >= args.patience:
            print(f"\nEarly stopping at epoch {epoch} (patience={args.patience})")
            break

    # ── Post-training ──
    print(f"\n{'='*70}")
    print(f"Training complete. Best epoch: {best_epoch}, Best val macro F1: {best_val_f1:.4f}")
    print(f"{'='*70}")

    # Save training log
    save_json(training_log, output_dir / "training_log.json")
    print(f"Saved: training_log.json ({len(training_log)} epochs)")

    # Save label config
    label_config = {
        "labels": all_labels,
        "label_to_id": {label: i for i, label in enumerate(all_labels)},
        "id_to_label": {i: label for i, label in enumerate(all_labels)},
    }
    save_json(label_config, output_dir / "label_config.json")

    # Save hyperparameters
    hparams = {
        "model_name": args.model_name,
        "num_labels": num_labels,
        "max_seq_len": args.max_seq_len,
        "batch_size": args.batch_size,
        "grad_accum": args.grad_accum,
        "effective_batch_size": effective_batch,
        "lr": args.lr,
        "weight_decay": args.weight_decay,
        "warmup_ratio": args.warmup_ratio,
        "epochs_max": args.epochs,
        "epochs_run": len(training_log),
        "patience": args.patience,
        "best_epoch": best_epoch,
        "best_val_macro_f1": round(best_val_f1, 4),
        "seed": args.seed,
        "train_size": len(train_data),
        "val_size": len(val_data),
        "class_weights_used": weights_path.exists(),
        "hidden_dropout": args.hidden_dropout,
        "classifier_dropout": classifier_dropout,
    }
    save_json(hparams, output_dir / "hparams.json")

    # Generate training curves
    plot_training_curves(training_log, output_dir / "training_curves.png", best_epoch)

    # Final classification report on val set (using best checkpoint)
    print("\n--- Val Classification Report (best checkpoint) ---")
    model = RobertaForSequenceClassification.from_pretrained(output_dir).to(device)
    _, _, _, _, val_preds, val_true = evaluate(model, val_loader, device, num_labels)
    report = classification_report(
        val_true, val_preds,
        labels=list(range(num_labels)),
        target_names=all_labels,
        zero_division=0,
    )
    print(report)


if __name__ == "__main__":
    main()
