import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.explanations import generate_explanations


class DummySessionContext:
    def __enter__(self):  # noqa: ANN204
        return object()

    def __exit__(self, exc_type, exc, traceback):  # noqa: ANN001
        return False


def test_generate_explanations_supports_provider_override_and_quiet_output(monkeypatch, capsys) -> None:
    original_provider = generate_explanations.settings.explanation_provider
    generate_explanations.settings.explanation_provider = "gemini"
    calls: list[int] = []

    def fake_run_explanation_for_anomaly(session, anomaly_id: int) -> int:  # noqa: ANN001
        assert generate_explanations.settings.explanation_provider == "rules_based"
        calls.append(anomaly_id)
        return 1

    monkeypatch.setattr(sys, "argv", ["generate_explanations.py", "--provider", "rules_based", "--quiet"])
    monkeypatch.setattr(generate_explanations, "iter_target_anomaly_ids", lambda args: iter([3, 2]))
    monkeypatch.setattr(generate_explanations.SessionLocal, "begin", lambda: DummySessionContext())
    monkeypatch.setattr(generate_explanations, "run_explanation_for_anomaly", fake_run_explanation_for_anomaly)

    try:
        generate_explanations.main()
        output = capsys.readouterr().out
        assert calls == [3, 2]
        assert "explanations: anomaly" not in output
        assert "explanations: stored 2 row(s) across 2 anomaly/anomalies" in output
        assert generate_explanations.settings.explanation_provider == "gemini"
    finally:
        generate_explanations.settings.explanation_provider = original_provider
