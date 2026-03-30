import json
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal


def fetch_scalar(session, query: str) -> int:
    return int(session.execute(text(query)).scalar_one())


def fetch_mappings(session, query: str) -> list[dict[str, object]]:
    return [dict(row) for row in session.execute(text(query)).mappings().all()]


def build_report() -> dict[str, object]:
    with SessionLocal() as session:
        summary = {
            "datasets": fetch_scalar(session, "SELECT COUNT(*) FROM datasets"),
            "data_points": fetch_scalar(session, "SELECT COUNT(*) FROM data_points"),
            "anomalies": fetch_scalar(session, "SELECT COUNT(*) FROM anomalies"),
            "clusters": fetch_scalar(session, "SELECT COUNT(*) FROM anomaly_clusters"),
            "correlations": fetch_scalar(session, "SELECT COUNT(*) FROM correlations"),
            "news_context_rows": fetch_scalar(session, "SELECT COUNT(*) FROM news_context"),
            "explanations": fetch_scalar(session, "SELECT COUNT(*) FROM explanations"),
        }

        quality_distribution = fetch_mappings(
            session,
            """
            SELECT quality_band, COUNT(*) AS count
            FROM anomaly_clusters
            GROUP BY quality_band
            ORDER BY count DESC
            """,
        )
        episode_kind_distribution = fetch_mappings(
            session,
            """
            SELECT episode_kind, COUNT(*) AS count
            FROM anomaly_clusters
            GROUP BY episode_kind
            ORDER BY count DESC
            """,
        )
        anomaly_supply = fetch_mappings(
            session,
            """
            SELECT
                d.symbol,
                d.frequency,
                COUNT(a.id) AS anomaly_count,
                COUNT(*) FILTER (WHERE a.detection_method = 'z_score') AS z_score_count,
                COUNT(*) FILTER (WHERE a.detection_method = 'change_point') AS change_point_count
            FROM datasets AS d
            LEFT JOIN anomalies AS a ON a.dataset_id = d.id
            GROUP BY d.symbol, d.frequency
            ORDER BY anomaly_count DESC, d.symbol ASC
            """,
        )
        context_coverage = fetch_mappings(
            session,
            """
            WITH anomaly_context AS (
                SELECT
                    a.id AS anomaly_id,
                    d.symbol,
                    COUNT(nc.id) AS context_count
                FROM anomalies AS a
                JOIN datasets AS d ON d.id = a.dataset_id
                LEFT JOIN news_context AS nc ON nc.anomaly_id = a.id
                GROUP BY a.id, d.symbol
            )
            SELECT
                symbol,
                COUNT(*) AS anomaly_count,
                COUNT(*) FILTER (WHERE context_count > 0) AS anomalies_with_context
            FROM anomaly_context
            GROUP BY symbol
            ORDER BY anomalies_with_context DESC, symbol ASC
            """,
        )
        bridge_preserved = fetch_scalar(
            session,
            """
            SELECT COUNT(*)
            FROM anomalies
            WHERE metadata ->> 'episode_filter_status' = 'eligible'
              AND metadata ->> 'episode_filter_reason' IS NULL
              AND detection_method = 'change_point'
            """,
        )
        suppressed = fetch_scalar(
            session,
            """
            SELECT COUNT(*)
            FROM anomalies
            WHERE metadata ->> 'episode_filter_status' = 'suppressed'
            """,
        )

    return {
        "summary": summary,
        "quality_distribution": quality_distribution,
        "episode_kind_distribution": episode_kind_distribution,
        "anomaly_supply": anomaly_supply,
        "context_coverage": context_coverage,
        "bridge_preserved_change_points": bridge_preserved,
        "suppressed_anomalies": suppressed,
    }


def render_report(report: dict[str, object]) -> str:
    lines = ["MacroLens Graph Quality Report", ""]
    lines.append("Summary")
    for key, value in report["summary"].items():
        lines.append(f"- {key}: {value}")

    lines.append("")
    lines.append("Cluster quality distribution")
    for row in report["quality_distribution"]:
        lines.append(f"- {row['quality_band']}: {row['count']}")

    lines.append("")
    lines.append("Episode kind distribution")
    for row in report["episode_kind_distribution"]:
        lines.append(f"- {row['episode_kind']}: {row['count']}")

    lines.append("")
    lines.append("Anomaly supply by dataset")
    for row in report["anomaly_supply"]:
        lines.append(
            f"- {row['symbol']} ({row['frequency']}): total={row['anomaly_count']} z_score={row['z_score_count']} change_point={row['change_point_count']}"
        )

    lines.append("")
    lines.append("Context coverage by dataset")
    for row in report["context_coverage"]:
        lines.append(
            f"- {row['symbol']}: {row['anomalies_with_context']} / {row['anomaly_count']} anomalies with stored context"
        )

    lines.append("")
    lines.append(f"- bridge_preserved_change_points: {report['bridge_preserved_change_points']}")
    lines.append(f"- suppressed_anomalies: {report['suppressed_anomalies']}")
    return "\n".join(lines)


def main() -> None:
    report = build_report()
    print(render_report(report))
    output_path = ROOT / "documentation" / "research" / "latest_graph_quality_snapshot.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("")
    print(f"Saved JSON snapshot to {output_path}")


if __name__ == "__main__":
    main()
