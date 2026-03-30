import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal


@dataclass(frozen=True)
class ContextBenchmarkCase:
    label: str
    dataset_symbol: str
    timestamp: str
    expected_event_ids: tuple[str, ...]
    expected_themes: tuple[str, ...]
    notes: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate MacroLens context ranking against a small benchmark set."
    )
    parser.add_argument(
        "--cases-file",
        default=str(ROOT / "documentation" / "research" / "context_ranking_benchmark.json"),
        help="Path to the benchmark case JSON file.",
    )
    return parser.parse_args()


def load_cases(path: Path) -> list[ContextBenchmarkCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        ContextBenchmarkCase(
            label=str(item["label"]),
            dataset_symbol=str(item["dataset_symbol"]),
            timestamp=str(item["timestamp"]),
            expected_event_ids=tuple(item.get("expected_event_ids", [])),
            expected_themes=tuple(item.get("expected_themes", [])),
            notes=str(item.get("notes", "")),
        )
        for item in payload
    ]


def fetch_case_result(case: ContextBenchmarkCase) -> dict[str, object]:
    query = text(
        """
        WITH target_anomaly AS (
            SELECT a.id AS anomaly_id
            FROM anomalies AS a
            JOIN datasets AS d ON d.id = a.dataset_id
            WHERE d.symbol = :dataset_symbol
              AND a.timestamp = CAST(:timestamp AS TIMESTAMPTZ)
            LIMIT 1
        )
        SELECT
            ta.anomaly_id,
            nc.provider,
            nc.title,
            nc.metadata ->> 'historical_event_id' AS historical_event_id,
            nc.metadata ->> 'primary_theme' AS primary_theme,
            CAST(nc.metadata ->> 'context_score' AS DOUBLE PRECISION) AS context_score,
            e.generated_text
        FROM target_anomaly AS ta
        LEFT JOIN LATERAL (
            SELECT *
            FROM news_context
            WHERE anomaly_id = ta.anomaly_id
            ORDER BY
                CAST(COALESCE(metadata ->> 'context_score', '0') AS DOUBLE PRECISION) DESC,
                relevance_rank ASC,
                id ASC
            LIMIT 1
        ) AS nc ON TRUE
        LEFT JOIN LATERAL (
            SELECT generated_text
            FROM explanations
            WHERE anomaly_id = ta.anomaly_id
            ORDER BY created_at DESC
            LIMIT 1
        ) AS e ON TRUE
        """
    )
    with SessionLocal() as session:
        row = session.execute(
            query,
            {"dataset_symbol": case.dataset_symbol, "timestamp": case.timestamp},
        ).mappings().first()
    return dict(row) if row else {}


def evaluate_case(case: ContextBenchmarkCase, result: dict[str, object]) -> dict[str, object]:
    anomaly_id = result.get("anomaly_id")
    if anomaly_id is None:
        return {
            "label": case.label,
            "status": "missing_anomaly",
            "notes": case.notes,
        }

    top_event_id = result.get("historical_event_id")
    top_theme = result.get("primary_theme")
    event_match = bool(top_event_id and top_event_id in case.expected_event_ids)
    theme_match = bool(top_theme and top_theme in case.expected_themes)
    matched = event_match or theme_match

    return {
        "label": case.label,
        "status": "matched" if matched else "mismatch",
        "dataset_symbol": case.dataset_symbol,
        "timestamp": case.timestamp,
        "anomaly_id": anomaly_id,
        "expected_event_ids": list(case.expected_event_ids),
        "expected_themes": list(case.expected_themes),
        "actual_provider": result.get("provider"),
        "actual_title": result.get("title"),
        "actual_event_id": top_event_id,
        "actual_theme": top_theme,
        "context_score": result.get("context_score"),
        "notes": case.notes,
    }


def render_summary(evaluations: list[dict[str, object]]) -> str:
    matched = sum(1 for item in evaluations if item["status"] == "matched")
    missing = sum(1 for item in evaluations if item["status"] == "missing_anomaly")
    total = len(evaluations)
    lines = [
        "MacroLens Context Ranking Benchmark",
        f"Cases: {total}",
        f"Matched: {matched}",
        f"Missing anomalies: {missing}",
        "",
    ]
    for item in evaluations:
        lines.append(f"[{item['status']}] {item['label']}")
        if item["status"] == "missing_anomaly":
            lines.append(f"  notes: {item['notes']}")
            continue
        lines.append(
            f"  actual: provider={item['actual_provider']} event_id={item['actual_event_id']} theme={item['actual_theme']} score={item['context_score']}"
        )
        lines.append(
            f"  expected: events={item['expected_event_ids']} themes={item['expected_themes']}"
        )
        lines.append(f"  title: {item['actual_title']}")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    cases = load_cases(Path(args.cases_file))
    evaluations = [evaluate_case(case, fetch_case_result(case)) for case in cases]
    print(render_summary(evaluations))


if __name__ == "__main__":
    main()
