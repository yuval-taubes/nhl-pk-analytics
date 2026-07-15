"""Scan NHL shiftchart source availability for a selected game sample.

This is a source-coverage diagnostic, not a modeling validator. It checks the
NHL shiftcharts endpoint directly and writes a compact report showing which
games returned shift rows and which returned zero rows or request errors.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

sys.path.append(os.path.dirname(os.path.dirname(__file__)))



REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
MD_REPORT_PATH = REPORT_DIR / "latest_shift_availability.md"
CSV_REPORT_PATH = REPORT_DIR / "latest_shift_availability.csv"
JSON_REPORT_PATH = REPORT_DIR / "latest_shift_availability.json"
SHIFTCHART_URL = "https://api.nhle.com/stats/rest/en/shiftcharts?cayenneExp={expr}"
SOURCE_STATUS_MAP = {
    "covered": "available",
    "missing": "missing_empty_response",
    "error": "request_error",
}


def markdown_table(rows, columns):
    if not rows:
        return "_No rows._"

    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(col, "")).replace("|", "\\|") for col in columns) + " |")
    return "\n".join(lines)


def parse_game_ids(value):
    if not value:
        return []
    normalized = value.replace(";", ",").replace(" ", ",")
    return [int(part) for part in normalized.split(",") if part.strip()]


def select_games(db, game_limit, game_ids, game_id_min=None, game_id_max=None, source_statuses=None):
    if game_ids:
        return game_ids

    if source_statuses:
        rows = db.query_to_df(
            """
            SELECT g.game_id
            FROM games g
            LEFT JOIN game_shift_source_status gsss ON gsss.game_id = g.game_id
            WHERE COALESCE(gsss.source_status, 'not_checked') = ANY(%s)
            ORDER BY g.game_id
            """,
            (source_statuses,),
        )
        return [int(game_id) for game_id in rows["game_id"]]

    if game_id_min is not None or game_id_max is not None:
        rows = db.query_to_df(
            """
            SELECT game_id
            FROM games
            WHERE (%s IS NULL OR game_id >= %s)
              AND (%s IS NULL OR game_id <= %s)
            ORDER BY game_id
            """,
            (game_id_min, game_id_min, game_id_max, game_id_max),
        )
        return [int(game_id) for game_id in rows["game_id"]]

    rows = db.query_to_df(
        """
        SELECT game_id
        FROM games
        ORDER BY game_id DESC
        LIMIT %s
        """,
        (game_limit,),
    )
    return [int(game_id) for game_id in rows["game_id"]]


def fetch_shift_count(game_id, timeout_seconds):
    expr = quote(f"gameId={game_id}", safe="=()")
    url = SHIFTCHART_URL.format(expr=expr)
    request = Request(url, headers={"User-Agent": "NHL-PK-Analytics/shift-availability-scan"})
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))

    total = payload.get("total")
    data = payload.get("data") or []
    return int(total if total is not None else len(data))


def scan_games(
    game_ids,
    delay_seconds,
    timeout_seconds,
    batch_callback=None,
    batch_size=25,
    progress_every=100,
):
    rows = []
    pending = []
    for index, game_id in enumerate(game_ids, start=1):
        try:
            shift_rows = fetch_shift_count(game_id, timeout_seconds)
            status = "covered" if shift_rows > 0 else "missing"
            error = ""
        except Exception as exc:  # diagnostic should record failures and continue
            shift_rows = 0
            status = "error"
            error = f"{type(exc).__name__}: {exc}"

        row = {"game_id": game_id, "status": status, "shift_rows": shift_rows, "error": error}
        rows.append(row)
        pending.append(row)
        if batch_callback and len(pending) >= batch_size:
            batch_callback(pending)
            pending = []
        if progress_every and index % progress_every == 0:
            print(f"Scanned {index}/{len(game_ids)} games", flush=True)
        if delay_seconds > 0 and index < len(game_ids):
            time.sleep(delay_seconds)

    if batch_callback and pending:
        batch_callback(pending)

    return rows


def persist_results(db, rows):
    with db.conn.cursor() as cursor:
        for row in rows:
            game_id = int(row["game_id"])
            endpoint_url = SHIFTCHART_URL.format(expr=f"gameId={game_id}")
            cursor.execute(
                """
                INSERT INTO game_shift_source_status
                    (game_id, source_status, checked_at, row_count, endpoint_url, error_message)
                VALUES (%s, %s, NOW(), %s, %s, %s)
                ON CONFLICT (game_id) DO UPDATE SET
                    source_status = CASE
                        WHEN EXCLUDED.source_status <> 'available'
                         AND EXISTS (SELECT 1 FROM game_shifts gs WHERE gs.game_id = EXCLUDED.game_id)
                        THEN 'available'
                        ELSE EXCLUDED.source_status
                    END,
                    checked_at = EXCLUDED.checked_at,
                    row_count = CASE
                        WHEN EXCLUDED.source_status <> 'available'
                         AND EXISTS (SELECT 1 FROM game_shifts gs WHERE gs.game_id = EXCLUDED.game_id)
                        THEN (SELECT COUNT(*) FROM game_shifts gs WHERE gs.game_id = EXCLUDED.game_id)
                        ELSE EXCLUDED.row_count
                    END,
                    endpoint_url = EXCLUDED.endpoint_url,
                    http_status_code = NULL,
                    error_message = EXCLUDED.error_message
                """,
                (game_id, SOURCE_STATUS_MAP[row["status"]], int(row["shift_rows"]), endpoint_url, row["error"] or None),
            )
    db.conn.commit()


def write_reports(rows, report_stem="latest_shift_availability"):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    md_report_path = REPORT_DIR / f"{report_stem}.md"
    csv_report_path = REPORT_DIR / f"{report_stem}.csv"
    json_report_path = REPORT_DIR / f"{report_stem}.json"

    with csv_report_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["game_id", "status", "shift_rows", "error"])
        writer.writeheader()
        writer.writerows(rows)

    requested = len(rows)
    covered = sum(1 for row in rows if row["status"] == "covered")
    missing = sum(1 for row in rows if row["status"] == "missing")
    errors = sum(1 for row in rows if row["status"] == "error")
    coverage_rate = covered / requested if requested else 0.0
    json_report_path.write_text(
        json.dumps(
            {
                "generatedAt": datetime.now().isoformat(timespec="seconds"),
                "requestedGames": requested,
                "availableGames": covered,
                "missingGames": missing,
                "errorGames": errors,
                "coverageRate": coverage_rate,
                "modelEligibility": "source-covered games only",
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    top_missing = [row for row in rows if row["status"] != "covered"][:30]
    report = [
        "# Shiftchart Source Availability",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Requested games: `{requested}`",
        f"Games with shift rows: `{covered}`",
        f"Games with zero rows: `{missing}`",
        f"Games with request errors: `{errors}`",
        f"Coverage rate: `{coverage_rate:.2%}`",
        "",
        "## Missing Or Error Games",
        "",
        markdown_table(top_missing, ["game_id", "status", "shift_rows", "error"]),
        "",
        "## Interpretation",
        "",
        "This report checks whether the NHL shiftcharts endpoint returns source rows. "
        "Games with zero rows should not be used for shift-derived TOI, on-ice, or fatigue models unless another source fills the gap.",
        "",
    ]
    md_report_path.write_text("\n".join(report), encoding="utf-8")
    return requested, covered, missing, errors, md_report_path, csv_report_path, json_report_path


def main():
    parser = argparse.ArgumentParser(description="Scan NHL shiftchart source availability.")
    parser.add_argument("--game-limit", type=int, default=50, help="Latest N games to scan when --game-ids is omitted.")
    parser.add_argument("--game-ids", default="", help="Comma/semicolon/space-separated explicit game IDs to scan.")
    parser.add_argument("--game-id-min", type=int, help="Minimum ingested game ID for a focused range scan.")
    parser.add_argument("--game-id-max", type=int, help="Maximum ingested game ID for a focused range scan.")
    parser.add_argument("--delay-seconds", type=float, default=0.1, help="Delay between NHL endpoint requests.")
    parser.add_argument("--timeout-seconds", type=float, default=20.0, help="Per-request timeout.")
    parser.add_argument("--persist", action="store_true", help="Persist verified source states to PostgreSQL.")
    parser.add_argument("--persist-batch-size", type=int, default=25, help="Commit every N results so interrupted scans can resume.")
    parser.add_argument("--not-checked", action="store_true", help="Scan every game whose shift source has not been checked.")
    parser.add_argument("--retry-errors", action="store_true", help="Rescan games whose last source check ended in a request error.")
    parser.add_argument("--report-stem", default="latest_shift_availability", help="Filename stem under Analytics/reports.")
    args = parser.parse_args()

    from db import DatabaseConnection

    db = DatabaseConnection()
    db.connect()
    try:
        source_statuses = []
        if args.not_checked:
            source_statuses.append("not_checked")
        if args.retry_errors:
            source_statuses.append("request_error")
        game_ids = select_games(
            db,
            args.game_limit,
            parse_game_ids(args.game_ids),
            args.game_id_min,
            args.game_id_max,
            source_statuses,
        )
        callback = (lambda batch: persist_results(db, batch)) if args.persist else None
        rows = scan_games(
            game_ids,
            args.delay_seconds,
            args.timeout_seconds,
            batch_callback=callback,
            batch_size=args.persist_batch_size,
        )
    finally:
        db.close()

    requested, covered, missing, errors, md_path, csv_path, json_path = write_reports(rows, args.report_stem)
    print(f"Scanned {requested} games: {covered} covered, {missing} missing, {errors} errors")
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")

    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
