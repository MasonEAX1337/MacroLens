from datetime import datetime, timezone

import httpx

from app.services.ingestion import DataPointRecord, DatasetDefinition


BITCOIN_DATASET = DatasetDefinition(
    key="bitcoin",
    name="Bitcoin Price",
    symbol="BTC",
    source="CoinGecko",
    description="Bitcoin spot price in USD.",
    frequency="daily",
)


class CoinGeckoClient:
    base_url = "https://api.coingecko.com/api/v3"

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def fetch_bitcoin_market_chart(self, days: int = 365) -> list[DataPointRecord]:
        url = f"{self.base_url}/coins/bitcoin/market_chart"
        response = httpx.get(
            url,
            params={"vs_currency": "usd", "days": days, "interval": "daily"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        daily_points: dict[datetime, float] = {}
        for timestamp_ms, value in payload.get("prices", []):
            raw_timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
            normalized_timestamp = raw_timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            daily_points[normalized_timestamp] = float(value)
        return [
            DataPointRecord(timestamp=timestamp, value=value)
            for timestamp, value in sorted(daily_points.items(), key=lambda item: item[0])
        ]
