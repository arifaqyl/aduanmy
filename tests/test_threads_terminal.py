"""Tests for Threads Terminal v2 — service layer + CLI commands.

No network calls. All tests use synthetic data or mock DB paths.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.services.threads_terminal_service import (
    add_eval_case,
    dashboard_snapshot,
    explain_rider_gate,
    explain_rider_gate_verbose,
    export_ops_report,
    impact_preview,
    prune_candidates,
    run_eval_cases,
    session_panel,
)


# ── Gate replay ───────────────────────────────────────────────────────────────


def test_explain_rider_gate_accepts_direct_evidence():
    text = "Stuck at Bangsar on Kelana Jaya line for 25 min already, train not moving"
    result = explain_rider_gate(text)
    assert result["accepted"] is True
    assert result["entity"]


def test_explain_rider_gate_rejects_grab_rant():
    text = "Minute tunggu grab lebih lama dari naik LRT, better mrt or lrt laju"
    result = explain_rider_gate(text)
    assert result["accepted"] is False


def test_explain_rider_gate_rejects_sarcastic_wait():
    text = "nabiledler92 20h Dgn 3 koc tren LRT3 tu ko tunggu je la dia akan ada problem cepat rosak"
    result = explain_rider_gate(text)
    assert result["accepted"] is False


def test_explain_rider_gate_rejects_future_prediction():
    text = "KTM komuter ko tunggu je la nanti akan rosak macam dulu jugak"
    result = explain_rider_gate(text)
    assert result["accepted"] is False


def test_explain_rider_gate_rejects_generic_complaint():
    text = "Kelana Jaya Line delay memang teruk"
    result = explain_rider_gate(text)
    assert result["accepted"] is False


def test_explain_rider_gate_rejects_size_opinion():
    text = "dandihusnah 10h Kecik sangat kalau sama size dgn kelana jaya line. X function kalau rumah sebelah lrt."
    result = explain_rider_gate(text)
    assert result["accepted"] is False


def test_explain_rider_gate_accepts_present_delay():
    text = "Kelana Jaya Line delay again, waiting 25 minutes at Bangsar station hari ni"
    result = explain_rider_gate(text)
    assert result["accepted"] is True


def test_explain_rider_gate_accepts_tak_gerak():
    text = "LRT Ampang tak gerak sekarang, penuh dekat platform"
    result = explain_rider_gate(text)
    assert result["accepted"] is True


def test_explain_rider_gate_accepts_signal_failure():
    text = "MRT Kajang delay due to a signal failure"
    result = explain_rider_gate(text)
    assert result["accepted"] is True


# ── Verbose replay ────────────────────────────────────────────────────────────


def test_verbose_replay_has_matched_terms():
    text = "Kelana Jaya Line delay again, waiting 25 minutes at Bangsar station hari ni"
    result = explain_rider_gate_verbose(text)
    assert result["accepted"] is True
    # At least one step should have matched_terms
    has_terms = any(step.get("matched_terms") for step in result.get("steps", []))
    assert has_terms, "verbose replay should include matched_terms"


def test_verbose_replay_sarcastic_shows_match():
    text = "KTM komuter ko tunggu je la nanti akan rosak macam dulu jugak"
    result = explain_rider_gate_verbose(text)
    assert result["accepted"] is False
    # The non_live_opinion step should show what matched
    for step in result.get("steps", []):
        if step["gate"] == "non_live_opinion" and step["pass"] == "false":
            assert step.get("matched_terms"), "should show which non-live pattern matched"
            break


# ── Session panel shape ───────────────────────────────────────────────────────


def test_session_panel_shape():
    panel = session_panel()
    assert "available" in panel
    assert "path" in panel


# ── Eval case management ─────────────────────────────────────────────────────


def test_add_eval_case_creates_and_detects_duplicate(tmp_path):
    cases_path = tmp_path / "cases.json"
    cases_path.write_text("[]", encoding="utf-8")

    # Add first case
    result = add_eval_case("test post", expected=False, note="test", cases_path=cases_path)
    assert result["added"] is True
    assert result["total_cases"] == 1

    # Duplicate
    result2 = add_eval_case("test post", expected=False, cases_path=cases_path)
    assert result2["added"] is False
    assert result2["reason"] == "duplicate"

    # Verify file
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    assert len(cases) == 1
    assert cases[0]["text"] == "test post"
    assert cases[0]["expected"] is False


def test_run_eval_cases_on_seed_set():
    """Run the actual eval harness seed set — should have zero failures."""
    result = run_eval_cases()
    assert result["total"] > 0
    assert result["passed"] == result["total"], (
        f"Eval harness has {result['failed']} failures: "
        + "; ".join(f.get("text", "")[:60] for f in result.get("failures", []))
    )


def test_run_eval_cases_custom(tmp_path):
    cases_path = tmp_path / "mini.json"
    cases = [
        {"text": "MRT Kajang delay due to a signal failure", "expected": True, "note": "concrete cause"},
        {"text": "Kelana Jaya Line delay memang teruk", "expected": False, "note": "generic"},
    ]
    cases_path.write_text(json.dumps(cases), encoding="utf-8")
    result = run_eval_cases(cases_path=cases_path)
    assert result["total"] == 2
    assert result["passed"] == 2


# ── Dashboard snapshot ────────────────────────────────────────────────────────


def test_dashboard_snapshot_shape():
    snap = dashboard_snapshot()
    assert "session" in snap
    assert "runs" in snap
    # accepted_sample and suspicious_sample may be empty but must exist
    assert "accepted_sample" in snap
    assert "suspicious_sample" in snap


def test_export_ops_report_writes_json(tmp_path):
    out = tmp_path / "report.json"
    path = export_ops_report(out_path=out)
    assert path == out
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "dashboard" in data
    assert "qa" in data
    assert "eval" in data
    assert data["eval"]["total"] > 0


def test_prune_candidates_empty_db(tmp_path):
    import sqlite3

    db = tmp_path / "empty.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE complaints (
            id INTEGER PRIMARY KEY,
            source_platform TEXT,
            raw_text TEXT,
            entity TEXT,
            category TEXT
        )
        """
    )
    conn.commit()
    conn.close()
    assert prune_candidates(db) == []


# ── Regression cases from the prompt ──────────────────────────────────────────


class TestRegressionCases:
    """These must stay rejected/accepted per the prompt spec."""

    @pytest.mark.parametrize(
        "text",
        [
            "nabiledler92 20h Dgn 3 koc tren LRT3 tu ko tunggu je la dia akan ada problem cepat rosak",
            "KTM komuter ko tunggu je la nanti akan rosak macam dulu jugak",
            "Kelana Jaya Line delay memang teruk",
            "dandihusnah 10h Kecik sangat kalau sama size dgn kelana jaya line. X function kalau rumah sebelah lrt. Cuma yg terpaling terdesak je guna lrt. Dah lambat. Sesak. Apa faedah guna lrt?",
        ],
    )
    def test_must_reject(self, text):
        result = explain_rider_gate(text)
        assert result["accepted"] is False, f"Should be REJECTED: {text[:80]}"

    @pytest.mark.parametrize(
        "text",
        [
            "Kelana Jaya Line delay again, waiting 25 minutes at Bangsar station hari ni",
            "LRT Ampang tak gerak sekarang, penuh dekat platform",
            "MRT Kajang delay due to a signal failure",
        ],
    )
    def test_must_accept(self, text):
        result = explain_rider_gate(text)
        assert result["accepted"] is True, f"Should be ACCEPTED: {text[:80]}"
