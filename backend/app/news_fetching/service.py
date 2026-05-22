from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.config import Settings
from app.news_fetching.models import NewsRegion, NewsSourceConfig, RawNewsCandidate
from app.news_fetching.parser import parse_feed
from app.news_fetching.sources import build_source_configs


def fetch_news_candidates(settings: Settings) -> list[dict[str, str]]:
    sources = build_source_configs(
        international_urls=settings.international_news_source_urls,
        domestic_urls=settings.domestic_news_source_urls,
        legacy_urls=settings.news_source_urls,
        per_source_limit=settings.news_per_source_limit,
    )
    candidates = fetch_raw_news_candidates(settings, sources)
    return [candidate.to_prompt_dict() for candidate in candidates]


def fetch_raw_news_candidates(settings: Settings, sources: list[NewsSourceConfig]) -> list[RawNewsCandidate]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(24, settings.news_lookback_hours))
    all_candidates: list[RawNewsCandidate] = []
    seen_urls: set[str] = set()
    region_limits = {
        NewsRegion.international: max(0, settings.international_news_candidates),
        NewsRegion.domestic: max(0, settings.domestic_news_candidates),
    }

    with httpx.Client(timeout=20, follow_redirects=True) as client:
        for source in sources:
            if not source.enabled:
                continue
            source_candidates = fetch_source_candidates(client, source, cutoff)
            added_for_source = 0
            for candidate in source_candidates:
                normalized_url = normalize_url(candidate.url)
                if not normalized_url or normalized_url in seen_urls:
                    continue
                seen_urls.add(normalized_url)
                all_candidates.append(
                    RawNewsCandidate(
                        title=candidate.title,
                        source=candidate.source,
                        region=candidate.region,
                        url=normalized_url,
                        published_at=candidate.published_at,
                        summary=candidate.summary,
                    )
                )
                added_for_source += 1
                if added_for_source >= source.max_items:
                    break

    selected = select_by_region(all_candidates, region_limits)
    return selected[: max(1, settings.max_news_candidates)]


def fetch_source_candidates(
    client: httpx.Client,
    source: NewsSourceConfig,
    cutoff: datetime,
) -> list[RawNewsCandidate]:
    try:
        response = client.get(source.url)
        response.raise_for_status()
    except httpx.HTTPError:
        return []

    candidates = parse_feed(response.text, source)
    filtered = [
        candidate
        for candidate in candidates
        if not candidate.published_at or candidate.published_at >= cutoff
    ]
    return sorted(filtered, key=candidate_sort_key, reverse=True)


def candidate_sort_key(candidate: RawNewsCandidate) -> datetime:
    return candidate.published_at or datetime.min.replace(tzinfo=timezone.utc)


def select_by_region(
    candidates: list[RawNewsCandidate],
    region_limits: dict[NewsRegion, int],
) -> list[RawNewsCandidate]:
    selected: list[RawNewsCandidate] = []
    for region in (NewsRegion.international, NewsRegion.domestic):
        region_candidates = sorted(
            [candidate for candidate in candidates if candidate.region == region],
            key=candidate_sort_key,
            reverse=True,
        )
        limit = region_limits[region]
        selected.extend(region_candidates[:limit] if limit else region_candidates)
    return sorted(selected, key=candidate_sort_key, reverse=True)


def normalize_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in {"ref", "fbclid", "gclid"}
        ],
        doseq=True,
    )
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/") or "/", query, ""))
