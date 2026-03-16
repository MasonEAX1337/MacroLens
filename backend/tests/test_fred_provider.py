from app.services.providers.fred import FRED_SERIES


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
