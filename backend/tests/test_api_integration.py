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
    assert payload["cluster"]["anomaly_count"] == 1
    assert payload["cluster"]["episode_kind"] == "isolated_signal"
    assert payload["cluster"]["quality_band"] == "low"
    assert payload["cluster"]["frequency_mix"] == "daily_only"
    assert payload["cluster"]["members"][0]["anomaly_id"] == seeded_event_graph["anomaly_id"]
    assert payload["propagation_timeline"][0]["target_anchor_anomaly_id"] == seeded_event_graph["target_anomaly_id"]
    assert payload["propagation_timeline"][0]["target_dataset_names"] == ["S&P 500 Index"]
    assert payload["propagation_timeline"][0]["target_episode_kind"] == "isolated_signal"
    assert payload["propagation_timeline"][0]["target_quality_band"] == "low"
    assert payload["propagation_timeline"][0]["evidence_strength_components"]["episode_quality"] == 0.8
    assert payload["propagation_timeline"][0]["supporting_link_count"] == 1
    assert payload["propagation_timeline"][0]["evidence_strength_components"]["overall"] == payload["propagation_timeline"][0]["evidence_strength"]
    assert payload["correlations"][0]["related_dataset_name"] == "S&P 500 Index"
    assert payload["news_context"][0]["title"] == "Bitcoin Selloff Deepens as Risk Assets Weaken"
    assert payload["news_context"][0]["provider"] == "gdelt"
    assert payload["news_context"][0]["retrieval_scope"] == "episode"
    assert payload["news_context"][0]["timing_relation"] == "during"
    assert payload["news_context"][0]["primary_theme"] == "market_stress"
    assert payload["news_context"][0]["context_score"] is not None
    assert payload["news_context_status"]["status"] == "available"
    assert payload["explanations"][0]["provider"] == "gemini"


def test_dataset_leading_indicators_endpoint_returns_cluster_aggregates(client, seeded_leading_indicators) -> None:  # noqa: ANN001
    response = client.get(
        f"/api/v1/datasets/{seeded_leading_indicators['dataset_id']}/leading-indicators?limit=5"
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["related_dataset_name"] == "WTI Oil Price"
    assert payload[0]["supporting_cluster_count"] == 2
    assert payload[0]["target_cluster_count"] == 2
    assert payload[0]["cluster_coverage"] == 1.0
    assert payload[0]["related_dataset_frequency"] == "daily"
    assert payload[0]["target_dataset_frequency"] == "monthly"
    assert payload[0]["average_lead_days"] == 19
    assert payload[0]["frequency_alignment"] == 0.65
    assert payload[0]["support_confidence"] == 0.55
    assert payload[0]["supporting_episodes"][0]["target_anomaly_id"] == 2
    assert payload[0]["supporting_episodes"][0]["target_cluster_id"] == 2
    assert payload[0]["supporting_episodes"][0]["target_cluster_anomaly_count"] == 2
    assert payload[0]["supporting_episodes"][0]["target_cluster_episode_kind"] == "single_dataset_wave"
    assert payload[0]["supporting_episodes"][0]["target_cluster_quality_band"] == "low"
    assert len(payload[0]["supporting_episodes"][0]["cluster_members"]) == 2
    assert payload[0]["supporting_episodes"][0]["cluster_members"][0]["dataset_name"] == "Consumer Price Index"


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


def test_anomaly_detail_exposes_structured_driver_fallback(client, db_session) -> None:  # noqa: ANN001
    from app.services.ingestion import DatasetDefinition, upsert_dataset
    from sqlalchemy import text
    from datetime import datetime, timezone

    dataset_id = upsert_dataset(
        db_session,
        DatasetDefinition(
            key="fed_funds",
            name="Federal Funds Rate",
            symbol="FEDFUNDS",
            source="FRED",
            description="Effective Federal Funds Rate.",
            frequency="monthly",
        ),
    )
    anomaly_id = int(
        db_session.execute(
            text(
                """
                INSERT INTO anomalies (dataset_id, timestamp, severity_score, direction, detection_method)
                VALUES (:dataset_id, :timestamp, :severity_score, :direction, :detection_method)
                RETURNING id
                """
            ),
            {
                "dataset_id": dataset_id,
                "timestamp": datetime(2025, 11, 1, tzinfo=timezone.utc),
                "severity_score": 2.4,
                "direction": "down",
                "detection_method": "z_score",
            },
        ).scalar_one()
    )
    db_session.execute(
        text(
            """
            INSERT INTO news_context (
                anomaly_id,
                provider,
                article_url,
                title,
                domain,
                language,
                source_country,
                published_at,
                search_query,
                relevance_rank,
                metadata
            )
            VALUES (
                :anomaly_id,
                'dataset_backdrop',
                'https://fred.stlouisfed.org/series/FEDFUNDS',
                'Likely macro drivers for Fed policy',
                'structured-fallback',
                'English',
                'United States',
                :published_at,
                'dataset_backdrop:FEDFUNDS',
                1,
                CAST(:metadata AS JSONB)
            )
            """
        ),
        {
            "anomaly_id": anomaly_id,
            "published_at": datetime(2025, 11, 1, tzinfo=timezone.utc),
            "metadata": '{"retrieval_scope":"dataset_backdrop","timing_relation":"during","source_kind":"dataset_driver_fallback","driver_summary":"No direct article or curated historical event was matched for this anomaly. This rate move most likely reflects changing Federal Reserve policy expectations tied to inflation data, labor-market conditions, banking stress, financial conditions, or recession risk.","event_themes":["fed_policy","inflation"],"primary_theme":"fed_policy","context_score":0.22}',
        },
    )
    db_session.commit()

    response = client.get(f"/api/v1/anomalies/{anomaly_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["news_context"][0]["provider"] == "dataset_backdrop"
    assert payload["news_context"][0]["source_kind"] == "dataset_driver_fallback"
    assert "Federal Reserve policy expectations" in payload["news_context"][0]["driver_summary"]
    assert payload["news_context_status"]["provider"] == "dataset_backdrop"


def test_episode_filter_status_is_exposed_for_suppressed_and_preserved_anomalies(
    client,
    seeded_episode_filter_graph,
) -> None:  # noqa: ANN001
    suppressed_response = client.get(f"/api/v1/anomalies/{seeded_episode_filter_graph['suppressed_anomaly_id']}")
    assert suppressed_response.status_code == 200
    suppressed_payload = suppressed_response.json()
    assert suppressed_payload["episode_filter_status"] == "suppressed"
    assert suppressed_payload["episode_filter_reason"] == "weak_monthly_isolated_change_point"
    assert suppressed_payload["cluster"] is None

    preserved_response = client.get(f"/api/v1/anomalies/{seeded_episode_filter_graph['bridge_anomaly_id']}")
    assert preserved_response.status_code == 200
    preserved_payload = preserved_response.json()
    assert preserved_payload["episode_filter_status"] == "eligible"
    assert preserved_payload["episode_filter_reason"] is None
    assert preserved_payload["cluster"]["episode_kind"] == "cross_dataset_episode"

    list_response = client.get(
        f"/api/v1/datasets/{seeded_episode_filter_graph['house_dataset_id']}/anomalies?limit=10"
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload[0]["episode_filter_status"] == "suppressed"
    assert list_payload[0]["cluster_id"] is None
