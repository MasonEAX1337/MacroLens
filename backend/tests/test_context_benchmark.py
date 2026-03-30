import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluation.evaluate_context_ranking import evaluate_case, load_cases


def test_load_cases_parses_expected_fields(tmp_path) -> None:
    payload = [
        {
            "label": "test case",
            "dataset_symbol": "FEDFUNDS",
            "timestamp": "2022-03-01T00:00:00+00:00",
            "expected_event_ids": ["ukraine_war_energy_inflation_2022"],
            "expected_themes": ["geopolitics"],
            "notes": "sample",
        }
    ]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    cases = load_cases(path)

    assert len(cases) == 1
    assert cases[0].dataset_symbol == "FEDFUNDS"
    assert cases[0].expected_event_ids == ("ukraine_war_energy_inflation_2022",)


def test_evaluate_case_accepts_event_or_theme_match() -> None:
    case = load_cases(
        Path(ROOT / "documentation" / "research" / "context_ranking_benchmark.json")
    )[0]

    result = evaluate_case(
        case,
        {
            "anomaly_id": 1099,
            "provider": "macro_timeline",
            "title": "IMF Blog: How War in Ukraine Is Reverberating Across World's Regions",
            "historical_event_id": "ukraine_war_energy_inflation_2022",
            "primary_theme": "geopolitics",
            "context_score": 0.73,
        },
    )

    assert result["status"] == "matched"
    assert result["actual_event_id"] == "ukraine_war_energy_inflation_2022"
