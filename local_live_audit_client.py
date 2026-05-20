#!/usr/bin/env python3
"""Run the V297.01 live audit from an operator computer and save proof JSON.

This script does not solve tasks locally. It only calls the deployed backend,
starts the live DeepSeek audit, polls summary, then downloads the evidence
endpoints that ChatGPT needs for analysis.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

DEFAULT_BASE = "https://wolandvp-beep-ai-math-1-4-8e2f.twc1.net"
DEFAULT_RELEASE = "v297.01_live_g1_text_problems_ui_render_guard_and_dom_fix"
DEFAULT_KEY = "v297.01-live-audit"
DEFAULT_SECTION = "g1_text_problems"


def build_url(base: str, path: str, params: dict[str, Any] | None = None) -> str:
    base = base.rstrip("/") + "/"
    path = path.lstrip("/")
    url = urljoin(base, path)
    if params:
        url += "?" + urlencode([(k, v) for k, v in params.items() if v is not None])
    return url


def get_json(url: str, timeout: float = 120.0) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": "MathAuditLocalClient/V297.01"})
    with urlopen(req, timeout=timeout) as resp:  # nosec: operator-provided backend URL
        raw = resp.read()
        content_type = resp.headers.get("content-type", "")
    text = raw.decode("utf-8", errors="replace")
    if "json" not in content_type.lower():
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        preview = text[:800].replace("\n", " ")
        raise RuntimeError(f"Endpoint did not return JSON: {url}\nPreview: {preview}") from exc


def stable_query_links(base: str, release: str, key: str, run_id: str) -> dict[str, str]:
    common = {"key": key, "release": release, "runId": run_id}
    return {
        "summaryQueryUrl": build_url(base, "/api/diagnostics/live-audit/summary", common),
        "acceptanceQueryUrl": build_url(base, "/api/diagnostics/live-audit/acceptance", common),
        "resultsFullQueryUrl": build_url(base, "/api/diagnostics/live-audit/results", {**common, "includeFull": 1, "limit": 200}),
        "evidenceQueryUrl": build_url(base, "/api/diagnostics/live-audit/evidence", {**common, "limit": 500}),
        "suspiciousQueryUrl": build_url(base, "/api/diagnostics/live-audit/suspicious", common),
        "acceptanceReportQueryUrl": build_url(base, "/api/diagnostics/live-audit/report", common),
        "failuresQueryUrl": build_url(base, "/api/diagnostics/live-audit/failures", {**common, "limit": 200}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run V297.01 production live audit and save proof results.")
    parser.add_argument("--base", default=DEFAULT_BASE, help="Backend base URL")
    parser.add_argument("--release", default=DEFAULT_RELEASE, help="Expected backend release")
    parser.add_argument("--key", default=DEFAULT_KEY, help="Live audit key")
    parser.add_argument("--section", default=DEFAULT_SECTION, help="Audit section")
    parser.add_argument("--limit", type=int, default=100, help="Number of audit cases")
    parser.add_argument("--offset", type=int, default=0, help="Audit offset")
    parser.add_argument("--max-external-calls", type=int, default=150, help="External API call budget")
    parser.add_argument("--poll-seconds", type=float, default=5.0, help="Polling interval")
    parser.add_argument("--timeout-minutes", type=float, default=90.0, help="Maximum polling duration")
    parser.add_argument("--force", action="store_true", help="Force new run and spend tokens again")
    parser.add_argument("--out", default="v296_12_live_audit_result.json", help="Output JSON file")
    args = parser.parse_args()

    start_url = build_url(
        args.base,
        "/api/diagnostics/live-audit/start",
        {
            "key": args.key,
            "section": args.section,
            "limit": args.limit,
            "offset": args.offset,
            "allowExternal": 1,
            "force": 1 if args.force else 0,
            "maxExternalCalls": args.max_external_calls,
            "release": args.release,
            "cacheBust": f"{args.release}-{uuid.uuid4().hex[:8]}",
        },
    )

    print("Starting live audit:", start_url, flush=True)
    start = get_json(start_url)
    run_id = str(start.get("runId") or "").strip()
    if not run_id:
        print(json.dumps(start, ensure_ascii=False, indent=2), file=sys.stderr)
        raise RuntimeError("No runId returned by start endpoint")

    links = stable_query_links(args.base, args.release, args.key, run_id)
    deadline = time.monotonic() + max(1.0, args.timeout_minutes) * 60.0
    summary = start
    while True:
        summary = get_json(links["summaryQueryUrl"])
        status = summary.get("status")
        completed = int(summary.get("completed") or 0)
        planned = int(summary.get("planned") or args.limit)
        passed = int(summary.get("passed") or 0)
        failed = int(summary.get("failed") or 0)
        external = int(summary.get("externalApiCalls") or 0) + int(summary.get("cachedExternalApiCalls") or 0)
        print(f"status={status} completed={completed}/{planned} passed={passed} failed={failed} external={external}", flush=True)
        if status in {"done", "error", "cancelled"}:
            break
        if time.monotonic() >= deadline:
            print("Polling timeout reached; downloading current evidence snapshot.", flush=True)
            break
        time.sleep(max(1.0, args.poll_seconds))

    print("Downloading acceptance/results/suspicious/failures proof endpoints...", flush=True)
    acceptance = get_json(links["acceptanceQueryUrl"])
    results_full = get_json(links["resultsFullQueryUrl"])
    evidence = get_json(links["evidenceQueryUrl"])
    suspicious = get_json(links["suspiciousQueryUrl"])
    report = get_json(links["acceptanceReportQueryUrl"])
    failures = get_json(links["failuresQueryUrl"])

    # Prefer fresh path-based links from backend summary when available. They are convenient for ChatGPT/web-tool viewing.
    proof_links = {
        **links,
        "summaryFreshUrl": summary.get("summaryFreshUrl"),
        "acceptanceFreshUrl": summary.get("acceptanceFreshUrl") or acceptance.get("acceptanceFreshUrl"),
        "resultsFullFreshUrl": summary.get("resultsFullFreshUrl") or results_full.get("resultsFullFreshUrl"),
        "evidenceFreshUrl": summary.get("evidenceFreshUrl") or evidence.get("evidenceFreshUrl"),
        "suspiciousFreshUrl": summary.get("suspiciousFreshUrl") or suspicious.get("suspiciousFreshUrl"),
        "reportFreshUrl": summary.get("reportFreshUrl") or report.get("reportFreshUrl"),
        "failuresFreshUrl": summary.get("failuresFreshUrl") or failures.get("failuresFreshUrl"),
    }

    bundle = {
        "client": "local_live_audit_client.py",
        "release": args.release,
        "base": args.base,
        "runId": run_id,
        "startedVia": start_url,
        "proofLinks": proof_links,
        "start": start,
        "summary": summary,
        "acceptance": acceptance,
        "resultsFull": results_full,
        "evidence": evidence,
        "suspicious": suspicious,
        "report": report,
        "failures": failures,
    }
    out_path = Path(args.out).expanduser().resolve()
    out_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nSaved proof JSON:", out_path)
    print("\nSend ChatGPT these links or attach the saved JSON:")
    for name in ["reportFreshUrl", "acceptanceFreshUrl", "resultsFullFreshUrl", "evidenceFreshUrl", "suspiciousFreshUrl", "failuresFreshUrl"]:
        value = proof_links.get(name)
        if value:
            print(f"{name}: {value}")
    print("\nAcceptance flags:")
    print("finalAcceptance:", acceptance.get("finalAcceptance"))
    print("acceptancePassed:", acceptance.get("acceptancePassed"))
    print("acceptanceIssues:", acceptance.get("acceptanceIssues"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
