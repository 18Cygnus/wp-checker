"""Tests for pipeline/whitepaper_gate.py"""

import importlib.util
import os


spec = importlib.util.spec_from_file_location(
    "whitepaper_gate",
    os.path.join(os.path.dirname(__file__), "..", "pipeline", "whitepaper_gate.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _section(label: str, confidence: float, heading: str) -> dict:
    return {
        "heading": heading,
        "predicted_label": label,
        "confidence": confidence,
        "body": f"Content for {heading}",
    }


def test_accepts_obvious_whitepaper():
    markdown = """# NovaChain Whitepaper

## Project Overview
NovaChain is a blockchain protocol for cross-chain liquidity.

## Technical Architecture
The protocol uses validators and smart contracts.

## Tokenomics
Token supply, vesting, and treasury allocation are described here.

## Roadmap
Mainnet milestones and ecosystem expansion.
"""

    sections = [
        _section("project overview", 0.91, "Project Overview"),
        _section("technical architecture", 0.88, "Technical Architecture"),
        _section("tokenomics", 0.93, "Tokenomics"),
        _section("roadmap", 0.84, "Roadmap"),
    ]

    result = mod.assess_whitepaper_candidate(markdown, page_count=8, sections=sections)

    assert result["is_whitepaper"] is True
    assert result["score"] >= mod.ACCEPT_THRESHOLD
    assert "tokenomics" in result["signals"]["text_hits"]
    assert "technical architecture" in result["signals"]["unique_gate_labels"]


def test_rejects_operational_document():
    markdown = """# Invoice 2026

## Billing Summary
Invoice amount and payment due date.

## Payment Details
Bank statement reference and purchase order number.

## Terms of Service
Operational policy for payment handling.
"""

    sections = [
        _section("project overview", 0.24, "Billing Summary"),
        _section("risk and legal", 0.29, "Payment Details"),
        _section("project overview", 0.26, "Terms of Service"),
    ]

    result = mod.assess_whitepaper_candidate(markdown, page_count=2, sections=sections)

    assert result["is_whitepaper"] is False
    assert "invoice" in result["signals"]["negative_hits"]
    assert "whitepaper" not in result["signals"]["text_hits"]


def test_accepts_short_litepaper_with_strong_signals():
    markdown = """# Atlas Protocol Litepaper

## Tokenomics
Utility token distribution for validators and treasury.

## Architecture
Consensus design and staking flow.
"""

    sections = [
        _section("tokenomics", 0.87, "Tokenomics"),
        _section("technical architecture", 0.82, "Architecture"),
    ]

    result = mod.assess_whitepaper_candidate(markdown, page_count=3, sections=sections)

    assert result["is_whitepaper"] is True
    assert "litepaper" in result["signals"]["text_hits"]