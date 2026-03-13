def test_datasets_endpoint_returns_seeded_dataset(client, seeded_event_graph) -> None:  # noqa: ANN001
    response = client.get("/api/v1/datasets")

    assert response.status_code == 200
    payload = response.json()
    assert any(item["name"] == "Bitcoin Price" for item in payload)


def test_timeseries_endpoint_returns_ordered_points(client, seeded_event_graph) -> None:  # noqa: ANN001
    response = client.get(f"/api/v1/datasets/{seeded_event_graph['dataset_id']}/timeseries?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert [item["timestamp"] for item in payload] == sorted(item["timestamp"] for item in payload)
    assert payload[-1]["value"] == 99500.0


def test_anomaly_detail_returns_news_context_and_explanations(client, seeded_event_graph) -> None:  # noqa: ANN001
    response = client.get(f"/api/v1/anomalies/{seeded_event_graph['anomaly_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_name"] == "Bitcoin Price"
    assert payload["correlations"][0]["related_dataset_name"] == "S&P 500 Index"
    assert payload["news_context"][0]["title"] == "Bitcoin Selloff Deepens as Risk Assets Weaken"
    assert payload["news_context"][0]["provider"] == "gdelt"
    assert payload["explanations"][0]["provider"] == "gemini"


def test_regenerate_explanation_endpoint_returns_updated_detail(client, seeded_event_graph, monkeypatch) -> None:  # noqa: ANN001
    from app.services.explanations import RulesBasedExplanationProvider

    monkeypatch.setattr(
        "app.services.explanations.get_explanation_provider",
        lambda: RulesBasedExplanationProvider(),
    )

    response = client.post(f"/api/v1/anomalies/{seeded_event_graph['anomaly_id']}/regenerate-explanation")

    assert response.status_code == 200
    payload = response.json()
    assert any(item["provider"] == "rules_based" for item in payload["explanations"])
