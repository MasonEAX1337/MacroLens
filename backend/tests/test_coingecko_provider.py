from app.services.providers.coingecko import CoinGeckoClient


def test_fetch_bitcoin_market_chart_normalizes_daily_timestamps(monkeypatch) -> None:
    payload = {
        "prices": [
            [1741737600000, 70000.0],
            [1741756492000, 69415.49],
        ]
    }

    class MockResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return payload

    def mock_get(*args, **kwargs):  # noqa: ANN002, ANN003
        return MockResponse()

    monkeypatch.setattr("app.services.providers.coingecko.httpx.get", mock_get)

    client = CoinGeckoClient()
    points = client.fetch_bitcoin_market_chart()

    assert len(points) == 1
    assert points[0].timestamp.hour == 0
    assert points[0].timestamp.minute == 0
    assert points[0].value == 69415.49
