"""
validate_engine.py — Verity Prism engine validation script.

Usage:
    python scripts/validate_engine.py --list
    python scripts/validate_engine.py <workspace_id>
    python scripts/validate_engine.py <workspace_id> --email user@example.com --password secret
"""

import argparse
import getpass
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

BASE_URL = "http://localhost:8000"
DB_URL = "postgresql://catalyst:catalyst@localhost:5432/catalyst"  # noqa: S105

NLP_QUERIES = [
    "property transfer deed",
    "nonprofit organization revenue",
    "building permit application",
    "secretary of state filing",
    "parcel owner address",
]


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def make_client(token: str) -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {token}"},
        follow_redirects=True,
        timeout=30.0,
    )


def login(email: str, password: str) -> str:
    """Authenticate and return a Bearer token."""
    try:
        r = httpx.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=10.0,
        )
    except httpx.ConnectError:
        print("\nERROR: Cannot reach the API.")
        print("Start Docker with: docker-compose up --build")
        sys.exit(1)

    if r.status_code == 401:
        return None
    r.raise_for_status()
    data = r.json()
    return data["access_token"]


def fetch_workspaces(client: httpx.Client) -> list[dict]:
    r = client.get("/workspaces/")
    r.raise_for_status()
    return r.json()


def fetch_documents(client: httpx.Client, workspace_id: str) -> list[dict]:
    r = client.get(f"/workspaces/{workspace_id}/documents")
    r.raise_for_status()
    return r.json()


def fetch_extractions_json(client: httpx.Client, workspace_id: str) -> list[dict]:
    r = client.get(f"/workspaces/{workspace_id}/extractions.json")
    if r.status_code == 200:
        try:
            return r.json()
        except Exception:
            return []
    return []


def fetch_review_queue(client: httpx.Client, workspace_id: str) -> list[dict]:
    r = client.get(f"/workspaces/{workspace_id}/review-queue")
    if r.status_code == 200:
        return r.json()
    return []


def run_search(client: httpx.Client, workspace_id: str, query: str) -> dict:
    r = client.post(
        f"/workspaces/{workspace_id}/search/",
        json={"query": query},
        timeout=60.0,
    )
    if r.status_code == 200:
        return r.json()
    return {"query": query, "result_count": 0, "results": []}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def open_db():
    """Return a psycopg2 connection or None if unavailable."""
    if not PSYCOPG2_AVAILABLE:
        return None
    try:
        conn = psycopg2.connect(DB_URL, connect_timeout=5)
        return conn
    except Exception:
        return None


def run_db_queries(workspace_id: str) -> dict | None:
    conn = open_db()
    if conn is None:
        return None

    result = {}
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

                # Per-document stats
                cur.execute("""
                    SELECT
                        d.filename,
                        d.detected_doc_type,
                        d.extraction_status,
                        d.extraction_error,
                        COUNT(de.id) AS field_count,
                        COUNT(de.id) FILTER (WHERE de.confidence < 0.7) AS low_conf_fields,
                        ROUND(AVG(de.confidence)::numeric, 3) AS avg_confidence,
                        ROUND(AVG(de.ocr_confidence)::numeric, 3) AS avg_ocr_confidence
                    FROM documents d
                    LEFT JOIN document_extractions de
                        ON d.id = de.document_id
                        AND de.attempt = (
                            SELECT MAX(attempt)
                            FROM document_extractions
                            WHERE document_id = d.id AND field_name = de.field_name
                        )
                    WHERE d.workspace_id = %(workspace_id)s AND d.is_deleted = false
                    GROUP BY d.id, d.filename, d.detected_doc_type, d.extraction_status, d.extraction_error
                    ORDER BY d.uploaded_at
                """, {"workspace_id": workspace_id})
                result["doc_stats"] = [dict(r) for r in cur.fetchall()]

                # Confidence distribution by field type
                cur.execute("""
                    SELECT
                        field_type,
                        COUNT(*) AS total_fields,
                        ROUND(AVG(confidence)::numeric, 3) AS avg_confidence,
                        ROUND(MIN(confidence)::numeric, 3) AS min_confidence,
                        COUNT(*) FILTER (WHERE confidence < 0.7) AS low_confidence_count
                    FROM document_extractions de
                    JOIN documents d ON de.document_id = d.id
                    WHERE d.workspace_id = %(workspace_id)s
                      AND de.attempt = (
                          SELECT MAX(attempt) FROM document_extractions
                          WHERE document_id = de.document_id AND field_name = de.field_name
                      )
                    GROUP BY field_type ORDER BY avg_confidence
                """, {"workspace_id": workspace_id})
                result["conf_by_type"] = [dict(r) for r in cur.fetchall()]

                # Claude call log stats
                cur.execute("""
                    SELECT
                        call_type,
                        COUNT(*) AS calls,
                        ROUND(AVG(latency_ms)::numeric, 0) AS avg_latency_ms,
                        SUM(input_tokens) AS total_input_tokens,
                        SUM(output_tokens) AS total_output_tokens,
                        COUNT(*) FILTER (WHERE NOT success) AS failed_calls
                    FROM claude_call_logs cl
                    JOIN documents d ON cl.document_id = d.id
                    WHERE d.workspace_id = %(workspace_id)s
                    GROUP BY call_type ORDER BY calls DESC
                """, {"workspace_id": workspace_id})
                result["claude_stats"] = [dict(r) for r in cur.fetchall()]

                # Low confidence fields — worst 15
                cur.execute("""
                    SELECT
                        d.filename,
                        d.detected_doc_type,
                        de.field_name,
                        de.field_value,
                        ROUND(de.confidence::numeric, 3) AS confidence,
                        ROUND(de.ocr_confidence::numeric, 3) AS ocr_confidence
                    FROM document_extractions de
                    JOIN documents d ON de.document_id = d.id
                    WHERE d.workspace_id = %(workspace_id)s
                      AND de.confidence < 0.7
                      AND de.attempt = (
                          SELECT MAX(attempt) FROM document_extractions
                          WHERE document_id = de.document_id AND field_name = de.field_name
                      )
                    ORDER BY de.confidence LIMIT 15
                """, {"workspace_id": workspace_id})
                result["low_conf_fields"] = [dict(r) for r in cur.fetchall()]

    except Exception as e:
        result["db_error"] = str(e)
    finally:
        conn.close()

    return result


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def pct(n: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{round(n / total * 100)}%"


def fmt_num(val) -> str:
    if val is None:
        return "—"
    return str(val)


def fmt_float(val) -> str:
    if val is None:
        return "—"
    try:
        return f"{float(val):.3f}"
    except (TypeError, ValueError):
        return "—"


def status_icon(status: str) -> str:
    return {
        "complete": "✅ complete",
        "needs_review": "⚠️ needs_review",
        "failed": "❌ failed",
        "no_schema": "🔷 no_schema",
        "pending": "⏳ pending",
    }.get(status, status)


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_report(workspace: dict, docs: list[dict],
                 review_queue: list[dict], search_results: list[dict],
                 db_data: dict | None) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    ws_id = workspace["id"]
    ws_name = workspace.get("name", ws_id)
    vertical = workspace.get("vertical", "unknown")

    lines = []
    lines.append(f"# Engine Validation Baseline — {now}")
    lines.append("")
    lines.append(f"**Workspace:** {ws_name} ({ws_id})")
    lines.append(f"**Vertical:** {vertical}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Summary ----
    total = len(docs)
    status_counts: dict[str, int] = {}
    for d in docs:
        s = d.get("extraction_status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    complete = status_counts.get("complete", 0)
    needs_review = status_counts.get("needs_review", 0)
    failed = status_counts.get("failed", 0)
    no_schema = status_counts.get("no_schema", 0)
    pending = status_counts.get("pending", 0)
    automation = complete + needs_review  # auto-processed without manual upload
    # Automation rate = fully auto-complete / total
    auto_rate = complete / total if total > 0 else 0

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Documents uploaded | {total} |")
    lines.append(f"| Complete (no human review) | {complete} ({pct(complete, total)}) |")
    lines.append(f"| Needs review | {needs_review} ({pct(needs_review, total)}) |")
    lines.append(f"| Failed | {failed} ({pct(failed, total)}) |")
    lines.append(f"| No schema | {no_schema} ({pct(no_schema, total)}) |")
    lines.append(f"| Pending | {pending} ({pct(pending, total)}) |")
    lines.append(f"| **Automation rate** | **{pct(complete, total)}** |")
    lines.append("")
    lines.append("> Target: 70%+")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Document Breakdown ----
    lines.append("## Document Breakdown")
    lines.append("")

    # Use DB stats if available, else fall back to API data
    if db_data and "doc_stats" in db_data:
        db_by_filename = {r["filename"]: r for r in db_data["doc_stats"]}
    else:
        db_by_filename = {}

    lines.append("| Filename | Type | Status | Fields | Avg Conf | Low Conf Fields |")
    lines.append("|---|---|---|---|---|---|")

    errors = []
    for d in docs:
        fname = d.get("filename", "?")
        doc_type = d.get("detected_doc_type") or "UNKNOWN"
        status = d.get("extraction_status", "unknown")
        err = d.get("extraction_error")
        if err:
            errors.append((fname, err))

        if fname in db_by_filename:
            row = db_by_filename[fname]
            field_count = fmt_num(row.get("field_count"))
            avg_conf = fmt_float(row.get("avg_confidence"))
            low_conf = fmt_num(row.get("low_conf_fields"))
        else:
            field_count = "—"
            avg_conf = "—"
            low_conf = "—"

        lines.append(f"| {fname} | {doc_type} | {status_icon(status)} | {field_count} | {avg_conf} | {low_conf} |")

    lines.append("")

    if errors:
        lines.append("**Extraction errors:**")
        for fname, err in errors:
            lines.append(f"- `{fname}`: {err}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ---- Confidence Distribution ----
    lines.append("## Confidence Score Distribution")
    lines.append("")

    if db_data and "conf_by_type" in db_data and db_data["conf_by_type"]:
        lines.append("| Field Type | Fields | Avg Conf | Min Conf | Low Conf (<0.7) |")
        lines.append("|---|---|---|---|---|")
        for row in db_data["conf_by_type"]:
            ft = row.get("field_type") or "unknown"
            lines.append(
                f"| {ft} | {fmt_num(row.get('total_fields'))} "
                f"| {fmt_float(row.get('avg_confidence'))} "
                f"| {fmt_float(row.get('min_confidence'))} "
                f"| {fmt_num(row.get('low_confidence_count'))} |"
            )
    elif db_data is None:
        lines.append("*DB unavailable — confidence distribution not collected.*")
    else:
        lines.append("*No extraction data found.*")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Lowest Confidence Fields ----
    lines.append("## Lowest Confidence Fields")
    lines.append("")

    if db_data and "low_conf_fields" in db_data and db_data["low_conf_fields"]:
        lines.append("| Document | Type | Field | Value | Confidence | OCR Confidence |")
        lines.append("|---|---|---|---|---|---|")
        for row in db_data["low_conf_fields"]:
            val = str(row.get("field_value") or "").replace("|", "\\|")[:60]
            lines.append(
                f"| {row.get('filename', '?')} "
                f"| {row.get('detected_doc_type') or 'UNKNOWN'} "
                f"| {row.get('field_name', '?')} "
                f"| {val} "
                f"| {fmt_float(row.get('confidence'))} "
                f"| {fmt_float(row.get('ocr_confidence'))} |"
            )
    elif db_data is None:
        lines.append("*DB unavailable.*")
    else:
        lines.append("*No fields below 0.7 confidence.*")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Claude API Usage ----
    lines.append("## Claude API Usage")
    lines.append("")

    if db_data and "claude_stats" in db_data and db_data["claude_stats"]:
        lines.append("| Call Type | Calls | Avg Latency (ms) | Input Tokens | Output Tokens | Failures |")
        lines.append("|---|---|---|---|---|---|")
        for row in db_data["claude_stats"]:
            lines.append(
                f"| {row.get('call_type', '?')} "
                f"| {fmt_num(row.get('calls'))} "
                f"| {fmt_num(row.get('avg_latency_ms'))} "
                f"| {fmt_num(row.get('total_input_tokens'))} "
                f"| {fmt_num(row.get('total_output_tokens'))} "
                f"| {fmt_num(row.get('failed_calls'))} |"
            )
    elif db_data is None:
        lines.append("*DB unavailable — Claude call logs not collected.*")
    else:
        lines.append("*No Claude call log data.*")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- NLP Search Results ----
    lines.append("## NLP Search Results")
    lines.append("")
    lines.append("| Query | Results | Top Match |")
    lines.append("|---|---|---|")

    for sr in search_results:
        query = sr.get("query", "?")
        count = sr.get("result_count", 0)
        results = sr.get("results", [])
        if results:
            top = results[0]
            top_fname = top.get("filename") or top.get("document", {}).get("filename", "?")
            top_type = top.get("detected_doc_type") or top.get("document", {}).get("detected_doc_type", "?")
            top_match = f"{top_fname} ({top_type})"
        else:
            top_match = "—"
        lines.append(f'| "{query}" | {count} | {top_match} |')

    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Review Queue ----
    lines.append("## Review Queue")
    lines.append("")

    if review_queue:
        lines.append(f"{len(review_queue)} document(s) pending human review:")
        lines.append("")
        for item in review_queue:
            fname = item.get("filename", "?")
            doc_type = item.get("detected_doc_type") or "UNKNOWN"
            low_count = item.get("low_confidence_count", "?")
            lines.append(f"- `{fname}` ({doc_type}) — {low_count} low-confidence field(s)")
    else:
        lines.append("No documents pending human review.")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Observations for Debugging ----
    lines.append("## Observations for Debugging")
    lines.append("")
    observations = []

    # Extraction errors
    for fname, err in errors:
        observations.append(f"- **Extraction error** in `{fname}`: {err}")

    # Claude call failures
    if db_data and "claude_stats" in db_data:
        for row in db_data["claude_stats"]:
            if row.get("failed_calls", 0) > 0:
                observations.append(
                    f"- **Claude call failures**: {row['failed_calls']} failed `{row['call_type']}` call(s)"
                )

    # DB error
    if db_data and "db_error" in db_data:
        observations.append(f"- **DB query error**: {db_data['db_error']}")

    # DB unavailable
    if db_data is None:
        observations.append(
            "- **DB unavailable**: confidence distribution and Claude call logs not collected. "
            "Report uses API data only."
        )

    # Low automation rate
    if auto_rate < 0.70 and total > 0:
        observations.append(
            f"- **Automation rate below target**: {pct(complete, total)} (target: 70%+). "
            f"{failed} failed, {no_schema} no schema, {needs_review} needs review."
        )

    # Field types with low average confidence
    if db_data and "conf_by_type" in db_data:
        for row in db_data["conf_by_type"]:
            avg = row.get("avg_confidence")
            if avg is not None:
                try:
                    if float(avg) < 0.6:
                        observations.append(
                            f"- **Low avg confidence** for field type `{row.get('field_type', '?')}`: "
                            f"{fmt_float(avg)} (below 0.6 threshold)"
                        )
                except (TypeError, ValueError):
                    pass

    if not observations:
        observations.append("- No issues detected.")

    lines.extend(observations)
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Verity Prism engine validation script")
    parser.add_argument("workspace_id", nargs="?", help="Workspace ID to validate")
    parser.add_argument("--list", action="store_true", help="List all workspaces")
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    if not args.list and not args.workspace_id:
        parser.print_help()
        sys.exit(1)

    # Auth
    email = args.email or input("Email [analyst@example.com]: ").strip() or "analyst@example.com"
    password = args.password or getpass.getpass("Password: ")
    print(f"Authenticating as {email}...")
    token = login(email, password)
    if token is None:
        print("ERROR: Authentication failed.")
        sys.exit(1)

    client = make_client(token)

    # Verify auth
    me = client.get("/auth/me")
    if me.status_code != 200:
        print(f"ERROR: /auth/me returned {me.status_code}")
        sys.exit(1)
    print(f"Authenticated as {me.json().get('email')}")

    # Fetch workspaces
    print("Fetching workspaces...")
    workspaces = fetch_workspaces(client)

    if args.list:
        if not workspaces:
            print("No workspaces found.")
        else:
            print(f"\n{'ID':<38} {'Name':<30} {'Vertical'}")
            print("-" * 80)
            for ws in workspaces:
                print(f"{ws['id']:<38} {ws.get('name', ''):<30} {ws.get('vertical', '')}")
        return

    # Find workspace
    workspace_id = args.workspace_id
    workspace = next((w for w in workspaces if w["id"] == workspace_id), None)
    if workspace is None:
        print(f"ERROR: Workspace '{workspace_id}' not found.")
        print("Available workspaces:")
        for ws in workspaces:
            print(f"  {ws['id']}  {ws.get('name', '')}  ({ws.get('vertical', '')})")
        sys.exit(1)

    ws_name = workspace.get("name", workspace_id)
    print(f"Validating workspace: {ws_name} ({workspace_id})")

    # Fetch documents
    print("Fetching documents...")
    docs = fetch_documents(client, workspace_id)
    print(f"  {len(docs)} document(s) found")

    # Fetch review queue
    print("Fetching review queue...")
    review_queue = fetch_review_queue(client, workspace_id)
    print(f"  {len(review_queue)} document(s) in review queue")

    # Run searches
    print(f"Running {len(NLP_QUERIES)} NLP search queries...")
    search_results = []
    for q in NLP_QUERIES:
        print(f"  Searching: \"{q}\"")
        sr = run_search(client, workspace_id, q)
        search_results.append(sr)
        count = sr.get("result_count", 0)
        print(f"    → {count} result(s)")

    # DB queries
    print("Querying database directly...")
    if not PSYCOPG2_AVAILABLE:
        print("  WARNING: psycopg2 not available — skipping DB queries")
        db_data = None
    else:
        db_data = run_db_queries(workspace_id)
        if db_data is None:
            print("  WARNING: DB not reachable — skipping DB queries")
        elif "db_error" in db_data:
            print(f"  WARNING: DB error: {db_data['db_error']}")
        else:
            doc_count = len(db_data.get("doc_stats", []))
            type_count = len(db_data.get("conf_by_type", []))
            call_count = sum(r.get("calls", 0) for r in db_data.get("claude_stats", []))
            low_count = len(db_data.get("low_conf_fields", []))
            print(f"  {doc_count} doc stats, {type_count} field types, {call_count} Claude calls, {low_count} low-conf fields")

    # Build report
    print("Building report...")
    report = build_report(workspace, docs, review_queue, search_results, db_data)

    # Write report
    private_dir = Path(__file__).resolve().parent.parent / "private"
    private_dir.mkdir(exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = private_dir / f"engine-validation-{date_str}.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"\nDone. Report written to: {report_path}")

    # Print summary
    total = len(docs)
    status_counts: dict[str, int] = {}
    for d in docs:
        s = d.get("extraction_status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1
    complete = status_counts.get("complete", 0)
    print(f"Automation rate: {pct(complete, total)} ({complete}/{total} complete)")


if __name__ == "__main__":
    main()
