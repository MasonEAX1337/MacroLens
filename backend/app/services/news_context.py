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

DATASET_NEWS_QUERY_OVERRIDES: dict[str, str] = {
    "CSUSHPISA": '(("home prices" OR "house prices" OR "home values" OR "case shiller") AND (housing OR "real estate" OR homes))',
    "MORTGAGE30US": '(("mortgage rates" OR mortgage OR refinancing OR refinance OR "home loans") AND (housing OR homebuyers OR affordability))',
    "A229RX0": '((("disposable income" OR "personal income" OR "household income") AND (income OR households OR wages)) OR ("stimulus checks" OR stimulus OR "relief package" OR benefits OR paycheck))',
}

DATASET_TITLE_KEYWORDS: dict[str, list[str]] = {
    "BTC": ["bitcoin", "btc", "crypto"],
    "CPIAUCSL": ["inflation", "consumer price", "cpi"],
    "FEDFUNDS": ["federal reserve", "interest rate", "fed funds", "rate hike", "rate cut"],
    "DCOILWTICO": ["oil", "wti", "crude"],
    "SP500": ["s&p 500", "stock market", "stocks", "equities"],
    "CSUSHPISA": [
        "case shiller",
        "home price",
        "house price",
        "housing market",
        "home values",
        "real estate",
        "home sales",
    ],
    "MORTGAGE30US": [
        "mortgage",
        "mortgage rate",
        "home loan",
        "homebuyer",
        "housing affordability",
        "refinance",
        "refinancing",
    ],
    "A229RX0": [
        "disposable income",
        "personal income",
        "household income",
        "consumer spending",
        "stimulus",
        "relief package",
        "benefits",
        "paycheck",
    ],
}


@dataclass(frozen=True)
class NewsContextRequest:
    anomaly_id: int
    dataset_name: str
    dataset_symbol: str
    dataset_frequency: str
    timestamp: datetime
    cluster_id: int | None = None
    cluster_start_timestamp: datetime | None = None
    cluster_end_timestamp: datetime | None = None
    cluster_episode_kind: str | None = None
    cluster_quality_band: str | None = None
    cluster_dataset_symbols: tuple[str, ...] = ()


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


@dataclass(frozen=True)
class MacroTimelineEntry:
    dataset_symbols: frozenset[str]
    start_at: datetime
    end_at: datetime
    published_at: datetime
    title: str
    article_url: str
    domain: str
    search_query: str
    metadata: dict[str, object]


HOUSEHOLD_NEWS_SYMBOLS = {"CSUSHPISA", "MORTGAGE30US", "A229RX0"}
EPISODE_RETRIEVAL_EPISODE_KINDS = {"single_dataset_wave", "cross_dataset_episode"}

DATASET_EVENT_HINT_TERMS: dict[str, list[str]] = {
    "BTC": ["crypto", '"risk assets"'],
    "CPIAUCSL": ["inflation", '"consumer prices"'],
    "FEDFUNDS": ['"federal reserve"', '"interest rates"'],
    "DCOILWTICO": ["oil", "energy"],
    "SP500": ['"stock market"', "equities"],
    "CSUSHPISA": ["housing", '"home prices"'],
    "MORTGAGE30US": ['"mortgage rates"', "housing"],
    "A229RX0": ['"household income"', '"consumer spending"'],
}

EVENT_THEME_KEYWORDS: dict[str, list[str]] = {
    "fed_policy": ["federal reserve", "fed", "rate hike", "rate cut", "powell", "policy meeting"],
    "inflation": ["inflation", "consumer prices", "cpi", "price pressures"],
    "energy_shock": ["oil", "crude", "opec", "energy prices", "gas prices"],
    "geopolitics": ["war", "ukraine", "russia", "middle east", "conflict", "invasion", "sanctions"],
    "banking_stress": ["banking stress", "bank failure", "svb", "regional bank", "credit stress"],
    "housing": ["housing", "home prices", "house prices", "mortgage", "affordability", "real estate"],
    "labor_market": ["jobs", "employment", "unemployment", "payrolls", "labor market"],
    "fiscal_policy": ["stimulus", "relief package", "spending bill", "tax", "fiscal"],
    "consumer_demand": ["consumer spending", "demand", "retail sales"],
    "market_stress": ["selloff", "sell off", "risk assets", "market stress", "risk-off", "volatility"],
}

DATASET_THEME_PRIORS: dict[str, list[str]] = {
    "CPIAUCSL": ["inflation", "energy_shock", "fed_policy"],
    "FEDFUNDS": ["fed_policy", "banking_stress", "inflation"],
    "DCOILWTICO": ["energy_shock", "geopolitics", "inflation"],
    "CSUSHPISA": ["housing", "fed_policy"],
    "MORTGAGE30US": ["housing", "fed_policy", "banking_stress"],
    "A229RX0": ["consumer_demand", "fiscal_policy", "labor_market"],
    "SP500": ["market_stress", "fed_policy", "geopolitics"],
    "BTC": ["market_stress", "fed_policy"],
}


class NewsContextProvider(Protocol):
    provider_name: str

    def fetch(self, request: NewsContextRequest) -> list[NewsArticleRecord]:
        ...


def utc_datetime(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


MACRO_TIMELINE_ENTRIES: tuple[MacroTimelineEntry, ...] = (
    MacroTimelineEntry(
        dataset_symbols=frozenset({"CSUSHPISA", "MORTGAGE30US", "SP500", "FEDFUNDS", "DCOILWTICO"}),
        start_at=utc_datetime(2007, 1, 1),
        end_at=utc_datetime(2010, 12, 31, 23, 59, 59),
        published_at=utc_datetime(2008, 9, 15),
        title="Federal Reserve History: Subprime Mortgage Crisis",
        article_url="https://www.federalreservehistory.org/essays/subprime-mortgage-crisis",
        domain="federalreservehistory.org",
        search_query="macro_timeline:subprime_mortgage_crisis",
        metadata={
            "timeline_id": "subprime_mortgage_crisis",
            "coverage": "2007-2010 housing and mortgage stress",
            "evidence_kind": "curated_historical_context",
        },
    ),
    MacroTimelineEntry(
        dataset_symbols=frozenset({"MORTGAGE30US", "FEDFUNDS", "CPIAUCSL", "DCOILWTICO"}),
        start_at=utc_datetime(1979, 8, 1),
        end_at=utc_datetime(1982, 12, 31, 23, 59, 59),
        published_at=utc_datetime(1979, 10, 6),
        title="Federal Reserve History: The Great Inflation",
        article_url="https://www.federalreservehistory.org/essays/great-inflation",
        domain="federalreservehistory.org",
        search_query="macro_timeline:great_inflation",
        metadata={
            "timeline_id": "great_inflation",
            "coverage": "1979-1982 high-rate inflation regime",
            "evidence_kind": "curated_historical_context",
        },
    ),
    MacroTimelineEntry(
        dataset_symbols=frozenset({"DCOILWTICO", "CPIAUCSL", "FEDFUNDS", "MORTGAGE30US", "SP500"}),
        start_at=utc_datetime(2022, 2, 1),
        end_at=utc_datetime(2022, 6, 30, 23, 59, 59),
        published_at=utc_datetime(2022, 3, 15),
        title="IMF Blog: How War in Ukraine Is Reverberating Across World's Regions",
        article_url="https://www.imf.org/en/Blogs/Articles/2022/03/15/how-war-in-ukraine-is-reverberating-across-worlds-regions",
        domain="imf.org",
        search_query="macro_timeline:ukraine_war_energy_inflation_2022",
        metadata={
            "timeline_id": "ukraine_war_energy_inflation_2022",
            "coverage": "2022 energy, inflation, and policy shock after Russia's invasion of Ukraine",
            "evidence_kind": "curated_historical_context",
        },
    ),
    MacroTimelineEntry(
        dataset_symbols=frozenset({"DCOILWTICO", "CPIAUCSL", "FEDFUNDS", "MORTGAGE30US", "SP500", "A229RX0"}),
        start_at=utc_datetime(1990, 7, 1),
        end_at=utc_datetime(1991, 6, 30, 23, 59, 59),
        published_at=utc_datetime(2009, 6, 1),
        title="IMF Finance & Development: Out of the Ballpark",
        article_url="https://www.imf.org/external/pubs/ft/fandd/2009/06/kose.htm",
        domain="imf.org",
        search_query="macro_timeline:gulf_war_oil_recession_1990_1991",
        metadata={
            "timeline_id": "gulf_war_oil_recession_1990_1991",
            "coverage": "1990-1991 Gulf War, oil-price shock, and recession backdrop",
            "evidence_kind": "curated_historical_context",
        },
    ),
    MacroTimelineEntry(
        dataset_symbols=frozenset({"CSUSHPISA", "MORTGAGE30US", "FEDFUNDS", "A229RX0", "SP500"}),
        start_at=utc_datetime(2001, 1, 1),
        end_at=utc_datetime(2006, 12, 31, 23, 59, 59),
        published_at=utc_datetime(2013, 11, 22),
        title="Federal Reserve History: The Great Recession and Its Aftermath",
        article_url="https://www.federalreservehistory.org/essays/great-recession-and-its-aftermath",
        domain="federalreservehistory.org",
        search_query="macro_timeline:housing_boom_low_rates_2001_2006",
        metadata={
            "timeline_id": "housing_boom_low_rates_2001_2006",
            "coverage": "2001-2006 housing expansion, low rates, and mortgage-credit growth",
            "evidence_kind": "curated_historical_context",
        },
    ),
    MacroTimelineEntry(
        dataset_symbols=frozenset({"A229RX0"}),
        start_at=utc_datetime(2020, 3, 1),
        end_at=utc_datetime(2020, 6, 30, 23, 59, 59),
        published_at=utc_datetime(2020, 3, 30),
        title="IRS: Economic impact payments: What you need to know",
        article_url="https://www.irs.gov/newsroom/economic-impact-payments-what-you-need-to-know",
        domain="irs.gov",
        search_query="macro_timeline:economic_impact_payments_2020",
        metadata={
            "timeline_id": "economic_impact_payments_2020",
            "coverage": "2020 pandemic relief payments",
            "evidence_kind": "curated_historical_context",
        },
    ),
    MacroTimelineEntry(
        dataset_symbols=frozenset({"A229RX0"}),
        start_at=utc_datetime(2021, 3, 1),
        end_at=utc_datetime(2021, 12, 31, 23, 59, 59),
        published_at=utc_datetime(2021, 3, 12),
        title="IRS: Third-round Economic Impact Payments issued in 2021",
        article_url="https://www.irs.gov/individuals/understanding-your-letter-6475",
        domain="irs.gov",
        search_query="macro_timeline:economic_impact_payments_2021",
        metadata={
            "timeline_id": "economic_impact_payments_2021",
            "coverage": "2021 third-round and plus-up payments",
            "evidence_kind": "curated_historical_context",
        },
    ),
)


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


def get_context_window(request: NewsContextRequest) -> tuple[str, datetime, datetime]:
    if (
        request.cluster_id is not None
        and request.cluster_start_timestamp is not None
        and request.cluster_end_timestamp is not None
        and request.cluster_episode_kind in EPISODE_RETRIEVAL_EPISODE_KINDS
    ):
        return (
            "episode",
            ensure_utc(request.cluster_start_timestamp),
            ensure_utc(request.cluster_end_timestamp),
        )
    anomaly_timestamp = ensure_utc(request.timestamp)
    return ("anomaly", anomaly_timestamp, anomaly_timestamp)


def get_search_window(request: NewsContextRequest, base_window_days: int) -> tuple[datetime, datetime]:
    _, context_start, context_end = get_context_window(request)
    effective_window_days = get_effective_window_days(request, base_window_days)
    search_start = context_start - timedelta(days=effective_window_days)
    search_end = context_end + timedelta(days=effective_window_days, hours=23, minutes=59, seconds=59)
    return search_start, search_end


def get_article_distance_from_window(
    published_at: datetime | None,
    window_start: datetime,
    window_end: datetime,
) -> int | None:
    if published_at is None:
        return None
    published_date = ensure_utc(published_at).date()
    start_date = ensure_utc(window_start).date()
    end_date = ensure_utc(window_end).date()
    if published_date < start_date:
        return (start_date - published_date).days
    if published_date > end_date:
        return (published_date - end_date).days
    return 0


def classify_article_timing_for_request(article: NewsArticleRecord, request: NewsContextRequest) -> str:
    scope, context_start, context_end = get_context_window(request)
    if article.published_at is None:
        return "unknown"
    published_date = ensure_utc(article.published_at).date()
    start_date = context_start.date()
    end_date = context_end.date()
    if published_date < start_date:
        return "before"
    if published_date > end_date:
        return "after"
    if scope == "anomaly":
        return "during"
    return "during"


def describe_article_timing_for_request(article: NewsArticleRecord, request: NewsContextRequest) -> str:
    timing_relation = classify_article_timing_for_request(article, request)
    if timing_relation == "before":
        return "before the episode"
    if timing_relation == "during":
        return "during the episode"
    if timing_relation == "after":
        return "after the episode"
    return "unknown timing"


def article_matches_dataset(article: NewsArticleRecord, request: NewsContextRequest) -> bool:
    return article_match_score(article, request) > 0


def article_match_score(article: NewsArticleRecord, request: NewsContextRequest) -> int:
    keywords = DATASET_TITLE_KEYWORDS.get(request.dataset_symbol)
    if not keywords:
        return 1
    normalized_title = normalize_text(article.title)
    return sum(1 for keyword in keywords if normalize_text(keyword) in normalized_title)


def get_effective_window_days(request: NewsContextRequest, base_window_days: int) -> int:
    frequency = request.dataset_frequency.strip().lower()
    if frequency == "monthly":
        return max(base_window_days, 21)
    if frequency == "weekly":
        return max(base_window_days, 14)
    return base_window_days


def article_within_window(
    article: NewsArticleRecord,
    request: NewsContextRequest,
    window_days: int,
    *,
    grace_days: int = 2,
) -> bool:
    scope, context_start, context_end = get_context_window(request)
    del scope
    distance = get_article_distance_from_window(article.published_at, context_start, context_end)
    if distance is None:
        return False
    effective_window_days = get_effective_window_days(request, window_days)
    return distance <= effective_window_days + grace_days


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

    def sort_key(article: NewsArticleRecord) -> tuple[int, int, int, int]:
        timing_relation = classify_article_timing_for_request(article, request)
        scope, context_start, context_end = get_context_window(request)
        del scope
        distance = get_article_distance_from_window(article.published_at, context_start, context_end)
        keyword_score = article_match_score(article, request)
        if distance is None:
            return (-keyword_score, 3, 999, article.relevance_rank)
        if timing_relation == "during":
            timing_bucket = 0
        elif timing_relation == "before":
            timing_bucket = 1
        else:
            timing_bucket = 2
        return (-keyword_score, timing_bucket, distance, article.relevance_rank)

    ranked = sorted(filtered, key=sort_key)[:max_articles]
    return [
        replace(article, relevance_rank=index)
        for index, article in enumerate(ranked, start=1)
    ]


def wait_for_gdelt_rate_limit(min_interval_seconds: float) -> None:
    global _LAST_GDELT_REQUEST_AT

    elapsed = time.monotonic() - _LAST_GDELT_REQUEST_AT
    if elapsed < min_interval_seconds:
        time.sleep(min_interval_seconds - elapsed)
    _LAST_GDELT_REQUEST_AT = time.monotonic()


def build_news_query(request: NewsContextRequest, language: str) -> str:
    override = DATASET_NEWS_QUERY_OVERRIDES.get(request.dataset_symbol)
    episode_hint_terms: list[str] = []
    retrieval_scope, _, _ = get_context_window(request)
    if retrieval_scope == "episode":
        for symbol in request.cluster_dataset_symbols:
            if symbol == request.dataset_symbol:
                continue
            episode_hint_terms.extend(DATASET_EVENT_HINT_TERMS.get(symbol, []))
        episode_hint_terms = list(dict.fromkeys(episode_hint_terms))[:3]
    if override:
        if episode_hint_terms:
            joined_hints = " OR ".join(episode_hint_terms)
            return f"({override}) AND ({joined_hints}) sourcelang:{language.lower()}"
        return f"{override} sourcelang:{language.lower()}"
    terms = DATASET_NEWS_TERMS.get(request.dataset_symbol, [f'"{request.dataset_name}"'])
    if episode_hint_terms:
        terms = [*terms, *episode_hint_terms]
    joined_terms = " OR ".join(terms)
    return f"({joined_terms}) sourcelang:{language.lower()}"


def extract_event_themes(
    article: NewsArticleRecord,
    request: NewsContextRequest,
) -> list[str]:
    searchable_text = normalize_text(f"{article.title} {article.search_query}")
    scores: dict[str, int] = {}
    dataset_priors = set(DATASET_THEME_PRIORS.get(request.dataset_symbol, []))

    for theme, keywords in EVENT_THEME_KEYWORDS.items():
        keyword_hits = sum(1 for keyword in keywords if normalize_text(keyword) in searchable_text)
        if keyword_hits <= 0:
            continue
        scores[theme] = keyword_hits + (1 if theme in dataset_priors else 0)

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [theme for theme, _score in ranked[:3]]


def get_fetch_record_limit(max_articles: int) -> int:
    return min(max(max_articles * 5, 10), 50)


def get_news_context_status(
    *,
    dataset_symbol: str,
    dataset_frequency: str,
    has_articles: bool,
    attempted_provider_names: list[str],
    article_provider_names: list[str] | None = None,
) -> dict[str, str]:
    active_provider_names = article_provider_names if has_articles and article_provider_names else attempted_provider_names
    provider_label = "+".join(active_provider_names) if active_provider_names else "unknown"
    if has_articles:
        if "macro_timeline" in active_provider_names and "gdelt" in active_provider_names:
            note = "Stored citations are available from curated historical context and live article retrieval."
        elif "macro_timeline" in active_provider_names:
            note = "Stored citations are available from the curated macro timeline."
        else:
            note = "Stored citations are available for this anomaly."
        return {
            "provider": provider_label,
            "status": "available",
            "note": note,
        }

    normalized_frequency = dataset_frequency.strip().lower()
    if dataset_symbol in HOUSEHOLD_NEWS_SYMBOLS:
        return {
            "provider": provider_label,
            "status": "limited_coverage",
            "note": "No citations were stored. Broad household macro topics are still weak with live retrieval, and curated timeline coverage is limited to selected historical regimes.",
        }
    if normalized_frequency in {"weekly", "monthly"}:
        return {
            "provider": provider_label,
            "status": "limited_coverage",
            "note": "No citations were stored. Slower weekly and monthly series often have weaker news alignment than daily market moves.",
        }
    return {
        "provider": provider_label,
        "status": "unavailable",
        "note": "No citations were stored for this anomaly from the current news provider.",
    }


def context_window_overlaps_entry(
    request: NewsContextRequest,
    entry: MacroTimelineEntry,
) -> bool:
    _, context_start, context_end = get_context_window(request)
    return not (entry.end_at < context_start or entry.start_at > context_end)


def get_request_context_symbols(request: NewsContextRequest) -> frozenset[str]:
    context_symbols = {request.dataset_symbol}
    if request.cluster_episode_kind in EPISODE_RETRIEVAL_EPISODE_KINDS:
        context_symbols.update(request.cluster_dataset_symbols)
    return frozenset(context_symbols)


def get_macro_timeline_overlap_score(
    request: NewsContextRequest,
    entry: MacroTimelineEntry,
) -> int:
    return len(get_request_context_symbols(request) & entry.dataset_symbols)


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
        start, end = get_search_window(request, self.window_days)
        query = build_news_query(request, self.language)
        payload: dict[str, object] = {}
        for attempt in range(settings.gdelt_retry_attempts):
            wait_for_gdelt_rate_limit(settings.gdelt_min_interval_seconds)
            try:
                response = httpx.get(
                    f"{self.base_url}/doc",
                    params={
                        "query": query,
                        "mode": "ArtList",
                        "format": "json",
                        "sort": "datedesc",
                        "maxrecords": get_fetch_record_limit(self.max_articles),
                        "startdatetime": format_gdelt_timestamp(start),
                        "enddatetime": format_gdelt_timestamp(end),
                    },
                    timeout=self.timeout_seconds,
                )
            except httpx.RequestError:
                if attempt < settings.gdelt_retry_attempts - 1:
                    time.sleep(settings.gdelt_retry_backoff_seconds * (attempt + 1))
                    continue
                return []
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code == 429 and attempt < settings.gdelt_retry_attempts - 1:
                    time.sleep(settings.gdelt_retry_backoff_seconds * (attempt + 1))
                    continue
                return []
            try:
                payload = response.json()
                break
            except ValueError:
                if (
                    "Please limit requests" in response.text
                    and attempt < settings.gdelt_retry_attempts - 1
                ):
                    time.sleep(settings.gdelt_retry_backoff_seconds * (attempt + 1))
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


class MacroTimelineNewsContextProvider:
    provider_name = "macro_timeline"

    def __init__(self, *, max_articles: int) -> None:
        self.max_articles = max_articles

    def fetch(self, request: NewsContextRequest) -> list[NewsArticleRecord]:
        matching_entries = [
            entry
            for entry in MACRO_TIMELINE_ENTRIES
            if get_macro_timeline_overlap_score(request, entry) > 0
            and context_window_overlaps_entry(request, entry)
        ]
        ranked_entries = sorted(
            matching_entries,
            key=lambda entry: (
                -get_macro_timeline_overlap_score(request, entry),
                abs((ensure_utc(entry.published_at).date() - ensure_utc(request.timestamp).date()).days),
                entry.title,
            ),
        )[: self.max_articles]
        return [
            NewsArticleRecord(
                provider=self.provider_name,
                article_url=entry.article_url,
                title=entry.title,
                domain=entry.domain,
                language="English",
                source_country="United States",
                published_at=entry.published_at,
                search_query=entry.search_query,
                relevance_rank=index,
                metadata=entry.metadata,
            )
            for index, entry in enumerate(ranked_entries, start=1)
        ]


def build_gdelt_provider() -> NewsContextProvider:
    return GDELTNewsContextProvider(
        base_url=settings.gdelt_base_url,
        window_days=settings.news_context_window_days,
        max_articles=settings.news_context_max_articles,
        language=settings.news_context_language,
    )


def build_macro_timeline_provider() -> NewsContextProvider:
    return MacroTimelineNewsContextProvider(max_articles=settings.news_context_max_articles)


def get_news_context_provider_names(request: NewsContextRequest) -> list[str]:
    provider_name = settings.news_context_provider.strip().lower()
    if provider_name == "gdelt":
        return ["gdelt"]
    if provider_name == "macro_timeline":
        return ["macro_timeline"]
    if provider_name == "hybrid":
        return ["gdelt", "macro_timeline"]
    raise ValueError(f"Unsupported news context provider: {settings.news_context_provider}")


def should_query_gdelt(request: NewsContextRequest) -> bool:
    max_age_days = settings.gdelt_max_anomaly_age_days
    if max_age_days <= 0:
        return True
    age_days = (datetime.now(timezone.utc).date() - ensure_utc(request.timestamp).date()).days
    return age_days <= max_age_days


def get_news_context_providers(request: NewsContextRequest) -> list[NewsContextProvider]:
    provider_names = get_news_context_provider_names(request)
    providers: list[NewsContextProvider] = []
    for provider_name in provider_names:
        if provider_name == "gdelt":
            if not should_query_gdelt(request):
                continue
            providers.append(build_gdelt_provider())
            continue
        if provider_name == "macro_timeline":
            providers.append(build_macro_timeline_provider())
            continue
        raise ValueError(f"Unsupported news context provider: {provider_name}")
    return providers


def get_active_news_context_provider_names(request: NewsContextRequest) -> list[str]:
    return [provider.provider_name for provider in get_news_context_providers(request)]


def load_news_context_request(db: Session, anomaly_id: int) -> NewsContextRequest | None:
    query = text(
        """
        SELECT
            a.id AS anomaly_id,
            d.name AS dataset_name,
            d.symbol AS dataset_symbol,
            d.frequency AS dataset_frequency,
            a.timestamp,
            ac.id AS cluster_id,
            ac.start_timestamp AS cluster_start_timestamp,
            ac.end_timestamp AS cluster_end_timestamp,
            ac.episode_kind AS cluster_episode_kind,
            ac.quality_band AS cluster_quality_band,
            ARRAY(
                SELECT DISTINCT d2.symbol
                FROM anomaly_cluster_members AS acm2
                JOIN anomalies AS a2 ON a2.id = acm2.anomaly_id
                JOIN datasets AS d2 ON d2.id = a2.dataset_id
                WHERE acm2.cluster_id = ac.id
                ORDER BY d2.symbol
            ) AS cluster_dataset_symbols
        FROM anomalies AS a
        JOIN datasets AS d ON d.id = a.dataset_id
        LEFT JOIN anomaly_cluster_members AS acm ON acm.anomaly_id = a.id
        LEFT JOIN anomaly_clusters AS ac ON ac.id = acm.cluster_id
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
        dataset_frequency=str(row["dataset_frequency"]),
        timestamp=ensure_utc(row["timestamp"]),
        cluster_id=int(row["cluster_id"]) if row["cluster_id"] is not None else None,
        cluster_start_timestamp=ensure_utc(row["cluster_start_timestamp"]) if row["cluster_start_timestamp"] is not None else None,
        cluster_end_timestamp=ensure_utc(row["cluster_end_timestamp"]) if row["cluster_end_timestamp"] is not None else None,
        cluster_episode_kind=str(row["cluster_episode_kind"]) if row["cluster_episode_kind"] is not None else None,
        cluster_quality_band=str(row["cluster_quality_band"]) if row["cluster_quality_band"] is not None else None,
        cluster_dataset_symbols=tuple(row["cluster_dataset_symbols"] or ()),
    )


def annotate_articles_for_request(
    articles: list[NewsArticleRecord],
    request: NewsContextRequest,
) -> list[NewsArticleRecord]:
    retrieval_scope, context_start, context_end = get_context_window(request)
    annotated: list[NewsArticleRecord] = []
    for article in articles:
        effective_scope = "curated_timeline" if article.provider == "macro_timeline" else retrieval_scope
        event_themes = extract_event_themes(article, request)
        metadata = dict(article.metadata)
        metadata.update(
            {
                "retrieval_scope": effective_scope,
                "context_window_start": context_start.isoformat(),
                "context_window_end": context_end.isoformat(),
                "timing_relation": classify_article_timing_for_request(article, request),
                "event_themes": event_themes,
                "primary_theme": event_themes[0] if event_themes else None,
            }
        )
        annotated.append(replace(article, metadata=metadata))
    return annotated


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
    inserted = 0
    for provider in get_news_context_providers(request):
        articles = annotate_articles_for_request(provider.fetch(request), request)
        inserted += replace_news_context(db, anomaly_id, provider.provider_name, articles)
    return inserted


def run_news_context_for_all_anomalies(db: Session) -> int:
    inserted = 0
    for anomaly_id in load_anomaly_ids(db):
        inserted += run_news_context_for_anomaly(db, anomaly_id)
    return inserted
