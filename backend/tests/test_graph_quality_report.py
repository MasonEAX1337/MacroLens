import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluation.report_graph_quality import render_report


def test_render_report_includes_key_sections() -> None:
    report = {
        "summary": {"datasets": 8, "anomalies": 10},
        "quality_distribution": [{"quality_band": "low", "count": 7}],
        "episode_kind_distribution": [{"episode_kind": "isolated_signal", "count": 6}],
        "anomaly_supply": [
            {
                "symbol": "CPIAUCSL",
                "frequency": "monthly",
                "anomaly_count": 5,
                "z_score_count": 4,
                "change_point_count": 1,
            }
        ],
        "context_coverage": [
            {"symbol": "CPIAUCSL", "anomaly_count": 5, "anomalies_with_context": 3}
        ],
        "bridge_preserved_change_points": 2,
        "suppressed_anomalies": 1,
    }

    output = render_report(report)

    assert "MacroLens Graph Quality Report" in output
    assert "Cluster quality distribution" in output
    assert "CPIAUCSL" in output
    assert "bridge_preserved_change_points: 2" in output
