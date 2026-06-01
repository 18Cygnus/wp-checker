"""
inference.py — Load fine-tuned RoBERTa checkpoint for section classification.

Provides SectionClassifier that can be used by:
  - pipeline/7_section_classifier.py (dual-mode)
  - Flask web app (/api/analyze endpoint)
  - standalone CLI testing

Usage (standalone):
    python -m pipeline.finetune.inference \
        --checkpoint models/roberta-finetuned/ \
        --text "The token burn mechanism reduces supply by 2% quarterly..."

Usage (as module):
    from pipeline.finetune.inference import SectionClassifier
    clf = SectionClassifier("models/roberta-finetuned/")
    result = clf.predict("Some whitepaper section text...")
"""

import argparse
import json
import os
import sys
from pathlib import Path

import torch
from transformers import (
    RobertaForSequenceClassification,
    RobertaTokenizer,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class SectionClassifier:
    """Fine-tuned RoBERTa section classifier with lazy loading."""

    def __init__(self, checkpoint_dir: str, max_seq_len: int = 256, device: str | None = None):
        self.checkpoint_dir = Path(checkpoint_dir)
        if not self.checkpoint_dir.is_absolute():
            self.checkpoint_dir = PROJECT_ROOT / self.checkpoint_dir
        self.max_seq_len = max_seq_len

        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        # Load label config
        label_config_path = self.checkpoint_dir / "label_config.json"
        with open(label_config_path, encoding="utf-8") as f:
            label_config = json.load(f)
        self.labels = label_config["labels"]
        self.id_to_label = {int(k): v for k, v in label_config["id_to_label"].items()}
        self.num_labels = len(self.labels)

        # Load model & tokenizer
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        self.tokenizer = RobertaTokenizer.from_pretrained(str(self.checkpoint_dir))
        self.model = RobertaForSequenceClassification.from_pretrained(
            str(self.checkpoint_dir),
            num_labels=self.num_labels,
        )
        self.model.to(self.device)
        self.model.eval()

    def predict(self, text: str) -> dict:
        """Classify a single text into one of the 11 section labels.

        Args:
            text: Section text (heading + body concatenated).

        Returns:
            {"predicted_label": str, "confidence": float, "all_scores": dict}
        """
        if not text or not text.strip():
            return {
                "predicted_label": "",
                "confidence": 0.0,
                "all_scores": {},
                "classification_note": "empty_text_skipped",
            }

        encoding = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_seq_len,
            padding="max_length",
            return_tensors="pt",
        )
        input_ids = encoding["input_ids"].to(self.device)
        attention_mask = encoding["attention_mask"].to(self.device)

        with torch.no_grad():
            outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1).squeeze(0)

        pred_id = torch.argmax(probs).item()
        confidence = probs[pred_id].item()

        all_scores = {
            self.id_to_label[i]: round(probs[i].item(), 4)
            for i in range(self.num_labels)
        }

        return {
            "predicted_label": self.id_to_label[pred_id],
            "confidence": round(confidence, 4),
            "all_scores": all_scores,
        }

    def predict_batch(self, texts: list[str], batch_size: int = 32) -> list[dict]:
        """Classify a batch of texts.

        Args:
            texts: List of section texts.
            batch_size: Inference batch size.

        Returns:
            List of prediction dicts (same format as predict()).
        """
        results = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]

            # Handle empty texts
            non_empty_indices = [j for j, t in enumerate(batch_texts) if t and t.strip()]
            batch_results = [None] * len(batch_texts)

            for j in range(len(batch_texts)):
                if j not in non_empty_indices:
                    batch_results[j] = {
                        "predicted_label": "",
                        "confidence": 0.0,
                        "all_scores": {},
                        "classification_note": "empty_text_skipped",
                    }

            if non_empty_indices:
                valid_texts = [batch_texts[j] for j in non_empty_indices]
                encoding = self.tokenizer(
                    valid_texts,
                    truncation=True,
                    max_length=self.max_seq_len,
                    padding="max_length",
                    return_tensors="pt",
                )
                input_ids = encoding["input_ids"].to(self.device)
                attention_mask = encoding["attention_mask"].to(self.device)

                with torch.no_grad():
                    outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
                    probs = torch.softmax(outputs.logits, dim=-1)

                for k, j in enumerate(non_empty_indices):
                    p = probs[k]
                    pred_id = torch.argmax(p).item()
                    batch_results[j] = {
                        "predicted_label": self.id_to_label[pred_id],
                        "confidence": round(p[pred_id].item(), 4),
                        "all_scores": {
                            self.id_to_label[idx]: round(p[idx].item(), 4)
                            for idx in range(self.num_labels)
                        },
                    }

            results.extend(batch_results)
        return results


# Convenience loader for Flask / web app
_cached_classifier = None


def load_classifier(checkpoint_dir: str = "models/roberta-finetuned/",
                    max_seq_len: int = 256) -> SectionClassifier:
    """Load classifier once and cache for reuse (e.g. Flask app)."""
    global _cached_classifier
    if _cached_classifier is None:
        _cached_classifier = SectionClassifier(checkpoint_dir, max_seq_len=max_seq_len)
    return _cached_classifier


# CLI for quick testing
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test fine-tuned section classifier")
    parser.add_argument("--checkpoint", type=str, default="models/roberta-finetuned/",
                        help="Checkpoint directory")
    parser.add_argument("--text", type=str, required=True,
                        help="Text to classify")
    parser.add_argument("--max-seq-len", type=int, default=256)
    args = parser.parse_args()

    clf = SectionClassifier(args.checkpoint, max_seq_len=args.max_seq_len)
    result = clf.predict(args.text)

    print(f"\nPredicted: {result['predicted_label']}")
    print(f"Confidence: {result['confidence']:.4f}")
    print("\nAll scores:")
    for label, score in sorted(result["all_scores"].items(), key=lambda x: -x[1]):
        bar = "█" * int(score * 40)
        print(f"  {label:<28s} {score:.4f} {bar}")
