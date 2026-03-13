from datetime import datetime, timezone

import httpx

from app.services.ingestion import DataPointRecord, DatasetDefinition


FRED_SERIES: dict[str, DatasetDefinition] = {
    "cpi": DatasetDefinition(
        key="cpi",
        name="Consumer Price Index",
        symbol="CPIAUCSL",
        source="FRED",
        description="Consumer Price Index for All Urban Consumers.",
        frequency="monthly",
    ),
    "fed_funds": DatasetDefinition(
        key="fed_funds",
        name="Federal Funds Rate",
        symbol="FEDFUNDS",
        source="FRED",
        description="Effective Federal Funds Rate.",
        frequency="monthly",
    ),
    "wti": DatasetDefinition(
        key="wti",
        name="WTI Oil Price",
        symbol="DCOILWTICO",
        source="FRED",
        description="Crude Oil Prices: West Texas Intermediate.",
        frequency="daily",
    ),
    "sp500": DatasetDefinition(
        key="sp500",
        name="S&P 500 Index",
        symbol="SP500",
        source="FRED",
        description="S&P 500 stock market index.",
        frequency="daily",
    ),
}


class FredClient:
    base_url = "https://api.stlouisfed.org/fred"

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.timeout = timeout

    def fetch_series(self, dataset: DatasetDefinition) -> list[DataPointRecord]:
        response = httpx.get(
            f"{self.base_url}/series/observations",
            params={
                "series_id": dataset.symbol,
                "api_key": self.api_key,
                "file_type": "json",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        points: list[DataPointRecord] = []
        for item in payload.get("observations", []):
            raw_value = item.get("value")
            if raw_value in {".", None, ""}:
                continue
            timestamp = datetime.strptime(item["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            points.append(DataPointRecord(timestamp=timestamp, value=float(raw_value)))
        return points
