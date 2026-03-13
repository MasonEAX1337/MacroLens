import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import re
import time
from typing import Protocol

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings

_LAST_GDELT_REQUEST_AT = 0.0


DATASET_NEWS_TERMS: dict[str, list[str]] = {
    "BTC": ['"bitcoin"', "btc", "crypto"],
    "CPIAUCSL": ['"consumer price index"', "inflation", "cpi"],
    "FEDFUNDS": ['"federal funds rate"', '"interest rates"', "federal reserve"],
    "DCOILWTICO": ['"wti"', '"oil prices"', "crude"],
    "SP500": ['"S&P 500"', '"stock market"', "equities"],
}

DATASET_TITLE_KEYWORDS: dict[str, list[str]] = {
    "BTC": ["bitcoin", "btc", "crypto"],
    "CPIAUCSL": ["inflation", "consumer price", "cpi"],
    "FEDFUNDS": ["federal reserve", "interest rate", "fed funds", "rate hike", "rate cut"],
    "DCOILWTICO": ["oil", "wti", "crude"],
    "SP500": ["s&p 500", "stock market", "stocks", "equities"],
}


@dataclass(frozen=True)
class NewsContextRequest:
    anomaly_id: int
    dataset_name: str
    dataset_symbol: str
    timestamp: datetime


@dataclass(frozen=True)
class NewsArticleRecord:
    provider: str
    article_url: str
    title: str
    domain: str | None
    language: str | None
    source_country: str | None
    published_at: datetime | None
    search_query: str
    relevance_rank: int
    metadata: dict[str, object]


class NewsContextProvider(Protocol):
    provider_name: str

    def fetch(self, request: NewsContextRequest) -> list[NewsArticleRecord]:
        ...


def ensure_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def format_gdelt_timestamp(timestamp: datetime) -> str:
    return ensure_utc(timestamp).strftime("%Y%m%d%H%M%S")


def parse_gdelt_seendate(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def normalize_text(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(normalized.split())


def compute_article_day_offset(published_at: datetime | None, anomaly_timestamp: datetime) -> int | None:
    if published_at is None:
        return None
    return (ensure_utc(published_at).date() - ensure_utc(anomaly_timestamp).date()).days


def classify_article_timing(published_at: datetime | None, anomaly_timestamp: datetime) -> str:
    day_offset = compute_article_day_offset(published_at, anomaly_timestamp)
    if day_offset is None:
        return "unknown"
    if day_offset < 0:
        return "leading"
    if day_offset > 0:
        return "lagging"
    return "concurrent"


def article_matches_dataset(article: NewsArticleRecord, request: NewsContextRequest) -> bool:
    keywords = DATASET_TITLE_KEYWORDS.get(request.dataset_symbol)
    if not keywords:
        return True
    normalized_title = normalize_text(article.title)
    return any(normalize_text(keyword) in normalized_title for keyword in keywords)


def article_within_window(
    article: NewsArticleRecord,
    request: NewsContextRequest,
    window_days: int,
    *,
    grace_days: int = 2,
) -> bool:
    day_offset = compute_article_day_offset(article.published_at, request.timestamp)
    if day_offset is None:
        return False
    return abs(day_offset) <= window_days + grace_days


def rank_and_filter_articles(
    articles: list[NewsArticleRecord],
    request: NewsContextRequest,
    *,
    window_days: int,
    max_articles: int,
) -> list[NewsArticleRecord]:
    filtered: list[NewsArticleRecord] = []
    seen_titles: set[str] = set()
    for article in articles:
        if not article_within_window(article, request, window_days):
            continue
        if not article_matches_dataset(article, request):
            continue
        title_key = normalize_text(article.title)
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        filtered.append(article)

    def sort_key(article: NewsArticleRecord) -> tuple[int, int, int]:
        day_offset = compute_article_day_offset(article.published_at, request.timestamp)
        if day_offset is None:
            return (3, 999, article.relevance_rank)
        if day_offset < 0:
            timing_bucket = 0
        elif day_offset == 0:
            timing_bucket = 1
        else:
            timing_bucket = 2
        return (timing_bucket, abs(day_offset), article.relevance_rank)

    ranked = sorted(filtered, key=sort_key)[:max_articles]
    return [
        replace(article, relevance_rank=index)
        for index, article in enumerate(ranked, start=1)
    ]


def wait_for_gdelt_rate_limit(min_interval_seconds: float = 5.1) -> None:
    global _LAST_GDELT_REQUEST_AT

    elapsed = time.monotonic() - _LAST_GDELT_REQUEST_AT
    if elapsed < min_interval_seconds:
        time.sleep(min_interval_seconds - elapsed)
    _LAST_GDELT_REQUEST_AT = time.monotonic()


def build_news_query(request: NewsContextRequest, language: str) -> str:
    terms = DATASET_NEWS_TERMS.get(request.dataset_symbol, [f'"{request.dataset_name}"'])
    joined_terms = " OR ".join(terms)
    return f"({joined_terms}) sourcelang:{language.lower()}"


class GDELTNewsContextProvider:
    provider_name = "gdelt"

    def __init__(
        self,
        *,
        base_url: str,
        window_days: int,
        max_articles: int,
        language: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.window_days = window_days
        self.max_articles = max_articles
        self.language = language
        self.timeout_seconds = timeout_seconds

    def fetch(self, request: NewsContextRequest) -> list[NewsArticleRecord]:
        start = request.timestamp - timedelta(days=self.window_days)
        end = request.timestamp + timedelta(days=self.window_days, hours=23, minutes=59, seconds=59)
        query = build_news_query(request, self.language)
        payload: dict[str, object] = {}
        for attempt in range(2):
            wait_for_gdelt_rate_limit()
            response = httpx.get(
                f"{self.base_url}/doc",
                params={
                    "query": query,
                    "mode": "ArtList",
                    "format": "json",
                    "sort": "datedesc",
                    "maxrecords": self.max_articles,
                    "startdatetime": format_gdelt_timestamp(start),
                    "enddatetime": format_gdelt_timestamp(end),
                },
                timeout=self.timeout_seconds,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code == 429 and attempt == 0:
                    time.sleep(5.1)
                    continue
                return []
            try:
                payload = response.json()
                break
            except ValueError:
                if "Please limit requests" in response.text and attempt == 0:
                    time.sleep(5.1)
                    continue
                return []

        articles: list[NewsArticleRecord] = []
        for index, item in enumerate(payload.get("articles", []), start=1):
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            article_url = item.get("url")
            if not isinstance(title, str) or not title.strip():
                continue
            if not isinstance(article_url, str) or not article_url.strip():
                continue
            articles.append(
                NewsArticleRecord(
                    provider=self.provider_name,
                    article_url=article_url.strip(),
                    title=title.strip(),
                    domain=item.get("domain"),
                    language=item.get("language"),
                    source_country=item.get("sourcecountry"),
                    published_at=parse_gdelt_seendate(item.get("seendate")),
                    search_query=query,
                    relevance_rank=index,
                    metadata={
                        "social_image": item.get("socialimage"),
                        "url_mobile": item.get("url_mobile"),
                    },
                )
            )
        return rank_and_filter_articles(
            articles,
            request,
            window_days=self.window_days,
            max_articles=self.max_articles,
        )


def get_news_context_provider() -> NewsContextProvider:
    provider_name = settings.news_context_provider.strip().lower()
    if provider_name == "gdelt":
        return GDELTNewsContextProvider(
            base_url=settings.gdelt_base_url,
            window_days=settings.news_context_window_days,
            max_articles=settings.news_context_max_articles,
            language=settings.news_context_language,
        )
    raise ValueError(f"Unsupported news context provider: {settings.news_context_provider}")


def load_news_context_request(db: Session, anomaly_id: int) -> NewsContextRequest | None:
    query = text(
        """
        SELECT
            a.id AS anomaly_id,
            d.name AS dataset_name,
            d.symbol AS dataset_symbol,
            a.timestamp
        FROM anomalies AS a
        JOIN datasets AS d ON d.id = a.dataset_id
        WHERE a.id = :anomaly_id
        """
    )
    row = db.execute(query, {"anomaly_id": anomaly_id}).mappings().first()
    if row is None:
        return None

    return NewsContextRequest(
        anomaly_id=int(row["anomaly_id"]),
        dataset_name=str(row["dataset_name"]),
        dataset_symbol=str(row["dataset_symbol"]),
        timestamp=ensure_utc(row["timestamp"]),
    )


def replace_news_context(
    db: Session,
    anomaly_id: int,
    provider_name: str,
    articles: list[NewsArticleRecord],
) -> int:
    delete_query = text(
        """
        DELETE FROM news_context
        WHERE anomaly_id = :anomaly_id
          AND provider = :provider
        """
    )
    db.execute(delete_query, {"anomaly_id": anomaly_id, "provider": provider_name})

    if not articles:
        return 0

    insert_query = text(
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
            :provider,
            :article_url,
            :title,
            :domain,
            :language,
            :source_country,
            :published_at,
            :search_query,
            :relevance_rank,
            CAST(:metadata AS JSONB)
        )
        """
    )
    db.execute(
        insert_query,
        [
            {
                "anomaly_id": anomaly_id,
                "provider": item.provider,
                "article_url": item.article_url,
                "title": item.title,
                "domain": item.domain,
                "language": item.language,
                "source_country": item.source_country,
                "published_at": item.published_at,
                "search_query": item.search_query,
                "relevance_rank": item.relevance_rank,
                "metadata": json.dumps(item.metadata),
            }
            for item in articles
        ],
    )
    return len(articles)


def load_anomaly_ids(db: Session) -> list[int]:
    query = text(
        """
        SELECT id
        FROM anomalies
        ORDER BY timestamp DESC
        """
    )
    return [int(item) for item in db.execute(query).scalars().all()]


def run_news_context_for_anomaly(db: Session, anomaly_id: int) -> int:
    request = load_news_context_request(db, anomaly_id)
    if request is None:
        return 0
    provider = get_news_context_provider()
    articles = provider.fetch(request)
    return replace_news_context(db, anomaly_id, provider.provider_name, articles)


def run_news_context_for_all_anomalies(db: Session) -> int:
    inserted = 0
    for anomaly_id in load_anomaly_ids(db):
        inserted += run_news_context_for_anomaly(db, anomaly_id)
    return inserted
