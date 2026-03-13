import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text

from app.db.session import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="View stored MacroLens explanations from PostgreSQL.")
    parser.add_argument(
        "--anomaly-id",
        action="append",
        type=int,
        default=None,
        help="Anomaly id to inspect. Repeat for multiple anomalies.",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="Optional provider filter such as rules_based, openai, or gemini.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of anomalies to show when --anomaly-id is not provided.",
    )
    return parser.parse_args()


def fetch_rows(anomaly_ids: list[int] | None, provider: str | None, limit: int) -> list[dict[str, object]]:
    provider_clause = ""
    params: dict[str, object] = {"limit": limit}

    if provider:
        provider_clause = "AND e.provider = :provider"
        params["provider"] = provider

    if anomaly_ids:
        query = text(
            f"""
            SELECT
                a.id AS anomaly_id,
                d.name AS dataset_name,
                a.timestamp,
                a.severity_score,
                a.direction,
                e.provider,
                e.model,
                e.generated_text,
                e.created_at
            FROM anomalies AS a
            JOIN datasets AS d ON d.id = a.dataset_id
            JOIN explanations AS e ON e.anomaly_id = a.id
            WHERE a.id = ANY(:anomaly_ids)
              {provider_clause}
            ORDER BY a.id ASC, e.created_at DESC
            """
        )
        params["anomaly_ids"] = anomaly_ids
    else:
        query = text(
            f"""
            SELECT
                a.id AS anomaly_id,
                d.name AS dataset_name,
                a.timestamp,
                a.severity_score,
                a.direction,
                e.provider,
                e.model,
                e.generated_text,
                e.created_at
            FROM anomalies AS a
            JOIN datasets AS d ON d.id = a.dataset_id
            JOIN explanations AS e ON e.anomaly_id = a.id
            WHERE TRUE
              {provider_clause}
            ORDER BY a.timestamp DESC, e.created_at DESC
            LIMIT :limit
            """
        )

    with SessionLocal() as session:
        rows = session.execute(query, params).mappings().all()
    return [dict(row) for row in rows]


def render_row(row: dict[str, object]) -> str:
    return "\n".join(
        [
            f"Anomaly ID : {row['anomaly_id']}",
            f"Dataset    : {row['dataset_name']}",
            f"Timestamp  : {row['timestamp']}",
            f"Severity   : {float(row['severity_score']):.2f}",
            f"Direction  : {row['direction']}",
            f"Provider   : {row['provider']}",
            f"Model      : {row['model']}",
            f"Created At : {row['created_at']}",
            "Explanation:",
            str(row["generated_text"]),
        ]
    )


def main() -> None:
    args = parse_args()
    rows = fetch_rows(args.anomaly_id, args.provider, args.limit)
    if not rows:
        print("No explanations found.")
        return

    for index, row in enumerate(rows):
        if index:
            print("\n" + "=" * 80 + "\n")
        print(render_row(row))


if __name__ == "__main__":
    main()
