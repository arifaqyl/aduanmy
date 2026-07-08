#!/usr/bin/env python3
"""TrafficMY Threads Terminal Web UI

Minimal local-only web UI at scripts/threads_terminal_web.py.
Reuses the app.services.threads_terminal_service layer.

Usage:
  python scripts/threads_terminal_web.py [--port 8080] [--prod]
"""
from __future__ import annotations

import argparse
import sys
import uvicorn
from pathlib import Path
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.core.runtime import bootstrap_repo_root
bootstrap_repo_root()

from app.services.threads_terminal_service import (
    dashboard_snapshot,
    explain_rider_gate_verbose,
    add_eval_case,
    run_eval_cases,
    impact_preview,
    prune_candidates,
    session_panel,
)
from scripts.threads_terminal import fetch_prod_db

app = FastAPI(title="Threads Terminal Web UI")

# Global flag set at startup
IS_PROD_MODE = False

class CaseAddRequest(BaseModel):
    text: str
    expected: bool
    note: str = ""

# HTML Dashboard with gorgeous dark-themed glassmorphism
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Threads Terminal Ops Dashboard</title>
    <meta name="description" content="Operational terminal and scraper debugging console for Meta Threads rider signal lane.">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(255, 255, 255, 0.03);
            --card-border: rgba(255, 255, 255, 0.06);
            --accent-glow: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
            --accent-cyan: #00f2fe;
            --accent-blue: #4facfe;
            --success-color: #00e676;
            --danger-color: #ff1744;
            --warning-color: #ffea00;
            --text-primary: #ffffff;
            --text-secondary: #90a4ae;
            --font-outfit: 'Outfit', sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: var(--font-outfit);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(0, 242, 254, 0.05) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(79, 172, 254, 0.05) 0%, transparent 40%);
        }

        header {
            padding: 1.5rem 2rem;
            background: rgba(11, 15, 25, 0.8);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--card-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .logo-section h1 {
            font-size: 1.5rem;
            font-weight: 800;
            background: var(--accent-glow);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }

        .logo-section p {
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-top: 0.2rem;
        }

        .badge {
            padding: 0.4rem 0.8rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .badge-prod {
            background: rgba(255, 23, 68, 0.15);
            color: var(--danger-color);
            border: 1px solid rgba(255, 23, 68, 0.3);
        }

        .badge-local {
            background: rgba(0, 230, 176, 0.15);
            color: var(--success-color);
            border: 1px solid rgba(0, 230, 176, 0.3);
        }

        main {
            flex: 1;
            max-width: 1400px;
            width: 100%;
            margin: 0 auto;
            padding: 2rem;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
        }

        @media (max-width: 1024px) {
            main {
                grid-template-columns: 1fr;
            }
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(8px);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: transparent;
            transition: background 0.3s;
        }

        .card:hover {
            border-color: rgba(255, 255, 255, 0.15);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
        }

        .card-cyan:hover::before {
            background: var(--accent-glow);
        }

        .card h2 {
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 1.2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .card h2 span.status-indicator {
            font-size: 0.8rem;
            padding: 0.2rem 0.6rem;
            border-radius: 12px;
        }

        /* Health parameters grid */
        .health-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }

        .health-stat {
            background: rgba(255, 255, 255, 0.015);
            border: 1px solid var(--card-border);
            padding: 1rem;
            border-radius: 12px;
            display: flex;
            flex-direction: column;
            gap: 0.3rem;
        }

        .health-stat label {
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
        }

        .health-stat val {
            font-size: 1.1rem;
            font-weight: 600;
            font-family: var(--font-mono);
        }

        .val-ok { color: var(--success-color); }
        .val-bad { color: var(--danger-color); }
        .val-warn { color: var(--warning-color); }

        /* Tables style */
        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
            text-align: left;
        }

        .data-table th, .data-table td {
            padding: 0.75rem;
            border-bottom: 1px solid var(--card-border);
        }

        .data-table th {
            color: var(--text-secondary);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.75rem;
        }

        .data-table tr:hover td {
            background: rgba(255, 255, 255, 0.01);
        }

        /* Interactive Section styles */
        .interactive-section {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        textarea, input, select {
            width: 100%;
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            color: var(--text-primary);
            padding: 0.75rem;
            font-family: inherit;
            outline: none;
            transition: border-color 0.2s;
        }

        textarea:focus, input:focus, select:focus {
            border-color: var(--accent-cyan);
        }

        textarea {
            resize: vertical;
            min-height: 80px;
        }

        .btn {
            background: var(--accent-glow);
            color: #000;
            font-family: var(--font-outfit);
            font-weight: 600;
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: opacity 0.2s, transform 0.1s;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }

        .btn:hover {
            opacity: 0.9;
        }

        .btn:active {
            transform: scale(0.98);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-primary);
            border: 1px solid var(--card-border);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        /* Gate step diagram */
        .step-list {
            margin-top: 1rem;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }

        .step-item {
            background: rgba(0,0,0,0.15);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 0.75rem;
            display: flex;
            flex-direction: column;
            gap: 0.3rem;
        }

        .step-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-weight: 600;
            font-family: var(--font-mono);
            font-size: 0.8rem;
        }

        .step-details {
            font-size: 0.75rem;
            color: var(--text-secondary);
        }

        .matched-badge {
            background: rgba(0, 242, 254, 0.1);
            color: var(--accent-cyan);
            padding: 0.1rem 0.4rem;
            border-radius: 4px;
            font-size: 0.7rem;
            margin-right: 0.3rem;
            font-family: var(--font-mono);
            display: inline-block;
        }

        .sample-preview {
            max-width: 320px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            color: var(--text-secondary);
        }

        .tab-bar {
            display: flex;
            gap: 0.5rem;
            border-bottom: 1px solid var(--card-border);
            margin-bottom: 1.5rem;
        }

        .tab-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            padding: 0.5rem 1rem;
            cursor: pointer;
            font-family: var(--font-outfit);
            font-size: 0.9rem;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }

        .tab-btn.active {
            color: var(--accent-cyan);
            border-bottom-color: var(--accent-cyan);
            font-weight: 600;
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        footer {
            padding: 0.75rem 2rem;
            border-top: 1px solid var(--card-border);
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 1rem;
            color: var(--text-secondary);
            font-size: 0.75rem;
        }

        kbd {
            display: inline-block;
            padding: 0.1rem 0.4rem;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 4px;
            font-family: var(--font-mono);
            font-size: 0.7rem;
            color: var(--text-primary);
        }

        .footer-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 0.75rem;
            font-family: inherit;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            transition: color 0.2s, background 0.2s;
        }

        .footer-btn:hover {
            color: var(--text-primary);
            background: rgba(255,255,255,0.05);
        }

        .toast {
            position: fixed;
            bottom: 1.5rem;
            right: 1.5rem;
            padding: 0.75rem 1.25rem;
            border-radius: 8px;
            font-weight: 600;
            z-index: 9999;
            font-size: 0.875rem;
            backdrop-filter: blur(8px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
            transition: opacity 0.3s ease;
        }
    </style>
</head>
<body>

    <header>
        <div class="logo-section">
            <h1>Threads Terminal v2</h1>
            <p>TrafficMY Ops Console</p>
        </div>
        <div id="mode-badge" class="badge">Local Mode</div>
    </header>

    <main>
        <!-- LEFT COLUMN: System Status & Diagnostic Summary -->
        <div class="interactive-section">
            <div class="card card-cyan">
                <h2>Health Snapshot</h2>
                <div class="health-grid">
                    <div class="health-stat">
                        <label>Session</label>
                        <val id="session-status">Loading...</val>
                    </div>
                    <div class="health-stat">
                        <label>Collector Status</label>
                        <val id="collector-status">Loading...</val>
                    </div>
                    <div class="health-stat">
                        <label>Last Ingest Inflow</label>
                        <val id="last-ingest-inflow">Loading...</val>
                    </div>
                    <div class="health-stat">
                        <label>Empty Streak</label>
                        <val id="empty-streak">Loading...</val>
                    </div>
                </div>

                <h2>Recent Runs</h2>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Status</th>
                            <th style="text-align: right;">Rows</th>
                            <th style="text-align: right;">Dur</th>
                        </tr>
                    </thead>
                    <tbody id="runs-table-body">
                        <tr><td colspan="4" style="color: var(--text-secondary);">Loading runs...</td></tr>
                    </tbody>
                </table>
            </div>

            <!-- Samples view card -->
            <div class="card">
                <div class="tab-bar">
                    <button class="tab-btn active" onclick="switchTab(event, 'tab-accepted')">Accepted Queue</button>
                    <button class="tab-btn" onclick="switchTab(event, 'tab-suspicious')">Suspicious (QA Flag)</button>
                </div>

                <div id="tab-accepted" class="tab-content active">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Entity</th>
                                <th>Preview</th>
                            </tr>
                        </thead>
                        <tbody id="accepted-table-body">
                            <tr><td colspan="2">No data yet.</td></tr>
                        </tbody>
                    </table>
                </div>

                <div id="tab-suspicious" class="tab-content">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Entity</th>
                                <th>Preview</th>
                            </tr>
                        </thead>
                        <tbody id="suspicious-table-body">
                            <tr><td colspan="2">No data yet.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- RIGHT COLUMN: Gate Replay & Scraper Debugging tools -->
        <div class="interactive-section">
            <div class="card card-cyan">
                <h2>Gate Replay Simulator</h2>
                <div style="display: flex; gap: 0.5rem; margin-bottom: 1rem;">
                    <textarea id="replay-text" placeholder="Paste social media / threads post to run against scraping gates..."></textarea>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <button class="btn" onclick="runReplay()">Analyze Gate Replay</button>
                    <div id="replay-verdict" class="badge" style="display: none;">Accepted</div>
                </div>

                <div id="replay-steps-container" style="margin-top: 1.2rem; display: none;">
                    <h3>Pipeline Steps Breakdown</h3>
                    <div class="step-list" id="replay-steps"></div>
                    
                    <div style="margin-top: 1rem; border-top: 1px solid var(--card-border); padding-top: 1rem; display: flex; align-items: center; justify-content: space-between;">
                        <input id="case-note" placeholder="Add optional developer notes..." style="width: 60%; margin: 0;">
                        <div style="display: flex; gap: 0.4rem;">
                            <button class="btn btn-secondary" style="background: rgba(0, 230, 118, 0.1); color: var(--success-color); border-color: rgba(0, 230, 118, 0.2);" onclick="saveToEval(true)">+ Eval Accept</button>
                            <button class="btn btn-secondary" style="background: rgba(255, 23, 68, 0.1); color: var(--danger-color); border-color: rgba(255, 23, 68, 0.2);" onclick="saveToEval(false)">+ Eval Reject</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Operations / Impact Card -->
            <div class="card">
                <h2>System Controls & Eval</h2>
                <div style="display: flex; gap: 0.5rem; margin-bottom: 1.5rem;">
                    <button class="btn" onclick="runEvalSuite()">Run Regression Eval</button>
                    <button class="btn btn-secondary" onclick="previewImpact()">Preview Prune Impact</button>
                </div>

                <div id="eval-results" style="display: none; background: rgba(0,0,0,0.15); border: 1px solid var(--card-border); padding: 1rem; border-radius: 12px; margin-bottom: 1.5rem;">
                    <h3 style="font-size: 1rem; margin-bottom: 0.5rem;">Evaluation Harness Results</h3>
                    <div id="eval-metrics" style="font-family: var(--font-mono); font-size: 0.85rem; line-height: 1.6;"></div>
                </div>

                <div id="impact-preview-container" style="display: none;">
                    <h3 style="font-size: 1rem; margin-bottom: 0.5rem;">Prune Board Severity Impact</h3>
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Entity</th>
                                <th>Volume</th>
                                <th>Prune Count</th>
                                <th>Severity Transition</th>
                            </tr>
                        </thead>
                        <tbody id="impact-table-body"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </main>

    <footer>
        <span><kbd>r</kbd> focus replay</span>
        <span>·</span>
        <span><kbd>Ctrl+Enter</kbd> run replay</span>
        <span>·</span>
        <button class="footer-btn" onclick="fetchDashboard()">↻ refresh dashboard</button>
        <span>·</span>
        <span id="last-refresh" style="color: var(--text-secondary);">—</span>
    </footer>

    <script>
        let isProdMode = window.location.search.includes('prod=true');

        async function initApp() {
            try {
                const cfg = await fetch('/api/config').then(r => r.json());
                if (cfg.is_prod) isProdMode = true;
            } catch (_) {}

            const badge = document.getElementById('mode-badge');
            if (isProdMode) {
                badge.innerText = "Production Mode";
                badge.className = "badge badge-prod";
            } else {
                badge.innerText = "Local Mode";
                badge.className = "badge badge-local";
            }
            fetchDashboard();
        }

        function showToast(msg, ok = true) {
            const color = ok ? '#00e676' : '#ff1744';
            const bg = ok ? 'rgba(0,230,118,0.12)' : 'rgba(255,23,68,0.12)';
            const toast = document.createElement('div');
            toast.className = 'toast';
            toast.style.cssText = `background:${bg};color:${color};border:1px solid ${color}44;`;
            toast.textContent = msg;
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }, 2500);
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            const tag = document.activeElement ? document.activeElement.tagName : '';
            if (e.key === 'r' && !e.ctrlKey && !e.metaKey && !e.altKey &&
                tag !== 'TEXTAREA' && tag !== 'INPUT') {
                e.preventDefault();
                const ta = document.getElementById('replay-text');
                if (ta) ta.focus();
            }
        });

        async function fetchDashboard() {
            try {
                const response = await fetch(`/api/dashboard?prod=${isProdMode}`);
                const data = await response.json();
                
                // Set health items
                const sessionStatusVal = document.getElementById('session-status');
                sessionStatusVal.innerText = data.session.available ? "ACTIVE" : "MISSING";
                sessionStatusVal.className = data.session.available ? "val-ok" : "val-bad";

                const colStatusVal = document.getElementById('collector-status');
                const lastRun = data.collector || {};
                colStatusVal.innerText = (lastRun.status || "UNKNOWN").toUpperCase();
                const okStatuses = ['completed', 'healthy', 'ok', 'success'];
                colStatusVal.className = okStatuses.includes((lastRun.status || '').toLowerCase()) && !lastRun.needs_attention ? "val-ok" : "val-bad";

                const inflowVal = document.getElementById('last-ingest-inflow');
                inflowVal.innerText = `${lastRun.row_count || 0} rows`;
                inflowVal.className = (lastRun.row_count || 0) > 0 ? "val-ok" : "val-warn";

                const streakVal = document.getElementById('empty-streak');
                streakVal.innerText = lastRun.consecutive_empty_runs || 0;
                streakVal.className = (lastRun.consecutive_empty_runs || 0) >= 3 ? "val-bad" : "val-ok";

                // Set runs
                const runsTbody = document.getElementById('runs-table-body');
                runsTbody.innerHTML = '';
                (data.runs || []).forEach(run => {
                    const dateStr = (run.finished_at || '').substring(11, 19) || '—';
                    const tr = document.createElement('tr');
                    const st = (run.status || '').toLowerCase();
                    const stOk = ['completed', 'healthy', 'ok', 'success'].includes(st);
                    tr.innerHTML = `
                        <td>${dateStr}</td>
                        <td class="${stOk ? 'val-ok' : 'val-bad'}">${run.status}</td>
                        <td style="text-align: right;">${run.row_count}</td>
                        <td style="text-align: right; color: var(--text-secondary);">${parseFloat(run.duration_seconds || 0).toFixed(1)}s</td>
                    `;
                    runsTbody.appendChild(tr);
                });

                // Set accepted table
                const acceptedTbody = document.getElementById('accepted-table-body');
                acceptedTbody.innerHTML = '';
                if (data.accepted_sample && data.accepted_sample.length > 0) {
                    data.accepted_sample.forEach(item => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td><span style="color: var(--accent-cyan); font-weight: 600;">${item.entity || '—'}</span></td>
                            <td><div class="sample-preview">${item.preview}</div></td>
                        `;
                        acceptedTbody.appendChild(tr);
                    });
                } else {
                    acceptedTbody.innerHTML = '<tr><td colspan="2" style="color: var(--text-secondary);">No accepted rows.</td></tr>';
                }

                // Set suspicious table
                const suspiciousTbody = document.getElementById('suspicious-table-body');
                suspiciousTbody.innerHTML = '';
                if (data.suspicious_sample && data.suspicious_sample.length > 0) {
                    data.suspicious_sample.forEach(item => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td><span style="color: var(--warning-color); font-weight: 600;">${item.entity || '—'}</span></td>
                            <td><div class="sample-preview">${item.preview}</div></td>
                        `;
                        suspiciousTbody.appendChild(tr);
                    });
                } else {
                    suspiciousTbody.innerHTML = '<tr><td colspan="2" style="color: var(--text-secondary);">No suspicious rows flagging warnings.</td></tr>';
                }

                const ts = document.getElementById('last-refresh');
                if (ts) ts.textContent = 'refreshed ' + new Date().toLocaleTimeString();

            } catch (err) {
                console.error("Failed to load dashboard:", err);
                showToast('Dashboard fetch failed — is the server running?', false);
            }
        }

        async function runReplay() {
            const text = document.getElementById('replay-text').value.trim();
            if (!text) return;

            try {
                const response = await fetch(`/api/replay?text=${encodeURIComponent(text)}`);
                const data = await response.json();

                const verdictBadge = document.getElementById('replay-verdict');
                verdictBadge.style.display = 'block';
                if (data.accepted) {
                    verdictBadge.innerText = 'ACCEPTED';
                    verdictBadge.style.background = 'rgba(0, 230, 118, 0.15)';
                    verdictBadge.style.color = 'var(--success-color)';
                    verdictBadge.style.border = '1px solid rgba(0, 230, 118, 0.3)';
                } else {
                    verdictBadge.innerText = 'REJECTED';
                    verdictBadge.style.background = 'rgba(255, 23, 68, 0.15)';
                    verdictBadge.style.color = 'var(--danger-color)';
                    verdictBadge.style.border = '1px solid rgba(255, 23, 68, 0.3)';
                }

                const stepsContainer = document.getElementById('replay-steps-container');
                stepsContainer.style.display = 'block';

                const stepsDiv = document.getElementById('replay-steps');
                stepsDiv.innerHTML = '';

                (data.steps || []).forEach(step => {
                    const isPass = step.pass === 'true';
                    const matchBadges = (step.matched_terms || []).map(term => `<span class="matched-badge">${term}</span>`).join('');
                    
                    const stepItem = document.createElement('div');
                    stepItem.className = 'step-item';
                    stepItem.innerHTML = `
                        <div class="step-header">
                            <span>${step.gate}</span>
                            <span class="${isPass ? 'val-ok' : 'val-bad'}">${isPass ? 'PASS' : 'FAIL'}</span>
                        </div>
                        <div class="step-details">${step.detail}</div>
                        ${matchBadges ? `<div style="margin-top: 0.4rem;">${matchBadges}</div>` : ''}
                    `;
                    stepsDiv.appendChild(stepItem);
                });

            } catch (err) {
                console.error("Replay failure:", err);
            }
        }

        async function saveToEval(expected) {
            const text = document.getElementById('replay-text').value.trim();
            const note = document.getElementById('case-note').value.trim();
            if (!text) { showToast('No replay text to save.', false); return; }

            try {
                const response = await fetch('/api/case/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text, expected, note })
                });
                const result = await response.json();
                if (result.added) {
                    showToast(`Eval case added (expected=${expected ? 'accept' : 'reject'}, total=${result.total_cases})`, true);
                    document.getElementById('case-note').value = '';
                } else {
                    showToast(`Not added: ${result.reason}`, false);
                }
            } catch (err) {
                console.error("Failed to add eval case:", err);
                showToast('Network error saving eval case.', false);
            }
        }

        async function runEvalSuite() {
            try {
                const response = await fetch('/api/case/run');
                const result = await response.json();
                
                const evalPanel = document.getElementById('eval-results');
                evalPanel.style.display = 'block';
                
                const metricsDiv = document.getElementById('eval-metrics');
                metricsDiv.innerHTML = `
                    <strong>Passed:</strong> ${result.passed}/${result.total}<br>
                    <strong>Accuracy:</strong> ${(result.accuracy * 100).toFixed(1)}%<br>
                    <strong>Precision:</strong> ${(result.precision * 100).toFixed(1)}%<br>
                    <strong>Recall:</strong> ${(result.recall * 100).toFixed(1)}%<br>
                    <strong>Failures count:</strong> ${result.failed}
                `;
            } catch (err) {
                console.error("Failed to run eval:", err);
            }
        }

        async function previewImpact() {
            try {
                const response = await fetch(`/api/impact?prod=${isProdMode}`);
                const data = await response.json();

                const container = document.getElementById('impact-preview-container');
                container.style.display = 'block';

                const tbody = document.getElementById('impact-table-body');
                tbody.innerHTML = '';

                data.forEach(item => {
                    const tr = document.createElement('tr');
                    const hasChange = item.current_severity !== item.projected_severity;
                    tr.innerHTML = `
                        <td><span style="font-weight: 600;">${item.entity || '—'}</span></td>
                        <td>${item.total_rows}</td>
                        <td class="val-bad">${item.would_prune}</td>
                        <td>
                            <span class="${hasChange ? 'val-warn' : ''}">
                                ${item.current_severity} → ${item.projected_severity}
                            </span>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (err) {
                console.error("Failed to load impact preview:", err);
            }
        }

        function switchTab(evt, tabId) {
            const tabs = document.getElementsByClassName('tab-content');
            for (let i = 0; i < tabs.length; i++) {
                tabs[i].classList.remove('active');
            }
            const buttons = document.getElementsByClassName('tab-btn');
            for (let i = 0; i < buttons.length; i++) {
                buttons[i].classList.remove('active');
            }
            document.getElementById(tabId).classList.add('active');
            evt.currentTarget.classList.add('active');
        }

        // Ctrl+Enter in replay textarea triggers analysis
        document.addEventListener('DOMContentLoaded', function() {
            const ta = document.getElementById('replay-text');
            if (ta) {
                ta.addEventListener('keydown', function(e) {
                    if (e.ctrlKey && e.key === 'Enter') {
                        e.preventDefault();
                        runReplay();
                    }
                });
            }
        });

        window.onload = initApp;
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index(prod: bool = False):
    return HTMLResponse(content=HTML_TEMPLATE, status_code=200)

@app.get("/api/dashboard")
def get_dashboard(prod: bool = False):
    db_path = fetch_prod_db() if prod else None
    return dashboard_snapshot(
        prod_health_url=f"https://arifaqyl.me/traffic" if prod else None,
        db_path=db_path
    )

@app.get("/api/replay")
def get_replay(text: str):
    return explain_rider_gate_verbose(text)

@app.post("/api/case/add")
def post_case(req: CaseAddRequest):
    return add_eval_case(req.text, expected=req.expected, note=req.note)

@app.get("/api/case/run")
def get_case_run():
    return run_eval_cases()

@app.get("/api/impact")
def get_impact(prod: bool = False):
    db_path = fetch_prod_db() if prod else None
    return impact_preview(db_path=db_path)

@app.get("/api/prune-candidates")
def get_prune_candidates(prod: bool = False):
    db_path = fetch_prod_db() if prod else None
    if not db_path:
        raise HTTPException(status_code=400, detail="Requires production database path")
    return prune_candidates(db_path=db_path)


@app.get("/api/config")
def get_config():
    """Return server-side configuration so the UI can pick up --prod mode."""
    return {"is_prod": IS_PROD_MODE}

def main():
    parser = argparse.ArgumentParser(description="Threads Terminal Web UI Server")
    parser.add_argument("--port", type=int, default=8005, help="Port to run the local web dashboard on")
    parser.add_argument("--prod", action="store_true", help="Launch backend connected to production DO database")
    args = parser.parse_args()

    print(f"Launching Threads Terminal Web Dashboard on http://localhost:{args.port}")
    if args.prod:
        print("Backend initialized with --prod (reading database from production container)")
        global IS_PROD_MODE
        IS_PROD_MODE = True

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")

if __name__ == "__main__":
    main()
