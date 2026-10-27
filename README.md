# Vidhu Astro Prediction

**A Level 4 Agentic AI platform combining deterministic Swiss Ephemeris math with Gemini orchestration and zero-token QA hallucination controls.**

## 📊 The Business Problem
Traditional astrology platforms rely on static, ambiguous reports, while modern generative AI alone fails at astrological prediction due to severe mathematical hallucinations (inventing planetary degrees, invalid date spans, and broken Dasa calculations). The challenge was to build a system that allows conversational flexibility while strictly anchoring the AI to mathematically precise, deterministic astronomical data.

## 🚀 The Digital Transformation Solution
Vidhu Astro Prediction solves this by implementing a **Level 4 Agentic System** built on a strict two-layer hybrid architecture:

1. **Deterministic Math Engine (Layer 1):** Utilizes C-bound Swiss Ephemeris (`pyswisseph`) to calculate exact planetary degrees, house cusps, and Vimshottari Dasa timelines natively in Python. The LLM is strictly prohibited from performing calculations.
2. **Orchestrated Multi-Agent Pipeline (Layer 2):** 
   * **The Researcher (`rule_service.py`):** Uses key-indexed lookups to attach classical slokas from texts like *Jathaga Alangaram*.
   * **The Interpreter (`palan_service.py`):** Ingests the structured "Fact Pack" and generates a grounded narrative using the Google Gemini API.
   * **The Critic (`validation_service.py`):** Executes zero-token Python verification passes over the LLM output to ensure no dates or Dasa periods were hallucinated.

## 🛡️ Quality Assurance, Governance & System Resilience
To ensure enterprise-grade reliability and hallucination control, the following QA protocols and systemic safeguards were implemented:

* **Bounded Correction Loops:** If the Critic flags an unverified date or math error, the Orchestrator (`orchestrator.py`) rejects the output and forces a targeted revision (capped at a maximum of 2 retries) before rendering the final report.
* **Algorithmic Edge-Case Trapping:** Hardcoded logic to handle complex classical rules, such as Bhanga (Cancellation) rules (e.g., Kemadruma Dosha cancellation), preventing false positives.
* **Dynamic Model Discovery:** To prevent downtime from API endpoint deprecation or `404/429` errors, the engine dynamically queries Google's `ListModels` API, ranks active models by performance tier, and utilizes exponential jitter backoff for seamless failovers.
* **Concurrency Management:** Implemented SQLite in Write-Ahead Logging (WAL) mode to track daily API quota usage accurately without triggering database locks under multi-worker WSGI servers.

## 🛠️ Technology Stack
* **Backend:** Python 3.13, Flask, SQLite3 (WAL Mode)
* **Astrological Engine:** Swiss Ephemeris (`pyswisseph` C-wrappers)
* **AI & Orchestration:** Google GenAI SDK, Custom Level 4 Multi-Agent Orchestrator
* **Automation:** n8n Workflow Automation (Async cron monitoring for API quotas)
* **Frontend:** HTML5, CSS3 (@media print layout engine), Jinja2, JavaScript
