import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings


REPORT_CONNECT_TIMEOUT_SECONDS = 5


def fetch_scalar(session, query: str) -> int:
    return int(session.execute(text(query)).scalar_one())


def fetch_mappings(session, query: str) -> list[dict[str, object]]:
    return [dict(row) for row in session.execute(text(query)).mappings().all()]


def build_report() -> dict[str, object]:
    engine = create_engine(
        settings.database_url,
        future=True,
        pool_pre_ping=True,
        connect_args={"connect_timeout": REPORT_CONNECT_TIMEOUT_SECONDS},
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    try:
        with session_factory() as session:
            return build_report_from_session(session)
    finally:
        engine.dispose()


def build_report_from_session(session) -> dict[str, object]:  # noqa: ANN001
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
    anomaly_episode_outcomes = fetch_mappings(
        session,
        """
        SELECT
            d.symbol,
            d.frequency,
            a.detection_method,
            COUNT(a.id) AS anomaly_count,
            COUNT(a.id) FILTER (
                WHERE a.metadata ->> 'episode_filter_status' = 'suppressed'
            ) AS suppressed_count,
            COUNT(a.id) FILTER (
                WHERE acm.cluster_id IS NOT NULL
            ) AS clustered_count,
            COUNT(a.id) FILTER (
                WHERE ac.episode_kind = 'isolated_signal'
            ) AS isolated_signal_count,
            COUNT(a.id) FILTER (
                WHERE ac.episode_kind = 'single_dataset_wave'
            ) AS single_dataset_wave_count,
            COUNT(a.id) FILTER (
                WHERE ac.episode_kind = 'cross_dataset_episode'
            ) AS cross_dataset_episode_count,
            COUNT(a.id) FILTER (
                WHERE ac.quality_band IN ('medium', 'high')
            ) AS medium_or_high_quality_count
        FROM anomalies AS a
        JOIN datasets AS d ON d.id = a.dataset_id
        LEFT JOIN anomaly_cluster_members AS acm ON acm.anomaly_id = a.id
        LEFT JOIN anomaly_clusters AS ac ON ac.id = acm.cluster_id
        GROUP BY d.symbol, d.frequency, a.detection_method
        ORDER BY
            d.symbol ASC,
            CASE a.detection_method
                WHEN 'z_score' THEN 0
                WHEN 'change_point' THEN 1
                ELSE 2
            END ASC
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
        "anomaly_episode_outcomes": anomaly_episode_outcomes,
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
    lines.append("Episode outcomes by dataset and detection method")
    for row in report["anomaly_episode_outcomes"]:
        lines.append(
            f"- {row['symbol']} ({row['frequency']}, {row['detection_method']}): "
            f"total={row['anomaly_count']} clustered={row['clustered_count']} "
            f"suppressed={row['suppressed_count']} isolated={row['isolated_signal_count']} "
            f"single_dataset_wave={row['single_dataset_wave_count']} "
            f"cross_dataset_episode={row['cross_dataset_episode_count']} "
            f"medium_or_high_quality={row['medium_or_high_quality_count']}"
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
    try:
        report = build_report()
    except SQLAlchemyError as exc:
        raise SystemExit(
            "Could not build graph quality report because PostgreSQL is unavailable or too slow to respond. "
            f"Check DATABASE_URL and start the local database, then rerun this command. Details: {exc}"
        ) from exc
    print(render_report(report))
    output_path = ROOT / "documentation" / "research" / "latest_graph_quality_snapshot.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("")
    print(f"Saved JSON snapshot to {output_path}")


if __name__ == "__main__":
    main()
