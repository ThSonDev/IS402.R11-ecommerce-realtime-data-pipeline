"""Precision and recall of the 4 rules: ASA `alerts` vs the producer's scenario ground truth.

Usage (from the repo root):
    python analysis/evaluate_rules.py --alerts alerts.csv --scenario-log data/scenario_logs/<run>.json
    python analysis/evaluate_rules.py --alerts alerts.csv --scenario-log <run>.json \\
        --incident 2026-11-11T14:00:00Z,2026-11-11T15:00:00Z      # extra real incident window(s)

--alerts is an export of dbo.alerts (or the lake), CSV / JSON / Parquet, columns as in
docs/event-schema.md. Rules 1-3 are scored per entity (user / device / product); rule 4 per
alert and per incident window, since an outage is a stretch of time, not a set of events.
"""
import argparse
import json
from datetime import UTC, datetime, timedelta

import duckdb

ENTITY_RULES = {"bot": "user", "multi_account": "device", "price_glitch": "product"}
WINDOW_RULE = "payment_outage"


def parse_time(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.strptime(str(value)[:19].replace(" ", "T"), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)


def load_alerts(path: str) -> list[dict]:
    reader = "read_json_auto" if path.endswith((".json", ".jsonl")) else "read_csv_auto"
    if path.endswith(".parquet"):
        reader = "read_parquet"
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")   # alert_time as UTC text, whatever type the file holds
    rel = con.sql(f"SELECT * REPLACE (CAST(alert_time AS VARCHAR) AS alert_time) FROM {reader}('{path}')")
    rows = [dict(zip(rel.columns, row)) for row in rel.fetchall()]
    con.close()
    return rows


def ratio(num: int, den: int):
    return num / den if den else None


def evaluate(alerts: list[dict], log: dict, incidents=(), tolerance: float = 120) -> list[dict]:
    """One result row per rule: counts, precision, recall and the entities behind the errors."""
    scenarios = {e["scenario"]: e for e in log["scenarios"]}
    results = []
    for rule, entity_type in ENTITY_RULES.items():
        truth = set(scenarios.get(rule, {}).get("entity_ids", []))
        predicted = {str(a["entity_id"]) for a in alerts
                     if a["rule_name"] == rule and a.get("entity_id") is not None}
        hits = predicted & truth
        results.append({
            "rule": rule, "unit": entity_type, "alerts": sum(a["rule_name"] == rule for a in alerts),
            "truth": len(truth), "predicted": len(predicted), "true_positive": len(hits),
            "precision": ratio(len(hits), len(predicted)), "recall": ratio(len(hits), len(truth)),
            "false_positive": sorted(predicted - truth), "missed": sorted(truth - predicted),
        })

    windows = [(parse_time(e["start"]), parse_time(e["end"]))
               for e in log["scenarios"] if e["scenario"] == WINDOW_RULE]
    windows += [(parse_time(a), parse_time(b)) for a, b in incidents]
    slack = timedelta(seconds=tolerance)
    times = [parse_time(a["alert_time"]) for a in alerts if a["rule_name"] == WINDOW_RULE]

    def inside(t, window):
        return window[0] <= t <= window[1] + slack

    good = [t for t in times if any(inside(t, w) for w in windows)]
    caught = [w for w in windows if any(inside(t, w) for t in times)]
    results.append({
        "rule": WINDOW_RULE, "unit": "window", "alerts": len(times), "truth": len(windows),
        "predicted": len(times), "true_positive": len(good),
        "precision": ratio(len(good), len(times)), "recall": ratio(len(caught), len(windows)),
        "false_positive": sorted(t.isoformat() for t in times if t not in good),
        "missed": sorted(f"{a.isoformat()} - {b.isoformat()}" for a, b in windows if (a, b) not in caught),
    })
    return results


def to_markdown(results: list[dict]) -> str:
    def pct(x):
        return "–" if x is None else f"{x:.0%}"

    lines = ["| Rule | Unit | Alerts | Ground truth | True positive | Precision | Recall |",
             "|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['rule']} | {r['unit']} | {r['alerts']:,} | {r['truth']:,} | {r['true_positive']:,} "
                     f"| {pct(r['precision'])} | {pct(r['recall'])} |")
    for r in results:
        if r["false_positive"] or r["missed"]:
            lines.append(f"\n{r['rule']}: false positive {r['false_positive'][:20]}, missed {r['missed'][:20]}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Precision / recall of the 4 rules.")
    parser.add_argument("--alerts", required=True, help="dbo.alerts export: .csv, .json(l) or .parquet")
    parser.add_argument("--scenario-log", required=True, help="JSON written by producer/main.py --scenarios")
    parser.add_argument("--incident", action="append", default=[],
                        help="extra rule-4 ground truth window 'START,END' (ISO, UTC), repeatable")
    parser.add_argument("--tolerance", type=float, default=120,
                        help="seconds after a window still counted as detecting it (default 120)")
    parser.add_argument("--json", help="also write the full results here")
    args = parser.parse_args()

    with open(args.scenario_log, encoding="utf-8") as f:
        log = json.load(f)
    incidents = [tuple(x.split(",", 1)) for x in args.incident]
    results = evaluate(load_alerts(args.alerts), log, incidents, args.tolerance)
    print(to_markdown(results))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)


if __name__ == "__main__":
    main()
