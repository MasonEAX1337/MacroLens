from app.services.providers.fred import FRED_SERIES


def test_sp500_dataset_definition_is_registered() -> None:
    dataset = FRED_SERIES["sp500"]

    assert dataset.name == "S&P 500 Index"
    assert dataset.symbol == "SP500"
    assert dataset.source == "FRED"
    assert dataset.frequency == "daily"
