import httpx

from app.services.providers.fred import FRED_SERIES, FredClient


def test_sp500_dataset_definition_is_registered() -> None:
    dataset = FRED_SERIES["sp500"]

    assert dataset.name == "S&P 500 Index"
    assert dataset.symbol == "SP500"
    assert dataset.source == "FRED"
    assert dataset.frequency == "daily"


def test_household_macro_dataset_definitions_are_registered() -> None:
    house_price = FRED_SERIES["house_price_us"]
    mortgage_rate = FRED_SERIES["mortgage_30y"]
    income = FRED_SERIES["income_real_per_capita"]

    assert house_price.name == "Case-Shiller U.S. National Home Price Index"
    assert house_price.symbol == "CSUSHPISA"
    assert house_price.frequency == "monthly"

    assert mortgage_rate.name == "30-Year Fixed Rate Mortgage Average in the United States"
    assert mortgage_rate.symbol == "MORTGAGE30US"
    assert mortgage_rate.frequency == "weekly"

    assert income.name == "Real Disposable Personal Income Per Capita"
    assert income.symbol == "A229RX0"
    assert income.frequency == "monthly"


def test_fred_client_sanitizes_http_errors(monkeypatch) -> None:
    request = httpx.Request(
        "GET",
        "https://api.stlouisfed.org/fred/series/observations?series_id=CPIAUCSL&api_key=secret-key&file_type=json",
    )
    response = httpx.Response(500, request=request)

    class MockResponse:
        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError(
                "Server error for url with api_key=secret-key",
                request=request,
                response=response,
            )

    def mock_get(*args, **kwargs):  # noqa: ANN002, ANN003
        return MockResponse()

    monkeypatch.setattr("app.services.providers.fred.httpx.get", mock_get)

    client = FredClient(api_key="secret-key")

    try:
        client.fetch_series(FRED_SERIES["cpi"])
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected sanitized FRED failure")

    assert message == "FRED request failed for CPIAUCSL: HTTP 500"
    assert "secret-key" not in message
    assert "api_key" not in message
